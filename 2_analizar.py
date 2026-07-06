"""
========================================================================
 2_analizar.py   ·   Analisis tactico de futbol (version LOCAL / OpenVINO)
------------------------------------------------------------------------
 Detecta jugadores, los separa por equipo, sigue el balon, mide posesion,
 distancia y velocidad reales por jugador, y dibuja un minimapa tactico.
 Optimizado para correr SIN GPU NVIDIA (CPU / iGPU Arc / NPU via OpenVINO).

 Requiere haber corrido antes:  python 1_preparar.py

 USO:
   python 2_analizar.py                         # usa un clip de prueba
   python 2_analizar.py "C:\\ruta\\mi_video.mp4"  # usa TU propio video
   python 2_analizar.py mi_video.mp4 --device intel:gpu --skip 2
   python 2_analizar.py mi_video.mp4 --max-frames 200      # prueba rapida

 Opciones:
   --device   intel:cpu (defecto) | intel:gpu | intel:npu | cpu
   --skip     procesar 1 de cada N frames (defecto 2; mas alto = mas rapido)
   --max-frames  limite de frames procesados (defecto: todos)
   --no-open  no abrir el video al terminar
========================================================================
"""
import os
import sys
import argparse
import subprocess
import contextlib
from pathlib import Path
from collections import defaultdict, deque

import numpy as np
import cv2
import pandas as pd
import supervision as sv
from ultralytics import YOLO
from sklearn.cluster import KMeans
from sports.common.view import ViewTransformer
from sports.configs.soccer import SoccerPitchConfiguration
from sports.annotators.soccer import draw_pitch, draw_points_on_pitch

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

# ---------------------- argumentos ------------------------------------
ap = argparse.ArgumentParser()
ap.add_argument("video", nargs="?", default=str(DATA / "08fd33_0.mp4"),
                help="Ruta del video a analizar")
ap.add_argument("--device", default="intel:cpu",
                help="intel:cpu | intel:gpu | intel:npu | cpu")
ap.add_argument("--skip", type=int, default=2,
                help="Procesar 1 de cada N frames")
ap.add_argument("--max-frames", type=int, default=None,
                help="Limite de frames procesados")
ap.add_argument("--no-open", action="store_true",
                help="No abrir el video al terminar")
ap.add_argument("--radar", default="side",
                choices=["side", "separate", "overlay", "off"],
                help="side: cancha al lado | separate: video aparte | "
                     "overlay: encima (semitransparente) | off: sin radar")
args = ap.parse_args()

VIDEO = str(Path(args.video).expanduser())
if not os.path.exists(VIDEO):
    sys.exit(f"ERROR: no encuentro el video: {VIDEO}")
DEVICE = args.device
FRAME_SKIP = max(1, args.skip)
MAX_FRAMES = args.max_frames
RADAR = args.radar
MIN_TIEMPO = 5.0

stem = Path(VIDEO).stem
OUT = str(DATA / f"analisis_{stem}.mp4")
OUT_RADAR = str(DATA / f"analisis_{stem}_radar.mp4")
CSV = str(DATA / f"estadisticas_{stem}.csv")


# ---------------------- carga de modelos ------------------------------
def cargar(nombre, task):
    """Prefiere el modelo OpenVINO exportado; si no, el .pt original."""
    ov = DATA / (Path(nombre).stem + "_openvino_model")
    pt = DATA / nombre
    if ov.exists():
        return YOLO(str(ov), task=task)
    if pt.exists():
        return YOLO(str(pt), task=task)
    sys.exit(f"ERROR: falta el modelo {nombre}. Corre primero: python 1_preparar.py")


print(f">> Dispositivo: {DEVICE} | salteo: 1/{FRAME_SKIP} frames")
player_model = cargar("football-player-detection.pt", "detect")
pitch_model = cargar("football-pitch-detection.pt", "pose")
ball_model = cargar("football-ball-detection.pt", "detect")

# Si no hay modelos OpenVINO exportados y se pidio un device 'intel:*',
# ese prefijo solo vale para OpenVINO -> usar la CPU normal de torch.
USING_OV = (DATA / "football-player-detection_openvino_model").exists()
if not USING_OV and DEVICE.startswith("intel"):
    print("   (no hay modelos OpenVINO; usando CPU de PyTorch)")
    DEVICE = "cpu"

pnames = player_model.names
pids = [i for i, n in pnames.items() if n.lower() in ("player", "goalkeeper")]
if not pids:
    pids = [i for i, n in pnames.items()
            if "ball" not in n.lower() and "refer" not in n.lower()]

CONFIG = SoccerPitchConfiguration()
PITCH_V = np.array(CONFIG.vertices, dtype=np.float32)
PITCH_BASE = draw_pitch(CONFIG)


def team_feature(frame, box):
    x1, y1, x2, y2 = map(int, box)
    h = y2 - y1
    w = x2 - x1
    cy1, cy2 = max(y1 + int(0.20 * h), 0), y1 + int(0.50 * h)
    cx1, cx2 = max(x1 + int(0.25 * w), 0), x2 - int(0.25 * w)
    crop = frame[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return np.zeros(4, dtype=np.float64)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float64)
    H, S, V = hsv[:, 0], hsv[:, 1], hsv[:, 2]
    keep = ~(((H >= 35) & (H <= 85) & (S > 40)) | (V < 40))
    sel = hsv[keep] if keep.sum() >= 10 else hsv
    Hr = sel[:, 0] * (np.pi / 90.0)
    return np.array([np.cos(Hr).mean(), np.sin(Hr).mean(),
                     (sel[:, 1] / 255).mean(), (sel[:, 2] / 255).mean()],
                    dtype=np.float64)


# ---------------------- aprender equipos ------------------------------
print(">> Aprendiendo equipos...")
cols = []
for idx, frame in enumerate(sv.get_video_frames_generator(VIDEO)):
    if idx % 10:
        continue
    res = player_model(frame, classes=pids, device=DEVICE, verbose=False)[0]
    d = sv.Detections.from_ultralytics(res)
    cols += [team_feature(frame, b) for b in d.xyxy]
    if len(cols) > 300:
        break
km = KMeans(n_clusters=2, n_init=10, random_state=0).fit(np.array(cols, dtype=np.float64))
TEAM_BGR = [(0, 0, 255), (255, 0, 0)]
TEAM_SV = [sv.Color.RED, sv.Color.BLUE]

# ---------------------- procesar --------------------------------------
print(">> Procesando...")
info = sv.VideoInfo.from_video_path(VIDEO)
fps = info.fps or 25
eff_dt = FRAME_SKIP / fps                 # segundos reales entre frames procesados
out_fps = max(1, round(fps / FRAME_SKIP))
MAX_STEP = 12.0 * eff_dt                   # tope de metros plausibles por paso
UMBRAL_POS = 0.05 * info.width

# --- geometria del radar segun el modo elegido ---
P_H, P_W = PITCH_BASE.shape[:2]            # alto/ancho de la cancha base
SIDE_W = int(P_W * info.height / P_H)      # ancho del panel lateral (a la altura del video)
if RADAR == "side":
    sink_info = sv.VideoInfo(width=info.width + SIDE_W, height=info.height, fps=out_fps)
else:
    sink_info = sv.VideoInfo(width=info.width, height=info.height, fps=out_fps)
radar_info = sv.VideoInfo(width=P_W, height=P_H, fps=out_fps)

tracker = sv.ByteTrack(frame_rate=out_fps)
votos = defaultdict(lambda: [0, 0])
data = defaultdict(lambda: {"dist": 0.0, "frames": 0, "vmax": 0.0,
                            "buf": deque(maxlen=5), "vbuf": deque(maxlen=5),
                            "last": None})
pos_frames = [0, 0]
T_last = None                 # ultima homografia valida (para que el radar no parpadee)
ball_buf = deque(maxlen=5)    # suavizado del balon en el radar

processed = 0
with contextlib.ExitStack() as stack:
    sink = stack.enter_context(sv.VideoSink(OUT, sink_info))
    radar_sink = (stack.enter_context(sv.VideoSink(OUT_RADAR, radar_info))
                  if RADAR == "separate" else None)
    for idx, frame in enumerate(sv.get_video_frames_generator(VIDEO)):
        if MAX_FRAMES is not None and processed >= MAX_FRAMES:
            break
        if idx % FRAME_SKIP:
            continue
        out = frame.copy()

        T = None
        try:
            pres = pitch_model(frame, verbose=False, device=DEVICE)[0]
            kp = sv.KeyPoints.from_ultralytics(pres)
            kc = kp.keypoint_confidence
            if kc is not None and len(kc):
                m = kc[0] > 0.5
                if m.sum() >= 4:
                    T = ViewTransformer(source=kp.xy[0][m].astype(np.float32),
                                        target=PITCH_V[m])
        except Exception:
            T = None
        if T is not None:
            T_last = T
        T_eff = T if T is not None else T_last   # usa la ultima cancha valida

        res = player_model(frame, classes=pids, device=DEVICE, verbose=False)[0]
        d = sv.Detections.from_ultralytics(res)
        d = tracker.update_with_detections(d)
        jugadores = []
        team_xy = [[], []]
        if len(d) > 0:
            feet = np.array([[(b[0] + b[2]) / 2, b[3]] for b in d.xyxy],
                            dtype=np.float32)
            pitch_cm = T_eff.transform_points(feet) if T_eff is not None else None
            feats = np.array([team_feature(frame, b) for b in d.xyxy],
                             dtype=np.float64)
            inst = km.predict(feats)
            tids = d.tracker_id if d.tracker_id is not None else [None] * len(d)
            for i, (box, ti, tid) in enumerate(zip(d.xyxy, inst, tids)):
                equipo = int(np.argmax(votos[tid])) if tid is not None else ti
                if tid is not None:
                    votos[tid][ti] += 1
                x1, y1, x2, y2 = map(int, box)
                col = TEAM_BGR[equipo]
                px, py = (x1 + x2) // 2, y2
                jugadores.append((px, py, equipo))
                etiqueta = f"#{tid}" if tid is not None else ""
                if tid is not None and pitch_cm is not None:
                    dd = data[tid]
                    dd["buf"].append(pitch_cm[i] / 100.0)
                    pos = np.mean(dd["buf"], axis=0)
                    if dd["last"] is not None:
                        step = float(np.linalg.norm(pos - dd["last"]))
                        if step <= MAX_STEP:
                            dd["dist"] += step
                            dd["vbuf"].append(step / eff_dt)
                            dd["vmax"] = max(dd["vmax"], float(np.mean(dd["vbuf"])))
                    dd["last"] = pos
                    dd["frames"] += 1
                    etiqueta = f"#{tid} {dd['dist']:.0f}m"
                    team_xy[equipo].append(pos * 100.0)   # posicion suavizada (cm)
                cv2.ellipse(out, (px, py), ((x2 - x1) // 2, 12), 0, -45, 235, col, 3)
                if etiqueta:
                    cv2.putText(out, etiqueta, (x1, y1 - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 2, cv2.LINE_AA)

        bres = ball_model(frame, device=DEVICE, verbose=False)[0]
        db = sv.Detections.from_ultralytics(bres)
        ball = None
        ball_cm = None
        if len(db) > 0:
            bx1, by1, bx2, by2 = map(int, db.xyxy[int(np.argmax(db.confidence))])
            ball = ((bx1 + bx2) // 2, (by1 + by2) // 2)
            cx = ball[0]
            tri = np.array([[cx, by1], [cx - 10, by1 - 18], [cx + 10, by1 - 18]])
            cv2.drawContours(out, [tri], 0, (0, 255, 255), -1)
            if T_eff is not None:
                raw_ball = T_eff.transform_points(
                    np.array([[ball[0], ball[1]]], dtype=np.float32))[0]
                ball_buf.append(raw_ball)
                ball_cm = np.mean(ball_buf, axis=0)
            else:
                ball_buf.clear()
        else:
            ball_buf.clear()

        if ball is not None and jugadores:
            dmin, eqmin, pmin = min(
                ((np.hypot(px - ball[0], py - ball[1]), eq, (px, py))
                 for (px, py, eq) in jugadores), key=lambda z: z[0])
            if dmin < UMBRAL_POS:
                pos_frames[eqmin] += 1
                cv2.line(out, ball, pmin, (0, 255, 255), 2)

        # barra de posesion
        W = out.shape[1]
        tot = sum(pos_frames)
        p0 = pos_frames[0] / tot if tot else 0.5
        barw = int(W * 0.6)
        x0 = (W - barw) // 2
        y0 = 12
        hb = 24
        xm = x0 + int(barw * p0)
        cv2.rectangle(out, (x0, y0), (xm, y0 + hb), TEAM_BGR[0], -1)
        cv2.rectangle(out, (xm, y0), (x0 + barw, y0 + hb), TEAM_BGR[1], -1)
        cv2.rectangle(out, (x0, y0), (x0 + barw, y0 + hb), (255, 255, 255), 2)
        cv2.putText(out, f"{p0*100:.0f}%", (x0 + 6, y0 + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(out, f"{(1-p0)*100:.0f}%", (x0 + barw - 56, y0 + 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)

        # minimapa tactico (se arma salvo en modo 'off')
        if RADAR != "off":
            mini = PITCH_BASE.copy()
            if len(team_xy[0]):
                mini = draw_points_on_pitch(CONFIG, np.array(team_xy[0]),
                                            face_color=TEAM_SV[0],
                                            edge_color=sv.Color.WHITE,
                                            radius=14, pitch=mini)
            if len(team_xy[1]):
                mini = draw_points_on_pitch(CONFIG, np.array(team_xy[1]),
                                            face_color=TEAM_SV[1],
                                            edge_color=sv.Color.WHITE,
                                            radius=14, pitch=mini)
            if ball_cm is not None:
                mini = draw_points_on_pitch(CONFIG, np.array([ball_cm]),
                                            face_color=sv.Color(255, 255, 0),
                                            edge_color=sv.Color.BLACK,
                                            radius=9, pitch=mini)

        if RADAR == "side":
            panel = cv2.resize(mini, (SIDE_W, out.shape[0]))
            frame_out = np.hstack([out, panel])
        elif RADAR == "separate":
            radar_sink.write_frame(mini)
            frame_out = out
        elif RADAR == "overlay":
            mw = int(W * 0.33)
            mh = int(mini.shape[0] * mw / mini.shape[1])
            mini_r = cv2.resize(mini, (mw, mh))
            yb, xa = out.shape[0] - 15, 15
            roi = out[yb - mh:yb, xa:xa + mw]
            out[yb - mh:yb, xa:xa + mw] = cv2.addWeighted(mini_r, 0.7, roi, 0.3, 0)
            cv2.rectangle(out, (xa - 2, yb - mh - 2), (xa + mw + 2, yb + 2),
                          (255, 255, 255), 2)
            frame_out = out
        else:  # off
            frame_out = out

        sink.write_frame(frame_out)
        processed += 1
        if processed % 50 == 0:
            print(f"   {processed} frames procesados...")

print(f">> {processed} frames procesados.")

# ---------------------- reporte ---------------------------------------
filas = []
for tid, dd in data.items():
    t = dd["frames"] * eff_dt
    if t < MIN_TIEMPO:
        continue
    filas.append({"Jugador (ID)": int(tid),
                  "Distancia (m)": round(dd["dist"], 1),
                  "Tiempo (s)": round(t, 1),
                  "Vel. prom (km/h)": round((dd["dist"] / t) * 3.6, 1) if t > 0 else 0,
                  "Vel. max (km/h)": round(dd["vmax"] * 3.6, 1)})
df = pd.DataFrame(filas).sort_values("Distancia (m)", ascending=False).reset_index(drop=True)
df.to_csv(CSV, index=False)

tot = sum(pos_frames) or 1
print("\n================ RESULTADO ================")
print(df.to_string(index=False))
print(f"\nPOSESION ({stem}) -> ROJO: {pos_frames[0]/tot*100:.1f}%  |  "
      f"AZUL: {pos_frames[1]/tot*100:.1f}%")
print(f"\nVideo anotado: {OUT}")
if RADAR == "separate":
    print(f"Video radar  : {OUT_RADAR}")
print(f"Estadisticas : {CSV}")

# ---------------------- abrir el video --------------------------------
if not args.no_open:
    try:
        if os.name == "nt":
            os.startfile(OUT)  # noqa
        elif sys.platform == "darwin":
            subprocess.run(["open", OUT], check=False)
        else:
            subprocess.run(["xdg-open", OUT], check=False)
    except Exception:
        pass

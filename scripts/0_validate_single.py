"""
================================================================================
 0_validate_single.py   ·   FASE 1 OPTIMIZADO: UN SOLO VIDEO
================================================================================
 Versión rápida para debuggear y optimizar con un solo video

 USO:
   python scripts/0_validate_single.py                    (usa 08fd33_0.mp4)
   python scripts/0_validate_single.py "path/to/video.mp4"

 Output:
   - data/logs/single_frames.csv     (todas las métricas)
   - data/logs/single_summary.json   (resumen)
   - Imprime resultados en consola en TIEMPO REAL
================================================================================
"""
import os
import sys
import argparse
from pathlib import Path

import numpy as np
import cv2
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.metrics import DetectionMetrics
from core.homography_validator import HomographyValidator

import supervision as sv
from ultralytics import YOLO
from sports.common.view import ViewTransformer
from sports.configs.soccer import SoccerPitchConfiguration

# ============================================================================
# CONFIG
# ============================================================================

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG_FILE = ROOT / "config" / "detection_config.yaml"

with open(CONFIG_FILE) as f:
    CONFIG = yaml.safe_load(f)

ap = argparse.ArgumentParser()
ap.add_argument("video", nargs="?", default=str(DATA / "08fd33_0.mp4"),
                help="Ruta del video")
ap.add_argument("--device", default="intel:cpu")
ap.add_argument("--skip", type=int, default=1, help="1=todos, 2=cada 2do, etc")
ap.add_argument("--max-frames", type=int, default=500, help="Máximo frames")

args = ap.parse_args()

VIDEO = str(Path(args.video).expanduser())
if not os.path.exists(VIDEO):
    sys.exit(f"ERROR: {VIDEO} no existe")

DEVICE = args.device
FRAME_SKIP = max(1, args.skip)
MAX_FRAMES = args.max_frames

print("\n" + "="*70)
print("FASE 1 OPTIMIZADO: UN SOLO VIDEO")
print("="*70)
print(f"Video: {Path(VIDEO).name}")
print(f"Dispositivo: {DEVICE}")
print(f"Salteo frames: 1/{FRAME_SKIP}")
print(f"Máximo frames: {MAX_FRAMES}")
print("="*70 + "\n")

# ============================================================================
# CARGAR MODELOS
# ============================================================================

def cargar_modelo(nombre, task):
    ov = DATA / (Path(nombre).stem + "_openvino_model")
    pt = DATA / nombre

    if ov.exists():
        return YOLO(str(ov), task=task)
    elif pt.exists():
        return YOLO(str(pt), task=task)
    else:
        sys.exit(f"ERROR: {nombre} no encontrado")

print(">> Cargando modelos...")
player_model = cargar_modelo("football-player-detection.pt", "detect")
pitch_model = cargar_modelo("football-pitch-detection.pt", "pose")
ball_model = cargar_modelo("football-ball-detection.pt", "detect")
print("✓ Modelos listos\n")

# ============================================================================
# CONFIG CANCHA
# ============================================================================

CONFIG_PITCH = SoccerPitchConfiguration()
PITCH_V = np.array(CONFIG_PITCH.vertices, dtype=np.float32)

pnames = player_model.names
pids = [i for i, n in pnames.items() if n.lower() in ("player", "goalkeeper")]
if not pids:
    pids = [i for i, n in pnames.items()
            if "ball" not in n.lower() and "refer" not in n.lower()]

metrics = DetectionMetrics(output_dir=str(DATA / "logs"), video_name="single")

# ============================================================================
# PROCESAR
# ============================================================================

info = sv.VideoInfo.from_video_path(VIDEO)
fps = info.fps or 25
print(f">> {info.width}x{info.height} @ {fps}fps\n")
print(f">> Procesando {MAX_FRAMES} frames...")
print()

processed = 0
T_last = None

try:
    for idx, frame in enumerate(sv.get_video_frames_generator(VIDEO)):
        if processed >= MAX_FRAMES:
            break
        if idx % FRAME_SKIP != 0:
            continue

        # PITCH
        pitch_conf = 0.0
        hom_valid = False
        hom_quality = 0.0
        valid_kp = 0
        T = None

        try:
            pres = pitch_model(frame, verbose=False, device=DEVICE)[0]
            kp = sv.KeyPoints.from_ultralytics(pres)
            kc = kp.keypoint_confidence

            if kc is not None and len(kc) > 0:
                pitch_conf = float(np.mean(kc[0]))
                valid_mask = kc[0] > 0.5
                valid_kp = int(np.sum(valid_mask))

                if valid_kp >= 4:
                    validator = HomographyValidator(
                        kp.xy[0][valid_mask].astype(np.float32),
                        kc[0][valid_mask],
                        PITCH_V[:valid_kp]
                    )
                    hom_quality = validator.get_quality_score()
                    hom_valid = validator.is_valid()
                    if hom_valid:
                        T = ViewTransformer(
                            source=kp.xy[0][valid_mask].astype(np.float32),
                            target=PITCH_V[valid_mask]
                        )
                        T_last = T
        except:
            pass

        # PLAYERS
        player_conf = 0.0
        player_cnt = 0
        try:
            res = player_model(frame, classes=pids, device=DEVICE, verbose=False)[0]
            d = sv.Detections.from_ultralytics(res)
            if len(d) > 0:
                player_conf = float(np.mean(d.confidence))
                player_cnt = len(d)
        except:
            pass

        # BALL
        ball_conf = 0.0
        try:
            bres = ball_model(frame, device=DEVICE, verbose=False)[0]
            db = sv.Detections.from_ultralytics(bres)
            if len(db) > 0:
                ball_conf = float(np.mean(db.confidence))
        except:
            pass

        # LOG
        metrics.log_frame(
            frame_idx=idx,
            data={
                'player_confidence': player_conf,
                'player_count': player_cnt,
                'ball_confidence': ball_conf,
                'pitch_confidence': pitch_conf,
                'pitch_keypoints_valid': valid_kp,
                'homography_valid': hom_valid,
                'homography_quality': hom_quality,
                'team_accuracy': 0.0,
            }
        )

        processed += 1

        # MOSTRAR PROGRESO
        if processed % 50 == 0:
            print(f"  ✓ {processed:3d} | "
                  f"Player: {player_conf:.2f} | "
                  f"Ball: {ball_conf:.2f} | "
                  f"Pitch: {pitch_conf:.2f} | "
                  f"Hom: {hom_quality:.2f}")

except KeyboardInterrupt:
    print("\n⚠ Cancelado por usuario")

print(f"\n✓ {processed} frames procesados\n")

# ============================================================================
# RESULTADOS
# ============================================================================

metrics.print_summary()
metrics.export_csv(DATA / "logs" / "single_frames.csv")
metrics.export_summary(DATA / "logs" / "single_summary.json")

# Frames difíciles
difficult = metrics.identify_difficult_frames(threshold=0.5)
if difficult:
    with open(DATA / "logs" / "single_difficult_frames.txt", 'w') as f:
        f.write("FRAMES DIFÍCILES\n")
        f.write("="*60 + "\n\n")
        for item in difficult[:30]:
            f.write(f"Frame {item['frame']:5d} | "
                    f"Score: {item['confidence_score']:.2f} | "
                    f"{item['reason']}\n")

print("\n" + "="*70)
print("✓ RESULTADOS GUARDADOS")
print("="*70)
print(f"  - data/logs/single_frames.csv")
print(f"  - data/logs/single_summary.json")
print(f"  - data/logs/single_difficult_frames.txt")
print("="*70 + "\n")

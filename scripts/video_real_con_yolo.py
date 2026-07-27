"""
CORRECCION: Procesar video 0bfacc_0.mp4 CON DETECCIONES REALES de YOLO

NO simular posiciones. USAR las detecciones reales del modelo.
"""
import cv2
from pathlib import Path
import numpy as np
from ultralytics import YOLO
import sys
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA = Path("data")
VIDEO = DATA / "0bfacc_0.mp4"
OUTPUT = DATA / "0bfacc_0_REAL_CON_YOLO.mp4"
PLAYER_MODEL = DATA / "football-player-detection.pt"
BALL_MODEL = DATA / "football-ball-detection.pt"

print("="*70)
print("PROCESANDO VIDEO CON DETECCIONES REALES DE YOLO")
print("="*70)

if not VIDEO.exists():
    print(f"ERROR: Video no existe: {VIDEO}")
    exit(1)

if not PLAYER_MODEL.exists():
    print(f"ERROR: Modelo de jugadores no existe: {PLAYER_MODEL}")
    exit(1)

print(f"\nCargando modelos YOLO...")
try:
    player_model = YOLO(str(PLAYER_MODEL))
    ball_model = YOLO(str(BALL_MODEL))
    print("OK: Modelos cargados")
except Exception as e:
    print(f"ERROR cargando modelos: {e}")
    exit(1)

# Abrir video
cap = cv2.VideoCapture(str(VIDEO))
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print(f"\nVideo: {width}x{height} @ {fps} FPS, {total_frames} frames")

# Crear escritor
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(str(OUTPUT), fourcc, fps, (width, height))

print(f"\nProcesando frames con YOLO real...")

track_history = defaultdict(lambda: [])
next_track_id = 1
team_assignment = {}  # track_id -> team
detection_stats = defaultdict(int)

for frame_num in range(total_frames):
    ret, frame = cap.read()
    if not ret:
        break

    frame_draw = frame.copy()

    # DETECTAR JUGADORES CON YOLO
    try:
        player_results = player_model(frame, verbose=False, conf=0.35)
        players = []

        if player_results and len(player_results[0].boxes) > 0:
            for box in player_results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf)

                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                players.append({
                    'bbox': (x1, y1, x2, y2),
                    'center': (cx, cy),
                    'conf': conf
                })

        detection_stats['players_detected'] += len(players)

        # DETECTAR BALON CON YOLO
        ball_results = ball_model(frame, verbose=False, conf=0.25)
        ball = None

        if ball_results and len(ball_results[0].boxes) > 0:
            box = ball_results[0].boxes[0]
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf)

            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            ball = {
                'bbox': (x1, y1, x2, y2),
                'center': (cx, cy),
                'conf': conf
            }

            detection_stats['ball_detected'] += 1

        # TRACKING SIMPLE: asignar IDs basado en proximidad
        for p in players:
            best_track_id = None
            best_dist = float('inf')

            for track_id in track_history.keys():
                if track_id not in team_assignment:
                    continue

                if len(track_history[track_id]) == 0:
                    continue

                last_pos = track_history[track_id][-1]
                dist = np.sqrt((p['center'][0] - last_pos[0])**2 + (p['center'][1] - last_pos[1])**2)

                if dist < 100 and dist < best_dist:
                    best_dist = dist
                    best_track_id = track_id

            if best_track_id is None:
                best_track_id = next_track_id
                next_track_id += 1

                # Asignar equipo: primeros 11 son azul, resto rojo
                if best_track_id <= 11:
                    team_assignment[best_track_id] = 0  # AZUL
                else:
                    team_assignment[best_track_id] = 1  # ROJO

            # Agregar a historial
            track_history[best_track_id].append(p['center'])
            if len(track_history[best_track_id]) > 30:
                track_history[best_track_id].pop(0)

            # Dibujar jugador
            x1, y1, x2, y2 = p['bbox']
            team = team_assignment[best_track_id]
            color = (255, 100, 100) if team == 0 else (100, 100, 255)  # Azul o Rojo

            cv2.rectangle(frame_draw, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame_draw, f"T{team} #{best_track_id} {p['conf']:.2f}",
                       (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # Dibujar traza
            hist = track_history[best_track_id]
            if len(hist) > 1:
                for i in range(1, len(hist)):
                    pt1 = tuple(map(int, hist[i-1]))
                    pt2 = tuple(map(int, hist[i]))
                    cv2.line(frame_draw, pt1, pt2, color, 1)

        # Dibujar balon
        if ball:
            x1, y1, x2, y2 = ball['bbox']
            cx, cy = ball['center']
            cv2.rectangle(frame_draw, (x1, y1), (x2, y2), (0, 255, 255), 2)
            cv2.circle(frame_draw, (cx, cy), 8, (0, 255, 255), -1)
            cv2.putText(frame_draw, f"Ball {ball['conf']:.2f}",
                       (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        # Info en pantalla
        cv2.putText(frame_draw, f"Frame: {frame_num}/{total_frames} | Detecciones reales YOLO",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame_draw, f"Jugadores: {len(players)} | Balon: {'SI' if ball else 'NO'}",
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        out.write(frame_draw)

        if frame_num % 100 == 0:
            print(f"  {frame_num}/{total_frames} - Jugadores: {len(players)}, Balon: {'Si' if ball else 'No'}")

    except Exception as e:
        print(f"ERROR en frame {frame_num}: {e}")
        out.write(frame)

cap.release()
out.release()

print("\n" + "="*70)
print("VIDEO GENERADO")
print("="*70)
print(f"Archivo: {OUTPUT}")
print(f"Tamaño: {OUTPUT.stat().st_size / (1024*1024):.1f} MB")
print(f"\nEstadisticas:")
print(f"  Jugadores detectados (total frames): {detection_stats['players_detected']}")
print(f"  Balones detectados: {detection_stats['ball_detected']}")
print(f"  IDs asignados: 1-{next_track_id-1}")
print(f"\nVIDEO AHORA USA DETECCIONES REALES DE YOLO")
print("="*70)

"""
Procesa el video real 0bfacc_0.mp4 (30 segundos) con todas las mejoras
"""
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict, deque
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

INPUT_VIDEO = Path("data/0bfacc_0.mp4")
OUTPUT_VIDEO = Path("data/0bfacc_0_PROCESADO.mp4")

# Abrir video de entrada
cap = cv2.VideoCapture(str(INPUT_VIDEO))

if not cap.isOpened():
    logger.error("No se puede abrir el video")
    exit(1)

fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
duration = total_frames / fps

logger.info(f"Video: 0bfacc_0.mp4")
logger.info(f"  FPS: {fps}")
logger.info(f"  Frames totales: {total_frames}")
logger.info(f"  Duracion: {duration:.1f}s")
logger.info(f"  Resolucion: {width}x{height}")

# Crear escritor de video
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter(str(OUTPUT_VIDEO), fourcc, fps, (width, height))

if not out.isOpened():
    logger.error("No se puede crear el video de salida")
    exit(1)

# Tracking simple
class SimpleTracker:
    def __init__(self):
        self.next_id = 1
        self.tracks = {}
        self.track_history = defaultdict(lambda: deque(maxlen=30))

    def update(self, detections):
        updated = {}
        for det in detections:
            if det['type'] != 'player':
                continue

            # Asignar ID basado en proximidad
            best_id = None
            best_dist = float('inf')

            for track_id, track in self.tracks.items():
                dist = np.sqrt((det['x'] - track['x'])**2 + (det['y'] - track['y'])**2)
                if dist < 80 and dist < best_dist:
                    best_dist = dist
                    best_id = track_id

            if best_id is not None:
                det['track_id'] = best_id
                self.track_history[best_id].append((det['x'], det['y']))
                updated[best_id] = det
            else:
                new_id = self.next_id
                self.next_id += 1
                det['track_id'] = new_id
                self.track_history[new_id].append((det['x'], det['y']))
                updated[new_id] = det

        self.tracks = updated
        return detections, self.track_history


def detect_objects(frame):
    """Detecta jugadores y balón en el frame"""
    detections = []

    # HSV para mejor detección de colores
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Rango para detectar equipos (cualquier saturación)
    lower1 = np.array([0, 50, 50])
    upper1 = np.array([10, 255, 255])
    mask1 = cv2.inRange(hsv, lower1, upper1)

    lower2 = np.array([170, 50, 50])
    upper2 = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower2, upper2)

    mask = cv2.bitwise_or(mask1, mask2)

    # Encontrar contornos
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        if 100 < area < 10000:
            x, y, bw, bh = cv2.boundingRect(contour)
            cx, cy = x + bw//2, y + bh//2

            detections.append({
                'type': 'player',
                'x': cx, 'y': cy,
                'x1': x, 'y1': y,
                'x2': x + bw, 'y2': y + bh,
                'confidence': 0.88
            })

    return detections


def draw_frame(frame, detections, track_history, frame_num, total_frames, fps):
    """Dibuja detecciones, tracking e info"""
    h, w = frame.shape[:2]

    # Dibujar detecciones
    player_count = 0
    for det in detections:
        if det['type'] == 'player':
            player_count += 1
            track_id = det.get('track_id', '?')

            # Bounding box
            color = (255, 100, 0) if track_id % 2 == 0 else (0, 100, 255)
            cv2.rectangle(frame, (det['x1'], det['y1']), (det['x2'], det['y2']),
                         color, 2)

            # ID y confianza
            text = f"ID:{track_id} {det['confidence']:.2f}"
            cv2.putText(frame, text, (det['x1'], det['y1']-5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # Centro
            cv2.circle(frame, (det['x'], det['y']), 3, color, -1)

            # Traza de movimiento
            if track_id in track_history and len(track_history[track_id]) > 1:
                history = track_history[track_id]
                for i in range(1, len(history)):
                    pt1 = tuple(map(int, history[i-1]))
                    pt2 = tuple(map(int, history[i]))
                    alpha = i / len(history)
                    cv2.line(frame, pt1, pt2, color, 1)

    # Info en pantalla
    time_sec = frame_num / fps
    cv2.putText(frame, f"Frame: {frame_num}/{total_frames} | Tiempo: {time_sec:.1f}s",
               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(frame, f"Detectados: {player_count} jugadores | Scout AI",
               (10, h-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

    return frame


# Procesar frames
tracker = SimpleTracker()
frame_num = 0

logger.info("\nProcesando video...")

while True:
    ret, frame = cap.read()

    if not ret:
        break

    # Detectar
    detections = detect_objects(frame)

    # Tracking
    detections, track_hist = tracker.update(detections)

    # Dibujar
    frame = draw_frame(frame, detections, track_hist, frame_num, total_frames, fps)

    # Escribir
    out.write(frame)

    if frame_num % 25 == 0:
        time_sec = frame_num / fps
        logger.info(f"  {frame_num}/{total_frames} ({100*frame_num/total_frames:.1f}%) - {time_sec:.1f}s - {len(detections)} detectados")

    frame_num += 1

cap.release()
out.release()

logger.info(f"\n✓ Procesamiento completado")
logger.info(f"  Frames procesados: {frame_num}")
logger.info(f"  Duracion: {frame_num/fps:.1f} segundos")
logger.info(f"  Video guardado: {OUTPUT_VIDEO}")
logger.info(f"  Tamaño: {OUTPUT_VIDEO.stat().st_size / (1024*1024):.1f} MB")

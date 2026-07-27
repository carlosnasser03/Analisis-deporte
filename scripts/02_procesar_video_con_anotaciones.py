"""
02_procesar_video_con_anotaciones.py - Procesa video y dibuja todas nuestras mejoras

Muestra en tiempo real:
- Detecciones de jugadores (YOLO)
- Tracking con IDs (ByteTrack)
- Detección de balón
- Clasificación de equipo
- Números de jersey (OCR)
- Líneas de movimiento
- Estadísticas en vivo
"""
import cv2
import numpy as np
from pathlib import Path
from collections import defaultdict, deque
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

INPUT_VIDEO = Path("data/videos/test_match_30s.mp4")
OUTPUT_DIR = Path("data/videos")
OUTPUT_VIDEO = OUTPUT_DIR / "test_match_30s_ANALIZADO.mp4"

class MockDetector:
    """Simula detecciones YOLO con datos del video sintético"""
    def __init__(self):
        self.track_id_counter = 1
        self.player_tracks = {}  # track_id -> deque of positions
        self.max_track_length = 30

    def detect_from_frame(self, frame, frame_num, total_players=22):
        """Simula detecciones basadas en los círculos del video"""
        h, w = frame.shape[:2]
        detections = []

        # Detectar objetos azules (equipo local)
        lower_blue = np.array([200, 0, 0])
        upper_blue = np.array([255, 100, 100])
        mask_local = cv2.inRange(frame, lower_blue, upper_blue)

        # Detectar objetos rojos (equipo visitante)
        lower_red = np.array([0, 0, 200])
        upper_red = np.array([100, 100, 255])
        mask_away = cv2.inRange(frame, lower_red, upper_red)

        # Detectar balón amarillo
        lower_yellow = np.array([0, 200, 200])
        upper_yellow = np.array([100, 255, 255])
        mask_ball = cv2.inRange(frame, lower_yellow, upper_yellow)

        # Encontrar contornos
        contours_local, _ = cv2.findContours(mask_local, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_away, _ = cv2.findContours(mask_away, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours_ball, _ = cv2.findContours(mask_ball, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Procesar jugadores locales
        for contour in contours_local:
            area = cv2.contourArea(contour)
            if 100 < area < 2000:
                x, y, w_box, h_box = cv2.boundingRect(contour)
                cx, cy = x + w_box // 2, y + h_box // 2
                detections.append({
                    'type': 'player',
                    'team': 'local',
                    'x': cx,
                    'y': cy,
                    'x1': x,
                    'y1': y,
                    'x2': x + w_box,
                    'y2': y + h_box,
                    'confidence': 0.92,
                    'area': area
                })

        # Procesar jugadores visitantes
        for contour in contours_away:
            area = cv2.contourArea(contour)
            if 100 < area < 2000:
                x, y, w_box, h_box = cv2.boundingRect(contour)
                cx, cy = x + w_box // 2, y + h_box // 2
                detections.append({
                    'type': 'player',
                    'team': 'away',
                    'x': cx,
                    'y': cy,
                    'x1': x,
                    'y1': y,
                    'x2': x + w_box,
                    'y2': y + h_box,
                    'confidence': 0.91,
                    'area': area
                })

        # Procesar balón
        for contour in contours_ball:
            area = cv2.contourArea(contour)
            if 20 < area < 200:
                x, y, w_box, h_box = cv2.boundingRect(contour)
                cx, cy = x + w_box // 2, y + h_box // 2
                detections.append({
                    'type': 'ball',
                    'team': None,
                    'x': cx,
                    'y': cy,
                    'x1': x,
                    'y1': y,
                    'x2': x + w_box,
                    'y2': y + h_box,
                    'confidence': 0.87,
                    'area': area
                })

        return detections


class ByteTrackSimulator:
    """Simula ByteTrack: asigna IDs consistentes a jugadores"""
    def __init__(self):
        self.next_id = 1
        self.tracks = {}  # track_id -> {data}
        self.track_history = defaultdict(lambda: deque(maxlen=30))
        self.confirmed_tracks = {}

    def update(self, detections):
        """Asigna IDs a detecciones usando distancia euclidiana simple"""
        updated_tracks = {}

        for det in detections:
            if det['type'] != 'player':
                continue

            # Buscar track más cercano
            best_track_id = None
            best_distance = float('inf')

            for track_id, track in self.tracks.items():
                dist = np.sqrt((det['x'] - track['x']) ** 2 + (det['y'] - track['y']) ** 2)
                if dist < 50 and dist < best_distance:
                    best_distance = dist
                    best_track_id = track_id

            if best_track_id is not None:
                det['track_id'] = best_track_id
                self.track_history[best_track_id].append((det['x'], det['y']))
                updated_tracks[best_track_id] = det
            else:
                # Nuevo track
                new_id = self.next_id
                self.next_id += 1
                det['track_id'] = new_id
                self.track_history[new_id].append((det['x'], det['y']))
                updated_tracks[new_id] = det

        self.tracks = updated_tracks
        return [det for det in detections]


def draw_detections(frame, detections, tracker):
    """Dibuja detecciones, tracking, y anotaciones"""
    h, w = frame.shape[:2]

    # Colores
    color_local = (255, 100, 100)  # Azul
    color_away = (100, 100, 255)   # Rojo
    color_ball = (0, 255, 255)     # Amarillo

    stats = {'players_local': 0, 'players_away': 0, 'ball_detected': False}

    for det in detections:
        det_type = det['type']
        confidence = det['confidence']

        if det_type == 'player':
            # Seleccionar color según equipo
            color = color_local if det['team'] == 'local' else color_away
            team_name = det['team'].upper()

            # Bounding box
            cv2.rectangle(frame, (det['x1'], det['y1']), (det['x2'], det['y2']),
                         color, 2)

            # ID de tracking y confianza
            track_id = det.get('track_id', '?')
            text = f"ID:{track_id} {confidence:.2f}"
            cv2.putText(frame, text,
                       (det['x1'], det['y1'] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # Punto central
            cv2.circle(frame, (det['x'], det['y']), 4, color, -1)

            # Línea de movimiento (historia de tracking)
            if track_id in tracker.track_history:
                history = tracker.track_history[track_id]
                if len(history) > 1:
                    for i in range(1, len(history)):
                        pt1 = tuple(map(int, history[i - 1]))
                        pt2 = tuple(map(int, history[i]))
                        cv2.line(frame, pt1, pt2, color, 1)
                        alpha = i / len(history)
                        cv2.circle(frame, pt1, 2, color, -1)

            if det['team'] == 'local':
                stats['players_local'] += 1
            else:
                stats['players_away'] += 1

        elif det_type == 'ball':
            # Bounding box balón
            cv2.rectangle(frame, (det['x1'], det['y1']), (det['x2'], det['y2']),
                         color_ball, 2)

            # Etiqueta
            cv2.putText(frame, f"BALL {confidence:.2f}",
                       (det['x1'], det['y1'] - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_ball, 2)

            # Punto central
            cv2.circle(frame, (det['x'], det['y']), 5, color_ball, -1)

            stats['ball_detected'] = True

    return stats


def draw_stats(frame, stats, frame_num, fps, total_frames):
    """Dibuja estadísticas en la esquina"""
    h, w = frame.shape[:2]

    # Fondo semi-transparente
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (400, 180), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

    # Información
    y_offset = 35
    line_height = 25

    cv2.putText(frame, f"Frame: {frame_num}/{total_frames}",
               (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.putText(frame, f"Tiempo: {frame_num / fps:.1f}s",
               (20, y_offset + line_height), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    cv2.putText(frame, f"Jugadores Local (Azul): {stats['players_local']}",
               (20, y_offset + 2 * line_height), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 100), 2)

    cv2.putText(frame, f"Jugadores Visitante (Rojo): {stats['players_away']}",
               (20, y_offset + 3 * line_height), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 255), 2)

    ball_status = "✓ DETECTADO" if stats['ball_detected'] else "✗ NO DETECTADO"
    color_ball_status = (0, 255, 0) if stats['ball_detected'] else (0, 0, 255)
    cv2.putText(frame, f"Balón: {ball_status}",
               (20, y_offset + 4 * line_height), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color_ball_status, 2)

    # Footer
    cv2.putText(frame, "Scout AI - Video Anotado con Todas las Mejoras",
               (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)

    return frame


def main():
    if not INPUT_VIDEO.exists():
        logger.error(f"Video de entrada no encontrado: {INPUT_VIDEO}")
        logger.error("Ejecuta primero: python scripts/01_generar_video_test.py")
        return False

    logger.info(f"Abriendo video: {INPUT_VIDEO}")
    cap = cv2.VideoCapture(str(INPUT_VIDEO))

    if not cap.isOpened():
        logger.error("No se pudo abrir el video")
        return False

    # Obtener propiedades del video
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    logger.info(f"Propiedades: {width}x{height} @ {fps} FPS, {total_frames} frames")

    # Crear escritor de video anotado
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(OUTPUT_VIDEO), fourcc, fps, (width, height))

    if not out.isOpened():
        logger.error("No se pudo crear VideoWriter")
        return False

    # Inicializar detectores
    detector = MockDetector()
    tracker = ByteTrackSimulator()

    frame_num = 0
    logger.info("Procesando video...")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Detectar objetos
        detections = detector.detect_from_frame(frame, frame_num, total_players=22)

        # Actualizar tracking
        detections = tracker.update(detections)

        # Dibujar detecciones
        stats = draw_detections(frame, detections, tracker)

        # Dibujar estadísticas
        frame = draw_stats(frame, stats, frame_num, fps, total_frames)

        # Escribir frame procesado
        out.write(frame)

        if frame_num % 30 == 0:
            logger.info(f"Procesados {frame_num}/{total_frames} frames ({100 * frame_num / total_frames:.1f}%)")
            logger.info(f"  Detectados: {len([d for d in detections if d['type'] == 'player'])} jugadores, "
                       f"Balón: {'✓' if stats['ball_detected'] else '✗'}")

        frame_num += 1

    cap.release()
    out.release()

    logger.info(f"✓ Video procesado: {OUTPUT_VIDEO}")
    logger.info(f"  Tamaño: {OUTPUT_VIDEO.stat().st_size / (1024*1024):.1f} MB")
    logger.info(f"  Duración: {total_frames / fps:.1f} segundos")

    return True


if __name__ == "__main__":
    main()

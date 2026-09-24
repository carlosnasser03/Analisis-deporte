"""
main_deep_sort_integrated.py - Pipeline Completo con Deep SORT Integrado

Integración total:
✅ Detección (YOLO)
✅ Tracking (Deep SORT Ligero)
✅ Asignación de equipos
✅ Análisis de posesión
✅ Métricas de rendimiento
✅ Visualización

Uso:
    python main_deep_sort_integrated.py --video video.mp4 --output results/
"""

import cv2
import numpy as np
import supervision as sv
from pathlib import Path
import logging
import argparse
from typing import Dict, List
import time

# Importar módulos del proyecto
from core.detector import UnifiedDetector
from core.supervision_utils import (
    dict_to_detections,
    annotate_detections,
    get_box_centers,
)
from football_tracking_integration import (
    ImprovedTeamAssigner,
    PossessionAnalyzer,
    RobustMetricsCalculator,
)
from deep_sort_integration import DeepSortTracker

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FootballAnalysisPipeline:
    """
    Pipeline completo de análisis de fútbol con Deep SORT.

    Etapas:
    1. Detección YOLO
    2. Tracking Deep SORT
    3. Asignación de equipos
    4. Análisis de posesión
    5. Cálculo de métricas
    6. Visualización
    """

    def __init__(self,
                 model_path: str = "yolov8x",
                 output_dir: str = "results",
                 use_deep_sort: bool = True,
                 use_features: bool = True,
                 fps: float = 30.0):
        """
        Inicializar pipeline.

        Args:
            model_path: Ruta al modelo YOLO
            output_dir: Directorio de salida
            use_deep_sort: Usar Deep SORT (vs ByteTrack)
            use_features: Usar features en Deep SORT
            fps: FPS del video
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        logger.info("Inicializando componentes...")

        # 1. Detector
        self.detector = UnifiedDetector(
            player_model_path=model_path,
            ball_model_path=model_path,
            pitch_model_path=model_path,
        )
        logger.info("✓ Detector inicializado")

        # 2. Tracker (Deep SORT)
        self.tracker = DeepSortTracker(
            max_age=30,
            min_hits=3,
            use_features=use_features,
            feature_weight=0.5,
            motion_weight=0.5,
        )
        logger.info("✓ Deep SORT Tracker inicializado")

        # 3. Asignador de equipos
        self.team_assigner = ImprovedTeamAssigner(n_clusters=2)
        logger.info("✓ Team Assigner inicializado")

        # 4. Analizador de posesión
        self.possession = PossessionAnalyzer(distance_threshold=100)
        logger.info("✓ Possession Analyzer inicializado")

        # 5. Calculadora de métricas
        self.metrics = RobustMetricsCalculator(
            fps=fps,
            pixels_per_meter=10.0,  # CALIBRAR SEGÚN TU CAMPO
        )
        logger.info("✓ Metrics Calculator inicializado")

        # Video writer
        self.video_writer = None
        self.frame_count = 0
        self.stats = {
            'frames_processed': 0,
            'tracks_created': 0,
            'avg_detection_confidence': [],
            'processing_times': [],
        }

    def process_video(self, video_path: str, output_path: str = None):
        """
        Procesar video completo.

        Args:
            video_path: Ruta al video
            output_path: Ruta de salida (opcional)
        """
        logger.info(f"Iniciando procesamiento: {video_path}")

        # Abrir video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"No se puede abrir video: {video_path}")
            return

        # Obtener propiedades
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        logger.info(f"Video: {width}x{height} @ {fps:.1f} FPS, {total_frames} frames")

        # Inicializar video writer
        if output_path is None:
            output_path = self.output_dir / f"output_{Path(video_path).stem}.mp4"

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(
            str(output_path), fourcc, fps, (width, height)
        )

        logger.info(f"Escribiendo a: {output_path}")

        # Procesar frames
        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            start_time = time.perf_counter()

            # Procesar frame
            annotated = self.process_frame(frame, frame_idx)

            # Escribir
            if self.video_writer:
                self.video_writer.write(annotated)

            # Estadísticas
            elapsed = (time.perf_counter() - start_time) * 1000
            self.stats['processing_times'].append(elapsed)

            # Log
            if frame_idx % 30 == 0:
                avg_time = np.mean(self.stats['processing_times'][-30:])
                fps_actual = 1000 / avg_time
                logger.info(
                    f"Frame {frame_idx}/{total_frames} - "
                    f"FPS: {fps_actual:.1f}, "
                    f"Tracks: {self.stats['tracks_created']}"
                )

            # Mostrar preview (opcional)
            if frame_idx % 10 == 0:  # Mostrar cada 10 frames
                cv2.imshow("Analysis", annotated)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        # Limpiar
        cap.release()
        if self.video_writer:
            self.video_writer.release()
        cv2.destroyAllWindows()

        logger.info(f"✓ Procesamiento completado: {output_path}")
        self.print_statistics()

    def process_frame(self, frame: np.ndarray, frame_idx: int) -> np.ndarray:
        """
        Procesar un frame individual.

        Args:
            frame: Frame BGR
            frame_idx: Índice del frame

        Returns:
            Frame anotado
        """
        self.frame_count = frame_idx

        # 1. DETECCIÓN
        detections_dict = self.detector.detect_frame(frame)
        players_sv = detections_dict['players_sv']
        ball_dict = detections_dict['ball']

        # 2. TRACKING con Deep SORT
        result = self.tracker.update(players_sv, frame)
        tracks = result['tracks']
        self.stats['tracks_created'] += result['new_tracks']

        # Crear detecciones para siguiente paso
        if tracks:
            track_bboxes = np.array([t['bbox'] for t in tracks])
            track_ids = np.array([t['track_id'] for t in tracks])

            tracks_sv = sv.Detections(
                xyxy=track_bboxes.astype(float),
                confidence=np.ones(len(tracks)),
                class_id=np.zeros(len(tracks), dtype=int),
                tracker_id=track_ids.astype(int),
            )
        else:
            tracks_sv = sv.Detections.empty()

        # 3. ASIGNACIÓN DE EQUIPOS
        if len(tracks_sv) > 0:
            team_labels, team_diag = self.team_assigner.assign_teams(frame, tracks_sv)
        else:
            team_labels = np.array([])

        # 4. ANÁLISIS DE POSESIÓN
        if len(tracks_sv) > 0 and ball_dict['detected']:
            ball_sv = sv.Detections(
                xyxy=np.array([ball_dict['bbox']]),
                confidence=np.array([ball_dict['confidence']]),
                class_id=np.array([2]),  # Clase 2 = balón
            )
            possession_info = self.possession.get_ball_possession(
                ball_sv, tracks_sv, team_labels
            )
        else:
            possession_info = None

        # 5. CÁLCULO DE MÉTRICAS
        if len(tracks_sv) > 0:
            centers = get_box_centers(tracks_sv)
            for track_id, center in zip(track_ids, centers):
                self.metrics.update_player_position(int(track_id), tuple(center))

        # 6. VISUALIZACIÓN
        annotated = self._annotate_frame(
            frame, tracks_sv, team_labels, possession_info, ball_dict, frame_idx
        )

        return annotated

    def _annotate_frame(self,
                       frame: np.ndarray,
                       tracks: sv.Detections,
                       team_labels: np.ndarray,
                       possession_info: Dict,
                       ball_dict: Dict,
                       frame_idx: int) -> np.ndarray:
        """Anotar frame con información de tracking."""

        annotated = frame.copy()
        h, w = frame.shape[:2]

        # 1. Dibujar tracks con IDs
        if len(tracks) > 0:
            # Colores por equipo
            colors = np.array([
                [255, 0, 0],    # Equipo 0: Azul
                [0, 0, 255],    # Equipo 1: Rojo
            ])

            for track_id, bbox, team_id in zip(
                tracks.tracker_id, tracks.xyxy, team_labels
            ):
                x1, y1, x2, y2 = bbox.astype(int)
                color = tuple(colors[int(team_id) % 2].tolist())

                # Dibujar bbox
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                # Dibujar ID
                cv2.putText(
                    annotated,
                    f"ID {int(track_id)}",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )

        # 2. Dibujar balón
        if ball_dict['detected']:
            x1, y1, x2, y2 = ball_dict['bbox']
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            cv2.circle(
                annotated,
                ((x1 + x2) // 2, (y1 + y2) // 2),
                5,
                (0, 255, 255),
                -1,
            )

        # 3. Información de posesión
        if possession_info and possession_info['possessing_team'] is not None:
            team = possession_info['possessing_team']
            confidence = possession_info['confidence']
            team_name = "TEAM 0 (BLUE)" if team == 0 else "TEAM 1 (RED)"

            cv2.putText(
                annotated,
                f"Possession: {team_name} ({confidence:.0%})",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )

        # 4. Información general
        cv2.putText(
            annotated,
            f"Frame: {frame_idx} | Tracks: {len(tracks)}",
            (10, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (200, 200, 200),
            2,
        )

        return annotated

    def print_statistics(self):
        """Imprimir estadísticas finales."""
        logger.info("\n" + "=" * 60)
        logger.info("ESTADÍSTICAS FINALES")
        logger.info("=" * 60)
        logger.info(f"Frames procesados: {self.frame_count}")
        logger.info(f"Tracks creados: {self.stats['tracks_created']}")

        if self.stats['processing_times']:
            avg_time = np.mean(self.stats['processing_times'])
            fps_avg = 1000 / avg_time
            logger.info(f"Tiempo promedio: {avg_time:.1f} ms ({fps_avg:.1f} FPS)")

        logger.info("=" * 60 + "\n")


def main():
    """Función main."""
    parser = argparse.ArgumentParser(
        description="Football Analysis Pipeline con Deep SORT"
    )
    parser.add_argument("--video", required=True, help="Ruta al video")
    parser.add_argument("--output", default="results/", help="Directorio de salida")
    parser.add_argument("--model", default="yolov8x", help="Modelo YOLO")
    parser.add_argument("--no-features", action="store_true", help="Desabilitar features")
    parser.add_argument("--fps", type=float, default=30.0, help="FPS del video")

    args = parser.parse_args()

    # Crear pipeline
    pipeline = FootballAnalysisPipeline(
        model_path=args.model,
        output_dir=args.output,
        use_deep_sort=True,
        use_features=not args.no_features,
        fps=args.fps,
    )

    # Procesar video
    pipeline.process_video(args.video)


if __name__ == "__main__":
    main()

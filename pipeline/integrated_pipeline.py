"""
FASE 5 - TAREA 1: Pipeline Completo Integrado

Módulo que conecta todos los componentes de análisis:
1. Video Loading
2. Frame Processing (Detection + Tracking)
3. Player Analysis (Distance, Velocity, Intensity)
4. Stats Aggregation
5. Report Generation

Uso:
    pipeline = IntegratedAnalysisPipeline(fps=30)
    results = pipeline.process_video("video.mp4")
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import cv2
import numpy as np

# Importar componentes disponibles
try:
    from core.detector import BallDetector
except ImportError:
    BallDetector = None

try:
    from core.tracker import PlayerTracker
except ImportError:
    PlayerTracker = None

try:
    from core.distance_velocity_calculator import DistanceVelocityAnalyzer, TrackPoint
except ImportError:
    DistanceVelocityAnalyzer = None
    TrackPoint = None

try:
    from core.intensity_analyzer import IntensityAnalyzer
except ImportError:
    IntensityAnalyzer = None

try:
    from core.heatmap_generator import HeatmapManager, HeatmapConfig
except ImportError:
    HeatmapManager = None
    HeatmapConfig = None

try:
    from core.player_stats_aggregator import PlayerStatsAggregator
except ImportError:
    PlayerStatsAggregator = None

try:
    from core.performance_validator import PerformanceValidator
except ImportError:
    PerformanceValidator = None

try:
    from core.adaptive_calibration import VideoQualityAnalyzer, AdaptiveCalibration
except ImportError:
    VideoQualityAnalyzer = None
    AdaptiveCalibration = None


logger = logging.getLogger(__name__)


@dataclass
class ProcessingConfig:
    """Configuración del pipeline."""
    fps: float = 30.0
    pixels_per_meter: float = 10.0
    field_length_m: float = 105.0
    field_width_m: float = 68.0
    confidence_threshold: float = 0.5
    min_track_length: int = 5
    tracker_max_distance: float = 50.0


@dataclass
class FrameResult:
    """Resultado de procesar un frame."""
    frame_idx: int
    players: List[Dict]
    ball: Optional[Tuple[float, float]]
    pitch_detected: bool
    processing_time_ms: float


@dataclass
class PipelineResult:
    """Resultado final del pipeline."""
    video_path: str
    total_frames: int
    duration_seconds: float
    fps: float
    frames_processed: int
    player_stats: Dict
    team_summary: Dict
    errors: List[str]
    warnings: List[str]
    processing_time_seconds: float
    validation_report: Dict = None
    quality_metrics: Dict = None
    adaptive_config: Dict = None


class IntegratedAnalysisPipeline:
    """
    Pipeline completo que procesa video de fútbol y genera análisis.

    Flujo:
        1. Cargar video
        2. Por cada frame:
           - Detectar jugadores/balón
           - Rastrar movimiento
           - Calcular métricas
        3. Agregar estadísticas finales
        4. Exportar resultados
    """

    def __init__(self, config: Optional[ProcessingConfig] = None):
        """
        Inicializar pipeline.

        Args:
            config: Configuración del pipeline (opcional)
        """
        self.config = config or ProcessingConfig()

        # Inicializar componentes (con validación)
        self.detector = None  # Se inicializa en process_video si está disponible
        self.tracker = PlayerTracker() if PlayerTracker else None
        self.distance_analyzer = (
            DistanceVelocityAnalyzer(
                fps=self.config.fps,
                pixels_per_meter=self.config.pixels_per_meter
            ) if DistanceVelocityAnalyzer else None
        )
        self.intensity_analyzer = IntensityAnalyzer(fps=self.config.fps) if IntensityAnalyzer else None
        self.stats_aggregator = PlayerStatsAggregator(team_id="HOME") if PlayerStatsAggregator else None
        self.heatmap_manager = (
            HeatmapManager(
                config=HeatmapConfig(canvas_width=1920, canvas_height=1080)
            ) if HeatmapManager and HeatmapConfig else None
        )

        # Inicializar analizadores de calibración adaptativa
        self.quality_analyzer = VideoQualityAnalyzer() if VideoQualityAnalyzer else None
        self.adaptive_calibration = AdaptiveCalibration if AdaptiveCalibration else None

        self.player_tracks = defaultdict(list)
        self.errors = []
        self.warnings = []
        self.performance_validator = (
            PerformanceValidator() if PerformanceValidator else None
        )
        self.player_validations = []  # Almacenar validaciones de cada jugador

        # Almacenar métricas de calibración
        self.quality_metrics = None
        self.applied_adaptive_config = None

    def process_video(self, video_path: str, output_dir: Optional[str] = None) -> PipelineResult:
        """
        Procesar video completo y generar análisis.

        Args:
            video_path: Ruta al video
            output_dir: Directorio para guardar resultados

        Returns:
            PipelineResult con estadísticas completas
        """
        import time
        start_time = time.time()

        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video no encontrado: {video_path}")

        logger.info(f"Iniciando procesamiento: {video_path}")

        # Abrir video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise IOError(f"No se pudo abrir video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = total_frames / fps if fps > 0 else 0

        logger.info(f"Video: {total_frames} frames @ {fps} fps ({duration_seconds:.1f}s)")

        # FASE 6: Análisis de calidad y calibración adaptativa
        quality_analysis_time = 0
        if self.quality_analyzer:
            try:
                import time as time_module
                quality_start = time_module.time()

                # Analizar calidad del video
                quality_metrics_result = self.quality_analyzer.analyze_video(str(video_path))

                if quality_metrics_result:
                    # Almacenar métricas en formato de diccionario
                    self.quality_metrics = quality_metrics_result.to_dict() if hasattr(
                        quality_metrics_result, 'to_dict'
                    ) else quality_metrics_result

                    # Obtener configuración optimizada
                    if self.adaptive_calibration:
                        calibrator = self.adaptive_calibration()
                        processing_config = calibrator.get_optimal_config(quality_metrics_result)

                        # Almacenar configuración adaptativa
                        self.applied_adaptive_config = {
                            'confidence_threshold': processing_config.confidence_threshold,
                            'tracker_max_distance': processing_config.tracker_max_distance,
                            'skip_frames': processing_config.skip_frames,
                            'use_motion_blur': processing_config.use_motion_blur,
                            'gk_sensitivity': processing_config.gk_sensitivity,
                            'quality_report': processing_config.quality_report,
                        }

                        # Aplicar ajustes a la configuración del pipeline
                        self.config.confidence_threshold = processing_config.confidence_threshold
                        self.config.tracker_max_distance = processing_config.tracker_max_distance
                        # min_track_length se ajusta basado en skip_frames
                        if processing_config.skip_frames > 2:
                            self.config.min_track_length = max(2, self.config.min_track_length - 1)

                        # Registrar ajustes aplicados
                        quality_str = self.quality_metrics.get('video_quality', 'UNKNOWN')
                        if hasattr(quality_str, 'value'):
                            quality_str = quality_str.value

                        logger.info(f"Video quality: {quality_str}")
                        logger.info(f"Applied adaptive adjustments:")
                        logger.info(f"  - Confidence threshold: {self.config.confidence_threshold:.2f}")
                        logger.info(f"  - Tracker max distance: {self.config.tracker_max_distance:.0f}px")
                        logger.info(f"  - Skip frames: {processing_config.skip_frames}")
                        logger.info(processing_config.quality_report)

                quality_analysis_time = time_module.time() - quality_start
                logger.info(f"Quality analysis completed in {quality_analysis_time:.2f}s")

            except Exception as e:
                self.warnings.append(f"Error durante análisis de calidad: {str(e)}")
                logger.warning(f"Quality analysis failed: {str(e)}")

        frame_idx = 0
        frame_results = []

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Procesar frame
                result = self._process_frame(frame, frame_idx)
                frame_results.append(result)
                frame_idx += 1

                # Progress
                if frame_idx % 100 == 0:
                    logger.info(f"Procesados {frame_idx}/{total_frames} frames")

        except Exception as e:
            self.errors.append(f"Error procesando frame {frame_idx}: {str(e)}")
            logger.error(f"Error en frame {frame_idx}: {str(e)}")

        finally:
            cap.release()

        # Agregar estadísticas
        logger.info("Agregando estadísticas...")
        player_stats = self._aggregate_player_stats()
        team_summary = self.stats_aggregator.get_team_summary()

        # Generar reporte de validación
        validation_report = None
        if self.performance_validator and self.player_validations:
            validation_report = self.performance_validator.generate_validation_report(
                self.player_validations
            )
            logger.info(
                f"Validación completada: {len(self.player_validations)} jugadores, "
                f"{validation_report['anomalies_detected']} anomalías detectadas"
            )

        # Crear resultado
        processing_time = time.time() - start_time

        result = PipelineResult(
            video_path=str(video_path),
            total_frames=total_frames,
            duration_seconds=duration_seconds,
            fps=fps,
            frames_processed=frame_idx,
            player_stats=player_stats,
            team_summary=team_summary,
            errors=self.errors,
            warnings=self.warnings,
            processing_time_seconds=processing_time,
            validation_report=validation_report or {},
            quality_metrics=self.quality_metrics or {},
            adaptive_config=self.applied_adaptive_config or {}
        )

        # Exportar si se especifica output_dir
        if output_dir:
            self._export_results(result, output_dir)

        logger.info(f"Procesamiento completado en {processing_time:.1f}s")
        return result

    def _process_frame(self, frame: np.ndarray, frame_idx: int) -> FrameResult:
        """
        Procesar un frame individual.

        Args:
            frame: Frame de OpenCV (BGR)
            frame_idx: Índice del frame

        Returns:
            FrameResult con detecciones
        """
        import time
        start = time.time()

        try:
            # 1. Detectar jugadores y balón
            detections = self.detector.detect(frame)

            # 2. Rastrar
            tracks = self.tracker.update(detections)

            # 3. Registrar trayectorias
            for track_id, track in tracks.items():
                if track.confidence >= self.config.confidence_threshold:
                    track_point = TrackPoint(
                        frame=frame_idx,
                        x=track.bbox[0] + track.bbox[2] / 2,
                        y=track.bbox[1] + track.bbox[3] / 2,
                        confidence=track.confidence,
                        is_interpolated=False
                    )
                    self.player_tracks[track_id].append(track_point)

            elapsed = (time.time() - start) * 1000

            return FrameResult(
                frame_idx=frame_idx,
                players=self._format_detections(tracks),
                ball=self._extract_ball(detections),
                pitch_detected=True,  # TODO: Agregar detección real
                processing_time_ms=elapsed
            )

        except Exception as e:
            self.errors.append(f"Error en frame {frame_idx}: {str(e)}")
            return FrameResult(
                frame_idx=frame_idx,
                players=[],
                ball=None,
                pitch_detected=False,
                processing_time_ms=0
            )

    def _format_detections(self, tracks: Dict) -> List[Dict]:
        """Formatear detecciones para exportación."""
        formatted = []
        for track_id, track in tracks.items():
            formatted.append({
                'id': track_id,
                'bbox': track.bbox,
                'confidence': track.confidence,
                'class': track.class_name
            })
        return formatted

    def _extract_ball(self, detections) -> Optional[Tuple[float, float]]:
        """Extraer posición del balón de detecciones."""
        # TODO: Implementar lógica real
        return None

    def _aggregate_player_stats(self) -> Dict:
        """Agregar estadísticas por jugador con validación de StatsBomb."""
        player_stats = {}

        for player_id, tracks in self.player_tracks.items():
            if len(tracks) < self.config.min_track_length:
                continue

            try:
                # Distancia y velocidad
                distance_analysis = self.distance_analyzer.analyze_player_trajectory(tracks)

                # Intensidad
                velocities = np.array(distance_analysis.velocity.velocity_per_frame)
                positions = [(t.x, t.y) for t in tracks]
                intensity_metrics = self.intensity_analyzer.analyze(velocities, positions)

                # Heatmap
                heatmap_data = self.heatmap_manager.generate_complete_analysis(
                    tracks=[t for t in tracks],
                    player_id=player_id
                )

                # Agregar al agregador
                stats = self.stats_aggregator.aggregate_player_stats(
                    player_id=player_id,
                    player_number=player_id,
                    player_name=f"Player {player_id}",
                    position="MID",
                    distance_metrics={
                        'total_distance_m': distance_analysis.distance.total_distance
                    },
                    velocity_metrics={
                        'max_velocity_m_s': distance_analysis.velocity.max_velocity,
                        'avg_velocity_m_s': distance_analysis.velocity.average_velocity,
                        'median_velocity_m_s': distance_analysis.velocity.median_velocity,
                        'percentile_90_m_s': distance_analysis.velocity.percentile_90,
                        'percentile_95_m_s': distance_analysis.velocity.percentile_95,
                    },
                    intensity_metrics={
                        'movement_intensity_percent': intensity_metrics.movement_intensity_percent,
                        'sprints_count': intensity_metrics.sprints_count,
                        'directional_changes': intensity_metrics.directional_changes,
                    }
                )

                # Generar validación contra benchmarks de StatsBomb
                validation = None
                validation_data = {}
                if self.performance_validator:
                    validation = self.performance_validator.generate_comparison(
                        player_id=player_id,
                        player_name=f"Player {player_id}",
                        position=stats.position,
                        distance_m=stats.distance_total_m,
                        max_velocity_m_s=stats.velocity_max,
                        intensity_pct=stats.intensity_pct
                    )
                    self.player_validations.append(validation)

                    # Construir diccionario de validación
                    validation_data = {
                        'distance_status': validation.metrics.get('distance').status,
                        'distance_percentile': round(
                            validation.metrics.get('distance').percentile, 1
                        ),
                        'velocity_status': validation.metrics.get('max_velocity').status,
                        'velocity_percentile': round(
                            validation.metrics.get('max_velocity').percentile, 1
                        ),
                        'intensity_status': validation.metrics.get('intensity').status,
                        'intensity_percentile': round(
                            validation.metrics.get('intensity').percentile, 1
                        ),
                        'overall_performance': validation.performance_level,
                        'overall_status': validation.overall_status,
                        'anomalies_detected': validation.anomalies_detected,
                    }

                # Agregar al resultado
                stats_dict = asdict(stats)
                stats_dict['validation'] = validation_data
                player_stats[str(player_id)] = stats_dict

            except Exception as e:
                self.warnings.append(f"Error analizando jugador {player_id}: {str(e)}")
                logger.warning(f"Error jugador {player_id}: {str(e)}")

        return player_stats

    def _export_results(self, result: PipelineResult, output_dir: str):
        """Exportar resultados a archivos."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Exportar JSON principal
        json_path = output_path / "analysis_complete.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(result), f, indent=2, default=str)

        logger.info(f"Resultados exportados a {json_path}")

    def get_player_track(self, player_id: int) -> List[TrackPoint]:
        """Obtener trayectoria de jugador."""
        return self.player_tracks.get(player_id, [])


def process_video_simple(
    video_path: str,
    output_dir: Optional[str] = None,
    fps: float = 30.0
) -> PipelineResult:
    """
    Función simple para procesar video en una línea.

    Args:
        video_path: Ruta al video
        output_dir: Directorio para resultados
        fps: FPS del video

    Returns:
        PipelineResult
    """
    config = ProcessingConfig(fps=fps)
    pipeline = IntegratedAnalysisPipeline(config)
    return pipeline.process_video(video_path, output_dir)


if __name__ == "__main__":
    # Ejemplo de uso
    logging.basicConfig(level=logging.INFO)

    # Procesar video de prueba
    video_file = "data/videos/test_match_30s.mp4"
    if Path(video_file).exists():
        result = process_video_simple(video_file, output_dir="data/logs/pipeline_output")
        print(f"\n✓ Procesamiento completado:")
        print(f"  - Frames: {result.frames_processed}/{result.total_frames}")
        print(f"  - Jugadores: {len(result.player_stats)}")
        print(f"  - Tiempo: {result.processing_time_seconds:.1f}s")
        if result.errors:
            print(f"  - Errores: {len(result.errors)}")

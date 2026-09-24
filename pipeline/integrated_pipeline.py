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
    from core.detector import UnifiedDetector
except ImportError:
    UnifiedDetector = None

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
        self.detector = self._initialize_detector()
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

    def _initialize_detector(self) -> Optional['UnifiedDetector']:
        """
        Inicializar el detector unificado con los modelos YOLO.

        Returns:
            UnifiedDetector inicializado o None si hay error

        Raises:
            ValueError: Si no se encuentran los archivos de modelos o falsa inicialización
        """
        if not UnifiedDetector:
            logger.warning("UnifiedDetector no disponible - módulo no importado")
            return None

        # Rutas a los modelos (basadas en la estructura del proyecto)
        base_dir = Path(__file__).parent.parent / "data"
        player_model = base_dir / "football-player-detection.pt"
        ball_model = base_dir / "football-ball-detection.pt"
        pitch_model = base_dir / "football-pitch-detection.pt"

        # Validar que existen los archivos
        models_to_check = {
            'player': player_model,
            'ball': ball_model,
            'pitch': pitch_model
        }

        missing_models = [name for name, path in models_to_check.items() if not path.exists()]
        if missing_models:
            error_msg = f"Modelos YOLO no encontrados: {', '.join(missing_models)}"
            logger.error(error_msg)
            self.warnings.append(error_msg)
            return None

        try:
            detector = UnifiedDetector(
                player_model_path=str(player_model),
                ball_model_path=str(ball_model),
                pitch_model_path=str(pitch_model),
                device="cpu"  # Usar CPU por defecto, puede cambiar a "cuda" si hay GPU
            )
            logger.info("Detector unificado inicializado correctamente")
            logger.info(f"  - Player model: {player_model}")
            logger.info(f"  - Ball model: {ball_model}")
            logger.info(f"  - Pitch model: {pitch_model}")
            return detector

        except Exception as e:
            error_msg = f"Error al inicializar detector: {str(e)}"
            logger.error(error_msg)
            self.warnings.append(error_msg)
            return None

    def process_video(self, video_path: str, output_dir: Optional[str] = None) -> PipelineResult:
        """
        Procesar video completo y generar análisis.

        Args:
            video_path: Ruta al video
            output_dir: Directorio para guardar resultados

        Returns:
            PipelineResult con estadísticas completas

        Raises:
            RuntimeError: Si el detector no está disponible
        """
        import time
        start_time = time.time()

        # Validación crítica: detector debe estar inicializado
        if self.detector is None:
            error_msg = (
                "DETECTOR NO INICIALIZADO: No se pueden procesar frames. "
                "Verifica que los modelos YOLO están en data/ (football-player-detection.pt, "
                "football-ball-detection.pt, football-pitch-detection.pt)"
            )
            logger.critical(error_msg)
            raise RuntimeError(error_msg)

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
            # Validación: detector debe estar disponible
            if self.detector is None:
                raise RuntimeError(
                    f"Detector no disponible en frame {frame_idx}. "
                    "Esto indica un error crítico en la inicialización."
                )

            # 1. Detectar jugadores, balón y cancha
            detection_result = self.detector.detect_frame(
                frame,
                player_conf=self.config.confidence_threshold,
                ball_conf=self.config.confidence_threshold,
                pitch_conf=self.config.confidence_threshold
            )

            # 2. Rastrar jugadores usando detecciones
            # CORRECCIÓN: usar track() no update() - track() retorna stats, no tracks
            self.tracker.track(detection_result['players'], frame_id=frame_idx)

            # 3. Obtener tracks activos (CORRECCIÓN: usar get_tracks())
            active_tracks = self.tracker.get_tracks(min_confidence=self.config.confidence_threshold)

            # Registrar trayectorias
            for track_dict in active_tracks:
                track_id = track_dict['track_id']
                position = track_dict['position']  # Tupla (x, y)
                confidence = track_dict['confidence']

                track_point = TrackPoint(
                    frame=frame_idx,
                    x=position[0],
                    y=position[1],
                    confidence=confidence,
                    is_interpolated=False
                )
                self.player_tracks[track_id].append(track_point)

            elapsed = (time.time() - start) * 1000

            return FrameResult(
                frame_idx=frame_idx,
                players=self._format_detections(active_tracks),
                ball=self._extract_ball_from_detection(detection_result),
                pitch_detected=detection_result['pitch']['valid'],
                processing_time_ms=elapsed
            )

        except Exception as e:
            self.errors.append(f"Error en frame {frame_idx}: {str(e)}")
            logger.error(f"Frame {frame_idx} error: {str(e)}", exc_info=True)
            return FrameResult(
                frame_idx=frame_idx,
                players=[],
                ball=None,
                pitch_detected=False,
                processing_time_ms=0
            )

    def _format_detections(self, tracks_list: List[Dict]) -> List[Dict]:
        """
        Formatear detecciones para exportación.

        Args:
            tracks_list: Lista de dicts con información de tracks (de get_tracks())

        Returns:
            Lista de dicts formateados para exportación
        """
        formatted = []
        for track_dict in tracks_list:
            # CORRECCIÓN: track_dict ya es un diccionario, no un objeto TrackState
            # No usar track.class_name que no existe
            formatted.append({
                'id': track_dict['track_id'],
                'bbox': track_dict['bbox'],
                'confidence': track_dict['confidence'],
                'team_id': track_dict.get('team_id'),
                'jersey_number': track_dict.get('jersey_number'),
                'position': track_dict['position']
            })
        return formatted

    def _extract_ball_from_detection(self, detection_result: Dict) -> Optional[Tuple[float, float]]:
        """
        Extraer posición del balón de detecciones.

        Args:
            detection_result: Resultado del detector.detect_frame()

        Returns:
            Tupla (x, y) del centro del balón o None
        """
        if not detection_result or 'ball' not in detection_result:
            return None

        ball_data = detection_result.get('ball', {})
        if ball_data.get('detected') and ball_data.get('center'):
            center = ball_data['center']
            return (float(center[0]), float(center[1]))

        return None

    def _aggregate_player_stats(self) -> Dict:
        """Agregar estadísticas por jugador con validación de StatsBomb."""
        player_stats = {}

        for player_id, tracks in self.player_tracks.items():
            if len(tracks) < self.config.min_track_length:
                continue

            try:
                # Distancia y velocidad
                # CORRECCIÓN: analyze_player_trajectory retorna Dict, no objeto
                distance_analysis = self.distance_analyzer.analyze_player_trajectory(tracks)

                # Intensidad
                # CORRECCIÓN: acceder a campos del diccionario con ['key']
                velocities = np.array(distance_analysis['velocity'].velocity_per_frame)
                positions = [(t.x, t.y) for t in tracks]
                intensity_metrics = self.intensity_analyzer.analyze(velocities, positions)

                # Heatmap
                # CORRECCIÓN: convertir TrackPoint a tuplas (x, y) para heatmap
                track_positions = [(t.x, t.y) for t in tracks]
                heatmap_data = self.heatmap_manager.generate_complete_analysis(
                    tracks=track_positions,
                    player_id=player_id,
                    fps=int(self.config.fps)
                )

                # Agregar al agregador
                # CORRECCIÓN: acceder a campos del diccionario y dataclass correctamente
                stats = self.stats_aggregator.aggregate_player_stats(
                    player_id=player_id,
                    player_number=player_id,
                    player_name=f"Player {player_id}",
                    position="MID",
                    distance_metrics={
                        'total_distance_m': distance_analysis['distance'].total_distance
                    },
                    velocity_metrics={
                        'max_velocity_m_s': distance_analysis['velocity'].max_velocity,
                        'avg_velocity_m_s': distance_analysis['velocity'].average_velocity,
                        'median_velocity_m_s': distance_analysis['velocity'].median_velocity,
                        'percentile_90_m_s': distance_analysis['velocity'].percentile_90,
                        'percentile_95_m_s': distance_analysis['velocity'].percentile_95,
                    },
                    intensity_metrics={
                        'movement_intensity_percent': intensity_metrics.active_movement_percentage,
                        'sprints_count': intensity_metrics.sprint_count,
                        'directional_changes': intensity_metrics.direction_changes_count,
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

"""
video_processor_fase3.py - Pipeline end-to-end integrado FASE 3

Pipeline mejorado que integra todos los componentes de FASE 2:
- TeamClassifier mejorado (clustering, validación de colores)
- Tracker mejorado (ByteTrack, oclusiones, velocidad)
- JerseyNumberDetector mejorado (OCR multi-engine, validaciones)
- Flujo: detectar → trackear → clasificar equipo → detectar números

Incluye manejo robusto de errores, logging detallado y perfilado de rendimiento.

Author: Scout AI - FASE 3
Date: 2026-07-06
"""

import numpy as np
import logging
import time
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
import json
from collections import defaultdict
import psutil
import cProfile
import pstats
import io

from tqdm import tqdm

from .frame_processor import FrameProcessor, FrameData
from ..utils.video_reader import VideoReader, OpenCVVideoReader
from ..core.team_classifier import TeamClassifier
from ..core.tracker import PlayerTracker
from ..core.jersey_number_detector import JerseyNumberDetector


@dataclass
class PerformanceBenchmark:
    """Benchmark de rendimiento de un componente"""
    component_name: str
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    calls_count: int

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ProcessingConfigFase3:
    """Configuración FASE 3 con opciones avanzadas"""
    min_confidence: float = 0.3
    skip_frames: int = 1
    max_frames: Optional[int] = None
    enable_tracking: bool = True
    enable_team_classification: bool = True
    enable_jersey_detection: bool = True
    enable_analysis: bool = True
    save_intermediate: bool = False
    output_dir: Optional[Path] = None

    # Tracking parameters
    tracker_max_age: int = 30
    tracker_min_hits: int = 3

    # Team classification parameters
    team_classifier_clusters: int = 2
    team_color_confidence_threshold: float = 0.3

    # Jersey detection parameters
    jersey_use_paddle: bool = True
    jersey_use_easyocr: bool = True
    jersey_confidence_threshold: float = 0.4

    # Benchmarking
    enable_profiling: bool = False
    profile_output_path: Optional[Path] = None


@dataclass
class ProcessingResultFase3:
    """Resultado mejorado del procesamiento de video FASE 3"""
    video_path: str
    total_frames: int
    processed_frames: int
    skipped_frames: int
    frame_data: List[FrameData] = field(default_factory=list)
    processing_stats: Dict[str, Any] = field(default_factory=dict)
    performance_benchmarks: Dict[str, PerformanceBenchmark] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    total_time_seconds: float = 0.0
    fps_processed: float = 0.0
    timestamp: str = ""

    # Nuevas métricas FASE 3
    team_classification_stats: Dict[str, Any] = field(default_factory=dict)
    tracking_stats: Dict[str, Any] = field(default_factory=dict)
    jersey_detection_stats: Dict[str, Any] = field(default_factory=dict)
    system_resources: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convertir resultado a diccionario"""
        d = asdict(self)
        d['frame_data'] = [f.to_dict() for f in self.frame_data]
        d['performance_benchmarks'] = {
            k: v.to_dict() for k, v in self.performance_benchmarks.items()
        }
        return d

    def save_json(self, path: Path):
        """Guardar resultado a JSON"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class VideoProcessorFase3:
    """
    Pipeline end-to-end integrado FASE 3.

    Orquesta el procesamiento completo incluyendo:
    - Detección de objetos (YOLO)
    - Tracking mejorado (ByteTrack + validaciones)
    - Clasificación de equipos (KMeans + validación de colores)
    - Detección de números de camiseta (OCR multi-engine)

    Con soporte para:
    - Fallbacks en cada componente
    - Logging detallado
    - Recuperación de fallos parciales
    - Perfilado de CPU
    - Monitoreo de memoria
    - Benchmarking de rendimiento

    Attributes:
        logger (logging.Logger): Logger para registro de eventos
        detector: Detector YOLO
        tracker: Tracker mejorado
        team_classifier: Clasificador de equipos
        jersey_detector: Detector de números
        analyzer: Analizador de características
        frame_processor (FrameProcessor): Procesador de frames individual
    """

    def __init__(
        self,
        detector=None,
        tracker: Optional[PlayerTracker] = None,
        team_classifier: Optional[TeamClassifier] = None,
        jersey_detector: Optional[JerseyNumberDetector] = None,
        analyzer=None,
        config: Optional[ProcessingConfigFase3] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Inicializa el procesador FASE 3.

        Args:
            detector: Instancia de detector YOLO
            tracker: Instancia de tracker mejorado
            team_classifier: Instancia de clasificador de equipos
            jersey_detector: Instancia de detector de jerseys
            analyzer: Instancia de analizador
            config: Configuración FASE 3
            logger: Logger personalizado
        """
        self.detector = detector
        self.tracker = tracker
        self.team_classifier = team_classifier
        self.jersey_detector = jersey_detector
        self.analyzer = analyzer

        self.config = config or ProcessingConfigFase3()
        self.logger = logger or self._setup_logger()

        # Inicializar frame processor
        self.frame_processor = self._initialize_frame_processor()

        # Estadísticas
        self.stats = self._init_stats()

        # Benchmarking
        self.benchmarks = defaultdict(lambda: {
            'times': [],
            'total_time': 0.0,
            'count': 0
        })

        # Profiler
        self.profiler = None
        if self.config.enable_profiling:
            self.profiler = cProfile.Profile()

    def _setup_logger(self) -> logging.Logger:
        """Configura el logger con salida detallada"""
        logger = logging.getLogger('VideoProcessorFase3')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] %(name)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        return logger

    def _init_stats(self) -> Dict[str, Any]:
        """Inicializa estadísticas"""
        return {
            'total_frames': 0,
            'processed_frames': 0,
            'skipped_frames': 0,
            'detection_errors': 0,
            'tracking_errors': 0,
            'team_classification_errors': 0,
            'jersey_detection_errors': 0,
            'total_detections': 0,
            'valid_detections': 0,
        }

    def _initialize_frame_processor(self) -> FrameProcessor:
        """Inicializa el procesador de frames"""
        return FrameProcessor(
            detector=self.detector,
            tracker=self.tracker if self.config.enable_tracking else None,
            team_classifier=(
                self.team_classifier if self.config.enable_team_classification else None
            ),
            analyzer=self.analyzer if self.config.enable_analysis else None,
            min_confidence=self.config.min_confidence,
            logger=self.logger
        )

    def _benchmark_component(self, component_name: str, func, *args, **kwargs) -> Any:
        """
        Ejecuta una función y registra su rendimiento.

        Args:
            component_name: Nombre del componente para logging
            func: Función a ejecutar
            *args, **kwargs: Argumentos de la función

        Returns:
            Resultado de la función
        """
        start_time = time.perf_counter()

        try:
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - start_time) * 1000  # ms

            # Registrar benchmark
            self.benchmarks[component_name]['times'].append(elapsed)
            self.benchmarks[component_name]['total_time'] += elapsed
            self.benchmarks[component_name]['count'] += 1

            return result

        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                f"Error en {component_name}: {str(e)} ({elapsed:.2f}ms)"
            )
            self.benchmarks[component_name]['times'].append(elapsed)
            self.benchmarks[component_name]['total_time'] += elapsed
            self.benchmarks[component_name]['count'] += 1
            raise

    def _get_system_memory_info(self) -> Dict[str, float]:
        """Obtiene información de memoria del sistema"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            return {
                'rss_mb': memory_info.rss / (1024 * 1024),
                'vms_mb': memory_info.vms / (1024 * 1024),
                'percent': process.memory_percent()
            }
        except Exception as e:
            self.logger.warning(f"No se pudo obtener info de memoria: {e}")
            return {}

    def setup_detectors(self) -> bool:
        """
        Inicializa y valida todos los detectores con fallbacks.

        Returns:
            bool: True si la configuración es válida
        """
        try:
            self.logger.info("=" * 60)
            self.logger.info("Validando configuración de detectores FASE 3")
            self.logger.info("=" * 60)

            errors = []
            warnings = []

            # Detector YOLO (requerido)
            if self.detector is None:
                errors.append("Detector YOLO no configurado")
            else:
                self.logger.info("✓ Detector YOLO disponible")

            # Tracker (opcional con fallback)
            if self.config.enable_tracking:
                if self.tracker is None:
                    self.logger.warning("Tracking habilitado pero tracker no disponible")
                    self.tracker = PlayerTracker(
                        max_age=self.config.tracker_max_age,
                        min_hits=self.config.tracker_min_hits
                    )
                    self.logger.info("✓ Tracker creado por defecto")
                else:
                    self.logger.info("✓ Tracker disponible")

            # Team Classifier (opcional con fallback)
            if self.config.enable_team_classification:
                if self.team_classifier is None:
                    self.logger.warning("Team classification habilitada pero no disponible")
                    self.team_classifier = TeamClassifier(
                        n_clusters=self.config.team_classifier_clusters
                    )
                    self.logger.info("✓ Team Classifier creado por defecto")
                else:
                    self.logger.info("✓ Team Classifier disponible")

            # Jersey Detector (opcional con fallback)
            if self.config.enable_jersey_detection:
                if self.jersey_detector is None:
                    self.logger.warning("Jersey detection habilitada pero no disponible")
                    self.jersey_detector = JerseyNumberDetector(
                        use_paddle=self.config.jersey_use_paddle,
                        use_easyocr=self.config.jersey_use_easyocr
                    )
                    self.logger.info(
                        f"✓ Jersey Detector creado (OCR: {self.jersey_detector.ocr_type})"
                    )
                else:
                    self.logger.info(f"✓ Jersey Detector disponible")

            # Analizer (opcional)
            if self.config.enable_analysis:
                if self.analyzer is None:
                    self.logger.warning("Análisis habilitado pero analizador no disponible")
                else:
                    self.logger.info("✓ Analyzer disponible")

            if errors:
                for error in errors:
                    self.logger.error(f"✗ {error}")
                return False

            if warnings:
                for warning in warnings:
                    self.logger.warning(f"⚠ {warning}")

            self.logger.info("=" * 60)
            self.logger.info("Validación de detectores completada ✓")
            self.logger.info("=" * 60)
            return True

        except Exception as e:
            self.logger.error(f"Error validando detectores: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return False

    def _process_frame_with_components(
        self,
        frame: np.ndarray,
        frame_number: int,
        timestamp: float
    ) -> Tuple[FrameData, Dict[str, Any]]:
        """
        Procesa un frame a través de todos los componentes.

        Flujo: detectar → trackear → clasificar equipo → detectar números

        Args:
            frame: Frame de video (BGR)
            frame_number: Número de frame
            timestamp: Timestamp en segundos

        Returns:
            Tupla (FrameData, componentes_stats)
        """
        component_stats = {}

        try:
            # 1. Procesar frame base (detección)
            frame_data = self.frame_processor.process_frame(
                frame,
                frame_number=frame_number,
                timestamp=timestamp
            )

            if not frame_data.detections:
                return frame_data, component_stats

            # Extraer bboxes de jugadores
            player_bboxes = [d.bbox for d in frame_data.detections
                           if d.class_name == 'player']

            if not player_bboxes:
                return frame_data, component_stats

            # 2. Tracking mejorado
            if self.config.enable_tracking and self.tracker:
                try:
                    detections_for_tracker = [
                        {
                            'bbox': d.bbox,
                            'confidence': d.confidence,
                            'class_name': d.class_name
                        }
                        for d in frame_data.detections
                    ]

                    tracking_result = self._benchmark_component(
                        'tracker',
                        self.tracker.track,
                        detections_for_tracker,
                        frame_id=frame_number
                    )

                    frame_data.tracking_data = tracking_result
                    component_stats['tracking'] = tracking_result

                except Exception as e:
                    self.logger.error(f"Error en tracking: {str(e)}")
                    self.stats['tracking_errors'] += 1

            # 3. Clasificación de equipos
            if self.config.enable_team_classification and self.team_classifier:
                try:
                    # Entrenar en primer frame con suficientes jugadores
                    if (not self.team_classifier.trained and
                        len(player_bboxes) >= self.config.team_classifier_clusters):
                        train_result = self._benchmark_component(
                            'team_classifier_train',
                            self.team_classifier.train,
                            player_bboxes,
                            frame
                        )
                        if train_result:
                            self.logger.debug(
                                f"Team Classifier entrenado en frame {frame_number}"
                            )

                    # Clasificar equipos
                    if self.team_classifier.trained:
                        classification_result = self._benchmark_component(
                            'team_classifier_classify',
                            self.team_classifier.classify,
                            player_bboxes,
                            frame
                        )

                        frame_data.team_assignments = {
                            i: team_id for i, team_id in
                            enumerate(classification_result['team_assignments'])
                        }
                        component_stats['team_classification'] = classification_result

                except Exception as e:
                    self.logger.error(f"Error en clasificación de equipos: {str(e)}")
                    self.stats['team_classification_errors'] += 1

            # 4. Detección de números de camiseta
            if self.config.enable_jersey_detection and self.jersey_detector:
                try:
                    jersey_result = self._benchmark_component(
                        'jersey_detector',
                        self.jersey_detector.detect,
                        player_bboxes,
                        frame
                    )

                    # Guardar números en frame_data
                    for i, number in enumerate(jersey_result['numbers']):
                        if number is not None and jersey_result['is_valid'][i]:
                            # Asociar con detecciones
                            if i < len(frame_data.detections):
                                frame_data.detections[i].features['jersey_number'] = number

                    component_stats['jersey_detection'] = {
                        'total_detected': len(jersey_result['numbers']),
                        'valid_numbers': sum(1 for v in jersey_result['is_valid'] if v),
                        'ocr_type': jersey_result['ocr_type']
                    }

                except Exception as e:
                    self.logger.error(f"Error en detección de jerseys: {str(e)}")
                    self.stats['jersey_detection_errors'] += 1

            return frame_data, component_stats

        except Exception as e:
            self.logger.error(f"Error crítico procesando frame {frame_number}: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise

    def process_video(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> ProcessingResultFase3:
        """
        Procesa un video completo del pipeline FASE 3.

        Args:
            video_path: Ruta al archivo de video
            output_path: Ruta para guardar resultados JSON

        Returns:
            ProcessingResultFase3: Resultado del procesamiento
        """
        start_time = time.time()
        start_memory = self._get_system_memory_info()

        try:
            # Validar entrada
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                raise FileNotFoundError(f"Video no encontrado: {video_path}")

            self.logger.info(f"\nIniciando procesamiento: {video_path}")

            # Validar detectores
            if not self.setup_detectors():
                raise RuntimeError("Falló validación de detectores")

            # Abrir video
            video_reader = OpenCVVideoReader(logger=self.logger)
            if not video_reader.open(str(video_path)):
                raise RuntimeError(f"No se pudo abrir video: {video_path}")

            # Obtener propiedades
            total_frames = video_reader.get_frame_count()
            fps = video_reader.get_fps()
            frame_width, frame_height = video_reader.get_resolution()

            self.logger.info(
                f"Video: {frame_width}x{frame_height} @ {fps:.1f}fps, "
                f"{total_frames} frames"
            )

            # Limitar frames si es necesario
            frames_to_process = total_frames
            if self.config.max_frames:
                frames_to_process = min(frames_to_process, self.config.max_frames)

            # Inicializar resultado
            result = ProcessingResultFase3(
                video_path=str(video_path),
                total_frames=total_frames,
                processed_frames=0,
                skipped_frames=0,
                timestamp=datetime.now().isoformat()
            )

            # Activar profiler si está habilitado
            if self.profiler:
                self.profiler.enable()

            # Procesar frames
            frame_num = 0
            processed_count = 0

            with tqdm(
                total=frames_to_process,
                desc="Procesando video FASE 3",
                unit="frames",
                leave=True
            ) as pbar:
                while video_reader.is_opened() and processed_count < frames_to_process:
                    ret, frame = video_reader.read_frame()

                    if not ret:
                        break

                    # Aplicar skip de frames
                    if frame_num % self.config.skip_frames != 0:
                        result.skipped_frames += 1
                        pbar.update(1)
                        frame_num += 1
                        continue

                    try:
                        # Obtener timestamp
                        timestamp = frame_num / fps if fps > 0 else 0.0

                        # Procesar frame con todos los componentes
                        frame_data, component_stats = self._process_frame_with_components(
                            frame,
                            frame_number=frame_num,
                            timestamp=timestamp
                        )

                        result.frame_data.append(frame_data)
                        result.processed_frames += 1
                        processed_count += 1

                        # Actualizar estadísticas
                        self.stats['processed_frames'] += 1
                        self.stats['total_detections'] += frame_data.detections_raw_count
                        self.stats['valid_detections'] += frame_data.detections_valid_count

                        if frame_data.errors:
                            self.stats['detection_errors'] += 1

                        pbar.update(1)
                        pbar.set_postfix({
                            'det': frame_data.detections_valid_count,
                            'time': f"{frame_data.processing_time_ms:.0f}ms"
                        })

                    except Exception as e:
                        self.logger.error(f"Error procesando frame {frame_num}: {str(e)}")
                        result.errors.append(f"Frame {frame_num}: {str(e)}")
                        self.stats['detection_errors'] += 1
                        pbar.update(1)

                    frame_num += 1

            # Desactivar profiler
            if self.profiler:
                self.profiler.disable()

            # Cerrar video
            video_reader.close()

            # Calcular estadísticas finales
            total_time = time.time() - start_time
            result.total_time_seconds = total_time
            if result.processed_frames > 0:
                result.fps_processed = result.processed_frames / total_time

            # Compilar estadísticas
            result.processing_stats = self._compile_stats()
            result.performance_benchmarks = self._compile_benchmarks()

            # Estadísticas de componentes
            if self.tracker:
                result.tracking_stats = self.tracker.get_statistics()
            if self.team_classifier:
                result.team_classification_stats = self.team_classifier.get_statistics()
            if self.jersey_detector:
                result.jersey_detection_stats = self.jersey_detector.get_statistics()

            # Información de recursos
            end_memory = self._get_system_memory_info()
            result.system_resources = {
                'start_memory': start_memory,
                'end_memory': end_memory,
                'total_time_seconds': total_time
            }

            # Log resumen
            self._log_processing_summary(result)

            # Guardar resultados si está configurado
            if output_path:
                output_path_obj = Path(output_path)
                result.save_json(output_path_obj)
                self.logger.info(f"Resultados guardados en: {output_path}")

            # Guardar profiling si está habilitado
            if self.profiler and self.config.profile_output_path:
                self._save_profile(self.config.profile_output_path)

            return result

        except Exception as e:
            self.logger.error(f"Error crítico procesando video: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise

    def _compile_stats(self) -> Dict[str, Any]:
        """Compila estadísticas del procesamiento"""
        stats = self.stats.copy()
        fp_stats = self.frame_processor.get_stats()
        stats['frame_processor'] = fp_stats

        if stats['processed_frames'] > 0:
            stats['avg_detections_per_frame'] = (
                stats['total_detections'] / stats['processed_frames']
            )
            stats['avg_valid_detections_per_frame'] = (
                stats['valid_detections'] / stats['processed_frames']
            )
            stats['error_rate'] = (
                stats['detection_errors'] / stats['processed_frames']
            )

        return stats

    def _compile_benchmarks(self) -> Dict[str, PerformanceBenchmark]:
        """Compila benchmarks de rendimiento"""
        benchmarks = {}

        for component_name, bench_data in self.benchmarks.items():
            if bench_data['count'] > 0:
                times = bench_data['times']
                benchmarks[component_name] = PerformanceBenchmark(
                    component_name=component_name,
                    total_time_ms=bench_data['total_time'],
                    avg_time_ms=bench_data['total_time'] / bench_data['count'],
                    min_time_ms=min(times),
                    max_time_ms=max(times),
                    calls_count=bench_data['count']
                )

        return benchmarks

    def _log_processing_summary(self, result: ProcessingResultFase3):
        """Log resumen del procesamiento"""
        self.logger.info("\n" + "=" * 60)
        self.logger.info("RESUMEN DEL PROCESAMIENTO")
        self.logger.info("=" * 60)
        self.logger.info(f"Frames procesados: {result.processed_frames}/{result.total_frames}")
        self.logger.info(f"Frames saltados: {result.skipped_frames}")
        self.logger.info(f"Tiempo total: {result.total_time_seconds:.2f}s")
        self.logger.info(f"FPS procesados: {result.fps_processed:.1f}")

        if result.processing_stats:
            stats = result.processing_stats
            self.logger.info(f"Detecciones totales: {stats.get('total_detections', 0)}")
            self.logger.info(f"Detecciones válidas: {stats.get('valid_detections', 0)}")

        if result.tracking_stats:
            self.logger.info(
                f"Tracks activos finales: {result.tracking_stats.get('active_tracks', 0)}"
            )

        if result.team_classification_stats:
            team_stats = result.team_classification_stats
            self.logger.info(f"Team Classifier entrenado: {team_stats.get('trained', False)}")

        if result.jersey_detection_stats:
            jersey_stats = result.jersey_detection_stats
            self.logger.info(f"Jersey OCR type: {jersey_stats.get('ocr_type', 'none')}")
            self.logger.info(f"Números detectados: {jersey_stats.get('valid_numbers', 0)}")

        if result.performance_benchmarks:
            self.logger.info("\nBenchmarks de rendimiento:")
            for name, bench in result.performance_benchmarks.items():
                self.logger.info(
                    f"  {name}: {bench.avg_time_ms:.2f}ms (min: {bench.min_time_ms:.2f}, "
                    f"max: {bench.max_time_ms:.2f})"
                )

        if result.system_resources.get('end_memory'):
            mem = result.system_resources['end_memory']
            self.logger.info(f"Memoria final: {mem.get('rss_mb', 0):.1f} MB")

        self.logger.info("=" * 60 + "\n")

    def _save_profile(self, output_path: Path):
        """Guarda profiling de CPU a archivo"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)

            s = io.StringIO()
            ps = pstats.Stats(self.profiler, stream=s).sort_stats('cumulative')
            ps.print_stats(30)  # Top 30 funciones

            with open(output_path, 'w') as f:
                f.write(s.getvalue())

            self.logger.info(f"Profiling guardado en: {output_path}")
        except Exception as e:
            self.logger.warning(f"No se pudo guardar profiling: {e}")

    def get_results(self) -> Dict[str, Any]:
        """Retorna los resultados del procesamiento"""
        return {
            'stats': self._compile_stats(),
            'benchmarks': {
                k: v.to_dict() for k, v in self._compile_benchmarks().items()
            },
            'timestamp': datetime.now().isoformat()
        }

    def reset(self):
        """Reinicia el estado del procesador"""
        self.stats = self._init_stats()
        self.benchmarks = defaultdict(lambda: {
            'times': [],
            'total_time': 0.0,
            'count': 0
        })
        self.frame_processor.reset_stats()
        if self.tracker:
            self.tracker.reset()
        if self.team_classifier:
            self.team_classifier.reset()
        if self.jersey_detector:
            self.jersey_detector.reset()
        self.logger.info("Procesador reiniciado")

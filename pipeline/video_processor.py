"""
video_processor.py - Orquestador principal del pipeline Scout AI

Este módulo proporciona la clase VideoProcessor que orquesta el procesamiento
completo de un video, coordinando la detección, tracking, clasificación de
equipos y análisis de jugadores. Es el componente de alto nivel que maneja
el flujo completo del pipeline.

Classes:
    VideoProcessor: Orquestador principal del pipeline de video
    ProcessingConfig: Configuración del procesador de video

Author: Scout AI Pipeline
Date: 2026-07-06
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
import json
from datetime import datetime
import time
import traceback
from tqdm import tqdm

from .frame_processor import FrameProcessor, FrameData


@dataclass
class ProcessingConfig:
    """Configuración para el VideoProcessor"""
    min_confidence: float = 0.3
    skip_frames: int = 1  # Procesar cada N frames
    max_frames: Optional[int] = None  # Máximo de frames a procesar
    enable_tracking: bool = True
    enable_team_classification: bool = True
    enable_analysis: bool = True
    save_intermediate: bool = False
    output_dir: Optional[Path] = None


@dataclass
class ProcessingResult:
    """Resultado del procesamiento de video"""
    video_path: str
    total_frames: int
    processed_frames: int
    skipped_frames: int
    frame_data: List[FrameData] = field(default_factory=list)
    processing_stats: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    total_time_seconds: float = 0.0
    fps_processed: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict:
        """Convertir resultado a diccionario"""
        d = asdict(self)
        d['frame_data'] = [f.to_dict() for f in self.frame_data]
        return d

    def save_json(self, path: Path):
        """Guardar resultado a JSON"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class VideoProcessor:
    """
    Orquestador principal del pipeline Scout AI.

    Coordina el procesamiento completo de un video, gestionando:
    - Lectura de frames
    - Detección de objetos
    - Tracking
    - Clasificación de equipos
    - Análisis de características

    Attributes:
        logger (logging.Logger): Logger para registro de eventos
        detector: Detector YOLO
        tracker: Tracker de objetos
        team_classifier: Clasificador de equipos
        analyzer: Analizador de características
        frame_processor (FrameProcessor): Procesador de frames individual

    Example:
        >>> processor = VideoProcessor(
        ...     detector=detector,
        ...     tracker=tracker,
        ...     team_classifier=team_classifier,
        ...     analyzer=analyzer
        ... )
        >>> result = processor.process_video('video.mp4')
        >>> print(f"Frames procesados: {result.processed_frames}")
    """

    def __init__(
        self,
        detector=None,
        tracker=None,
        team_classifier=None,
        analyzer=None,
        config: Optional[ProcessingConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Inicializa el procesador de video.

        Args:
            detector: Instancia de detector YOLO
            tracker: Instancia de tracker
            team_classifier: Instancia de clasificador de equipos
            analyzer: Instancia de analizador
            config (Optional[ProcessingConfig]): Configuración del procesador
            logger (Optional[logging.Logger]): Logger personalizado

        Raises:
            ValueError: Si los detectores son inválidos
        """
        self.detector = detector
        self.tracker = tracker
        self.team_classifier = team_classifier
        self.analyzer = analyzer

        self.config = config or ProcessingConfig()
        self.logger = logger or self._setup_logger()

        # Inicializar componentes
        self.frame_processor = self._initialize_frame_processor()

        # Estadísticas
        self.stats = {
            'total_frames': 0,
            'processed_frames': 0,
            'skipped_frames': 0,
            'detection_errors': 0,
            'total_detections': 0,
            'valid_detections': 0,
        }

    def _setup_logger(self) -> logging.Logger:
        """Configura el logger para el procesador de video"""
        logger = logging.getLogger('VideoProcessor')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _initialize_frame_processor(self) -> FrameProcessor:
        """
        Inicializa el procesador de frames.

        Returns:
            FrameProcessor: Procesador configurado
        """
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

    def setup_detectors(self) -> bool:
        """
        Inicializa y valida todos los detectores.

        Returns:
            bool: True si la configuración es válida

        Raises:
            RuntimeError: Si hay problemas en la configuración
        """
        try:
            self.logger.info("Validando configuración de detectores...")

            errors = []

            if self.detector is None:
                errors.append("Detector YOLO no configurado")

            if self.config.enable_tracking and self.tracker is None:
                self.logger.warning("Tracking habilitado pero tracker no configurado")

            if self.config.enable_team_classification and self.team_classifier is None:
                self.logger.warning("Clasificación de equipos habilitada pero clasificador no configurado")

            if self.config.enable_analysis and self.analyzer is None:
                self.logger.warning("Análisis habilitado pero analizador no configurado")

            if errors:
                for error in errors:
                    self.logger.error(error)
                return False

            self.logger.info("Detectores validados correctamente")
            return True

        except Exception as e:
            self.logger.error(f"Error validando detectores: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise RuntimeError(f"Fallo en validación de detectores: {str(e)}")

    def process_video(
        self,
        video_path: str,
        output_path: Optional[str] = None
    ) -> ProcessingResult:
        """
        Procesa un video completo del pipeline.

        Ejecuta el pipeline completo en todos los frames del video:
        1. Abre el video
        2. Lee frames (con skip si es necesario)
        3. Procesa cada frame con FrameProcessor
        4. Recopila resultados
        5. Opcionalmente guarda resultados a JSON

        Args:
            video_path (str): Ruta al archivo de video
            output_path (Optional[str]): Ruta para guardar resultados JSON

        Returns:
            ProcessingResult: Resultado del procesamiento

        Example:
            >>> result = processor.process_video('input.mp4', output_path='output.json')
            >>> print(f"Procesados {result.processed_frames} frames")

        Raises:
            FileNotFoundError: Si el video no existe
            RuntimeError: Si hay errores durante el procesamiento
        """
        start_time = time.time()

        try:
            # Validar entrada
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                raise FileNotFoundError(f"Video no encontrado: {video_path}")

            self.logger.info(f"Iniciando procesamiento de video: {video_path}")

            # Validar detectores
            if not self.setup_detectors():
                raise RuntimeError("Falló validación de detectores")

            # Abrir video
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise RuntimeError(f"No se pudo abrir video: {video_path}")

            # Obtener propiedades del video
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            self.logger.info(
                f"Video: {frame_width}x{frame_height} @ {fps:.1f}fps, "
                f"{total_frames} frames"
            )

            # Limitar frames si está configurado
            frames_to_process = total_frames
            if self.config.max_frames:
                frames_to_process = min(frames_to_process, self.config.max_frames)

            # Inicializar resultado
            result = ProcessingResult(
                video_path=str(video_path),
                total_frames=total_frames,
                processed_frames=0,
                skipped_frames=0,
                timestamp=datetime.now().isoformat()
            )

            # Procesar frames con barra de progreso
            frame_num = 0
            processed_count = 0

            with tqdm(
                total=frames_to_process,
                desc="Procesando video",
                unit="frames",
                leave=True
            ) as pbar:
                while cap.isOpened() and processed_count < frames_to_process:
                    ret, frame = cap.read()

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

                        # Procesar frame
                        frame_data = self.frame_processor.process_frame(
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

            # Cerrar video
            cap.release()

            # Calcular estadísticas finales
            total_time = time.time() - start_time
            result.total_time_seconds = total_time
            if result.processed_frames > 0:
                result.fps_processed = result.processed_frames / total_time

            result.processing_stats = self._compile_stats()

            self.logger.info(
                f"Procesamiento completado: {result.processed_frames} frames "
                f"en {total_time:.2f}s ({result.fps_processed:.1f} fps)"
            )

            # Guardar resultados si está configurado
            if output_path:
                output_path_obj = Path(output_path)
                result.save_json(output_path_obj)
                self.logger.info(f"Resultados guardados en: {output_path}")

            return result

        except Exception as e:
            self.logger.error(f"Error crítico procesando video: {str(e)}")
            self.logger.debug(traceback.format_exc())
            raise

    def process(self, video_path: str) -> ProcessingResult:
        """
        Alias para process_video().

        Args:
            video_path (str): Ruta al video

        Returns:
            ProcessingResult: Resultado del procesamiento
        """
        return self.process_video(video_path)

    def _compile_stats(self) -> Dict[str, Any]:
        """
        Compila estadísticas del procesamiento.

        Returns:
            Dict[str, Any]: Estadísticas compiladas
        """
        stats = self.stats.copy()

        # Agregar estadísticas del frame processor
        fp_stats = self.frame_processor.get_stats()
        stats['frame_processor'] = fp_stats

        # Calcular ratios
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

    def get_results(self) -> Dict[str, Any]:
        """
        Retorna los resultados del procesamiento.

        Returns:
            Dict[str, Any]: Diccionario con estadísticas y configuración

        Example:
            >>> results = processor.get_results()
            >>> print(results['stats']['processed_frames'])
        """
        return {
            'stats': self._compile_stats(),
            'config': asdict(self.config),
            'timestamp': datetime.now().isoformat()
        }

    def reset(self):
        """Reinicia el estado del procesador"""
        self.stats = {
            'total_frames': 0,
            'processed_frames': 0,
            'skipped_frames': 0,
            'detection_errors': 0,
            'total_detections': 0,
            'valid_detections': 0,
        }
        self.frame_processor.reset_stats()
        self.logger.info("Procesador reiniciado")

    @staticmethod
    def create_default(
        detector_path: Optional[str] = None,
        tracker=None,
        team_classifier=None,
        analyzer=None,
        **kwargs
    ) -> 'VideoProcessor':
        """
        Crea un VideoProcessor con configuración por defecto.

        Args:
            detector_path (Optional[str]): Ruta al modelo YOLO
            tracker: Tracker (opcional)
            team_classifier: Clasificador de equipos (opcional)
            analyzer: Analizador (opcional)
            **kwargs: Argumentos adicionales para ProcessingConfig

        Returns:
            VideoProcessor: Instancia configurada

        Example:
            >>> processor = VideoProcessor.create_default(
            ...     detector_path='models/yolo.pt'
            ... )
        """
        from ultralytics import YOLO

        config = ProcessingConfig(**kwargs)

        detector = None
        if detector_path and Path(detector_path).exists():
            detector = YOLO(detector_path)

        return VideoProcessor(
            detector=detector,
            tracker=tracker,
            team_classifier=team_classifier,
            analyzer=analyzer,
            config=config
        )

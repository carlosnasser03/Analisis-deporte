"""
frame_processor.py - Procesador de frames individuales del pipeline Scout AI

Este módulo proporciona la funcionalidad para procesar un frame individual del
video, ejecutando detección de objetos, validación, tracking y extracción de
características. Es el componente de bajo nivel que procesa frame por frame.

Classes:
    FrameProcessor: Orquestador de procesamiento de un frame individual

Author: Scout AI Pipeline
Date: 2026-07-06
"""

import numpy as np
import cv2
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import traceback
from datetime import datetime


class DetectionQuality(Enum):
    """Enumeración de calidad de detecciones"""
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    INVALID = 0


@dataclass
class Detection:
    """Estructura para una detección individual de objeto"""
    class_id: int
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    center: Tuple[float, float]
    area: float
    quality_score: float = 0.0
    track_id: Optional[int] = None
    features: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convertir a diccionario"""
        d = asdict(self)
        d['class_name'] = str(self.class_name)
        return d


@dataclass
class FrameData:
    """Estructura para datos procesados de un frame"""
    frame_number: int
    timestamp: float
    frame_shape: Tuple[int, int, int]
    detections: List[Detection] = field(default_factory=list)
    detections_raw_count: int = 0
    detections_valid_count: int = 0
    tracking_data: Dict[str, Any] = field(default_factory=dict)
    team_assignments: Dict[int, str] = field(default_factory=dict)
    analysis_results: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convertir a diccionario con detecciones convertidas"""
        d = asdict(self)
        d['detections'] = [det.to_dict() for det in self.detections]
        d['timestamp_iso'] = datetime.fromtimestamp(self.timestamp).isoformat()
        return d


class FrameProcessor:
    """
    Procesador de frames individuales del pipeline Scout AI.

    Este procesador maneja la detección, validación, tracking y extracción
    de características para un único frame. Orquesta la llamada a detectores,
    validadores y extractores de características.

    Attributes:
        frame_number (int): Número de frame actual
        logger (logging.Logger): Logger para registro de eventos
        min_confidence (float): Confianza mínima para detecciones
        min_detection_size (int): Tamaño mínimo en píxeles para detecciones
        max_detection_size (int): Tamaño máximo en píxeles para detecciones

    Example:
        >>> processor = FrameProcessor(
        ...     detector=detector,
        ...     tracker=tracker,
        ...     team_classifier=team_classifier,
        ...     analyzer=analyzer
        ... )
        >>> frame_data = processor.process_frame(frame, frame_num=0)
    """

    # Configuración de validación
    MIN_CONFIDENCE = 0.3
    MIN_DETECTION_SIZE = 10  # píxeles
    MAX_DETECTION_SIZE = 2000  # píxeles

    # Clases de objetos esperadas
    VALID_CLASSES = {
        0: 'player',
        1: 'ball',
        2: 'referee',
        3: 'pitch'
    }

    def __init__(
        self,
        detector=None,
        tracker=None,
        team_classifier=None,
        analyzer=None,
        min_confidence: float = MIN_CONFIDENCE,
        logger: Optional[logging.Logger] = None
    ):
        """
        Inicializa el procesador de frames.

        Args:
            detector: Instancia de detector YOLO (BallDetector, PlayerDetector, etc.)
            tracker: Instancia de tracker para seguimiento de objetos
            team_classifier: Instancia de clasificador de equipos
            analyzer: Instancia de analizador de características
            min_confidence (float): Confianza mínima para detecciones
            logger (Optional[logging.Logger]): Logger personalizado

        Raises:
            ValueError: Si los detectores son inválidos
        """
        self.detector = detector
        self.tracker = tracker
        self.team_classifier = team_classifier
        self.analyzer = analyzer

        self.min_confidence = min_confidence

        # Configurar logger
        self.logger = logger or self._setup_logger()

        # Estadísticas de procesamiento
        self.stats = {
            'frames_processed': 0,
            'total_detections': 0,
            'valid_detections': 0,
            'total_processing_time': 0.0,
            'errors_count': 0,
        }

    def _setup_logger(self) -> logging.Logger:
        """Configura el logger para el procesador de frames"""
        logger = logging.getLogger('FrameProcessor')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def process_frame(
        self,
        frame: np.ndarray,
        frame_number: int,
        timestamp: float = 0.0
    ) -> FrameData:
        """
        Procesa un frame completo del pipeline.

        Ejecuta: detección -> validación -> tracking -> extracción de características.

        Args:
            frame (np.ndarray): Frame de video (H, W, 3) en formato BGR
            frame_number (int): Número de secuencia del frame
            timestamp (float): Timestamp en segundos del frame

        Returns:
            FrameData: Datos procesados del frame con detecciones y análisis

        Example:
            >>> frame_data = processor.process_frame(frame, frame_num=0, timestamp=0.0)
            >>> print(f"Detecciones válidas: {frame_data.detections_valid_count}")
        """
        import time
        start_time = time.time()

        try:
            # Validar entrada
            if not isinstance(frame, np.ndarray):
                raise ValueError("Frame debe ser un numpy array")
            if frame.size == 0:
                raise ValueError("Frame vacío")
            if len(frame.shape) != 3:
                raise ValueError(f"Frame debe ser (H,W,3), recibido {frame.shape}")

            # Inicializar estructura de datos
            frame_data = FrameData(
                frame_number=frame_number,
                timestamp=timestamp,
                frame_shape=frame.shape
            )

            self.logger.debug(f"Procesando frame {frame_number} ({frame.shape})")

            # Paso 1: Detectar objetos
            detections = self.detect_objects(frame)
            frame_data.detections_raw_count = len(detections)

            # Paso 2: Validar detecciones
            if detections:
                valid_detections = self.validate_detections(detections, frame.shape)
                frame_data.detections_valid_count = len(valid_detections)

                # Paso 3: Rastrear objetos
                if self.tracker:
                    tracked_detections = self.track_objects(valid_detections)
                else:
                    tracked_detections = valid_detections

                # Paso 4: Extraer características
                if self.analyzer:
                    frame_data.detections = self.extract_features(
                        tracked_detections,
                        frame
                    )
                else:
                    frame_data.detections = tracked_detections

                # Paso 5: Clasificar equipos si es disponible
                if self.team_classifier:
                    frame_data.team_assignments = self._assign_teams(
                        frame_data.detections
                    )

            else:
                self.logger.warning(f"Frame {frame_number}: Sin detecciones")
                frame_data.warnings.append(f"Sin detecciones en frame {frame_number}")

            # Calcular tiempo de procesamiento
            processing_time = (time.time() - start_time) * 1000  # ms
            frame_data.processing_time_ms = processing_time

            # Actualizar estadísticas
            self.stats['frames_processed'] += 1
            self.stats['total_detections'] += frame_data.detections_raw_count
            self.stats['valid_detections'] += frame_data.detections_valid_count
            self.stats['total_processing_time'] += processing_time

            self.logger.debug(
                f"Frame {frame_number} procesado: "
                f"{frame_data.detections_raw_count} brutos, "
                f"{frame_data.detections_valid_count} válidos "
                f"({processing_time:.2f}ms)"
            )

            return frame_data

        except Exception as e:
            self.logger.error(f"Error procesando frame {frame_number}: {str(e)}")
            self.logger.debug(traceback.format_exc())
            self.stats['errors_count'] += 1

            # Retornar frame_data con error
            frame_data = FrameData(
                frame_number=frame_number,
                timestamp=timestamp,
                frame_shape=frame.shape if isinstance(frame, np.ndarray) else (0, 0, 0),
                errors=[str(e)]
            )
            return frame_data

    def detect_objects(self, frame: np.ndarray) -> List[Detection]:
        """
        Ejecuta la detección de objetos YOLO en el frame.

        Utiliza el detector configurado para identificar jugadores, balón, etc.

        Args:
            frame (np.ndarray): Frame en formato BGR

        Returns:
            List[Detection]: Lista de detecciones sin validar

        Raises:
            RuntimeError: Si el detector no está configurado
        """
        try:
            if not self.detector:
                self.logger.warning("Detector no configurado, retornando lista vacía")
                return []

            detections_raw = self.detector.detect(frame, self.min_confidence)

            # Convertir a formato Detection
            detections = []
            if detections_raw:
                for det in detections_raw:
                    if isinstance(det, dict):
                        bbox = det.get('bbox', [0, 0, 0, 0])
                        center = (
                            (bbox[0] + bbox[2]) / 2,
                            (bbox[1] + bbox[3]) / 2
                        )
                        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

                        detection = Detection(
                            class_id=det.get('class_id', -1),
                            class_name=det.get('class_name', 'unknown'),
                            confidence=det.get('confidence', 0.0),
                            bbox=bbox,
                            center=center,
                            area=area,
                            quality_score=det.get('confidence', 0.0)
                        )
                        detections.append(detection)
                    else:
                        detections.append(det)

            self.logger.debug(f"Detectadas {len(detections)} objetos")
            return detections

        except Exception as e:
            self.logger.error(f"Error en detect_objects: {str(e)}")
            raise

    def validate_detections(
        self,
        detections: List[Detection],
        frame_shape: Tuple[int, int, int]
    ) -> List[Detection]:
        """
        Valida la calidad de las detecciones basada en múltiples criterios.

        Criterios de validación:
        - Confianza mínima
        - Tamaño mínimo y máximo
        - Debe estar dentro de los límites del frame
        - Clase válida

        Args:
            detections (List[Detection]): Lista de detecciones a validar
            frame_shape (Tuple[int, int, int]): Forma del frame (H, W, C)

        Returns:
            List[Detection]: Detecciones validadas

        Example:
            >>> valid_dets = processor.validate_detections(detections, (720, 1280, 3))
        """
        valid_detections = []
        height, width = frame_shape[:2]

        for det in detections:
            errors = []

            # Validar confianza
            if det.confidence < self.min_confidence:
                errors.append(f"Confianza baja: {det.confidence:.2f}")

            # Validar tamaño
            if det.area < self.MIN_DETECTION_SIZE ** 2:
                errors.append(f"Área muy pequeña: {det.area:.0f}")
            if det.area > self.MAX_DETECTION_SIZE ** 2:
                errors.append(f"Área muy grande: {det.area:.0f}")

            # Validar límites
            bbox = det.bbox
            if (bbox[0] < 0 or bbox[1] < 0 or
                bbox[2] > width or bbox[3] > height):
                errors.append("Fuera de límites del frame")

            # Validar clase
            if det.class_id not in self.VALID_CLASSES:
                errors.append(f"Clase inválida: {det.class_id}")

            # Si pasó todas las validaciones
            if not errors:
                det.quality_score = self._calculate_quality_score(det)
                valid_detections.append(det)
            else:
                self.logger.debug(
                    f"Detección rechazada ({det.class_name}): {'; '.join(errors)}"
                )

        return valid_detections

    def _calculate_quality_score(self, detection: Detection) -> float:
        """
        Calcula un score de calidad para la detección (0-1).

        Basado en: confianza, tamaño y posición en el frame.

        Args:
            detection (Detection): Detección a evaluar

        Returns:
            float: Score de calidad (0-1)
        """
        # Base: confianza
        score = detection.confidence

        # Bonus/penalización por tamaño
        size_ratio = detection.area / (self.MIN_DETECTION_SIZE ** 2)
        size_ratio = min(size_ratio, 10)  # Cap en 10
        size_factor = min(1.0, size_ratio / 10)
        score = score * (0.7 + 0.3 * size_factor)

        return min(score, 1.0)

    def track_objects(self, detections: List[Detection]) -> List[Detection]:
        """
        Realiza tracking de objetos para mantener IDs consistentes.

        Utiliza el tracker configurado para asignar IDs consistentes a
        objetos detectados en frames consecutivos.

        Args:
            detections (List[Detection]): Detecciones a rastrear

        Returns:
            List[Detection]: Detecciones con track_id asignados

        Example:
            >>> tracked = processor.track_objects(detections)
        """
        try:
            if not self.tracker or not detections:
                return detections

            # Preparar formato para tracker (típicamente requiere [x, y, w, h, conf])
            detections_formatted = []
            for det in detections:
                x1, y1, x2, y2 = det.bbox
                detections_formatted.append({
                    'bbox': [x1, y1, x2, y2],
                    'confidence': det.confidence,
                    'class_id': det.class_id,
                    'center': det.center
                })

            # Ejecutar tracker
            tracked_results = self.tracker.update(detections_formatted)

            # Asignar track_ids
            for i, det in enumerate(detections):
                if i < len(tracked_results):
                    track_id = tracked_results[i].get('track_id', None)
                    det.track_id = track_id

            self.logger.debug(f"Rastreados {len(detections)} objetos")
            return detections

        except Exception as e:
            self.logger.error(f"Error en tracking: {str(e)}")
            # Retornar sin modificar si hay error
            return detections

    def extract_features(
        self,
        detections: List[Detection],
        frame: np.ndarray
    ) -> List[Detection]:
        """
        Extrae características visuales de cada detección.

        Utiliza el analyzer para extraer features como: histogramas,
        características de movimiento, posición relativa, etc.

        Args:
            detections (List[Detection]): Detecciones a analizar
            frame (np.ndarray): Frame completo en BGR

        Returns:
            List[Detection]: Detecciones con características extraídas

        Example:
            >>> detections_with_features = processor.extract_features(detections, frame)
        """
        try:
            if not self.analyzer or not detections:
                return detections

            for det in detections:
                x1, y1, x2, y2 = [int(v) for v in det.bbox]

                # Asegurar límites válidos
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(frame.shape[1], x2)
                y2 = min(frame.shape[0], y2)

                if x2 > x1 and y2 > y1:
                    # Extraer región de interés (ROI)
                    roi = frame[y1:y2, x1:x2]

                    # Extraer características
                    features = {}

                    # Color promedio
                    if roi.size > 0:
                        features['color_mean'] = roi.mean(axis=(0, 1)).tolist()

                        # Histograma HSV
                        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                        features['hsv_hist'] = {
                            'h': float(hsv_roi[:, :, 0].mean()),
                            's': float(hsv_roi[:, :, 1].mean()),
                            'v': float(hsv_roi[:, :, 2].mean())
                        }

                    det.features = features

            self.logger.debug(f"Características extraídas de {len(detections)} objetos")
            return detections

        except Exception as e:
            self.logger.error(f"Error extrayendo características: {str(e)}")
            # Retornar sin características si hay error
            return detections

    def _assign_teams(self, detections: List[Detection]) -> Dict[int, str]:
        """
        Asigna equipos a los jugadores detectados.

        Args:
            detections (List[Detection]): Detecciones con información de jugadores

        Returns:
            Dict[int, str]: Mapeo de track_id a equipo

        Example:
            >>> teams = processor._assign_teams(detections)
            >>> print(teams)  # {0: 'team_1', 1: 'team_2', ...}
        """
        team_assignments = {}

        try:
            if not self.team_classifier:
                return team_assignments

            for det in detections:
                if det.class_name == 'player' and det.track_id is not None:
                    # Obtener color promedio del jugador
                    color_mean = det.features.get('color_mean', None)
                    if color_mean:
                        team = self.team_classifier.classify(color_mean)
                        team_assignments[det.track_id] = team

        except Exception as e:
            self.logger.warning(f"Error asignando equipos: {str(e)}")

        return team_assignments

    def get_stats(self) -> Dict[str, Any]:
        """
        Retorna estadísticas de procesamiento.

        Returns:
            Dict[str, Any]: Diccionario con estadísticas acumuladas
        """
        stats = self.stats.copy()
        if stats['frames_processed'] > 0:
            stats['avg_processing_time_ms'] = (
                stats['total_processing_time'] / stats['frames_processed']
            )
        return stats

    def reset_stats(self):
        """Reinicia las estadísticas de procesamiento"""
        self.stats = {
            'frames_processed': 0,
            'total_detections': 0,
            'valid_detections': 0,
            'total_processing_time': 0.0,
            'errors_count': 0,
        }

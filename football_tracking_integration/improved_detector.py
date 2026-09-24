"""
improved_detector.py - Detector de Football-Tracking mejorado con Supervision

Integra YOLO con sv.Detections para máxima compatibilidad y validación.
"""

from typing import Dict, Tuple, Optional
import numpy as np
import supervision as sv
from ultralytics import YOLO
import logging

logger = logging.getLogger(__name__)


class ImprovedFootballDetector:
    """
    Detector mejorado que:
    - Usa sv.Detections internamente
    - Valida automáticamente
    - Devuelve formatos compatibles
    - Registra estadísticas
    """

    def __init__(
        self,
        model_path: str = "yolov8x",  # O tu modelo entrenado
        device: str = "cpu",
        conf_threshold: float = 0.3,
    ):
        """
        Args:
            model_path: Ruta al modelo YOLO
            device: 'cpu', 'cuda', etc.
            conf_threshold: Confianza mínima
        """
        self.model = YOLO(model_path)
        self.device = device
        self.conf_threshold = conf_threshold
        self.class_names = {
            0: 'player',
            1: 'referee',
            2: 'ball',
        }

        self.stats = {
            'frames_processed': 0,
            'avg_detections': [],
            'avg_confidence': [],
        }

    def detect(self, frame: np.ndarray) -> sv.Detections:
        """
        Detecta objetos en el frame y devuelve sv.Detections.

        Args:
            frame: Imagen BGR

        Returns:
            sv.Detections con jugadores, árbitros y balón
        """
        results = self.model(frame, verbose=False, conf=self.conf_threshold)

        if not results or len(results[0].boxes) == 0:
            return sv.Detections.empty()

        # Extraer datos
        xyxy = results[0].boxes.xyxy.cpu().numpy()
        confidence = results[0].boxes.conf.cpu().numpy()
        class_id = results[0].boxes.cls.cpu().numpy()

        # Crear sv.Detections
        detections = sv.Detections(
            xyxy=xyxy.astype(float),
            confidence=confidence.astype(float),
            class_id=class_id.astype(int)
        )

        # Estadísticas
        self.stats['frames_processed'] += 1
        self.stats['avg_detections'].append(len(detections))
        self.stats['avg_confidence'].append(float(np.mean(confidence)))

        logger.debug(
            f"Frame {self.stats['frames_processed']}: "
            f"{len(detections)} detecciones (conf avg: {np.mean(confidence):.2f})"
        )

        return detections

    def get_players_only(self, detections: sv.Detections) -> sv.Detections:
        """Filtrar solo jugadores"""
        return detections[detections.class_id == 0]

    def get_ball_only(self, detections: sv.Detections) -> sv.Detections:
        """Filtrar solo balón"""
        return detections[detections.class_id == 2]

    def get_referees_only(self, detections: sv.Detections) -> sv.Detections:
        """Filtrar solo árbitros"""
        return detections[detections.class_id == 1]

    def get_statistics(self) -> Dict:
        """Retorna estadísticas acumuladas"""
        return {
            'frames_processed': self.stats['frames_processed'],
            'avg_detections_per_frame': (
                np.mean(self.stats['avg_detections'])
                if self.stats['avg_detections'] else 0
            ),
            'avg_confidence': (
                np.mean(self.stats['avg_confidence'])
                if self.stats['avg_confidence'] else 0
            ),
        }


class MultiStageDetector:
    """
    Detector en múltiples etapas:
    1. Detección baja confianza (para jugadores parcialmente ocultos)
    2. Filtrado por tamaño (evitar ruido)
    3. Validación temporal (coherencia entre frames)
    """

    def __init__(self, model_path: str = "yolov8x", device: str = "cpu"):
        self.detector = ImprovedFootballDetector(model_path, device)
        self.high_conf_threshold = 0.6
        self.low_conf_threshold = 0.3
        self.min_box_area = 100  # píxeles²
        self.max_box_area = 100000
        self.temporal_buffer = []
        self.buffer_size = 5

    def detect(self, frame: np.ndarray) -> Tuple[sv.Detections, Dict]:
        """
        Detección multi-etapa con diagnósticos.

        Returns:
            (detections, diagnostics_dict)
        """
        all_detections = self.detector.detect(frame)
        diagnostics = {'raw_detections': len(all_detections)}

        # Etapa 1: Filtrar por confianza
        high_conf = all_detections[all_detections.confidence >= self.high_conf_threshold]
        low_conf = all_detections[
            (all_detections.confidence >= self.low_conf_threshold) &
            (all_detections.confidence < self.high_conf_threshold)
        ]
        diagnostics['high_conf'] = len(high_conf)
        diagnostics['low_conf'] = len(low_conf)

        # Etapa 2: Filtrar por tamaño
        xyxy = all_detections.xyxy
        areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
        size_mask = (areas >= self.min_box_area) & (areas <= self.max_box_area)
        valid_detections = all_detections[size_mask]

        diagnostics['after_size_filter'] = len(valid_detections)

        # Etapa 3: Validación temporal (si hay histórico)
        if len(self.temporal_buffer) > 0:
            valid_detections = self._temporal_validation(valid_detections)

        self.temporal_buffer.append(valid_detections)
        if len(self.temporal_buffer) > self.buffer_size:
            self.temporal_buffer.pop(0)

        diagnostics['after_temporal'] = len(valid_detections)

        return valid_detections, diagnostics

    def _temporal_validation(self, detections: sv.Detections) -> sv.Detections:
        """Valida coherencia con frame anterior"""
        if len(self.temporal_buffer) == 0:
            return detections

        prev_detections = self.temporal_buffer[-1]

        # Detecciones en this frame que tienen correspondencia en frame anterior
        if len(prev_detections) == 0:
            return detections

        # Calcular IoU con detecciones anteriores
        iou_matrix = sv.box_iou_batch(prev_detections.xyxy, detections.xyxy)

        # Mantener detecciones con IoU > 0.3 con algo en frame anterior
        valid_indices = np.max(iou_matrix, axis=0) > 0.3

        return detections[valid_indices]


__all__ = [
    'ImprovedFootballDetector',
    'MultiStageDetector',
]

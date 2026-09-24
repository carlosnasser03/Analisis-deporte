"""
feature_extractor.py - Extracción de características visuales

Extrae características de apariencia de los jugadores:
- Histograma de color RGB
- HOG (Histogram of Oriented Gradients)

Usado para mejor matching entre tracks y detecciones.
"""

import numpy as np
from typing import Tuple, Optional
import cv2
import logging

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Extractor de características visuales (sin CNN).

    Combina:
    - Color histogram (40D)
    - HOG features (324D)
    = 364D total

    Computation: ~1ms per image en CPU
    """

    def __init__(self,
                 color_bins: int = 16,
                 hog_cells_per_block: Tuple[int, int] = (8, 8)):
        """
        Args:
            color_bins: Bins por canal RGB (total: 3 * color_bins)
            hog_cells_per_block: Tamaño de celda para HOG
        """
        self.color_bins = color_bins
        self.hog_cells_per_block = hog_cells_per_block
        self.feature_dim = 3 * color_bins + 324  # 40 + 324

    def extract_color_histogram(self,
                               bbox: np.ndarray,
                               frame: np.ndarray) -> np.ndarray:
        """
        Extrae histograma de color del bbox.

        Args:
            bbox: [x1, y1, x2, y2]
            frame: Imagen BGR

        Returns:
            Feature vector (40D): Histograma normalizado RGB
        """
        x1, y1, x2, y2 = bbox.astype(int)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)

        if x2 <= x1 or y2 <= y1:
            return np.zeros(3 * self.color_bins, dtype=np.float32)

        roi = frame[y1:y2, x1:x2]
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)

        # Calcular histograma para cada canal
        hist = []
        for i in range(3):
            h = cv2.calcHist([roi_rgb], [i], None, [self.color_bins], [0, 256])
            h = h.flatten()
            h = h / (h.sum() + 1e-6)  # Normalizar
            hist.append(h)

        feature = np.concatenate(hist).astype(np.float32)
        return feature

    def extract_hog_features(self,
                            bbox: np.ndarray,
                            frame: np.ndarray) -> np.ndarray:
        """
        Extrae HOG features del bbox.

        Args:
            bbox: [x1, y1, x2, y2]
            frame: Imagen BGR

        Returns:
            Feature vector (324D): HOG descriptor
        """
        x1, y1, x2, y2 = bbox.astype(int)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)

        if x2 <= x1 or y2 <= y1:
            return np.zeros(324, dtype=np.float32)

        roi = frame[y1:y2, x1:x2]

        # Redimensionar a tamaño estándar (64x128 típico)
        roi_resized = cv2.resize(roi, (64, 128))

        # Convertir a escala de grises
        roi_gray = cv2.cvtColor(roi_resized, cv2.COLOR_BGR2GRAY)

        # Calcular HOG
        hog = cv2.HOGDescriptor()
        features = hog.compute(roi_gray)

        if features is None:
            return np.zeros(324, dtype=np.float32)

        features = features.flatten().astype(np.float32)

        # Normalizar
        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm

        return features

    def extract(self,
               bbox: np.ndarray,
               frame: np.ndarray,
               use_color: bool = True,
               use_hog: bool = True) -> np.ndarray:
        """
        Extrae características combinadas.

        Args:
            bbox: [x1, y1, x2, y2]
            frame: Imagen BGR
            use_color: Incluir histograma color
            use_hog: Incluir HOG

        Returns:
            Feature vector (364D por defecto)
        """
        features = []

        if use_color:
            color_feat = self.extract_color_histogram(bbox, frame)
            features.append(color_feat)

        if use_hog:
            hog_feat = self.extract_hog_features(bbox, frame)
            features.append(hog_feat)

        if not features:
            return np.zeros(self.feature_dim, dtype=np.float32)

        feature_vector = np.concatenate(features).astype(np.float32)

        # Normalizar
        norm = np.linalg.norm(feature_vector)
        if norm > 0:
            feature_vector = feature_vector / norm

        return feature_vector

    @staticmethod
    def cosine_distance(feat1: np.ndarray,
                       feat2: np.ndarray) -> float:
        """
        Calcula distancia coseno entre dos características.

        Args:
            feat1: Feature vector 1
            feat2: Feature vector 2

        Returns:
            Distancia coseno (0-2, menor = más similar)
        """
        if feat1.size == 0 or feat2.size == 0:
            return 1.0

        # Asegurar que están normalizados
        f1 = feat1 / (np.linalg.norm(feat1) + 1e-6)
        f2 = feat2 / (np.linalg.norm(feat2) + 1e-6)

        # Distancia coseno = 1 - similitud coseno
        distance = 1.0 - np.dot(f1, f2)

        return float(np.clip(distance, 0.0, 2.0))

    @staticmethod
    def euclidean_distance(feat1: np.ndarray,
                          feat2: np.ndarray) -> float:
        """
        Calcula distancia euclidea entre dos características.

        Args:
            feat1: Feature vector 1
            feat2: Feature vector 2

        Returns:
            Distancia euclidea
        """
        if feat1.size == 0 or feat2.size == 0:
            return float('inf')

        return float(np.linalg.norm(feat1 - feat2))


class FeatureBank:
    """
    Almacén de características para cada track.

    Mantiene N últimas características de cada track
    para matching más robusto.
    """

    def __init__(self, max_history: int = 30):
        """
        Args:
            max_history: Número de características a guardar por track
        """
        self.max_history = max_history
        self.features = {}  # {track_id: [features...]}

    def add(self, track_id: int, feature: np.ndarray):
        """Agregar feature a track"""
        if track_id not in self.features:
            self.features[track_id] = []

        self.features[track_id].append(feature)

        # Limitar histórico
        if len(self.features[track_id]) > self.max_history:
            self.features[track_id].pop(0)

    def get_mean_feature(self, track_id: int) -> Optional[np.ndarray]:
        """Obtener feature promedio de un track"""
        if track_id not in self.features:
            return None

        features = np.array(self.features[track_id])
        return np.mean(features, axis=0)

    def remove(self, track_id: int):
        """Remover track del banco"""
        if track_id in self.features:
            del self.features[track_id]

    def get_distance_to_track(self, track_id: int,
                             feature: np.ndarray) -> float:
        """Obtener distancia a feature promedio de track"""
        mean_feature = self.get_mean_feature(track_id)
        if mean_feature is None:
            return 1.0

        return FeatureExtractor.cosine_distance(feature, mean_feature)


__all__ = [
    'FeatureExtractor',
    'FeatureBank',
]

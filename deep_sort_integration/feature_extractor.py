"""
feature_extractor.py - Extraccion de características visuales (versión simplificada)

Extrae características de apariencia de los jugadores:
- Histograma de color RGB
- Características de gradiente simple

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
    - Color histogram (48D)
    - Gradient features (200D)
    = 248D total

    Computation: ~1ms per image en CPU
    """

    def __init__(self, color_bins: int = 16):
        """
        Args:
            color_bins: Bins por canal RGB
        """
        self.color_bins = color_bins
        self.feature_dim = 3 * color_bins + 200  # 48 + 200

    def extract_color_histogram(self,
                               bbox: np.ndarray,
                               frame: np.ndarray) -> np.ndarray:
        """
        Extrae histograma de color del bbox.

        Args:
            bbox: [x1, y1, x2, y2]
            frame: Imagen BGR

        Returns:
            Feature vector (48D): Histograma normalizado RGB
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

    def extract_gradient_features(self,
                                 bbox: np.ndarray,
                                 frame: np.ndarray) -> np.ndarray:
        """
        Extrae características de gradiente (alternativa simple a HOG).

        Args:
            bbox: [x1, y1, x2, y2]
            frame: Imagen BGR

        Returns:
            Feature vector (200D): Características de gradiente
        """
        x1, y1, x2, y2 = bbox.astype(int)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)

        if x2 <= x1 or y2 <= y1:
            return np.zeros(200, dtype=np.float32)

        roi = frame[y1:y2, x1:x2]

        # Redimensionar a tamaño estándar
        roi_resized = cv2.resize(roi, (32, 64))

        # Convertir a escala de grises
        roi_gray = cv2.cvtColor(roi_resized, cv2.COLOR_BGR2GRAY)

        # Calcular gradientes
        gx = cv2.Sobel(roi_gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(roi_gray, cv2.CV_32F, 0, 1, ksize=3)

        # Magnitud y ángulo
        magnitude, angle = cv2.cartToPolar(gx, gy)

        # Características: histogramas de magnitud en diferentes direcciones
        hist_mag = cv2.calcHist([magnitude], [0], None, [8], [0, magnitude.max()+1])
        hist_angle = cv2.calcHist([angle], [0], None, [8], [0, 360])

        features = np.concatenate([
            hist_mag.flatten(),
            hist_angle.flatten(),
            magnitude.flatten()[:128],  # Muestra de magnitud
        ]).astype(np.float32)

        # Pad a 200
        if features.shape[0] < 200:
            features = np.pad(features, (0, 200 - features.shape[0]), mode='constant')
        else:
            features = features[:200]

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
            use_hog: Incluir características gradiente

        Returns:
            Feature vector (248D por defecto)
        """
        features = []

        if use_color:
            color_feat = self.extract_color_histogram(bbox, frame)
            features.append(color_feat)

        if use_hog:
            grad_feat = self.extract_gradient_features(bbox, frame)
            features.append(grad_feat)

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

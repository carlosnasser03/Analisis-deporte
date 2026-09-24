"""
deep_sort_integration - Implementación Deep SORT Ligero

Módulos:
- kalman_filter: Predicción de movimiento
- feature_extractor: Características visuales (color + HOG)
- deep_sort_tracker: Tracker completo Deep SORT
"""

from .kalman_filter import KalmanFilter, TrackState
from .feature_extractor import FeatureExtractor, FeatureBank
from .deep_sort_tracker import DeepSortTracker

__all__ = [
    'KalmanFilter',
    'TrackState',
    'FeatureExtractor',
    'FeatureBank',
    'DeepSortTracker',
]

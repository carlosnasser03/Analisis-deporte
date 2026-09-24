"""
deep_sort_tracker.py - Tracker Deep SORT Ligero

Integra:
- Kalman Filter (predicción)
- Feature Extraction (color + HOG)
- Algoritmo Húngaro (asignación)
- Track Management

Mejor precisión que ByteTrack, sin overhead de CNN.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import supervision as sv
from scipy.optimize import linear_sum_assignment
import logging

from .kalman_filter import KalmanFilter, TrackState
from .feature_extractor import FeatureExtractor, FeatureBank

logger = logging.getLogger(__name__)


class DeepSortTracker:
    """
    Tracker Deep SORT Ligero (sin CNN).

    Componentes:
    1. Kalman Filter → Predicción de movimiento
    2. Feature Extraction → Color + HOG
    3. Hungarian Algorithm → Asignación óptima
    4. Track Management → Confirmación/eliminación
    """

    def __init__(self,
                 max_age: int = 30,
                 min_hits: int = 3,
                 iou_threshold: float = 0.3,
                 feature_weight: float = 0.5,
                 motion_weight: float = 0.5,
                 use_features: bool = True):
        """
        Args:
            max_age: Frames antes de eliminar track no asociado
            min_hits: Frames para confirmar track
            iou_threshold: IoU mínimo para gating inicial
            feature_weight: Peso de features en cost matrix
            motion_weight: Peso de movimiento en cost matrix
            use_features: Usar features (color+HOG)
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.feature_weight = feature_weight
        self.motion_weight = motion_weight
        self.use_features = use_features

        # Componentes
        self.kf = KalmanFilter()
        self.feature_extractor = FeatureExtractor() if use_features else None
        self.feature_bank = FeatureBank() if use_features else None

        # Tracks
        self.tracks: Dict[int, TrackState] = {}
        self.next_id = 1
        self.frame_count = 0

    def predict(self):
        """Predecir posición de todos los tracks"""
        for track_id, track in self.tracks.items():
            track.mean, track.covariance = self.kf.predict(
                track.mean, track.covariance
            )
            track.time_since_update += 1
            track.age += 1

    def update(self,
               detections: sv.Detections,
               frame: np.ndarray) -> Dict:
        """
        Actualizar tracks con nuevas detecciones.

        Args:
            detections: sv.Detections con jugadores
            frame: Frame para extracción de features

        Returns:
            {
                'tracks': List[Dict] con ID y bbox,
                'matched': int,
                'unmatched_det': int,
                'unmatched_track': int,
            }
        """
        self.frame_count += 1

        # 1. Predecir
        self.predict()

        # 2. Extraer características de detecciones
        det_features = []
        if self.use_features:
            for bbox in detections.xyxy:
                feat = self.feature_extractor.extract(bbox, frame)
                det_features.append(feat)

        # 3. Crear cost matrix
        cost_matrix = self._compute_cost_matrix(
            detections, det_features
        )

        # 4. Algoritmo Húngaro
        matched, unmatched_tracks, unmatched_dets = self._match_detections(
            cost_matrix
        )

        # 5. Actualizar tracks
        matched_count = 0
        for t_idx, d_idx in matched:
            track_id = list(self.tracks.keys())[t_idx]
            track = self.tracks[track_id]

            # Actualizar Kalman
            track.mean, track.covariance = self.kf.update(
                track.mean,
                track.covariance,
                detections.xyxy[d_idx]
            )

            # Actualizar features
            if self.use_features:
                self.feature_bank.add(track_id, det_features[d_idx])

            # Actualizar track state
            track.hits += 1
            track.time_since_update = 0

            # Confirmar si alcanza min_hits
            if track.hits >= self.min_hits:
                track.is_tentative = False
                track.is_confirmed = True

            matched_count += 1

        # 6. Crear nuevos tracks
        new_tracks = 0
        for d_idx in unmatched_dets:
            mean, covariance = self.kf.initiate(detections.xyxy[d_idx])

            track = TrackState(mean, covariance, self.next_id)
            self.tracks[self.next_id] = track

            # Agregar feature
            if self.use_features:
                self.feature_bank.add(self.next_id, det_features[d_idx])

            self.next_id += 1
            new_tracks += 1

        # 7. Envejecer y eliminar tracks
        self._age_and_prune(unmatched_tracks)

        # 8. Retornar tracks confirmados
        confirmed_tracks = []
        for track_id, track in self.tracks.items():
            if track.is_confirmed:
                x1, y1, w, h = track.mean[:4]
                confirmed_tracks.append({
                    'track_id': track_id,
                    'bbox': [x1, y1, x1 + w, y1 + h],
                    'confidence': track.hits / max(track.age, 1.0),
                })

        return {
            'tracks': confirmed_tracks,
            'matched': matched_count,
            'new_tracks': new_tracks,
            'active_tracks': len([t for t in self.tracks.values() if t.is_confirmed]),
        }

    def _compute_cost_matrix(self,
                            detections: sv.Detections,
                            features: Optional[List[np.ndarray]] = None) -> np.ndarray:
        """
        Computa matriz de costos entre tracks y detecciones.

        Combina:
        - Distancia de Mahalanobis (movimiento)
        - Distancia coseno (features)
        """
        n_tracks = len(self.tracks)
        n_dets = len(detections)

        if n_tracks == 0 or n_dets == 0:
            return np.full((n_tracks, n_dets), 1.0)

        cost_matrix = np.zeros((n_tracks, n_dets))

        track_ids = list(self.tracks.keys())

        for t_idx, track_id in enumerate(track_ids):
            track = self.tracks[track_id]

            for d_idx, bbox in enumerate(detections.xyxy):
                # Cost de Mahalanobis (movimiento)
                gate_dist = self.kf.gating_distance(
                    track.mean, track.covariance, bbox
                )

                # Normalizar
                motion_cost = 1.0 - np.exp(-gate_dist / 10.0)
                motion_cost = np.clip(motion_cost, 0.0, 1.0)

                # Cost de features
                feature_cost = 0.0
                if self.use_features and features is not None:
                    feature_cost = self.feature_bank.get_distance_to_track(
                        track_id, features[d_idx]
                    )

                # Combinar costos
                total_cost = (
                    self.motion_weight * motion_cost +
                    self.feature_weight * feature_cost
                )

                cost_matrix[t_idx, d_idx] = total_cost

        # Penalizar costos muy altos (gating)
        cost_matrix[cost_matrix > 1.0] = 1.0

        return cost_matrix

    def _match_detections(self,
                         cost_matrix: np.ndarray) -> Tuple[List, List, List]:
        """
        Usar algoritmo Húngaro para asignación óptima.

        Returns:
            (matched_pairs, unmatched_tracks, unmatched_dets)
        """
        if cost_matrix.size == 0:
            return [], [], list(range(cost_matrix.shape[1]))

        # Algoritmo Húngaro
        track_indices, det_indices = linear_sum_assignment(cost_matrix)

        # Filtrar por umbral
        matched = []
        for t_idx, d_idx in zip(track_indices, det_indices):
            if cost_matrix[t_idx, d_idx] < 0.7:  # Umbral
                matched.append((t_idx, d_idx))

        matched_track_set = set(t for t, _ in matched)
        matched_det_set = set(d for _, d in matched)

        unmatched_tracks = [i for i in range(cost_matrix.shape[0])
                           if i not in matched_track_set]
        unmatched_dets = [i for i in range(cost_matrix.shape[1])
                         if i not in matched_det_set]

        return matched, unmatched_tracks, unmatched_dets

    def _age_and_prune(self, unmatched_track_indices: List[int]):
        """Envejecer tracks sin pareja y eliminar viejos"""
        track_ids = list(self.tracks.keys())

        for t_idx in unmatched_track_indices:
            if t_idx < len(track_ids):
                track_id = track_ids[t_idx]
                self.tracks[track_id].time_since_update += 1

        # Eliminar tracks viejos
        to_remove = [
            tid for tid, track in self.tracks.items()
            if track.time_since_update > self.max_age
        ]

        for tid in to_remove:
            del self.tracks[tid]
            if self.feature_bank:
                self.feature_bank.remove(tid)

    def get_tracks(self) -> List[Dict]:
        """Retorna todos los tracks confirmados"""
        tracks = []
        for track_id, track in self.tracks.items():
            if track.is_confirmed:
                x1, y1, w, h = track.mean[:4]
                tracks.append({
                    'track_id': track_id,
                    'bbox': [x1, y1, x1 + w, y1 + h],
                    'confidence': track.hits / max(track.age, 1.0),
                    'age': track.age,
                })
        return tracks

    def reset(self):
        """Reiniciar tracker"""
        self.tracks.clear()
        self.next_id = 1
        self.frame_count = 0
        if self.feature_bank:
            self.feature_bank.features.clear()


__all__ = ['DeepSortTracker']

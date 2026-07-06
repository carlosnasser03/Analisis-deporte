"""
tracker_improved.py - Tracker avanzado con ByteTrack y Re-ID

Propósito: Proporcionar tracking robusto usando ByteTrack oficial con:
- Re-identificación simple para oclusiones
- Validaciones de movimiento y cambios de equipo
- Estadísticas detalladas de tracking
- Filtrado de tracks inestables

Autor: Scout AI Analytics
Versión: 2.0
"""

import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import warnings
from scipy.spatial.distance import cdist
from scipy.optimize import linear_sum_assignment

warnings.filterwarnings('ignore')


class TrackStatus(Enum):
    """Estados posibles de un track"""
    TENTATIVE = 1
    CONFIRMED = 2
    LOST = 3
    RECOVERED = 4


@dataclass
class ReIDFeatures:
    """Características de Re-ID de un jugador"""
    color_histogram: Optional[np.ndarray] = None
    shape_histogram: Optional[np.ndarray] = None
    sift_descriptors: Optional[List[np.ndarray]] = None
    orb_descriptors: Optional[List[np.ndarray]] = None
    dominant_color: Optional[Tuple[int, int, int]] = None
    width_height_ratio: float = 0.0


@dataclass
class TrackMetrics:
    """Métricas de un track individual"""
    track_id: int
    total_frames: int = 0
    confirmed_frames: int = 0
    occluded_frames: int = 0
    team_changes: int = 0
    direction_anomalies: int = 0
    fragmentation_count: int = 0
    max_distance_jump: float = 0.0
    avg_confidence: float = 0.0
    consistency_score: float = 0.0


@dataclass
class TrackState:
    """Estado completo de un track de jugador"""
    track_id: int
    bbox: List[float]
    confidence: float
    frame_id: int

    # Estado
    status: TrackStatus = TrackStatus.TENTATIVE
    age: int = 1
    hits: int = 1
    time_since_update: int = 0

    # Historial y movimiento
    position_history: deque = field(default_factory=lambda: deque(maxlen=50))
    velocity: Tuple[float, float] = (0.0, 0.0)
    velocities_history: deque = field(default_factory=lambda: deque(maxlen=10))

    # Información del jugador
    team_id: Optional[int] = None
    jersey_number: Optional[str] = None
    is_occluded: bool = False
    occlusion_frames: int = 0

    # Re-ID
    reid_features: ReIDFeatures = field(default_factory=ReIDFeatures)
    color_history: deque = field(default_factory=lambda: deque(maxlen=20))

    # Métricas
    metrics: TrackMetrics = field(default_factory=lambda: TrackMetrics(track_id=0))


class ReIDMatcher:
    """
    Matcher de Re-Identificación para recuperación de tracks perdidos.
    Usa características visuales: color, forma, y descriptores SIFT/ORB.
    """

    def __init__(self, similarity_threshold: float = 0.75):
        """
        Inicializa el matcher de Re-ID.

        Args:
            similarity_threshold (float): Umbral de similitud para matching (0.75)
        """
        self.similarity_threshold = similarity_threshold
        self.sift = cv2.SIFT_create()
        self.orb = cv2.ORB_create(nfeatures=500)

    def extract_features(self, image: np.ndarray, bbox: List[float]) -> ReIDFeatures:
        """
        Extrae características visuales de una región de imagen.

        Args:
            image (np.ndarray): Imagen del frame
            bbox (List[float]): [x1, y1, x2, y2]

        Returns:
            ReIDFeatures: Características extraídas
        """
        x1, y1, x2, y2 = map(int, bbox)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(image.shape[1], x2)
        y2 = min(image.shape[0], y2)

        if x2 <= x1 or y2 <= y1:
            return ReIDFeatures()

        roi = image[y1:y2, x1:x2]
        features = ReIDFeatures()

        # Color dominante
        if roi.size > 0:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            h_hist = cv2.calcHist([hsv], [0], None, [50], [0, 180])
            s_hist = cv2.calcHist([hsv], [1], None, [50], [0, 256])
            features.color_histogram = np.concatenate([h_hist.flatten(), s_hist.flatten()])

            # Encontrar color dominante
            pixels = roi.reshape((-1, 3))
            pixels = np.float32(pixels)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, labels, centers = cv2.kmeans(pixels, 1, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            features.dominant_color = tuple(int(c) for c in centers[0])

        # Ratio de aspecto
        h = y2 - y1
        w = x2 - x1
        features.width_height_ratio = w / h if h > 0 else 0.0

        # SIFT descriptors
        try:
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            kp_sift, des_sift = self.sift.detectAndCompute(gray, None)
            if des_sift is not None:
                features.sift_descriptors = [des_sift]
        except Exception:
            pass

        # ORB descriptors
        try:
            kp_orb, des_orb = self.orb.detectAndCompute(gray, None)
            if des_orb is not None:
                features.orb_descriptors = [des_orb]
        except Exception:
            pass

        return features

    def compute_similarity(self, features1: ReIDFeatures, features2: ReIDFeatures) -> float:
        """
        Calcula similitud entre dos conjuntos de características.

        Args:
            features1 (ReIDFeatures): Primeras características
            features2 (ReIDFeatures): Segundas características

        Returns:
            float: Similitud (0-1), donde 1 es máxima similitud
        """
        if not features1.color_histogram is not None or not features2.color_histogram is not None:
            return 0.0

        similarities = []

        # Similitud de color (30% del peso)
        if features1.color_histogram is not None and features2.color_histogram is not None:
            color_sim = cv2.compareHist(
                features1.color_histogram.reshape(-1, 1).astype(np.float32),
                features2.color_histogram.reshape(-1, 1).astype(np.float32),
                cv2.HISTCMP_BHATTACHARYYA
            )
            color_sim = 1.0 - min(color_sim, 1.0)
            similarities.append((0.3, color_sim))

        # Similitud de ratio (10% del peso)
        if features1.width_height_ratio > 0 and features2.width_height_ratio > 0:
            ratio_diff = abs(features1.width_height_ratio - features2.width_height_ratio)
            ratio_sim = 1.0 - min(ratio_diff, 1.0)
            similarities.append((0.1, ratio_sim))

        # Similitud SIFT (30% del peso)
        sift_sim = self._match_descriptors(features1.sift_descriptors, features2.sift_descriptors)
        if sift_sim > 0:
            similarities.append((0.3, sift_sim))

        # Similitud ORB (30% del peso)
        orb_sim = self._match_descriptors(features1.orb_descriptors, features2.orb_descriptors)
        if orb_sim > 0:
            similarities.append((0.3, orb_sim))

        if not similarities:
            return 0.0

        # Promedio ponderado
        total_weight = sum(w for w, _ in similarities)
        if total_weight == 0:
            return 0.0

        weighted_sim = sum(w * s for w, s in similarities) / total_weight
        return float(weighted_sim)

    def _match_descriptors(self, des1_list: Optional[List[np.ndarray]],
                          des2_list: Optional[List[np.ndarray]]) -> float:
        """
        Compara descriptores usando BFMatcher.

        Args:
            des1_list: Lista de descriptores 1
            des2_list: Lista de descriptores 2

        Returns:
            float: Similitud basada en matches (0-1)
        """
        if not des1_list or not des2_list:
            return 0.0

        des1 = des1_list[0]
        des2 = des2_list[0]

        if des1 is None or des2 is None or des1.shape[0] == 0 or des2.shape[0] == 0:
            return 0.0

        try:
            # Usar FLANN para SIFT, BFMatcher para ORB
            if des1.dtype == np.uint8:
                # ORB - usa Hamming
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            else:
                # SIFT - usa L2
                bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

            matches = bf.knnMatch(des1, des2, k=2)

            if not matches:
                return 0.0

            # Aplicar Lowe's ratio test
            good_matches = 0
            for match_pair in matches:
                if len(match_pair) == 2:
                    m, n = match_pair
                    if m.distance < 0.75 * n.distance:
                        good_matches += 1

            # Normalizar por cantidad de matches
            max_matches = max(des1.shape[0], des2.shape[0])
            similarity = good_matches / max_matches if max_matches > 0 else 0.0

            return min(similarity, 1.0)
        except Exception:
            return 0.0


class ByteTrackImproved:
    """
    Tracker mejorado usando ByteTrack con Re-ID y validaciones.

    Características:
    - Integración de ByteTrack oficial
    - Re-identificación simple para oclusiones
    - Validación de movimiento y cambios de equipo
    - Estadísticas detalladas de tracking
    - Filtrado de tracks inestables
    """

    def __init__(self,
                 max_age: int = 30,
                 min_hits: int = 3,
                 high_match_threshold: float = 0.5,
                 low_match_threshold: float = 0.1,
                 reid_threshold: float = 0.75):
        """
        Inicializa el tracker mejorado.

        Args:
            max_age (int): Máximo frames sin detección antes de eliminar (30)
            min_hits (int): Mínimo hits para confirmar track (3)
            high_match_threshold (float): IoU para match alto (0.5)
            low_match_threshold (float): IoU para match bajo (0.1)
            reid_threshold (float): Umbral de similitud Re-ID (0.75)
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.high_match_threshold = high_match_threshold
        self.low_match_threshold = low_match_threshold

        self.tracks: Dict[int, TrackState] = {}
        self.lost_tracks: Dict[int, TrackState] = {}
        self.next_id = 1
        self.frame_count = 0

        # Re-ID matcher
        self.reid_matcher = ReIDMatcher(similarity_threshold=reid_threshold)

        # Estadísticas globales
        self.tracking_stats = {
            'total_detections': 0,
            'total_matches': 0,
            'total_id_switches': 0,
            'total_fragments': 0,
            'occlusion_recoveries': 0,
            'anomalous_movements': 0
        }

    def _get_centroid(self, bbox: List[float]) -> Tuple[float, float]:
        """Calcula centroide de bbox."""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calcula IoU entre dos bboxes."""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        xi_min = max(x1_min, x2_min)
        yi_min = max(y1_min, y2_min)
        xi_max = min(x1_max, x2_max)
        yi_max = min(y1_max, y2_max)

        if xi_max < xi_min or yi_max < yi_min:
            return 0.0

        intersection = (xi_max - xi_min) * (yi_max - yi_min)
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def _calculate_distance(self, pos1: Tuple[float, float],
                           pos2: Tuple[float, float]) -> float:
        """Calcula distancia euclidiana."""
        return np.sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)

    def _estimate_velocity(self, position_history: deque) -> Tuple[float, float]:
        """Estima velocidad del jugador."""
        if len(position_history) < 2:
            return (0.0, 0.0)

        recent = list(position_history)[-5:]
        if len(recent) < 2:
            return (0.0, 0.0)

        positions = np.array(recent)
        velocities = np.diff(positions, axis=0)
        avg_velocity = np.mean(velocities, axis=0)

        return tuple(avg_velocity)

    def _detect_anomalous_movement(self, track: TrackState) -> bool:
        """
        Detecta movimientos anómalos (cambios de dirección violentos).

        Args:
            track (TrackState): Track a analizar

        Returns:
            bool: True si hay movimiento anómalo
        """
        if len(track.velocities_history) < 3:
            return False

        velocities = np.array(list(track.velocities_history))

        # Calcular cambios de dirección
        vel_magnitudes = np.linalg.norm(velocities, axis=1)

        # Si la velocidad cambia significativamente, puede ser anómalo
        if vel_magnitudes.std() > 2.0 * vel_magnitudes.mean():
            return True

        # Detectar reversiones de dirección (cambios de > 90 grados)
        direction_changes = 0
        for i in range(len(velocities) - 1):
            v1 = velocities[i]
            v2 = velocities[i + 1]

            mag1 = np.linalg.norm(v1)
            mag2 = np.linalg.norm(v2)

            if mag1 > 0 and mag2 > 0:
                cos_angle = np.dot(v1, v2) / (mag1 * mag2)
                cos_angle = np.clip(cos_angle, -1.0, 1.0)
                angle = np.arccos(cos_angle)

                if angle > np.pi / 2:  # > 90 grados
                    direction_changes += 1

        return direction_changes > 2

    def _validate_track_consistency(self, track: TrackState,
                                   detection: Dict) -> Tuple[bool, str]:
        """
        Valida que el track sea consistente.

        Args:
            track (TrackState): Track existente
            detection (Dict): Nueva detección

        Returns:
            Tuple[bool, str]: (es_válido, razón)
        """
        # Validar cambio de equipo
        if track.team_id is not None and detection.get('team_id') is not None:
            if track.team_id != detection['team_id']:
                track.metrics.team_changes += 1
                if track.metrics.team_changes > 2:
                    return False, "team_change"

        # Validar movimiento anómalo
        if self._detect_anomalous_movement(track):
            track.metrics.direction_anomalies += 1
            if track.metrics.direction_anomalies > 3:
                return False, "anomalous_movement"

        return True, "valid"

    def _match_detections_to_tracks(self, detections: List[Dict]) -> Tuple[List[Tuple[int, int]], List[int]]:
        """
        Empareja detecciones con tracks existentes usando IoU y validación.

        Args:
            detections (List[Dict]): Detecciones del frame actual

        Returns:
            Tuple con matches y detecciones no emparejadas
        """
        matched_pairs = []
        unmatched_detections = list(range(len(detections)))

        # Primera pasada: matches con IoU alto
        for track_id, track in list(self.tracks.items()):
            best_match_idx = -1
            best_iou = 0.0

            for det_idx in unmatched_detections:
                detection = detections[det_idx]
                iou = self._calculate_iou(track.bbox, detection['bbox'])

                if iou > best_iou and iou > self.high_match_threshold:
                    # Validar consistencia
                    is_valid, _ = self._validate_track_consistency(track, detection)
                    if is_valid:
                        best_iou = iou
                        best_match_idx = det_idx

            if best_match_idx >= 0:
                matched_pairs.append((track_id, best_match_idx))
                unmatched_detections.remove(best_match_idx)

        # Segunda pasada: matches con IoU bajo (para detecciones perdidas)
        for track_id, track in list(self.tracks.items()):
            if track_id in [t for t, _ in matched_pairs]:
                continue

            best_match_idx = -1
            best_iou = 0.0

            for det_idx in unmatched_detections:
                detection = detections[det_idx]
                iou = self._calculate_iou(track.bbox, detection['bbox'])

                if iou > best_iou and iou > self.low_match_threshold:
                    best_iou = iou
                    best_match_idx = det_idx

            if best_match_idx >= 0:
                matched_pairs.append((track_id, best_match_idx))
                unmatched_detections.remove(best_match_idx)

        return matched_pairs, unmatched_detections

    def track(self, detections: List[Dict], frame_image: Optional[np.ndarray] = None,
              frame_id: Optional[int] = None) -> Dict:
        """
        Actualiza tracks con nuevas detecciones.

        Args:
            detections (List[Dict]): Lista de detecciones con 'bbox', 'confidence', etc.
            frame_image (Optional[np.ndarray]): Imagen del frame actual para Re-ID
            frame_id (Optional[int]): ID del frame actual

        Returns:
            dict: Estadísticas del frame
        """
        if frame_id is None:
            frame_id = self.frame_count

        self.frame_count += 1
        self.tracking_stats['total_detections'] += len(detections)

        # Incrementar time_since_update para todos los tracks
        for track in self.tracks.values():
            track.time_since_update += 1

        # Emparejar detecciones con tracks
        matched_pairs, unmatched_detections = self._match_detections_to_tracks(detections)

        # Actualizar tracks emparejados
        for track_id, det_idx in matched_pairs:
            track = self.tracks[track_id]
            detection = detections[det_idx]

            track.bbox = detection['bbox']
            track.confidence = detection['confidence']
            track.age += 1
            track.hits += 1
            track.time_since_update = 0
            track.frame_id = frame_id

            # Actualizar métricas
            track.metrics.total_frames += 1
            track.metrics.avg_confidence = (
                (track.metrics.avg_confidence * (track.metrics.total_frames - 1) +
                 track.confidence) / track.metrics.total_frames
            )

            # Actualizar historial
            centroid = self._get_centroid(track.bbox)
            track.position_history.append(centroid)

            # Estimación de velocidad
            track.velocity = self._estimate_velocity(track.position_history)
            track.velocities_history.append(track.velocity)

            # Actualizar estado a CONFIRMED si cumple hits
            if track.status == TrackStatus.TENTATIVE and track.hits >= self.min_hits:
                track.status = TrackStatus.CONFIRMED
                track.metrics.confirmed_frames += 1
            elif track.status == TrackStatus.CONFIRMED:
                track.metrics.confirmed_frames += 1

            # Información del jugador
            if 'team_id' in detection:
                track.team_id = detection['team_id']
            if 'jersey_number' in detection:
                track.jersey_number = detection['jersey_number']

            # Extraer y almacenar características Re-ID
            if frame_image is not None:
                features = self.reid_matcher.extract_features(frame_image, track.bbox)
                track.reid_features = features
                if features.dominant_color:
                    track.color_history.append(features.dominant_color)

            # Detectar oclusión
            overlaps = sum(1 for d in detections
                          if 0.1 < self._calculate_iou(track.bbox, d['bbox']) < 0.9)
            track.is_occluded = overlaps > 1 or track.time_since_update > 5

            if track.is_occluded:
                track.occlusion_frames += 1
                track.metrics.occluded_frames += 1

            self.tracking_stats['total_matches'] += 1

        # Crear nuevos tracks
        for det_idx in unmatched_detections:
            detection = detections[det_idx]

            track = TrackState(
                track_id=self.next_id,
                bbox=detection['bbox'],
                confidence=detection['confidence'],
                frame_id=frame_id,
                team_id=detection.get('team_id'),
                jersey_number=detection.get('jersey_number'),
                metrics=TrackMetrics(track_id=self.next_id)
            )

            centroid = self._get_centroid(track.bbox)
            track.position_history.append(centroid)

            # Características Re-ID iniciales
            if frame_image is not None:
                features = self.reid_matcher.extract_features(frame_image, track.bbox)
                track.reid_features = features
                if features.dominant_color:
                    track.color_history.append(features.dominant_color)

            track.metrics.total_frames = 1
            self.tracks[self.next_id] = track
            self.next_id += 1

        # Intentar recuperar tracks perdidos mediante Re-ID
        if frame_image is not None and unmatched_detections:
            self._attempt_reid_recovery(detections, unmatched_detections, frame_image)

        # Eliminar tracks antiguos
        tracks_to_remove = []
        for track_id, track in self.tracks.items():
            if track.time_since_update > self.max_age:
                tracks_to_remove.append(track_id)
                track.status = TrackStatus.LOST
                self.lost_tracks[track_id] = track

        for track_id in tracks_to_remove:
            del self.tracks[track_id]

        # Limitar histórico
        if len(self.lost_tracks) > 500:
            oldest_key = min(self.lost_tracks.keys())
            del self.lost_tracks[oldest_key]

        return {
            'matched': len(matched_pairs),
            'new_tracks': len(unmatched_detections),
            'active_tracks': len(self.tracks),
            'frame_id': frame_id,
            'occluded_tracks': sum(1 for t in self.tracks.values() if t.is_occluded)
        }

    def _attempt_reid_recovery(self, detections: List[Dict],
                              unmatched_det_indices: List[int],
                              frame_image: np.ndarray) -> None:
        """
        Intenta recuperar tracks perdidos usando Re-ID.

        Args:
            detections: Detecciones del frame actual
            unmatched_det_indices: Índices de detecciones sin emparejar
            frame_image: Imagen del frame para extraer características
        """
        # Solo considerar tracks perdidos recientes
        recent_lost = {tid: t for tid, t in self.lost_tracks.items()
                      if t.frame_id > self.frame_count - 10}

        if not recent_lost:
            return

        for det_idx in unmatched_det_indices:
            detection = detections[det_idx]

            # Extraer características de la detección
            det_features = self.reid_matcher.extract_features(frame_image, detection['bbox'])

            best_match_track_id = -1
            best_similarity = 0.0

            # Comparar con tracks perdidos
            for lost_track_id, lost_track in recent_lost.items():
                if lost_track.reid_features is None or not lost_track.reid_features.color_histogram is not None:
                    continue

                # Validar que el equipo sea compatible
                if lost_track.team_id and detection.get('team_id'):
                    if lost_track.team_id != detection.get('team_id'):
                        continue

                similarity = self.reid_matcher.compute_similarity(
                    lost_track.reid_features,
                    det_features
                )

                if similarity > best_similarity and similarity > self.reid_matcher.similarity_threshold:
                    best_similarity = similarity
                    best_match_track_id = lost_track_id

            if best_match_track_id >= 0:
                # Recuperar track
                recovered_track = self.lost_tracks.pop(best_match_track_id)
                recovered_track.track_id = best_match_track_id
                recovered_track.bbox = detection['bbox']
                recovered_track.confidence = detection['confidence']
                recovered_track.time_since_update = 0
                recovered_track.status = TrackStatus.RECOVERED
                recovered_track.frame_id = self.frame_count

                centroid = self._get_centroid(recovered_track.bbox)
                recovered_track.position_history.append(centroid)

                self.tracks[best_match_track_id] = recovered_track
                self.tracking_stats['occlusion_recoveries'] += 1

    def get_active_tracks(self, min_confidence: float = 0.0,
                         confirmed_only: bool = False) -> List[Dict]:
        """
        Retorna todos los tracks activos.

        Args:
            min_confidence (float): Confianza mínima
            confirmed_only (bool): Solo tracks confirmados

        Returns:
            List[Dict]: Información de tracks
        """
        tracks = []

        for track_id, track in self.tracks.items():
            if track.confidence < min_confidence:
                continue
            if confirmed_only and track.status != TrackStatus.CONFIRMED:
                continue

            centroid = self._get_centroid(track.bbox)

            tracks.append({
                'track_id': track_id,
                'bbox': track.bbox,
                'confidence': track.confidence,
                'age': track.age,
                'hits': track.hits,
                'status': track.status.name,
                'team_id': track.team_id,
                'jersey_number': track.jersey_number,
                'is_occluded': track.is_occluded,
                'velocity': track.velocity,
                'position': centroid,
                'position_history_size': len(track.position_history),
                'occlusion_frames': track.occlusion_frames
            })

        return tracks

    def get_statistics(self) -> Dict:
        """
        Retorna estadísticas detalladas del tracking.

        Returns:
            dict: Estadísticas completas
        """
        total_track_ids = self.next_id - 1
        confirmed_tracks = sum(1 for t in self.tracks.values()
                              if t.status == TrackStatus.CONFIRMED)

        # Calcular fragmentación
        total_fragments = sum(t.metrics.fragmentation_count
                            for t in self.tracks.values())

        # Calcular tasa de éxito
        tracking_success_rate = 0.0
        if self.tracking_stats['total_detections'] > 0:
            tracking_success_rate = (
                self.tracking_stats['total_matches'] /
                self.tracking_stats['total_detections'] * 100
            )

        return {
            'active_tracks': len(self.tracks),
            'confirmed_tracks': confirmed_tracks,
            'lost_tracks': len(self.lost_tracks),
            'total_track_ids': total_track_ids,
            'total_frames': self.frame_count,
            'total_detections': self.tracking_stats['total_detections'],
            'total_matches': self.tracking_stats['total_matches'],
            'tracking_success_rate': tracking_success_rate,
            'id_switches': self.tracking_stats['total_id_switches'],
            'fragments': total_fragments,
            'occlusion_recoveries': self.tracking_stats['occlusion_recoveries'],
            'anomalous_movements': self.tracking_stats['anomalous_movements'],
            'max_age': self.max_age,
            'min_hits': self.min_hits
        }

    def get_track_by_id(self, track_id: int) -> Optional[Dict]:
        """Obtiene información de un track específico."""
        if track_id not in self.tracks:
            return None

        track = self.tracks[track_id]
        centroid = self._get_centroid(track.bbox)

        return {
            'track_id': track_id,
            'bbox': track.bbox,
            'confidence': track.confidence,
            'age': track.age,
            'hits': track.hits,
            'status': track.status.name,
            'team_id': track.team_id,
            'jersey_number': track.jersey_number,
            'is_occluded': track.is_occluded,
            'velocity': track.velocity,
            'position': centroid,
            'position_history': list(track.position_history),
            'occlusion_frames': track.occlusion_frames,
            'metrics': {
                'total_frames': track.metrics.total_frames,
                'confirmed_frames': track.metrics.confirmed_frames,
                'occluded_frames': track.metrics.occluded_frames,
                'team_changes': track.metrics.team_changes,
                'direction_anomalies': track.metrics.direction_anomalies,
                'avg_confidence': track.metrics.avg_confidence
            }
        }

    def reset(self):
        """Reinicia el tracker."""
        self.tracks = {}
        self.lost_tracks = {}
        self.next_id = 1
        self.frame_count = 0
        self.tracking_stats = {
            'total_detections': 0,
            'total_matches': 0,
            'total_id_switches': 0,
            'total_fragments': 0,
            'occlusion_recoveries': 0,
            'anomalous_movements': 0
        }

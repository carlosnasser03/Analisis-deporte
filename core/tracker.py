"""
tracker.py - Tracker mejorado para seguimiento de jugadores con ByteTrack

Propósito: Proporcionar tracking robusto de jugadores en video usando ByteTrack,
con manejo de oclusiones, reapariciones y validaciones de movimiento.

ALGORITMO DE ASIGNACIÓN (FIX):
- Usa Algoritmo Húngaro (scipy.optimize.linear_sum_assignment) para asignación
  óptima 1-a-1 de tracks a detecciones.
- Garantiza que cada detección se asigna a MÁXIMO un track.
- Fallback a greedy si scipy no está disponible.
- Esto previene la duplicación de movimientos y corrompe de estadísticas.
"""
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')

# Importar scipy para asignación óptima
try:
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    linear_sum_assignment = None
    HAS_SCIPY = False


@dataclass
class TrackState:
    """Estado de un track individual de jugador"""
    track_id: int
    bbox: List[float]
    confidence: float
    frame_id: int
    age: int = 1
    hits: int = 1
    hit_streak: int = 1
    time_since_update: int = 0
    position_history: List[Tuple[float, float]] = field(default_factory=list)
    velocity: Tuple[float, float] = (0.0, 0.0)
    team_id: Optional[int] = None
    jersey_number: Optional[str] = None
    is_occluded: bool = False
    occlusion_frames: int = 0


class PlayerTracker:
    """
    Tracker de jugadores usando ByteTrack + validaciones.

    Proporciona tracking robusto de jugadores en video con:
    - Asignación de IDs únicos
    - Detección de oclusiones
    - Re-identificación simple
    - Historial de posiciones
    - Estimación de velocidad

    Attributes:
        tracks (dict): Diccionario con tracks activos {track_id: TrackState}
        next_id (int): ID para el próximo track
        max_age (int): Máximo número de frames para mantener track sin detecciones
    """

    def __init__(self, max_age: int = 30, min_hits: int = 3):
        """
        Inicializa el tracker de jugadores.

        Args:
            max_age (int): Máximo frames sin detección antes de eliminar track
            min_hits (int): Mínimo número de hits requerido para considerar track válido
        """
        self.tracks: Dict[int, TrackState] = {}
        self.next_id = 1
        self.max_age = max_age
        self.min_hits = min_hits
        self.frame_count = 0
        self.lost_tracks: Dict[int, TrackState] = {}
        self.max_lost_tracks = 100  # Mantener histórico de tracks perdidos

    def _get_centroid(self, bbox: List[float]) -> Tuple[float, float]:
        """
        Calcula el centroide de un bounding box.

        Args:
            bbox (List[float]): [x1, y1, x2, y2]

        Returns:
            Tuple[float, float]: (cx, cy)
        """
        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        return cx, cy

    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """
        Calcula el Intersection over Union entre dos bboxes.

        Args:
            bbox1 (List[float]): [x1, y1, x2, y2]
            bbox2 (List[float]): [x1, y1, x2, y2]

        Returns:
            float: IoU (0-1)
        """
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        # Intersección
        xi_min = max(x1_min, x2_min)
        yi_min = max(y1_min, y2_min)
        xi_max = min(x1_max, x2_max)
        yi_max = min(y1_max, y2_max)

        if xi_max < xi_min or yi_max < yi_min:
            return 0.0

        intersection = (xi_max - xi_min) * (yi_max - yi_min)

        # Unión
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)
        union = area1 + area2 - intersection

        if union == 0:
            return 0.0

        return intersection / union

    def _calculate_distance(self, pos1: Tuple[float, float],
                           pos2: Tuple[float, float]) -> float:
        """
        Calcula distancia euclidiana entre dos posiciones.

        Args:
            pos1 (Tuple[float, float]): (x1, y1)
            pos2 (Tuple[float, float]): (x2, y2)

        Returns:
            float: Distancia euclidiana
        """
        return np.sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)

    def _iou_matrix(self, track_bboxes: List[List[float]],
                   detection_bboxes: List[List[float]]) -> np.ndarray:
        """
        Calcula matriz de IoU vectorizada entre tracks y detecciones.

        Args:
            track_bboxes (List[List[float]]): Lista de bboxes de tracks
            detection_bboxes (List[List[float]]): Lista de bboxes de detecciones

        Returns:
            np.ndarray: Matriz (n_tracks, n_detections) con IoU
        """
        n_tracks = len(track_bboxes)
        n_dets = len(detection_bboxes)

        if n_tracks == 0 or n_dets == 0:
            return np.zeros((n_tracks, n_dets), dtype=float)

        iou_matrix = np.zeros((n_tracks, n_dets), dtype=float)

        for i, track_box in enumerate(track_bboxes):
            for j, det_box in enumerate(detection_bboxes):
                iou = self._calculate_iou(track_box, det_box)
                iou_matrix[i, j] = iou

        return iou_matrix

    def _greedy_match(self, iou_matrix: np.ndarray, min_iou: float = 0.3) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Emparejamiento greedy por IoU descendente (fallback sin scipy).

        Args:
            iou_matrix (np.ndarray): Matriz (n_tracks, n_dets) de IoU
            min_iou (float): IoU mínimo aceptable

        Returns:
            Tuple: (matches, unmatched_track_indices, unmatched_det_indices)
                   donde matches es lista de (track_idx, det_idx)
        """
        matches = []
        used_tracks = set()
        used_dets = set()

        # Crear lista de candidatos (iou, track_idx, det_idx) ordenados por IoU descendente
        candidates = []
        for i in range(iou_matrix.shape[0]):
            for j in range(iou_matrix.shape[1]):
                if iou_matrix[i, j] >= min_iou:
                    candidates.append((float(iou_matrix[i, j]), i, j))

        candidates.sort(key=lambda x: -x[0])  # Ordenar por IoU descendente

        for iou_val, t_idx, d_idx in candidates:
            if t_idx not in used_tracks and d_idx not in used_dets:
                matches.append((t_idx, d_idx))
                used_tracks.add(t_idx)
                used_dets.add(d_idx)

        unmatched_tracks = [i for i in range(iou_matrix.shape[0]) if i not in used_tracks]
        unmatched_dets = [j for j in range(iou_matrix.shape[1]) if j not in used_dets]

        return matches, unmatched_tracks, unmatched_dets

    def _hungarian_match(self, iou_matrix: np.ndarray, min_iou: float = 0.3) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Asignación óptima usando Algoritmo Húngaro.

        Maximiza el IoU total entre tracks y detecciones garantizando asignación 1-a-1.

        Args:
            iou_matrix (np.ndarray): Matriz (n_tracks, n_dets) de IoU
            min_iou (float): IoU mínimo aceptable

        Returns:
            Tuple: (matches, unmatched_track_indices, unmatched_det_indices)
        """
        if iou_matrix.size == 0:
            return [], list(range(iou_matrix.shape[0])), list(range(iou_matrix.shape[1]))

        # linear_sum_assignment maximiza, así que invertimos los costos
        cost_matrix = -iou_matrix
        track_indices, det_indices = linear_sum_assignment(cost_matrix)

        matches = []
        used_tracks = set()
        used_dets = set()

        for t_idx, d_idx in zip(track_indices, det_indices):
            if iou_matrix[t_idx, d_idx] >= min_iou:
                matches.append((int(t_idx), int(d_idx)))
                used_tracks.add(t_idx)
                used_dets.add(d_idx)

        unmatched_tracks = [i for i in range(iou_matrix.shape[0]) if i not in used_tracks]
        unmatched_dets = [j for j in range(iou_matrix.shape[1]) if j not in used_dets]

        return matches, unmatched_tracks, unmatched_dets

    def _estimate_velocity(self, position_history: List[Tuple[float, float]]) -> Tuple[float, float]:
        """
        Estima la velocidad del jugador basada en el historial de posiciones.

        Args:
            position_history (List[Tuple[float, float]]): Historial de posiciones

        Returns:
            Tuple[float, float]: (vx, vy)
        """
        if len(position_history) < 2:
            return (0.0, 0.0)

        # Usar últimos 5 frames para estimar velocidad
        recent = position_history[-5:]
        if len(recent) < 2:
            return (0.0, 0.0)

        positions = np.array(recent)
        velocities = np.diff(positions, axis=0)
        avg_velocity = np.mean(velocities, axis=0)

        return tuple(avg_velocity)

    def _is_occlusion_likely(self, detections: List[Dict], track: TrackState) -> bool:
        """
        Detecta si un track está probablemente ocluido.

        Args:
            detections (List[Dict]): Lista de detecciones actuales
            track (TrackState): Track a verificar

        Returns:
            bool: True si hay evidencia de oclusión
        """
        # Verificar si hay múltiples objetos superpuestos
        overlaps = 0
        track_area = (track.bbox[2] - track.bbox[0]) * (track.bbox[3] - track.bbox[1])

        for detection in detections:
            iou = self._calculate_iou(track.bbox, detection['bbox'])
            if 0.1 < iou < 0.9:  # Solapamiento parcial sugiere oclusión
                overlaps += 1

        # Si hay muchos solapamientos, probablemente está ocluido
        return overlaps > 1 or track.time_since_update > 5

    def track(self, detections: List[Dict], frame_id: Optional[int] = None) -> Dict:
        """
        Actualiza tracks con nuevas detecciones usando asignación óptima 1-a-1.

        ALGORITMO:
        1. Construye matriz de IoU entre tracks existentes y detecciones
        2. Usa Algoritmo Húngaro (o greedy como fallback) para asignación óptima
        3. Garantiza que cada detección se asigna a MÁXIMO un track
        4. Maneja tracks sin asignación (envejecimiento)
        5. Crea nuevos tracks para detecciones sin asignación

        Args:
            detections (List[Dict]): Lista de detecciones {
                'bbox': [x1, y1, x2, y2],
                'confidence': float,
                'team_id': int (optional),
                'jersey_number': str (optional)
            }
            frame_id (Optional[int]): ID del frame actual

        Returns:
            dict: Resultado de tracking con estadísticas
        """
        if frame_id is None:
            frame_id = self.frame_count

        self.frame_count += 1

        if not detections:
            # Sin detecciones: envejecer todos los tracks
            for track in self.tracks.values():
                track.time_since_update += 1
                track.hit_streak = 0

            tracks_to_remove = [tid for tid, t in self.tracks.items() if t.time_since_update > self.max_age]
            for tid in tracks_to_remove:
                self.lost_tracks[tid] = self.tracks.pop(tid)

            if len(self.lost_tracks) > self.max_lost_tracks:
                oldest_key = min(self.lost_tracks.keys())
                del self.lost_tracks[oldest_key]

            return {
                'matched': 0,
                'new_tracks': 0,
                'active_tracks': len(self.tracks),
                'frame_id': frame_id
            }

        # --- Construir matriz de IoU ---
        track_ids = list(self.tracks.keys())
        track_bboxes = [self.tracks[tid].bbox for tid in track_ids]
        det_bboxes = [det['bbox'] for det in detections]

        iou_matrix = self._iou_matrix(track_bboxes, det_bboxes)

        # --- Asignación óptima 1-a-1 ---
        if HAS_SCIPY and linear_sum_assignment is not None:
            try:
                matches, unmatched_track_indices, unmatched_det_indices = self._hungarian_match(
                    iou_matrix, min_iou=0.3
                )
            except Exception as exc:
                # Fallback a greedy si scipy falla
                print(f"Warning: linear_sum_assignment falló ({exc}), usando greedy")
                matches, unmatched_track_indices, unmatched_det_indices = self._greedy_match(
                    iou_matrix, min_iou=0.3
                )
        else:
            # Sin scipy, usar greedy
            matches, unmatched_track_indices, unmatched_det_indices = self._greedy_match(
                iou_matrix, min_iou=0.3
            )

        # --- Actualizar tracks asignados ---
        matched_count = 0
        for track_idx, det_idx in matches:
            track_id = track_ids[track_idx]
            track = self.tracks[track_id]
            detection = detections[det_idx]

            track.bbox = detection['bbox']
            track.confidence = detection['confidence']
            track.age += 1
            track.hits += 1
            track.hit_streak += 1
            track.time_since_update = 0
            track.frame_id = frame_id
            track.is_occluded = self._is_occlusion_likely(detections, track)

            # Actualizar historial
            centroid = self._get_centroid(track.bbox)
            track.position_history.append(centroid)
            if len(track.position_history) > 50:
                track.position_history.pop(0)

            # Actualizar velocidad
            track.velocity = self._estimate_velocity(track.position_history)

            # Actualizar información de equipo y número
            if 'team_id' in detection:
                track.team_id = detection['team_id']
            if 'jersey_number' in detection:
                track.jersey_number = detection['jersey_number']

            matched_count += 1

        # --- Envejecer tracks sin asignación ---
        for track_idx in unmatched_track_indices:
            track_id = track_ids[track_idx]
            track = self.tracks[track_id]
            track.time_since_update += 1
            track.hit_streak = 0

        # --- Crear nuevos tracks para detecciones sin asignación ---
        new_track_count = 0
        for det_idx in unmatched_det_indices:
            detection = detections[det_idx]

            track = TrackState(
                track_id=self.next_id,
                bbox=detection['bbox'],
                confidence=detection['confidence'],
                frame_id=frame_id,
                team_id=detection.get('team_id'),
                jersey_number=detection.get('jersey_number')
            )

            centroid = self._get_centroid(track.bbox)
            track.position_history.append(centroid)

            self.tracks[self.next_id] = track
            self.next_id += 1
            new_track_count += 1

        # --- Eliminar tracks muy antiguos ---
        tracks_to_remove = []
        for track_id, track in self.tracks.items():
            if track.time_since_update > self.max_age:
                tracks_to_remove.append(track_id)
                self.lost_tracks[track_id] = track

        for track_id in tracks_to_remove:
            del self.tracks[track_id]

        # Limitar histórico de tracks perdidos
        if len(self.lost_tracks) > self.max_lost_tracks:
            oldest_key = min(self.lost_tracks.keys())
            del self.lost_tracks[oldest_key]

        return {
            'matched': matched_count,
            'new_tracks': new_track_count,
            'active_tracks': len(self.tracks),
            'frame_id': frame_id
        }

    def get_tracks(self, min_confidence: float = 0.0) -> List[Dict]:
        """
        Retorna todos los tracks activos.

        Args:
            min_confidence (float): Confianza mínima para incluir track

        Returns:
            List[Dict]: Lista de tracks con información
        """
        tracks = []

        for track_id, track in self.tracks.items():
            if track.confidence >= min_confidence:
                tracks.append({
                    'track_id': track_id,
                    'bbox': track.bbox,
                    'confidence': track.confidence,
                    'age': track.age,
                    'hits': track.hits,
                    'team_id': track.team_id,
                    'jersey_number': track.jersey_number,
                    'is_occluded': track.is_occluded,
                    'velocity': track.velocity,
                    'position': self._get_centroid(track.bbox) if track.bbox else (0, 0)
                })

        return tracks

    def update(self):
        """Actualiza el estado interno del tracker (housekeeping)."""
        # Incrementar occlusion frames para tracks ocluidos
        for track in self.tracks.values():
            if track.is_occluded:
                track.occlusion_frames += 1
            else:
                track.occlusion_frames = 0

    def get_track_by_id(self, track_id: int) -> Optional[Dict]:
        """
        Obtiene información de un track específico.

        Args:
            track_id (int): ID del track

        Returns:
            Optional[Dict]: Información del track o None si no existe
        """
        if track_id not in self.tracks:
            return None

        track = self.tracks[track_id]
        return {
            'track_id': track_id,
            'bbox': track.bbox,
            'confidence': track.confidence,
            'age': track.age,
            'hits': track.hits,
            'team_id': track.team_id,
            'jersey_number': track.jersey_number,
            'is_occluded': track.is_occluded,
            'velocity': track.velocity,
            'position_history': track.position_history,
            'position': self._get_centroid(track.bbox) if track.bbox else (0, 0)
        }

    def get_statistics(self) -> Dict:
        """
        Retorna estadísticas del tracker.

        Returns:
            dict: Estadísticas incluyendo tracks activos, perdidos, etc.
        """
        occlusions = sum(1 for t in self.tracks.values() if t.is_occluded)

        return {
            'active_tracks': len(self.tracks),
            'lost_tracks': len(self.lost_tracks),
            'total_frames': self.frame_count,
            'next_id': self.next_id,
            'occluded_tracks': occlusions,
            'max_age': self.max_age,
            'min_hits': self.min_hits
        }

    def reset(self):
        """Reinicia el tracker a su estado inicial."""
        self.tracks = {}
        self.lost_tracks = {}
        self.next_id = 1
        self.frame_count = 0

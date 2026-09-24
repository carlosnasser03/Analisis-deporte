"""
improved_team_assigner.py - Asignación mejorada de equipos

Usa clustering avanzado + histórico temporal para mayor precisión.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import supervision as sv
import cv2
from sklearn.cluster import KMeans
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ImprovedTeamAssigner:
    """
    Asignador de equipos mejorado que combina:
    - Extracción de color de camiseta
    - Clustering robusto con re-inicializaciones múltiples
    - Histórico temporal para continuidad
    - Validación de confianza
    """

    def __init__(self, n_clusters: int = 2):
        self.n_clusters = n_clusters
        self.team_colors = {}  # {team_id: [r, g, b]}
        self.track_team_history = defaultdict(lambda: [])  # {track_id: [team_ids]}
        self.max_history = 30  # 1 segundo @ 30fps

    def get_player_color(
        self,
        frame: np.ndarray,
        bbox: np.ndarray,
        method: str = 'dominant'
    ) -> np.ndarray:
        """
        Extrae el color dominante de una camiseta.

        Args:
            frame: Imagen BGR
            bbox: [x1, y1, x2, y2]
            method: 'dominant' o 'center'

        Returns:
            Color RGB como [r, g, b]
        """
        x1, y1, x2, y2 = bbox.astype(int)
        x1, y1 = max(0, x1), max(0, y1)
        x2 = min(frame.shape[1], x2)
        y2 = min(frame.shape[0], y2)

        if x2 <= x1 or y2 <= y1:
            return np.array([128, 128, 128], dtype=np.uint8)  # Default gris

        player_region = frame[y1:y2, x1:x2]

        if method == 'dominant':
            # Obtener color dominante usando KMeans en la región
            pixels = player_region.reshape(-1, 3).astype(np.float32)

            # Usar solo 30% de píxeles para acelerar
            sample_idx = np.random.choice(len(pixels), size=max(100, len(pixels)//3), replace=False)
            pixels_sample = pixels[sample_idx]

            kmeans = KMeans(n_clusters=3, n_init=3, max_iter=10, random_state=42)
            kmeans.fit(pixels_sample)

            # Color más común (por frecuencia en cluster)
            labels = kmeans.labels_
            dominant_cluster = np.argmax(np.bincount(labels))
            dominant_color = kmeans.cluster_centers_[dominant_cluster]

            return dominant_color.astype(np.uint8)

        else:  # center
            # Centro de la región
            center_y, center_x = player_region.shape[0] // 2, player_region.shape[1] // 2
            return player_region[center_y, center_x].astype(np.uint8)

    def assign_teams(
        self,
        frame: np.ndarray,
        detections: sv.Detections,
        track_ids: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, Dict]:
        """
        Asigna equipos a los jugadores detectados.

        Args:
            frame: Imagen BGR
            detections: sv.Detections con jugadores
            track_ids: IDs de tracks (para continuidad)

        Returns:
            (team_ids, diagnostics_dict)
        """
        if len(detections) == 0:
            return np.array([], dtype=int), {'players_processed': 0}

        diagnostics = {'players_processed': len(detections)}

        # Extraer colores de camisetas
        colors = []
        for bbox in detections.xyxy:
            color = self.get_player_color(frame, bbox)
            colors.append(color)

        colors = np.array(colors, dtype=np.float32)

        # Clustering
        kmeans = KMeans(
            n_clusters=self.n_clusters,
            n_init=10,  # Múltiples inicializaciones
            max_iter=100,
            random_state=42
        )
        team_labels = kmeans.fit_predict(colors)

        # Actualizar histórico si tenemos track_ids
        if track_ids is not None:
            for track_id, team_label in zip(track_ids, team_labels):
                self.track_team_history[track_id].append(int(team_label))
                if len(self.track_team_history[track_id]) > self.max_history:
                    self.track_team_history[track_id].pop(0)

        # Guardar colores de equipos
        self.team_colors = {
            0: kmeans.cluster_centers_[0].astype(np.uint8),
            1: kmeans.cluster_centers_[1].astype(np.uint8),
        }

        diagnostics['team_colors'] = self.team_colors.copy()

        logger.debug(f"Asignados {len(detections)} jugadores a {self.n_clusters} equipos")

        return team_labels.astype(int), diagnostics

    def get_team_for_track(self, track_id: int) -> Optional[int]:
        """Obtiene el equipo más probable para un track usando histórico"""
        if track_id not in self.track_team_history:
            return None

        history = self.track_team_history[track_id]
        if len(history) == 0:
            return None

        # Mayoría de votos en el histórico reciente
        return int(np.bincount(history).argmax())

    def get_team_color(self, team_id: int) -> Optional[np.ndarray]:
        """Obtiene el color RGB representativo de un equipo"""
        return self.team_colors.get(team_id)


class PossessionAnalyzer:
    """
    Analiza posesión de balón.

    Detecta qué jugador está más cerca del balón
    y calcula estadísticas de posesión.
    """

    def __init__(self, distance_threshold: float = 100):
        """
        Args:
            distance_threshold: Distancia máxima en píxeles para "posesión"
        """
        self.distance_threshold = distance_threshold
        self.possession_history = defaultdict(int)  # {team_id: frames_possession}

    def get_ball_possession(
        self,
        ball_detection: sv.Detections,
        player_detections: sv.Detections,
        team_labels: np.ndarray,
    ) -> Dict:
        """
        Determina qué equipo tiene la posesión.

        Returns:
            {
                'possessing_team': int (0 o 1),
                'closest_player_idx': int,
                'distance_to_ball': float,
                'confidence': float,
            }
        """
        if len(ball_detection) == 0 or len(player_detections) == 0:
            return {
                'possessing_team': None,
                'closest_player_idx': None,
                'distance_to_ball': None,
                'confidence': 0.0,
            }

        # Centro del balón
        ball_center = (
            (ball_detection.xyxy[0][0] + ball_detection.xyxy[0][2]) / 2,
            (ball_detection.xyxy[0][1] + ball_detection.xyxy[0][3]) / 2,
        )

        # Distancias a todos los jugadores
        player_centers = (
            (player_detections.xyxy[:, 0] + player_detections.xyxy[:, 2]) / 2,
            (player_detections.xyxy[:, 1] + player_detections.xyxy[:, 3]) / 2,
        )
        player_centers = np.column_stack(player_centers)

        distances = np.linalg.norm(player_centers - ball_center, axis=1)
        closest_player_idx = np.argmin(distances)
        closest_distance = distances[closest_player_idx]

        # Equipo del jugador más cercano
        possessing_team = team_labels[closest_player_idx]

        # Confianza basada en distancia (más cercano = más confianza)
        confidence = max(0, 1 - closest_distance / self.distance_threshold)

        # Actualizar histórico
        if confidence > 0.5:
            self.possession_history[possessing_team] += 1

        return {
            'possessing_team': int(possessing_team),
            'closest_player_idx': int(closest_player_idx),
            'distance_to_ball': float(closest_distance),
            'confidence': float(confidence),
        }

    def get_possession_stats(self) -> Dict:
        """Obtiene estadísticas acumuladas de posesión"""
        total = sum(self.possession_history.values())
        if total == 0:
            return {'team_0': 0.0, 'team_1': 0.0}

        return {
            'team_0': float(self.possession_history[0] / total),
            'team_1': float(self.possession_history[1] / total),
        }


__all__ = [
    'ImprovedTeamAssigner',
    'PossessionAnalyzer',
]

"""
improved_metrics.py - Cálculo de métricas de rendimiento

Velocidad, distancia, aceleración y cambios de dirección para jugadores.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class RobustMetricsCalculator:
    """
    Calcula métricas de rendimiento robustas para jugadores.

    Métricas:
    - Velocidad (km/h)
    - Distancia recorrida (metros)
    - Aceleración (m/s²)
    - Cambios de dirección
    - Distancia al balón
    """

    def __init__(
        self,
        fps: float = 30.0,
        pixels_per_meter: float = 10.0,  # Calibrar según campo
        smooth_window: int = 6,  # Ventana para suavizado
    ):
        """
        Args:
            fps: Fotogramas por segundo
            pixels_per_meter: Conversión píxeles a metros
            smooth_window: Ventana para suavizar velocidad
        """
        self.fps = fps
        self.pixels_per_meter = pixels_per_meter
        self.smooth_window = smooth_window

        # Histórico de posiciones por track
        self.position_history = defaultdict(list)
        self.max_history = 300  # 10 segundos @ 30fps

        # Métricas acumuladas
        self.metrics_history = defaultdict(dict)

    def update_player_position(self, track_id: int, center: Tuple[float, float]):
        """
        Actualiza la posición de un jugador.

        Args:
            track_id: ID único del jugador
            center: (x, y) en píxeles
        """
        self.position_history[track_id].append(center)

        if len(self.position_history[track_id]) > self.max_history:
            self.position_history[track_id].pop(0)

    def calculate_velocity(self, track_id: int) -> Optional[float]:
        """
        Calcula la velocidad instantánea de un jugador (km/h).

        Args:
            track_id: ID del jugador

        Returns:
            Velocidad en km/h o None si no hay histórico
        """
        if track_id not in self.position_history:
            return None

        positions = self.position_history[track_id]
        if len(positions) < 2:
            return None

        # Usar últimas N posiciones para suavizar
        recent = np.array(positions[-self.smooth_window:])

        # Desplazamientos entre frames consecutivos
        displacements = np.diff(recent, axis=0)
        distances_px = np.linalg.norm(displacements, axis=1)

        # Velocidad promedio: píxeles/frame → metros/segundo → km/h
        avg_distance_px = np.mean(distances_px)
        velocity_m_per_s = (avg_distance_px / self.pixels_per_meter) * self.fps
        velocity_kmh = velocity_m_per_s * 3.6  # m/s → km/h

        return float(velocity_kmh)

    def calculate_distance(self, track_id: int, last_n_frames: Optional[int] = None) -> Optional[float]:
        """
        Calcula la distancia recorrida por un jugador (metros).

        Args:
            track_id: ID del jugador
            last_n_frames: Si se especifica, solo últimos N frames

        Returns:
            Distancia en metros o None
        """
        if track_id not in self.position_history:
            return None

        positions = self.position_history[track_id]

        if last_n_frames is not None:
            positions = positions[-last_n_frames:]

        if len(positions) < 2:
            return None

        positions = np.array(positions)
        displacements = np.diff(positions, axis=0)
        distances_px = np.linalg.norm(displacements, axis=1)

        total_distance_m = np.sum(distances_px) / self.pixels_per_meter

        return float(total_distance_m)

    def calculate_acceleration(self, track_id: int) -> Optional[float]:
        """
        Calcula la aceleración instantánea (m/s²).

        Args:
            track_id: ID del jugador

        Returns:
            Aceleración en m/s² o None
        """
        if track_id not in self.position_history:
            return None

        positions = self.position_history[track_id]
        if len(positions) < 3:
            return None

        recent = np.array(positions[-self.smooth_window:])
        velocities = np.diff(recent, axis=0)
        velocity_magnitudes = np.linalg.norm(velocities, axis=1)

        # Cambio de velocidad
        accel = np.diff(velocity_magnitudes)

        if len(accel) == 0:
            return None

        # Aceleración media en píxeles/frame²
        avg_accel_px = np.mean(np.abs(accel))

        # Convertir a m/s²
        # 1 píxel/frame² = (píxeles/frame²) * (1 metro / pixels_per_meter) * fps²
        avg_accel_ms2 = (avg_accel_px / self.pixels_per_meter) * (self.fps ** 2)

        return float(avg_accel_ms2)

    def calculate_direction_changes(self, track_id: int, window: int = 10) -> Optional[int]:
        """
        Cuenta cambios de dirección (giros significativos).

        Args:
            track_id: ID del jugador
            window: Ventana para detectar cambios

        Returns:
            Número de cambios de dirección o None
        """
        if track_id not in self.position_history:
            return None

        positions = np.array(self.position_history[track_id])

        if len(positions) < window + 1:
            return None

        changes = 0
        angle_threshold = 30  # grados

        for i in range(window, len(positions) - 1):
            # Vectores de movimiento
            vec1 = positions[i - window] - positions[i - window - 1]
            vec2 = positions[i + 1] - positions[i]

            # Ángulo entre vectores
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 < 1 or norm2 < 1:  # Evitar división por cero
                continue

            cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)
            cos_angle = np.clip(cos_angle, -1, 1)  # Evitar errores numéricos
            angle = np.degrees(np.arccos(cos_angle))

            if angle > angle_threshold:
                changes += 1

        return int(changes)

    def calculate_all_metrics(self, track_id: int) -> Dict:
        """
        Calcula todas las métricas para un jugador.

        Returns:
            {
                'velocity_kmh': float,
                'distance_m': float,
                'acceleration_ms2': float,
                'direction_changes': int,
            }
        """
        return {
            'velocity_kmh': self.calculate_velocity(track_id),
            'distance_m': self.calculate_distance(track_id),
            'acceleration_ms2': self.calculate_acceleration(track_id),
            'direction_changes': self.calculate_direction_changes(track_id),
        }

    def get_team_statistics(
        self,
        track_ids: np.ndarray,
        team_labels: np.ndarray,
    ) -> Dict:
        """
        Obtiene estadísticas agregadas por equipo.

        Args:
            track_ids: IDs de tracks
            team_labels: Etiquetas de equipo para cada track

        Returns:
            {
                0: {'avg_velocity': ..., 'total_distance': ...},
                1: {...},
            }
        """
        stats = {0: {}, 1: {}}

        for team_id in [0, 1]:
            team_track_ids = track_ids[team_labels == team_id]

            velocities = []
            distances = []
            accelerations = []

            for track_id in team_track_ids:
                if vel := self.calculate_velocity(int(track_id)):
                    velocities.append(vel)
                if dist := self.calculate_distance(int(track_id)):
                    distances.append(dist)
                if accel := self.calculate_acceleration(int(track_id)):
                    accelerations.append(accel)

            stats[team_id] = {
                'avg_velocity_kmh': float(np.mean(velocities)) if velocities else 0,
                'total_distance_m': float(np.sum(distances)) if distances else 0,
                'avg_acceleration_ms2': float(np.mean(accelerations)) if accelerations else 0,
                'num_players': len(team_track_ids),
            }

        return stats


class ShotOnGoalDetector:
    """
    Detector simple de tiros a puerta.

    Detecta cuando el balón cruza la línea de meta.
    """

    def __init__(self, frame_width: int, goal_line_threshold: float = 0.05):
        """
        Args:
            frame_width: Ancho del frame
            goal_line_threshold: Porcentaje del ancho para considerar línea de meta
        """
        self.frame_width = frame_width
        self.goal_line_x = int(frame_width * goal_line_threshold)
        self.ball_history = []

    def check_goal(self, ball_center_x: float, last_n: int = 5) -> Tuple[bool, Optional[str]]:
        """
        Verifica si hay tiro a puerta (balón cruza línea).

        Returns:
            (is_goal, side)  # side = 'left' o 'right'
        """
        self.ball_history.append(ball_center_x)
        if len(self.ball_history) > last_n:
            self.ball_history.pop(0)

        if len(self.ball_history) < 2:
            return False, None

        prev_x = self.ball_history[-2]
        curr_x = self.ball_history[-1]

        # Detectar si cruza línea de meta
        left_goal_crossed = prev_x > self.goal_line_x and curr_x <= self.goal_line_x
        right_goal_crossed = prev_x < (self.frame_width - self.goal_line_x) and curr_x >= (self.frame_width - self.goal_line_x)

        if left_goal_crossed:
            return True, 'left'
        elif right_goal_crossed:
            return True, 'right'

        return False, None


__all__ = [
    'RobustMetricsCalculator',
    'ShotOnGoalDetector',
]

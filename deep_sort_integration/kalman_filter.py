"""
kalman_filter.py - Filtro de Kalman para predicción de movimiento

Predice la posición futura de un jugador basándose en:
- Estado actual (posición, tamaño)
- Histórico de movimiento
- Covarianza de predicción
"""

import numpy as np
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


class KalmanFilter:
    """
    Filtro de Kalman para tracking de objetos en 2D.

    Estado: [x, y, ancho, alto, ratio_aspecto, vx, vy]

    Usa movimiento constante como modelo de predicción.
    """

    # Factores de ruido (calibrados para jugadores de fútbol)
    STD_WEIGHT_POSITION = 1.0 / 20      # Confianza en posición
    STD_WEIGHT_VELOCITY = 1.0 / 160     # Confianza en velocidad

    def __init__(self):
        """Inicializar el filtro de Kalman"""

        # Número de dimensiones
        ndim = 7  # [x, y, w, h, ratio, vx, vy]
        dt = 1.0  # Delta tiempo (1 frame)

        # Matriz de transición (modelo de movimiento constante)
        # Estado siguiente = F * Estado anterior
        self.F = np.eye(ndim, ndim)
        for i in range(4):
            self.F[i, i + 4] = dt  # Agregar velocidad a posición

        # Matriz de medición
        # Solo observamos posición y tamaño, no velocidad
        self.H = np.eye(4, ndim)

        # Covarianza de proceso (ruido de proceso)
        self.Q = np.eye(ndim, ndim)
        self.Q[4:, 4:] *= 0.01  # Baja varianza en velocidad
        self.Q[5:, 5:] *= 0.01

        # Covarianza de medición (ruido de medición)
        self.R = np.eye(4, 4)

    def initiate(self, bbox: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Inicializar un nuevo track.

        Args:
            bbox: [x1, y1, x2, y2]

        Returns:
            (mean, covariance)
        """
        # Convertir bbox a [x, y, w, h]
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        width = x2 - x1
        height = y2 - y1
        ratio = width / max(height, 1e-6)

        # Estado inicial
        mean = np.array([
            center_x, center_y, width, height, ratio,
            0.0, 0.0  # Velocidad inicial 0
        ], dtype=float)

        # Covarianza inicial
        covariance = np.eye(7, 7)
        covariance[:4, :4] *= (self.STD_WEIGHT_POSITION * max(width, height)) ** 2
        covariance[4, 4] *= (self.STD_WEIGHT_POSITION * max(width, height)) ** 2
        covariance[5:, 5:] *= (self.STD_WEIGHT_VELOCITY * max(width, height)) ** 2

        return mean, covariance

    def predict(self,
                mean: np.ndarray,
                covariance: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predecir estado en siguiente frame.

        Args:
            mean: Estado actual [x, y, w, h, ratio, vx, vy]
            covariance: Covarianza actual

        Returns:
            (predicted_mean, predicted_covariance)
        """
        # Predecir nueva media
        std_pos = np.sqrt((self.STD_WEIGHT_POSITION * mean[2:4]).prod())
        std_vel = np.sqrt((self.STD_WEIGHT_VELOCITY * mean[2:4]).prod())

        motion_cov = np.eye(7, 7)
        motion_cov[:4, :4] *= (std_pos ** 2)
        motion_cov[5:, 5:] *= (std_vel ** 2)

        predicted_mean = self.F @ mean
        predicted_cov = self.F @ covariance @ self.F.T + motion_cov

        return predicted_mean, predicted_cov

    def update(self,
               mean: np.ndarray,
               covariance: np.ndarray,
               bbox: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Actualizar estado con nueva medición (detección).

        Args:
            mean: Estado predicho
            covariance: Covarianza predicha
            bbox: Nueva detección [x1, y1, x2, y2]

        Returns:
            (updated_mean, updated_covariance)
        """
        # Convertir bbox a medición
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        width = x2 - x1
        height = y2 - y1
        ratio = width / max(height, 1e-6)

        measurement = np.array([center_x, center_y, width, height])

        # Covarianza de medición
        std_pos = np.sqrt((self.STD_WEIGHT_POSITION * mean[2:4]).prod())
        measurement_cov = np.eye(4, 4)
        measurement_cov *= (std_pos ** 2)

        # Ganancia de Kalman
        innovation_cov = self.H @ covariance @ self.H.T + measurement_cov

        try:
            kalman_gain = covariance @ self.H.T @ np.linalg.inv(innovation_cov)
        except np.linalg.LinAlgError:
            # Si hay singularidad, usar pseudo-inversa
            kalman_gain = covariance @ self.H.T @ np.linalg.pinv(innovation_cov)

        # Innovación (diferencia entre medición y predicción)
        innovation = measurement - (self.H @ mean)

        # Actualizar media y covarianza
        updated_mean = mean + kalman_gain @ innovation
        updated_cov = (np.eye(7, 7) - kalman_gain @ self.H) @ covariance

        # Asegurar que la velocidad sea consistente
        updated_mean[5:7] = (updated_mean[:2] - mean[:2])  # Velocidad = cambio de posición

        return updated_mean, updated_cov

    def gating_distance(self,
                       mean: np.ndarray,
                       covariance: np.ndarray,
                       bbox: np.ndarray) -> float:
        """
        Calcula distancia de Mahalanobis (gating).

        Mide qué tan probable es que la detección pertenece a este track.

        Args:
            mean: Estado predicho
            covariance: Covarianza predicha
            bbox: Detección [x1, y1, x2, y2]

        Returns:
            Distancia de Mahalanobis (menor = más probable)
        """
        # Convertir bbox a medición
        x1, y1, x2, y2 = bbox
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        width = x2 - x1
        height = y2 - y1

        measurement = np.array([center_x, center_y, width, height])

        # Innovación
        innovation = measurement - (self.H @ mean)

        # Covarianza de innovación
        std_pos = np.sqrt((self.STD_WEIGHT_POSITION * mean[2:4]).prod())
        innovation_cov = self.H @ covariance @ self.H.T
        innovation_cov += np.eye(4, 4) * (std_pos ** 2)

        try:
            innovation_cov_inv = np.linalg.inv(innovation_cov)
        except np.linalg.LinAlgError:
            innovation_cov_inv = np.linalg.pinv(innovation_cov)

        # Distancia de Mahalanobis
        distance = np.sqrt(innovation @ innovation_cov_inv @ innovation.T)

        return float(distance)


class TrackState:
    """Representa el estado de un track individual"""

    def __init__(self,
                 mean: np.ndarray,
                 covariance: np.ndarray,
                 track_id: int):
        self.mean = mean
        self.covariance = covariance
        self.track_id = track_id

        self.hits = 1  # Número de detecciones exitosas
        self.age = 1   # Edad del track
        self.time_since_update = 0  # Frames sin actualización

        self.is_tentative = True  # No confirmado aún
        self.is_confirmed = False


__all__ = ['KalmanFilter', 'TrackState']

"""
homography_validator.py - Validar calidad de transformación de perspectiva

Propósito: Determinar si la homografía (transformación de cancha) es válida
y confiable para cálculos de posición/distancia
"""
import numpy as np
from pathlib import Path


class HomographyValidator:
    """Valida la calidad y confiabilidad de una transformación de perspectiva"""

    def __init__(self, keypoints_xy, keypoints_confidence, pitch_vertices,
                 min_confidence=0.5, min_valid_points=3):
        """
        Args:
            keypoints_xy (np.array): Shape (N, 2) - puntos de la cancha detectados
            keypoints_confidence (np.array): Shape (N,) - confianza de cada punto
            pitch_vertices (np.array): Shape (4, 2) - vértices esperados de la cancha
            min_confidence (float): Confianza mínima requerida
            min_valid_points (int): Mínimo de puntos válidos necesarios
        """
        self.keypoints_xy = keypoints_xy
        self.keypoints_confidence = keypoints_confidence
        self.pitch_vertices = pitch_vertices
        self.min_confidence = min_confidence
        self.min_valid_points = min_valid_points

        self.is_valid_flag = False
        self.quality_score = 0.0
        self.failure_reasons = []
        self.diagnostics = {}

        self._validate()

    def _validate(self):
        """Ejecuta todas las validaciones"""
        self.failure_reasons = []
        self.diagnostics = {}

        # 1. Validar confianza mínima de puntos
        valid_mask = self.keypoints_confidence > self.min_confidence
        valid_points = self.keypoints_xy[valid_mask]
        valid_count = len(valid_points)

        self.diagnostics['valid_points'] = valid_count
        self.diagnostics['required_points'] = self.min_valid_points
        self.diagnostics['avg_confidence'] = float(np.mean(self.keypoints_confidence))

        if valid_count < self.min_valid_points:
            self.failure_reasons.append(
                f'Insuficientes puntos válidos: {valid_count} < {self.min_valid_points}'
            )
            self.is_valid_flag = False
            self.quality_score = 0.0
            return

        # 2. Validar dispersión de puntos (deben estar bien distribuidos)
        spread = self._check_keypoint_spread(valid_points)
        self.diagnostics['point_spread'] = spread

        # Más permisivo: permitir spread menor si tenemos al menos 3 puntos
        min_spread_threshold = 0.15 if valid_count >= 3 else 0.3
        if spread < min_spread_threshold:
            self.failure_reasons.append(
                f'Puntos muy concentrados (spread: {spread:.2f})'
            )
            self.is_valid_flag = False
            self.quality_score = spread * 0.5  # Penalizar pero no rechazar completamente
            return

        # 3. Validar que puntos correspondan a estructura rectangular
        if not self._check_rectangular_structure(valid_points):
            self.failure_reasons.append('Puntos no forman estructura rectangular')
            self.is_valid_flag = False
            self.quality_score = 0.3
            return

        # 4. Validar que no haya oclusión parcial
        occlusion_level = self._check_occlusion(valid_points)
        self.diagnostics['occlusion_level'] = occlusion_level

        if occlusion_level > 0.5:
            self.failure_reasons.append(
                f'Posible oclusión alta: {occlusion_level:.2f}'
            )
            self.is_valid_flag = False
            self.quality_score = (1 - occlusion_level) * 0.7
            return

        # Si llegó aquí, la transformación es válida
        self.is_valid_flag = True

        # Calcular quality score final
        confidence_factor = np.mean(self.keypoints_confidence[valid_mask])
        spread_factor = min(spread, 1.0)
        occlusion_factor = 1 - occlusion_level

        self.quality_score = (confidence_factor * 0.4 +
                             spread_factor * 0.3 +
                             occlusion_factor * 0.3)

    def _check_keypoint_spread(self, points):
        """Verifica que los puntos estén distribuidos en el espacio"""
        if len(points) < 2:
            return 0.0

        # Calcular área de la envolvente convexa (aproximada)
        x_range = np.max(points[:, 0]) - np.min(points[:, 0])
        y_range = np.max(points[:, 1]) - np.min(points[:, 1])

        # Spread normalizado (0-1)
        area = x_range * y_range
        # Asumir que máxima área posible es 1000x1000 píxeles
        spread = min(area / (1000 * 1000), 1.0)

        return spread

    def _check_rectangular_structure(self, points):
        """Verifica que puntos formen aproximadamente un rectángulo (3+ puntos suficientes)"""
        if len(points) < 3:
            return False

        # Puntos deben estar en los 4 ángulos aproximadamente
        x_coords = points[:, 0]
        y_coords = points[:, 1]

        x_unique = len(np.unique(np.round(x_coords / 50)))  # Agrupar por 50px
        y_unique = len(np.unique(np.round(y_coords / 50)))

        # Esperamos al menos 2 valores x distintos y 2 valores y distintos
        is_rectangular = x_unique >= 2 and y_unique >= 2

        self.diagnostics['x_clusters'] = x_unique
        self.diagnostics['y_clusters'] = y_unique

        return is_rectangular

    def _check_occlusion(self, points):
        """Detecta si hay oclusión parcial de la cancha (3+ puntos aceptados)"""
        if len(points) < 3:
            return 0.7  # Mayor tolerancia para 3+ puntos

        # Si faltan puntos de esquinas → probable oclusión
        x_coords = points[:, 0]
        y_coords = points[:, 1]

        # Puntos en esquinas (cuadrantes)
        quadrant_coverage = 0
        if np.any((x_coords < np.median(x_coords)) & (y_coords < np.median(y_coords))):
            quadrant_coverage += 1
        if np.any((x_coords >= np.median(x_coords)) & (y_coords < np.median(y_coords))):
            quadrant_coverage += 1
        if np.any((x_coords < np.median(x_coords)) & (y_coords >= np.median(y_coords))):
            quadrant_coverage += 1
        if np.any((x_coords >= np.median(x_coords)) & (y_coords >= np.median(y_coords))):
            quadrant_coverage += 1

        # Oclusión = 1 - (cuadrantes cubiertos / 4)
        occlusion = 1 - (quadrant_coverage / 4)

        return occlusion

    def is_valid(self):
        """Retorna si la homografía es válida"""
        return self.is_valid_flag

    def get_quality_score(self):
        """Retorna score de calidad 0-1"""
        return self.quality_score

    def get_diagnostics(self):
        """Retorna dict con diagnósticos detallados"""
        return {
            'valid': self.is_valid_flag,
            'quality_score': self.quality_score,
            'reasons': self.failure_reasons,
            'details': self.diagnostics,
        }

    def __repr__(self):
        status = "✓ VÁLIDA" if self.is_valid_flag else "✗ INVÁLIDA"
        return (f"HomographyValidator({status}, "
                f"score: {self.quality_score:.2f}, "
                f"points: {self.diagnostics.get('valid_points', 0)})")

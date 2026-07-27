"""
distance_velocity_calculator.py - Calculador de distancia y velocidad

Propósito: Proporcionar cálculos precisos de distancia, velocidad y análisis
de movimiento para jugadores en video de deportes. Incluye calibración automática,
manejo de oclusiones y validación de datos.

Funcionalidades:
- DistanceCalculator: Cálculo de distancia total en metros
- VelocityCalculator: Análisis de velocidad (máx, prom, mediana, percentiles)
- MovementAnalyzer: Análisis de aceleración, desaceleración, cambios de dirección
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import json
from pathlib import Path
import logging
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


@dataclass
class TrackPoint:
    """Punto en el track de un jugador"""
    frame: int
    x: float
    y: float
    confidence: float = 1.0
    is_interpolated: bool = False


@dataclass
class DistanceMetrics:
    """Métricas de distancia calculadas"""
    total_distance: float  # metros
    distance_by_frame: List[float] = field(default_factory=list)
    cumulative_distance: List[float] = field(default_factory=list)
    jump_detections: List[Dict[str, Any]] = field(default_factory=list)
    interpolated_frames: int = 0
    confidence_avg: float = 1.0


@dataclass
class VelocityMetrics:
    """Métricas de velocidad calculadas"""
    velocity_per_frame: List[float] = field(default_factory=list)
    max_velocity: float = 0.0
    min_velocity: float = 0.0
    average_velocity: float = 0.0
    median_velocity: float = 0.0
    std_velocity: float = 0.0
    percentile_90: float = 0.0
    percentile_95: float = 0.0
    percentile_99: float = 0.0


@dataclass
class MovementMetrics:
    """Métricas de movimiento general"""
    acceleration: List[float] = field(default_factory=list)
    deceleration: List[float] = field(default_factory=list)
    max_acceleration: float = 0.0
    max_deceleration: float = 0.0
    average_acceleration: float = 0.0
    directional_changes: int = 0
    direction_angles: List[float] = field(default_factory=list)
    distance_by_quadrant: Dict[str, float] = field(
        default_factory=lambda: {
            'top_left': 0.0,
            'top_right': 0.0,
            'bottom_left': 0.0,
            'bottom_right': 0.0
        }
    )
    distance_by_zone: Dict[str, float] = field(default_factory=dict)


class DistanceCalculator:
    """
    Calcula la distancia total recorrida por un jugador en un video.

    Utiliza la fórmula euclidiana para calcular distancia entre frames
    consecutivos. Implementa filtrado de saltos (oclusiones) y suavizado
    de ruido mediante Kalman filter.

    Attributes:
        pixels_per_meter (float): Calibración de píxeles a metros
        max_jump_distance (float): Distancia máxima permitida entre frames (metros)
        use_kalman_filter (bool): Si aplicar filtro de Kalman
    """

    def __init__(
        self,
        pixels_per_meter: Optional[float] = None,
        max_jump_distance: float = 5.0,
        use_kalman_filter: bool = True,
        frame_rate: float = 30.0
    ):
        """
        Inicializa el calculador de distancia.

        Args:
            pixels_per_meter: Píxeles por metro. Si es None, se calibra automáticamente
            max_jump_distance: Distancia máxima en metros para detectar oclusiones (default: 5.0)
            use_kalman_filter: Si aplicar Kalman filter para suavizado (default: True)
            frame_rate: FPS del video (default: 30.0)
        """
        self.pixels_per_meter = pixels_per_meter
        self.max_jump_distance = max_jump_distance
        self.use_kalman_filter = use_kalman_filter
        self.frame_rate = frame_rate
        self.q_estimate = 0.0001  # Kalman filter Q parameter
        self.r_estimate = 0.01    # Kalman filter R parameter

    def pixels_to_meters(self, pixels: float) -> float:
        """Convierte píxeles a metros usando la calibración."""
        if self.pixels_per_meter is None:
            logger.warning("pixels_per_meter no está calibrado, usando 1.0")
            return pixels
        return pixels / self.pixels_per_meter

    def meters_to_pixels(self, meters: float) -> float:
        """Convierte metros a píxeles usando la calibración."""
        if self.pixels_per_meter is None:
            return meters
        return meters * self.pixels_per_meter

    def calibrate_pixels_per_meter(
        self,
        reference_distance_pixels: float,
        reference_distance_meters: float
    ) -> None:
        """
        Calibra la conversión de píxeles a metros usando distancia de referencia.

        Args:
            reference_distance_pixels: Distancia conocida en píxeles
            reference_distance_meters: Distancia conocida en metros (ej: 10.0)
        """
        if reference_distance_pixels > 0:
            self.pixels_per_meter = reference_distance_pixels / reference_distance_meters
            logger.info(f"Calibración: {self.pixels_per_meter:.4f} píxeles/metro")

    def smooth_trajectory_kalman(
        self,
        trajectory: List[TrackPoint]
    ) -> List[TrackPoint]:
        """
        Aplica Kalman filter para suavizar trayectoria.

        Args:
            trajectory: Lista de puntos de track

        Returns:
            Lista de puntos suavizados
        """
        if len(trajectory) < 2 or not self.use_kalman_filter:
            return trajectory

        smoothed = []

        # Estado inicial: [x, y, vx, vy]
        x_est = np.array([trajectory[0].x, trajectory[0].y, 0.0, 0.0])
        p_est = np.eye(4) * 0.1

        for i, point in enumerate(trajectory):
            # Medición
            z = np.array([point.x, point.y])

            # Predicción
            if i > 0:
                dt = 1.0 / self.frame_rate
                F = np.array([
                    [1, 0, dt, 0],
                    [0, 1, 0, dt],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1]
                ])
                x_est = F @ x_est
                p_est = F @ p_est @ F.T + self.q_estimate * np.eye(4)

            # Actualización
            H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]])
            z_pred = H @ x_est
            y = z - z_pred
            S = H @ p_est @ H.T + self.r_estimate * np.eye(2)
            K = p_est @ H.T @ np.linalg.inv(S)

            # Actualizar estado (K es 4x2, y es 2x1)
            x_est = x_est + (K @ y.reshape(-1, 1)).flatten()
            p_est = (np.eye(4) - K @ H) @ p_est

            # Crear punto suavizado
            smoothed_point = TrackPoint(
                frame=point.frame,
                x=float(x_est[0]),
                y=float(x_est[1]),
                confidence=point.confidence,
                is_interpolated=point.is_interpolated
            )
            smoothed.append(smoothed_point)

        return smoothed

    def detect_jumps(
        self,
        trajectory: List[TrackPoint]
    ) -> List[Dict[str, Any]]:
        """
        Detecta saltos en la trayectoria (posibles oclusiones).

        Args:
            trajectory: Lista de puntos de track

        Returns:
            Lista de saltos detectados con información
        """
        jumps = []
        max_jump_pixels = self.meters_to_pixels(self.max_jump_distance)

        for i in range(1, len(trajectory)):
            p1 = trajectory[i - 1]
            p2 = trajectory[i]

            dx = p2.x - p1.x
            dy = p2.y - p1.y
            distance_pixels = np.sqrt(dx**2 + dy**2)
            distance_meters = self.pixels_to_meters(distance_pixels)

            if distance_pixels > max_jump_pixels:
                jumps.append({
                    'frame_from': p1.frame,
                    'frame_to': p2.frame,
                    'distance_pixels': distance_pixels,
                    'distance_meters': distance_meters,
                    'severity': distance_meters / self.max_jump_distance
                })

        return jumps

    def interpolate_missing_frames(
        self,
        trajectory: List[TrackPoint],
        max_gap: int = 5
    ) -> List[TrackPoint]:
        """
        Interpola puntos faltantes en la trayectoria.

        Args:
            trajectory: Lista de puntos de track
            max_gap: Máximo número de frames a interpolar

        Returns:
            Trayectoria con frames interpolados
        """
        if len(trajectory) < 2:
            return trajectory

        interpolated = [trajectory[0]]
        interpolated_count = 0

        for i in range(1, len(trajectory)):
            prev = trajectory[i - 1]
            curr = trajectory[i]
            frame_gap = curr.frame - prev.frame

            if frame_gap > 1 and frame_gap <= max_gap:
                # Interpolar linealmente
                for j in range(1, frame_gap):
                    alpha = j / frame_gap
                    x = prev.x + alpha * (curr.x - prev.x)
                    y = prev.y + alpha * (curr.y - prev.y)

                    interp_point = TrackPoint(
                        frame=prev.frame + j,
                        x=x,
                        y=y,
                        confidence=min(prev.confidence, curr.confidence),
                        is_interpolated=True
                    )
                    interpolated.append(interp_point)
                    interpolated_count += 1

            interpolated.append(curr)

        return sorted(interpolated, key=lambda p: p.frame), interpolated_count

    def calculate_total_distance(
        self,
        trajectory: List[TrackPoint],
        remove_jumps: bool = True,
        smooth: bool = True
    ) -> Tuple[DistanceMetrics, List[TrackPoint]]:
        """
        Calcula la distancia total recorrida.

        Args:
            trajectory: Lista de puntos [x, y] por frame
            remove_jumps: Si filtrar saltos por oclusiones (default: True)
            smooth: Si aplicar suavizado (default: True)

        Returns:
            Tupla (DistanceMetrics, trayectoria_procesada)
        """
        if len(trajectory) < 2:
            metrics = DistanceMetrics(
                total_distance=0.0,
                distance_by_frame=[],
                cumulative_distance=[],
                jump_detections=[],
                interpolated_frames=0
            )
            return metrics, trajectory

        # Copiar y procesar trayectoria
        processed = trajectory.copy()

        # Interpolación
        processed, interpolated_count = self.interpolate_missing_frames(processed)

        # Suavizado
        if smooth:
            processed = self.smooth_trajectory_kalman(processed)

        # Detección de saltos
        jumps = self.detect_jumps(processed)

        # Calcular distancias frame por frame
        distances = []
        cumulative = 0.0
        confidence_scores = []

        for i in range(1, len(processed)):
            p1 = processed[i - 1]
            p2 = processed[i]

            dx = p2.x - p1.x
            dy = p2.y - p1.y
            distance_pixels = np.sqrt(dx**2 + dy**2)
            distance_meters = self.pixels_to_meters(distance_pixels)

            # Filtrar saltos si está habilitado
            if remove_jumps and distance_meters > self.max_jump_distance:
                # No contar esta distancia
                distances.append(0.0)
            else:
                distances.append(distance_meters)
                cumulative += distance_meters

            # Promediar confidencia
            avg_conf = (p1.confidence + p2.confidence) / 2
            confidence_scores.append(avg_conf)

        # Crear métricas
        cumulative_dist = np.cumsum([0.0] + distances).tolist()

        metrics = DistanceMetrics(
            total_distance=cumulative,
            distance_by_frame=distances,
            cumulative_distance=cumulative_dist,
            jump_detections=jumps,
            interpolated_frames=interpolated_count,
            confidence_avg=np.mean(confidence_scores) if confidence_scores else 1.0
        )

        return metrics, processed


class VelocityCalculator:
    """
    Calcula métricas de velocidad basadas en distancia y tiempo.

    Proporciona cálculos de velocidad instantánea, máxima, promedio,
    mediana y percentiles.

    Attributes:
        fps (float): Fotogramas por segundo del video
        frame_window (int): Ventana para calcular velocidad media
    """

    def __init__(self, fps: float = 30.0, frame_window: int = 1):
        """
        Inicializa el calculador de velocidad.

        Args:
            fps: Fotogramas por segundo (default: 30)
            frame_window: Ventana de frames para suavizar velocidad (default: 1)
        """
        self.fps = fps
        self.frame_window = max(1, frame_window)
        self.time_per_frame = 1.0 / fps

    def calculate_velocity_per_frame(
        self,
        distances: List[float]
    ) -> List[float]:
        """
        Calcula velocidad por frame desde distancias.

        Args:
            distances: Lista de distancias por frame (en metros)

        Returns:
            Lista de velocidades (m/s)
        """
        if not distances:
            return []

        velocities = []
        for distance in distances:
            velocity = distance / self.time_per_frame
            velocities.append(velocity)

        # Aplicar suavizado si frame_window > 1
        if self.frame_window > 1:
            velocities = self._smooth_velocities(velocities)

        return velocities

    def _smooth_velocities(self, velocities: List[float]) -> List[float]:
        """Suaviza velocidades usando media móvil."""
        if len(velocities) <= self.frame_window:
            return velocities

        smoothed = []
        for i in range(len(velocities)):
            start = max(0, i - self.frame_window // 2)
            end = min(len(velocities), i + self.frame_window // 2 + 1)
            window = velocities[start:end]
            smoothed.append(np.mean(window))

        return smoothed

    def max_velocity(self, velocities: List[float]) -> float:
        """Retorna la velocidad máxima."""
        return float(np.max(velocities)) if velocities else 0.0

    def min_velocity(self, velocities: List[float]) -> float:
        """Retorna la velocidad mínima (excluyendo ceros)."""
        if not velocities:
            return 0.0
        non_zero = [v for v in velocities if v > 0.001]
        return float(np.min(non_zero)) if non_zero else 0.0

    def average_velocity(self, velocities: List[float]) -> float:
        """Retorna la velocidad promedio."""
        return float(np.mean(velocities)) if velocities else 0.0

    def median_velocity(self, velocities: List[float]) -> float:
        """Retorna la velocidad mediana."""
        return float(np.median(velocities)) if velocities else 0.0

    def std_velocity(self, velocities: List[float]) -> float:
        """Retorna la desviación estándar de velocidad."""
        return float(np.std(velocities)) if velocities else 0.0

    def percentile_velocity(self, velocities: List[float], percentile: float) -> float:
        """
        Calcula velocidad en un percentil específico.

        Args:
            velocities: Lista de velocidades
            percentile: Percentil (0-100), ej: 90 para p90

        Returns:
            Velocidad en el percentil especificado
        """
        if not velocities:
            return 0.0
        return float(np.percentile(velocities, percentile))

    def calculate_velocity_metrics(
        self,
        distances: List[float]
    ) -> VelocityMetrics:
        """
        Calcula todas las métricas de velocidad.

        Args:
            distances: Lista de distancias por frame (metros)

        Returns:
            VelocityMetrics con todos los cálculos
        """
        velocities = self.calculate_velocity_per_frame(distances)

        metrics = VelocityMetrics(
            velocity_per_frame=velocities,
            max_velocity=self.max_velocity(velocities),
            min_velocity=self.min_velocity(velocities),
            average_velocity=self.average_velocity(velocities),
            median_velocity=self.median_velocity(velocities),
            std_velocity=self.std_velocity(velocities),
            percentile_90=self.percentile_velocity(velocities, 90),
            percentile_95=self.percentile_velocity(velocities, 95),
            percentile_99=self.percentile_velocity(velocities, 99)
        )

        return metrics


class MovementAnalyzer:
    """
    Analiza patrones de movimiento complejo.

    Proporciona análisis de aceleración, desaceleración, cambios de dirección
    y distribución espacial del movimiento.

    Attributes:
        fps (float): Fotogramas por segundo
        quadrant_width (float): Ancho del cuadrante para análisis zonal
        quadrant_height (float): Altura del cuadrante
    """

    def __init__(
        self,
        fps: float = 30.0,
        quadrant_width: Optional[float] = None,
        quadrant_height: Optional[float] = None
    ):
        """
        Inicializa el analizador de movimiento.

        Args:
            fps: Fotogramas por segundo
            quadrant_width: Ancho de referencia para cuadrantes
            quadrant_height: Altura de referencia para cuadrantes
        """
        self.fps = fps
        self.time_per_frame = 1.0 / fps
        self.quadrant_width = quadrant_width
        self.quadrant_height = quadrant_height

    def calculate_acceleration(
        self,
        velocities: List[float]
    ) -> List[float]:
        """
        Calcula aceleración frame por frame.

        Args:
            velocities: Lista de velocidades (m/s)

        Returns:
            Lista de aceleraciones (m/s²)
        """
        if len(velocities) < 2:
            return []

        accelerations = []
        for i in range(1, len(velocities)):
            dv = velocities[i] - velocities[i - 1]
            accel = dv / self.time_per_frame
            accelerations.append(accel)

        return accelerations

    def calculate_deceleration(
        self,
        accelerations: List[float]
    ) -> List[float]:
        """
        Extrae solo las desaceleraciones (aceleraciones negativas).

        Args:
            accelerations: Lista de aceleraciones

        Returns:
            Lista de desaceleraciones (valores absolutos)
        """
        decel = [abs(a) for a in accelerations if a < 0]
        return decel

    def calculate_directional_changes(
        self,
        trajectory: List[TrackPoint]
    ) -> Tuple[int, List[float]]:
        """
        Calcula cambios de dirección en la trayectoria.

        Args:
            trajectory: Lista de puntos de track

        Returns:
            Tupla (número de cambios, lista de ángulos)
        """
        if len(trajectory) < 3:
            return 0, []

        angles = []
        changes = 0
        threshold_angle = 10.0  # grados

        for i in range(1, len(trajectory) - 1):
            p1 = trajectory[i - 1]
            p2 = trajectory[i]
            p3 = trajectory[i + 1]

            # Vectores de dirección
            v1 = np.array([p2.x - p1.x, p2.y - p1.y])
            v2 = np.array([p3.x - p2.x, p3.y - p2.y])

            # Magnitudes
            mag1 = np.linalg.norm(v1)
            mag2 = np.linalg.norm(v2)

            if mag1 > 0 and mag2 > 0:
                # Ángulo entre vectores
                cos_angle = np.dot(v1, v2) / (mag1 * mag2)
                cos_angle = np.clip(cos_angle, -1, 1)
                angle_rad = np.arccos(cos_angle)
                angle_deg = np.degrees(angle_rad)

                angles.append(angle_deg)

                if angle_deg > threshold_angle:
                    changes += 1

        return changes, angles

    def calculate_distance_by_quadrant(
        self,
        trajectory: List[TrackPoint],
        distances: List[float],
        field_width: float,
        field_height: float
    ) -> Dict[str, float]:
        """
        Calcula distancia recorrida en cada cuadrante.

        Args:
            trajectory: Lista de puntos de track
            distances: Distancias frame por frame
            field_width: Ancho del campo (píxeles)
            field_height: Altura del campo (píxeles)

        Returns:
            Diccionario con distancias por cuadrante
        """
        quadrants = {
            'top_left': 0.0,
            'top_right': 0.0,
            'bottom_left': 0.0,
            'bottom_right': 0.0
        }

        mid_x = field_width / 2
        mid_y = field_height / 2

        for i in range(1, len(trajectory)):
            point = trajectory[i]
            distance = distances[i - 1] if i - 1 < len(distances) else 0.0

            if point.x < mid_x and point.y < mid_y:
                quadrants['top_left'] += distance
            elif point.x >= mid_x and point.y < mid_y:
                quadrants['top_right'] += distance
            elif point.x < mid_x and point.y >= mid_y:
                quadrants['bottom_left'] += distance
            else:
                quadrants['bottom_right'] += distance

        return quadrants

    def calculate_movement_metrics(
        self,
        trajectory: List[TrackPoint],
        velocities: List[float],
        distances: List[float],
        field_width: Optional[float] = None,
        field_height: Optional[float] = None
    ) -> MovementMetrics:
        """
        Calcula todas las métricas de movimiento.

        Args:
            trajectory: Lista de puntos de track
            velocities: Lista de velocidades
            distances: Lista de distancias por frame
            field_width: Ancho del campo (píxeles)
            field_height: Altura del campo (píxeles)

        Returns:
            MovementMetrics con todos los cálculos
        """
        # Aceleración y desaceleración
        accelerations = self.calculate_acceleration(velocities)
        decelerations = self.calculate_deceleration(accelerations)

        max_accel = float(np.max(accelerations)) if accelerations else 0.0
        max_decel = float(np.max(decelerations)) if decelerations else 0.0
        avg_accel = float(np.mean(accelerations)) if accelerations else 0.0

        # Cambios de dirección
        num_changes, angles = self.calculate_directional_changes(trajectory)

        # Distancia por cuadrante
        if field_width and field_height:
            quad_dist = self.calculate_distance_by_quadrant(
                trajectory, distances, field_width, field_height
            )
        else:
            quad_dist = {
                'top_left': 0.0,
                'top_right': 0.0,
                'bottom_left': 0.0,
                'bottom_right': 0.0
            }

        metrics = MovementMetrics(
            acceleration=accelerations,
            deceleration=decelerations,
            max_acceleration=max_accel,
            max_deceleration=max_decel,
            average_acceleration=avg_accel,
            directional_changes=num_changes,
            direction_angles=angles,
            distance_by_quadrant=quad_dist
        )

        return metrics


class DistanceVelocityAnalyzer:
    """
    Orquestador principal para análisis completo de distancia y velocidad.

    Combina DistanceCalculator, VelocityCalculator y MovementAnalyzer
    para proporcionar análisis integral.
    """

    def __init__(
        self,
        fps: float = 30.0,
        pixels_per_meter: Optional[float] = None,
        max_jump_distance: float = 5.0
    ):
        """
        Inicializa el analizador.

        Args:
            fps: Fotogramas por segundo
            pixels_per_meter: Calibración de píxeles a metros
            max_jump_distance: Distancia máxima para detectar oclusiones
        """
        self.fps = fps
        self.pixels_per_meter = pixels_per_meter

        self.distance_calc = DistanceCalculator(
            pixels_per_meter=pixels_per_meter,
            max_jump_distance=max_jump_distance,
            frame_rate=fps
        )
        self.velocity_calc = VelocityCalculator(fps=fps)
        self.movement_analyzer = MovementAnalyzer(fps=fps)

    def analyze_player_trajectory(
        self,
        trajectory: List[TrackPoint],
        field_width: Optional[float] = None,
        field_height: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Realiza análisis completo de trayectoria de jugador.

        Args:
            trajectory: Lista de puntos TrackPoint
            field_width: Ancho del campo (píxeles)
            field_height: Altura del campo (píxeles)

        Returns:
            Diccionario con todos los análisis
        """
        # Calcular distancia
        distance_metrics, processed_trajectory = self.distance_calc.calculate_total_distance(
            trajectory
        )

        # Calcular velocidad
        velocity_metrics = self.velocity_calc.calculate_velocity_metrics(
            distance_metrics.distance_by_frame
        )

        # Analizar movimiento
        movement_metrics = self.movement_analyzer.calculate_movement_metrics(
            processed_trajectory,
            velocity_metrics.velocity_per_frame,
            distance_metrics.distance_by_frame,
            field_width,
            field_height
        )

        return {
            'distance': distance_metrics,
            'velocity': velocity_metrics,
            'movement': movement_metrics,
            'summary': {
                'total_frames': len(processed_trajectory),
                'fps': self.fps,
                'duration_seconds': len(processed_trajectory) / self.fps
            }
        }

    def export_analysis_json(
        self,
        analysis: Dict[str, Any],
        output_path: Path
    ) -> None:
        """
        Exporta análisis a archivo JSON.

        Args:
            analysis: Diccionario de análisis
            output_path: Ruta del archivo de salida
        """
        # Convertir objetos dataclass a diccionarios
        export_data = {
            'distance': {
                'total_distance': analysis['distance'].total_distance,
                'distance_by_frame': analysis['distance'].distance_by_frame,
                'cumulative_distance': analysis['distance'].cumulative_distance,
                'jump_detections': analysis['distance'].jump_detections,
                'interpolated_frames': analysis['distance'].interpolated_frames,
                'confidence_avg': analysis['distance'].confidence_avg
            },
            'velocity': {
                'max_velocity': analysis['velocity'].max_velocity,
                'min_velocity': analysis['velocity'].min_velocity,
                'average_velocity': analysis['velocity'].average_velocity,
                'median_velocity': analysis['velocity'].median_velocity,
                'std_velocity': analysis['velocity'].std_velocity,
                'percentile_90': analysis['velocity'].percentile_90,
                'percentile_95': analysis['velocity'].percentile_95,
                'percentile_99': analysis['velocity'].percentile_99
            },
            'movement': {
                'max_acceleration': analysis['movement'].max_acceleration,
                'max_deceleration': analysis['movement'].max_deceleration,
                'average_acceleration': analysis['movement'].average_acceleration,
                'directional_changes': analysis['movement'].directional_changes,
                'distance_by_quadrant': analysis['movement'].distance_by_quadrant
            },
            'summary': analysis['summary']
        }

        # Crear directorio si no existe
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Guardar JSON
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Análisis exportado a {output_path}")

    def generate_report(self, analysis: Dict[str, Any]) -> str:
        """
        Genera un reporte textual del análisis.

        Args:
            analysis: Diccionario de análisis

        Returns:
            String con el reporte formateado
        """
        report = []
        report.append("=" * 60)
        report.append("REPORTE DE ANÁLISIS DE DISTANCIA Y VELOCIDAD")
        report.append("=" * 60)

        # Resumen
        summary = analysis['summary']
        report.append(f"\nDuración: {summary['duration_seconds']:.2f} segundos")
        report.append(f"Frames totales: {summary['total_frames']}")
        report.append(f"FPS: {summary['fps']}")

        # Distancia
        dist = analysis['distance']
        report.append(f"\n--- DISTANCIA ---")
        report.append(f"Distancia total: {dist.total_distance:.2f} metros")
        report.append(f"Frames interpolados: {dist.interpolated_frames}")
        report.append(f"Confianza promedio: {dist.confidence_avg:.3f}")
        report.append(f"Saltos detectados: {len(dist.jump_detections)}")

        # Velocidad
        vel = analysis['velocity']
        report.append(f"\n--- VELOCIDAD (m/s) ---")
        report.append(f"Máxima: {vel.max_velocity:.2f}")
        report.append(f"Mínima: {vel.min_velocity:.2f}")
        report.append(f"Promedio: {vel.average_velocity:.2f}")
        report.append(f"Mediana: {vel.median_velocity:.2f}")
        report.append(f"Std Dev: {vel.std_velocity:.2f}")
        report.append(f"P90: {vel.percentile_90:.2f}")
        report.append(f"P95: {vel.percentile_95:.2f}")
        report.append(f"P99: {vel.percentile_99:.2f}")

        # Movimiento
        mov = analysis['movement']
        report.append(f"\n--- MOVIMIENTO ---")
        report.append(f"Aceleración máxima: {mov.max_acceleration:.2f} m/s²")
        report.append(f"Desaceleración máxima: {mov.max_deceleration:.2f} m/s²")
        report.append(f"Aceleración promedio: {mov.average_acceleration:.2f} m/s²")
        report.append(f"Cambios de dirección: {mov.directional_changes}")

        # Cuadrantes
        report.append(f"\n--- DISTANCIA POR CUADRANTE ---")
        for quad, distance in mov.distance_by_quadrant.items():
            report.append(f"{quad}: {distance:.2f} metros")

        report.append("=" * 60)

        return "\n".join(report)

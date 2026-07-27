"""
intensity_analyzer.py - Análisis de intensidad y métricas avanzadas de juego

Propósito: Calcular intensidad de juego, categorizar movimientos y extraer
métricas avanzadas de performance deportivo (sprints, cambios de dirección, etc).

Funcionalidades:
- IntensityCalculator: % tiempo en movimiento activo
- MovementIntensity: Categorización de movimientos (estático, caminar, trotar, etc)
- AdvancedMetrics: Aceleración, desaceleración, sprints, cambios de dirección
- IntensityMetrics: Dataclass para almacenar resultados
- Exportación JSON y visualizaciones
"""

import numpy as np
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
import warnings

warnings.filterwarnings('ignore')


@dataclass
class MovementCategory:
    """Información sobre una categoría de movimiento"""
    name: str
    velocity_min: float
    velocity_max: float
    frame_count: int = 0
    duration_seconds: float = 0.0
    distance_covered: float = 0.0
    percentage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario"""
        return asdict(self)


@dataclass
class IntensityMetrics:
    """Dataclass para almacenar métricas de intensidad completas"""
    # Métricas básicas
    total_frames: int = 0
    total_duration_seconds: float = 0.0
    fps: float = 30.0

    # Intensidad general
    active_movement_percentage: float = 0.0
    average_velocity: float = 0.0
    max_velocity: float = 0.0
    min_velocity: float = 0.0

    # Categorías de movimiento
    movement_categories: Dict[str, MovementCategory] = field(default_factory=dict)

    # Métricas avanzadas
    average_acceleration: float = 0.0
    average_deceleration: float = 0.0
    max_acceleration: float = 0.0
    max_deceleration: float = 0.0

    # Sprints y alta intensidad
    sprint_count: int = 0
    total_sprint_distance: float = 0.0
    total_sprint_duration: float = 0.0
    high_intensity_distance: float = 0.0
    high_intensity_percentage: float = 0.0

    # Cambios de dirección
    direction_changes_count: int = 0
    average_direction_change_angle: float = 0.0
    sharp_direction_changes: int = 0  # > 90 grados

    # Recuperación
    total_recovery_time: float = 0.0
    average_recovery_time: float = 0.0
    recovery_attempts: int = 0

    # Distancia total
    total_distance: float = 0.0

    # Configuración utilizada
    velocity_threshold: float = 2.0
    sprint_threshold: float = 8.0
    high_intensity_threshold: float = 6.0
    direction_change_threshold: float = 45.0
    recovery_velocity_threshold: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario, incluyendo categorías"""
        data = asdict(self)
        # Convertir categorías a diccionario
        data['movement_categories'] = {
            name: cat.to_dict()
            for name, cat in self.movement_categories.items()
        }
        return data


class IntensityCalculator:
    """
    Calcula intensidad de juego basada en velocidades.

    Interpreta velocidades y determina qué porcentaje del tiempo
    el jugador estuvo en movimiento activo (v > threshold).
    """

    @staticmethod
    def calculate_intensity(velocity_array: np.ndarray,
                          threshold: float = 2.0) -> float:
        """
        Calcula el porcentaje de tiempo en movimiento activo.

        Args:
            velocity_array (np.ndarray): Array de velocidades por frame
            threshold (float): Velocidad mínima para considerar movimiento activo (m/s)

        Returns:
            float: Porcentaje de frames con v > threshold (0-100)

        Example:
            >>> velocities = np.array([0.5, 2.1, 3.5, 0.8, 5.0])
            >>> intensity = IntensityCalculator.calculate_intensity(velocities, 2.0)
            >>> print(f"Intensidad: {intensity:.1f}%")
            Intensidad: 60.0%
        """
        if len(velocity_array) == 0:
            return 0.0

        active_frames = np.sum(velocity_array > threshold)
        total_frames = len(velocity_array)

        intensity_percentage = (active_frames / total_frames) * 100.0
        return float(intensity_percentage)


class MovementIntensity:
    """
    Categoriza movimientos en intensidades predefinidas.

    Categorías de velocidad (m/s):
    - Estático: < 1.0 m/s
    - Caminando: 1.0 - 3.0 m/s
    - Trotando: 3.0 - 5.0 m/s
    - Corriendo: 5.0 - 8.0 m/s
    - Aceleración/Sprint: > 8.0 m/s
    """

    MOVEMENT_CATEGORIES = {
        'estatico': (0.0, 1.0),
        'caminando': (1.0, 3.0),
        'trotando': (3.0, 5.0),
        'corriendo': (5.0, 8.0),
        'aceleracion': (8.0, float('inf'))
    }

    @classmethod
    def categorize_movements(cls, velocity_array: np.ndarray,
                            fps: float = 30.0) -> Dict[str, MovementCategory]:
        """
        Categoriza frames según rango de velocidad.

        Args:
            velocity_array (np.ndarray): Array de velocidades por frame
            fps (float): Fotogramas por segundo para calcular duración

        Returns:
            Dict[str, MovementCategory]: Categorías con estadísticas

        Example:
            >>> velocities = np.array([0.5, 1.5, 3.5, 6.0, 9.0, 2.0])
            >>> categories = MovementIntensity.categorize_movements(velocities, fps=30)
            >>> for name, cat in categories.items():
            ...     print(f"{name}: {cat.frame_count} frames ({cat.percentage:.1f}%)")
        """
        categories = {}

        for cat_name, (v_min, v_max) in cls.MOVEMENT_CATEGORIES.items():
            mask = (velocity_array >= v_min) & (velocity_array < v_max)
            frame_count = np.sum(mask)
            duration = frame_count / fps if fps > 0 else 0.0
            distance = float(np.sum(velocity_array[mask]))
            percentage = (frame_count / len(velocity_array) * 100.0) if len(velocity_array) > 0 else 0.0

            categories[cat_name] = MovementCategory(
                name=cat_name,
                velocity_min=v_min,
                velocity_max=v_max,
                frame_count=int(frame_count),
                duration_seconds=float(duration),
                distance_covered=float(distance),
                percentage=float(percentage)
            )

        return categories

    @classmethod
    def get_movement_intensity_distribution(cls, categories: Dict[str, MovementCategory]) -> Dict[str, float]:
        """
        Retorna distribución de intensidades como porcentajes.

        Args:
            categories (Dict[str, MovementCategory]): Categorías calculadas

        Returns:
            Dict[str, float]: Distribución porcentual por categoría
        """
        return {
            name: cat.percentage
            for name, cat in categories.items()
        }


class AdvancedMetrics:
    """
    Calcula métricas avanzadas de performance deportivo.

    Incluye:
    - Aceleración y desaceleración promedio/máxima
    - Detección y conteo de sprints
    - Cambios de dirección
    - Tiempo de recuperación entre esfuerzos
    - Distancia en alta intensidad
    """

    @staticmethod
    def calculate_acceleration(velocity_array: np.ndarray,
                              fps: float = 30.0) -> Tuple[np.ndarray, float, float]:
        """
        Calcula aceleración frame-by-frame.

        Aceleración = cambio de velocidad / tiempo entre frames

        Args:
            velocity_array (np.ndarray): Array de velocidades
            fps (float): Fotogramas por segundo

        Returns:
            Tuple[np.ndarray, float, float]: (aceleración array, promedio, máximo)
        """
        if len(velocity_array) < 2:
            return np.array([]), 0.0, 0.0

        dt = 1.0 / fps  # Tiempo entre frames
        acceleration = np.diff(velocity_array) / dt

        # Acelerar y desacelerar (cambios positivos y negativos)
        avg_acceleration = float(np.mean(np.abs(acceleration)))
        max_acceleration = float(np.max(np.abs(acceleration)))

        return acceleration, avg_acceleration, max_acceleration

    @staticmethod
    def detect_sprints(velocity_array: np.ndarray,
                      sprint_threshold: float = 8.0,
                      min_sprint_frames: int = 5) -> List[Dict[str, Any]]:
        """
        Detecta sprints (periodos sostenidos de alta velocidad).

        Args:
            velocity_array (np.ndarray): Array de velocidades
            sprint_threshold (float): Velocidad mínima para considerar sprint (m/s)
            min_sprint_frames (int): Mínimo de frames para considerar un sprint

        Returns:
            List[Dict]: Lista de sprints con inicio, fin, duración y distancia

        Example:
            >>> velocities = np.array([3.0, 2.0, 9.0, 9.5, 8.5, 3.0, 10.0])
            >>> sprints = AdvancedMetrics.detect_sprints(velocities, 8.0)
            >>> for sprint in sprints:
            ...     print(f"Sprint {sprint['start']}-{sprint['end']}")
        """
        sprints = []
        in_sprint = False
        sprint_start = 0

        for i, velocity in enumerate(velocity_array):
            if velocity >= sprint_threshold:
                if not in_sprint:
                    sprint_start = i
                    in_sprint = True
            else:
                if in_sprint:
                    sprint_duration = i - sprint_start
                    if sprint_duration >= min_sprint_frames:
                        sprint_velocities = velocity_array[sprint_start:i]
                        sprints.append({
                            'start_frame': int(sprint_start),
                            'end_frame': int(i),
                            'duration_frames': int(sprint_duration),
                            'distance': float(np.sum(sprint_velocities)),
                            'peak_velocity': float(np.max(sprint_velocities)),
                            'avg_velocity': float(np.mean(sprint_velocities))
                        })
                    in_sprint = False

        # Manejar sprint que continúa hasta el final
        if in_sprint:
            sprint_duration = len(velocity_array) - sprint_start
            if sprint_duration >= min_sprint_frames:
                sprint_velocities = velocity_array[sprint_start:]
                sprints.append({
                    'start_frame': int(sprint_start),
                    'end_frame': int(len(velocity_array)),
                    'duration_frames': int(sprint_duration),
                    'distance': float(np.sum(sprint_velocities)),
                    'peak_velocity': float(np.max(sprint_velocities)),
                    'avg_velocity': float(np.mean(sprint_velocities))
                })

        return sprints

    @staticmethod
    def calculate_direction_changes(position_history: List[Tuple[float, float]],
                                   min_angle_threshold: float = 45.0) -> Tuple[int, float, int]:
        """
        Detecta y cuenta cambios de dirección significativos.

        Args:
            position_history (List[Tuple[float, float]]): Historial de posiciones (x, y)
            min_angle_threshold (float): Ángulo mínimo para considerar cambio de dirección (grados)

        Returns:
            Tuple[int, float, int]: (total cambios, ángulo promedio, cambios >90°)
        """
        if len(position_history) < 3:
            return 0, 0.0, 0

        change_count = 0
        change_angles = []
        sharp_changes = 0

        positions = np.array(position_history)

        # Calcular vectores de movimiento
        vectors = np.diff(positions, axis=0)

        for i in range(len(vectors) - 1):
            v1 = vectors[i]
            v2 = vectors[i + 1]

            # Magnitud de los vectores
            mag1 = np.linalg.norm(v1)
            mag2 = np.linalg.norm(v2)

            if mag1 < 1e-6 or mag2 < 1e-6:
                continue

            # Coseno del ángulo entre vectores
            cos_angle = np.dot(v1, v2) / (mag1 * mag2)
            cos_angle = np.clip(cos_angle, -1.0, 1.0)

            # Ángulo en grados
            angle = np.degrees(np.arccos(cos_angle))

            if angle >= min_angle_threshold:
                change_count += 1
                change_angles.append(angle)

                if angle > 90.0:
                    sharp_changes += 1

        avg_angle = float(np.mean(change_angles)) if change_angles else 0.0

        return change_count, avg_angle, sharp_changes

    @staticmethod
    def calculate_recovery_time(velocity_array: np.ndarray,
                               sprints: List[Dict],
                               recovery_threshold: float = 1.0,
                               fps: float = 30.0) -> Tuple[float, float, int]:
        """
        Calcula tiempo de recuperación entre sprints.

        Recuperación = tiempo en v < recovery_threshold después de un sprint.

        Args:
            velocity_array (np.ndarray): Array de velocidades
            sprints (List[Dict]): Sprints detectados
            recovery_threshold (float): Velocidad máxima durante recuperación (m/s)
            fps (float): Fotogramas por segundo

        Returns:
            Tuple[float, float, int]: (tiempo total, tiempo promedio, número de recuperaciones)
        """
        if not sprints:
            return 0.0, 0.0, 0

        recovery_times = []

        for sprint in sprints:
            sprint_end = sprint['end_frame']

            # Buscar periodo de recuperación después del sprint
            recovery_start = sprint_end
            recovery_frames = 0

            for i in range(sprint_end, min(sprint_end + 150, len(velocity_array))):
                if velocity_array[i] < recovery_threshold:
                    recovery_frames += 1
                elif recovery_frames > 0:
                    # Fin de la recuperación
                    break

            if recovery_frames > 0:
                recovery_time = recovery_frames / fps
                recovery_times.append(recovery_time)

        total_recovery = sum(recovery_times)
        avg_recovery = np.mean(recovery_times) if recovery_times else 0.0

        return float(total_recovery), float(avg_recovery), len(recovery_times)

    @staticmethod
    def calculate_high_intensity_distance(velocity_array: np.ndarray,
                                         high_intensity_threshold: float = 6.0) -> Tuple[float, float]:
        """
        Calcula distancia y porcentaje en alta intensidad (v > threshold).

        Args:
            velocity_array (np.ndarray): Array de velocidades
            high_intensity_threshold (float): Velocidad mínima para alta intensidad (m/s)

        Returns:
            Tuple[float, float]: (distancia total, porcentaje de distancia en alta intensidad)
        """
        total_distance = float(np.sum(velocity_array))

        if total_distance == 0:
            return 0.0, 0.0

        high_intensity_mask = velocity_array >= high_intensity_threshold
        high_intensity_distance = float(np.sum(velocity_array[high_intensity_mask]))
        high_intensity_percentage = (high_intensity_distance / total_distance * 100.0)

        return high_intensity_distance, high_intensity_percentage


class IntensityAnalyzer:
    """
    Analizador completo de intensidad que integra todos los componentes.

    Proporciona un interfaz unificado para:
    - Calcular todas las métricas de intensidad
    - Generar reportes detallados
    - Exportar datos a JSON
    - Crear visualizaciones
    """

    def __init__(self, fps: float = 30.0, output_dir: str = "data/logs"):
        """
        Inicializa el analizador de intensidad.

        Args:
            fps (float): Fotogramas por segundo del video
            output_dir (str): Directorio para guardar resultados
        """
        self.fps = fps
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def analyze(self, velocity_array: np.ndarray,
               position_history: Optional[List[Tuple[float, float]]] = None,
               config: Optional[Dict[str, float]] = None) -> IntensityMetrics:
        """
        Realiza análisis completo de intensidad.

        Args:
            velocity_array (np.ndarray): Array de velocidades por frame
            position_history (Optional[List]): Historial de posiciones
            config (Optional[Dict]): Configuración personalizada de umbrales

        Returns:
            IntensityMetrics: Métricas completas de intensidad
        """
        # Configuración por defecto
        cfg = {
            'velocity_threshold': 2.0,
            'sprint_threshold': 8.0,
            'high_intensity_threshold': 6.0,
            'direction_change_threshold': 45.0,
            'recovery_velocity_threshold': 1.0,
            'min_sprint_frames': 5
        }
        if config:
            cfg.update(config)

        # Crear métricas
        metrics = IntensityMetrics(
            total_frames=len(velocity_array),
            total_duration_seconds=len(velocity_array) / self.fps,
            fps=self.fps,
            velocity_threshold=cfg['velocity_threshold'],
            sprint_threshold=cfg['sprint_threshold'],
            high_intensity_threshold=cfg['high_intensity_threshold'],
            direction_change_threshold=cfg['direction_change_threshold'],
            recovery_velocity_threshold=cfg['recovery_velocity_threshold']
        )

        # Intensidad básica
        metrics.active_movement_percentage = IntensityCalculator.calculate_intensity(
            velocity_array, cfg['velocity_threshold']
        )
        metrics.average_velocity = float(np.mean(velocity_array))
        metrics.max_velocity = float(np.max(velocity_array)) if len(velocity_array) > 0 else 0.0
        metrics.min_velocity = float(np.min(velocity_array)) if len(velocity_array) > 0 else 0.0

        # Categorías de movimiento
        metrics.movement_categories = MovementIntensity.categorize_movements(
            velocity_array, self.fps
        )

        # Aceleración
        acceleration_array, avg_accel, max_accel = AdvancedMetrics.calculate_acceleration(
            velocity_array, self.fps
        )
        metrics.average_acceleration = avg_accel
        metrics.max_acceleration = max_accel

        # Desaceleración (cambios negativos)
        if len(acceleration_array) > 0:
            decel_mask = acceleration_array < 0
            decel_values = -acceleration_array[decel_mask]
            metrics.average_deceleration = float(np.mean(decel_values)) if len(decel_values) > 0 else 0.0
            metrics.max_deceleration = float(np.max(decel_values)) if len(decel_values) > 0 else 0.0

        # Sprints
        sprints = AdvancedMetrics.detect_sprints(
            velocity_array,
            cfg['sprint_threshold'],
            cfg['min_sprint_frames']
        )
        metrics.sprint_count = len(sprints)
        metrics.total_sprint_distance = sum(s['distance'] for s in sprints)
        metrics.total_sprint_duration = sum(s['duration_frames'] for s in sprints) / self.fps

        # Alta intensidad
        high_intensity_distance, high_intensity_pct = AdvancedMetrics.calculate_high_intensity_distance(
            velocity_array, cfg['high_intensity_threshold']
        )
        metrics.high_intensity_distance = high_intensity_distance
        metrics.high_intensity_percentage = high_intensity_pct

        # Cambios de dirección
        if position_history and len(position_history) >= 3:
            change_count, avg_angle, sharp_changes = AdvancedMetrics.calculate_direction_changes(
                position_history, cfg['direction_change_threshold']
            )
            metrics.direction_changes_count = change_count
            metrics.average_direction_change_angle = avg_angle
            metrics.sharp_direction_changes = sharp_changes

        # Recuperación
        total_recovery, avg_recovery, recovery_attempts = AdvancedMetrics.calculate_recovery_time(
            velocity_array, sprints, cfg['recovery_velocity_threshold'], self.fps
        )
        metrics.total_recovery_time = total_recovery
        metrics.average_recovery_time = avg_recovery
        metrics.recovery_attempts = recovery_attempts

        # Distancia total
        metrics.total_distance = float(np.sum(velocity_array))

        return metrics

    def export_json(self, metrics: IntensityMetrics,
                   filename: Optional[str] = None) -> Path:
        """
        Exporta métricas a JSON.

        Args:
            metrics (IntensityMetrics): Métricas a exportar
            filename (Optional[str]): Nombre de archivo (default: intensity_analysis.json)

        Returns:
            Path: Ruta del archivo generado
        """
        if filename is None:
            filename = "intensity_analysis.json"

        filepath = self.output_dir / filename

        with open(filepath, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)

        print(f"✓ Análisis de intensidad exportado: {filepath}")
        return filepath

    def export_summary_text(self, metrics: IntensityMetrics,
                           filename: Optional[str] = None) -> Path:
        """
        Exporta resumen de texto legible.

        Args:
            metrics (IntensityMetrics): Métricas a exportar
            filename (Optional[str]): Nombre de archivo (default: intensity_summary.txt)

        Returns:
            Path: Ruta del archivo generado
        """
        if filename is None:
            filename = "intensity_summary.txt"

        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("ANÁLISIS DE INTENSIDAD DE JUEGO\n")
            f.write("="*70 + "\n\n")

            # Resumen general
            f.write("📊 RESUMEN GENERAL\n")
            f.write("-"*70 + "\n")
            f.write(f"Duración total: {metrics.total_duration_seconds:.2f} segundos\n")
            f.write(f"Frames procesados: {metrics.total_frames}\n")
            f.write(f"FPS: {metrics.fps}\n\n")

            # Intensidad y velocidad
            f.write("⚡ INTENSIDAD Y VELOCIDAD\n")
            f.write("-"*70 + "\n")
            f.write(f"Intensidad de movimiento activo: {metrics.active_movement_percentage:.1f}%\n")
            f.write(f"Velocidad promedio: {metrics.average_velocity:.2f} m/s\n")
            f.write(f"Velocidad máxima: {metrics.max_velocity:.2f} m/s\n")
            f.write(f"Velocidad mínima: {metrics.min_velocity:.2f} m/s\n")
            f.write(f"Distancia total: {metrics.total_distance:.2f} m\n\n")

            # Categorías de movimiento
            f.write("🏃 CATEGORÍAS DE MOVIMIENTO\n")
            f.write("-"*70 + "\n")
            for name, cat in metrics.movement_categories.items():
                f.write(f"{name.capitalize():15s}: {cat.percentage:6.1f}% "
                       f"({cat.frame_count:4d} frames, {cat.duration_seconds:6.2f}s, "
                       f"{cat.distance_covered:7.2f}m)\n")
            f.write("\n")

            # Aceleración
            f.write("🚀 ACELERACIÓN Y DESACELERACIÓN\n")
            f.write("-"*70 + "\n")
            f.write(f"Aceleración promedio: {metrics.average_acceleration:.2f} m/s²\n")
            f.write(f"Aceleración máxima: {metrics.max_acceleration:.2f} m/s²\n")
            f.write(f"Desaceleración promedio: {metrics.average_deceleration:.2f} m/s²\n")
            f.write(f"Desaceleración máxima: {metrics.max_deceleration:.2f} m/s²\n\n")

            # Sprints
            f.write("⛹️ SPRINTS Y ALTA INTENSIDAD\n")
            f.write("-"*70 + "\n")
            f.write(f"Número de sprints: {metrics.sprint_count}\n")
            f.write(f"Distancia total en sprints: {metrics.total_sprint_distance:.2f} m\n")
            f.write(f"Duración total en sprints: {metrics.total_sprint_duration:.2f}s\n")
            f.write(f"Distancia en alta intensidad (>{metrics.high_intensity_threshold}m/s): "
                   f"{metrics.high_intensity_distance:.2f}m ({metrics.high_intensity_percentage:.1f}%)\n\n")

            # Cambios de dirección
            f.write("🔄 CAMBIOS DE DIRECCIÓN\n")
            f.write("-"*70 + "\n")
            f.write(f"Total de cambios: {metrics.direction_changes_count}\n")
            f.write(f"Ángulo promedio: {metrics.average_direction_change_angle:.1f}°\n")
            f.write(f"Cambios abruptos (>90°): {metrics.sharp_direction_changes}\n\n")

            # Recuperación
            f.write("💪 RECUPERACIÓN\n")
            f.write("-"*70 + "\n")
            f.write(f"Intentos de recuperación: {metrics.recovery_attempts}\n")
            f.write(f"Tiempo total de recuperación: {metrics.total_recovery_time:.2f}s\n")
            f.write(f"Tiempo promedio de recuperación: {metrics.average_recovery_time:.2f}s\n\n")

            f.write("="*70 + "\n")

        print(f"✓ Resumen exportado: {filepath}")
        return filepath

    def print_summary(self, metrics: IntensityMetrics):
        """Imprime resumen en consola"""
        print("\n" + "="*70)
        print("ANÁLISIS DE INTENSIDAD DE JUEGO")
        print("="*70)

        print(f"\n📊 RESUMEN GENERAL")
        print(f"  Duración: {metrics.total_duration_seconds:.2f}s | Frames: {metrics.total_frames}")

        print(f"\n⚡ INTENSIDAD Y VELOCIDAD")
        print(f"  Movimiento activo: {metrics.active_movement_percentage:.1f}%")
        print(f"  Velocidad media: {metrics.average_velocity:.2f} m/s "
              f"(máx: {metrics.max_velocity:.2f}, mín: {metrics.min_velocity:.2f})")
        print(f"  Distancia total: {metrics.total_distance:.2f} m")

        print(f"\n🏃 CATEGORÍAS DE MOVIMIENTO")
        for name, cat in metrics.movement_categories.items():
            print(f"  {name.capitalize():15s}: {cat.percentage:6.1f}% "
                  f"({cat.frame_count:4d}f, {cat.duration_seconds:6.2f}s)")

        print(f"\n🚀 ACELERACIÓN")
        print(f"  Media: {metrics.average_acceleration:.2f} m/s² | "
              f"Máx: {metrics.max_acceleration:.2f} m/s²")
        print(f"  Desaceleración: {metrics.average_deceleration:.2f} m/s²")

        print(f"\n⛹️ SPRINTS")
        print(f"  Cantidad: {metrics.sprint_count} | "
              f"Distancia: {metrics.total_sprint_distance:.2f}m")
        print(f"  Alta intensidad: {metrics.high_intensity_percentage:.1f}% "
              f"({metrics.high_intensity_distance:.2f}m)")

        print(f"\n🔄 CAMBIOS DE DIRECCIÓN")
        print(f"  Total: {metrics.direction_changes_count} | "
              f"Ángulo promedio: {metrics.average_direction_change_angle:.1f}°")

        print(f"\n💪 RECUPERACIÓN")
        print(f"  Intentos: {metrics.recovery_attempts} | "
              f"Tiempo promedio: {metrics.average_recovery_time:.2f}s")

        print("\n" + "="*70)

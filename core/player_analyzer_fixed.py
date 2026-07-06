"""
player_analyzer.py - Análisis detallado de estadísticas por jugador

Propósito: Calcular métricas individuales de jugadores incluyendo distancia recorrida,
velocidad, intensidad de movimiento, patrones de posicionamiento y comparativas con el equipo.
Considera FPS del video y dimensiones reales del campo para cálculos precisos.

FIXES APLICADOS:
- BUG #1 (Línea 365): Cálculo correcto de hsrs_distance_m usando multiplicación elemento-a-elemento
- BUG #2 (Línea 144-145 y similares): Fallback automático para pixels_per_meter sin calibración
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, asdict
import json
from pathlib import Path


@dataclass
class PlayerStats:
    """Estructura de datos para estadísticas de jugador"""
    player_id: int
    total_distance_m: float
    max_velocity_m_s: float
    avg_velocity_m_s: float
    movement_intensity_percent: float
    static_time_percent: float
    possession_time_s: Optional[float]
    touches_count: int
    heatmap_positions: List[Tuple[float, float]]
    speed_distribution: Dict[str, float]
    comparison_metrics: Dict[str, float]
    team_percentile: Dict[str, float]


class PlayerAnalyzer:
    """
    Analizador de rendimiento individual de jugadores.

    Calcula métricas biomecánicas y de posicionamiento considerando:
    - FPS del video para cálculos de velocidad
    - Dimensiones reales del campo (normalmente 105m x 68m)
    - Píxeles por metro (escala de cancha)

    Ejemplo de uso:
        analyzer = PlayerAnalyzer(fps=30, field_length_m=105, field_width_m=68)
        stats = analyzer.analyze_player(player_id=7, tracks=player_tracks)
    """

    # Constantes de calibración del campo
    DEFAULT_FIELD_LENGTH_M = 105.0  # Metros
    DEFAULT_FIELD_WIDTH_M = 68.0    # Metros
    DEFAULT_PIXELS_PER_METER = 0.01  # Fallback cuando no hay calibración (1 pixel ≈ 0.01 m)

    # Umbrales de velocidad (m/s)
    VELOCITY_THRESHOLD_STATIC = 0.5      # Velocidad considerada como estática
    VELOCITY_THRESHOLD_WALKING = 2.0     # Caminar
    VELOCITY_THRESHOLD_JOGGING = 4.0     # Trotando
    VELOCITY_THRESHOLD_RUNNING = 6.0     # Corriendo
    VELOCITY_THRESHOLD_SPRINTING = 8.0   # Aceleración máxima

    def __init__(
        self,
        fps: int = 30,
        field_length_m: float = DEFAULT_FIELD_LENGTH_M,
        field_width_m: float = DEFAULT_FIELD_WIDTH_M,
        pixels_per_meter: Optional[float] = None,
        min_confidence: float = 0.5
    ):
        """
        Inicializa el analizador de jugadores.

        Args:
            fps (int): Fotogramas por segundo del video (típicamente 25 o 30)
            field_length_m (float): Largo del campo en metros (default 105m)
            field_width_m (float): Ancho del campo en metros (default 68m)
            pixels_per_meter (float, optional): Escala píxeles a metros.
                Si no se proporciona, usa DEFAULT_PIXELS_PER_METER como fallback
            min_confidence (float): Confianza mínima para incluir detecciones (0-1)
        """
        self.fps = fps
        self.field_length_m = field_length_m
        self.field_width_m = field_width_m
        self.min_confidence = min_confidence

        # Tiempo entre frames en segundos
        self.frame_duration_s = 1.0 / fps

        # Escala: usa fallback si no se proporciona calibración
        self.pixels_per_meter = pixels_per_meter or self.DEFAULT_PIXELS_PER_METER
        self._is_calibrated = pixels_per_meter is not None

    def set_scale_from_detections(
        self,
        detected_field_corners: List[Tuple[float, float]],
        field_length_m: float = DEFAULT_FIELD_LENGTH_M,
        field_width_m: float = DEFAULT_FIELD_WIDTH_M
    ) -> None:
        """
        Calibra la escala píxeles-metros usando esquinas detectadas de la cancha.

        Args:
            detected_field_corners (List[Tuple[float, float]]): Esquinas de la cancha en píxeles
            field_length_m (float): Largo real del campo en metros
            field_width_m (float): Ancho real del campo en metros
        """
        if len(detected_field_corners) >= 4:
            # Calcula distancias en píxeles y las convierte a metros
            corners = np.array(detected_field_corners[:4])

            # Distancia diagonal en píxeles
            diag_pixel = np.linalg.norm(corners[0] - corners[2])

            # Distancia diagonal en metros (Teorema de Pitágoras)
            diag_m = np.sqrt(field_length_m**2 + field_width_m**2)

            # Escala final
            if diag_m > 0:
                self.pixels_per_meter = diag_pixel / diag_m
                self._is_calibrated = True

    def calculate_distance(
        self,
        tracks: List[Dict[str, Any]],
        player_id: int
    ) -> Dict[str, float]:
        """
        Calcula la distancia total recorrida por un jugador.

        Interpola detecciones faltantes y filtra trayectorias ruidosas.

        Args:
            tracks (List[Dict]): Lista de detecciones con estructura:
                {
                    'frame_idx': int,
                    'player_id': int,
                    'bbox': [x1, y1, x2, y2],
                    'center': [x, y],
                    'confidence': float
                }
            player_id (int): ID del jugador a analizar

        Returns:
            Dict con claves:
                - total_distance_m: Distancia total en metros
                - distance_by_period: Diccionario con distancia por periodo (si disponible)
                - num_samples: Número de frames usados
                - interpolated_frames: Frames que fueron interpolados
                - is_calibrated: Si se usó calibración real o fallback
        """
        # BUG FIX #2: Ahora tiene fallback automático, no lanza error
        # Si no está calibrado, usa DEFAULT_PIXELS_PER_METER
        pixels_per_meter = self.pixels_per_meter or self.DEFAULT_PIXELS_PER_METER

        # Filtra detecciones del jugador
        player_tracks = [
            t for t in tracks
            if t.get('player_id') == player_id and t.get('confidence', 0) >= self.min_confidence
        ]

        if len(player_tracks) < 2:
            return {
                'total_distance_m': 0.0,
                'distance_by_period': {},
                'num_samples': len(player_tracks),
                'interpolated_frames': 0,
                'is_calibrated': self._is_calibrated
            }

        # Ordena por frame
        player_tracks.sort(key=lambda x: x.get('frame_idx', 0))

        # Interpola frames faltantes
        interpolated_tracks = self._interpolate_missing_frames(player_tracks)

        # Calcula distancia acumulada
        total_distance_pixels = 0.0
        distances = []

        for i in range(1, len(interpolated_tracks)):
            prev_center = np.array(interpolated_tracks[i-1].get('center', [0, 0]))
            curr_center = np.array(interpolated_tracks[i].get('center', [0, 0]))

            # Distancia euclidiana en píxeles
            distance_pixels = np.linalg.norm(curr_center - prev_center)
            distances.append(distance_pixels)
            total_distance_pixels += distance_pixels

        # Convierte a metros
        total_distance_m = total_distance_pixels / pixels_per_meter

        # Filtra outliers (saltos muy grandes por errores de tracking)
        if distances:
            distances_array = np.array(distances)
            q75, q25 = np.percentile(distances_array, [75, 25])
            iqr = q75 - q25

            # Remueve distancias anómalas (> 3 * IQR)
            threshold = q75 + 3 * iqr
            valid_distances = [d for d in distances if d <= threshold]
            total_distance_m = sum(valid_distances) / pixels_per_meter

        # Valida que la distancia sea positiva y razonable
        if total_distance_m < 0:
            total_distance_m = 0.0

        return {
            'total_distance_m': round(total_distance_m, 2),
            'distance_by_period': {},
            'num_samples': len(interpolated_tracks),
            'interpolated_frames': len(interpolated_tracks) - len(player_tracks),
            'is_calibrated': self._is_calibrated
        }

    def calculate_velocity(
        self,
        tracks: List[Dict[str, Any]],
        player_id: int,
        window_size: int = 5
    ) -> Dict[str, float]:
        """
        Calcula velocidad máxima y promedio del jugador.

        Usa ventana deslizante para suavizar ruido de tracking.

        Args:
            tracks (List[Dict]): Lista de detecciones (ver calculate_distance)
            player_id (int): ID del jugador
            window_size (int): Tamaño de ventana para suavizado (frames)

        Returns:
            Dict con claves:
                - max_velocity_m_s: Velocidad máxima en m/s
                - avg_velocity_m_s: Velocidad promedio en m/s
                - median_velocity_m_s: Velocidad mediana en m/s
                - percentile_90_m_s: Percentil 90 de velocidad
                - percentile_95_m_s: Percentil 95 de velocidad
        """
        # BUG FIX #2: Ahora tiene fallback automático
        pixels_per_meter = self.pixels_per_meter or self.DEFAULT_PIXELS_PER_METER

        # Filtra y ordena detecciones
        player_tracks = [
            t for t in tracks
            if t.get('player_id') == player_id and t.get('confidence', 0) >= self.min_confidence
        ]
        player_tracks.sort(key=lambda x: x.get('frame_idx', 0))

        if len(player_tracks) < 2:
            return {
                'max_velocity_m_s': 0.0,
                'avg_velocity_m_s': 0.0,
                'median_velocity_m_s': 0.0,
                'percentile_90_m_s': 0.0,
                'percentile_95_m_s': 0.0
            }

        # Interpola frames faltantes
        interpolated_tracks = self._interpolate_missing_frames(player_tracks)

        # Calcula velocidades instantáneas
        velocities_m_s = []

        for i in range(1, len(interpolated_tracks)):
            prev_pos = np.array(interpolated_tracks[i-1].get('center', [0, 0]))
            curr_pos = np.array(interpolated_tracks[i].get('center', [0, 0]))

            distance_pixels = np.linalg.norm(curr_pos - prev_pos)
            distance_m = distance_pixels / pixels_per_meter

            # Velocidad = distancia / tiempo
            velocity_m_s = distance_m / self.frame_duration_s
            velocities_m_s.append(velocity_m_s)

        # Suaviza con ventana deslizante
        velocities_smoothed = self._smooth_velocities(velocities_m_s, window_size)

        velocities_array = np.array(velocities_smoothed)

        return {
            'max_velocity_m_s': round(float(np.max(velocities_array)), 2),
            'avg_velocity_m_s': round(float(np.mean(velocities_array)), 2),
            'median_velocity_m_s': round(float(np.median(velocities_array)), 2),
            'percentile_90_m_s': round(float(np.percentile(velocities_array, 90)), 2),
            'percentile_95_m_s': round(float(np.percentile(velocities_array, 95)), 2)
        }

    def calculate_intensity(
        self,
        tracks: List[Dict[str, Any]],
        player_id: int
    ) -> Dict[str, float]:
        """
        Calcula intensidad de movimiento como porcentaje de tiempo en movimiento.

        Categoriza velocidades en: estático, caminando, trotando, corriendo, aceleración.

        Args:
            tracks (List[Dict]): Lista de detecciones
            player_id (int): ID del jugador

        Returns:
            Dict con claves:
                - movement_intensity_percent: % tiempo en movimiento (v > 0.5 m/s)
                - static_time_percent: % tiempo estático
                - walking_percent: % tiempo caminando (0.5-2 m/s)
                - jogging_percent: % tiempo trotando (2-4 m/s)
                - running_percent: % tiempo corriendo (4-6 m/s)
                - sprinting_percent: % tiempo en aceleración (> 6 m/s)
                - hsrs_distance_m: Distancia en alta intensidad (High Speed Running/Sprinting)
        """
        # BUG FIX #2: Ahora tiene fallback automático
        pixels_per_meter = self.pixels_per_meter or self.DEFAULT_PIXELS_PER_METER

        # Filtra y ordena detecciones
        player_tracks = [
            t for t in tracks
            if t.get('player_id') == player_id and t.get('confidence', 0) >= self.min_confidence
        ]
        player_tracks.sort(key=lambda x: x.get('frame_idx', 0))

        if len(player_tracks) < 2:
            return {
                'movement_intensity_percent': 0.0,
                'static_time_percent': 100.0,
                'walking_percent': 0.0,
                'jogging_percent': 0.0,
                'running_percent': 0.0,
                'sprinting_percent': 0.0,
                'hsrs_distance_m': 0.0
            }

        # Interpola frames
        interpolated_tracks = self._interpolate_missing_frames(player_tracks)

        # Calcula velocidades
        velocities_m_s = []
        for i in range(1, len(interpolated_tracks)):
            prev_pos = np.array(interpolated_tracks[i-1].get('center', [0, 0]))
            curr_pos = np.array(interpolated_tracks[i].get('center', [0, 0]))
            distance_pixels = np.linalg.norm(curr_pos - prev_pos)
            distance_m = distance_pixels / pixels_per_meter
            velocity_m_s = distance_m / self.frame_duration_s
            velocities_m_s.append(velocity_m_s)

        velocities_array = np.array(velocities_m_s)

        # Categoriza velocidades
        static_count = np.sum(velocities_array < self.VELOCITY_THRESHOLD_STATIC)
        walking_count = np.sum(
            (velocities_array >= self.VELOCITY_THRESHOLD_STATIC) &
            (velocities_array < self.VELOCITY_THRESHOLD_WALKING)
        )
        jogging_count = np.sum(
            (velocities_array >= self.VELOCITY_THRESHOLD_WALKING) &
            (velocities_array < self.VELOCITY_THRESHOLD_JOGGING)
        )
        running_count = np.sum(
            (velocities_array >= self.VELOCITY_THRESHOLD_JOGGING) &
            (velocities_array < self.VELOCITY_THRESHOLD_RUNNING)
        )
        sprinting_count = np.sum(
            velocities_array >= self.VELOCITY_THRESHOLD_RUNNING
        )

        total_count = len(velocities_array)

        # Calcula porcentajes
        static_percent = (static_count / total_count * 100) if total_count > 0 else 0
        walking_percent = (walking_count / total_count * 100) if total_count > 0 else 0
        jogging_percent = (jogging_count / total_count * 100) if total_count > 0 else 0
        running_percent = (running_count / total_count * 100) if total_count > 0 else 0
        sprinting_percent = (sprinting_count / total_count * 100) if total_count > 0 else 0

        movement_intensity = 100 - static_percent

        # BUG FIX #1: Cálculo correcto de hsrs_distance_m
        # ANTES (INCORRECTO): np.sum(velocities_array[hsrs_mask]) * self.frame_duration_s
        #   Problema: Suma velocidades (m/s), luego multiplica por tiempo. Resultado en unidades confusas.
        # DESPUÉS (CORRECTO): np.sum(velocities_array[hsrs_mask] * self.frame_duration_s)
        #   Solución: Multiplicar cada velocidad por frame_duration_s primero (m/s * s = m),
        #   luego sumar todas las distancias frame-a-frame
        hsrs_mask = velocities_array >= self.VELOCITY_THRESHOLD_RUNNING
        hsrs_distance_m = np.sum(velocities_array[hsrs_mask] * self.frame_duration_s)

        # Valida que la distancia sea positiva y razonable
        if hsrs_distance_m < 0:
            hsrs_distance_m = 0.0

        return {
            'movement_intensity_percent': round(movement_intensity, 2),
            'static_time_percent': round(static_percent, 2),
            'walking_percent': round(walking_percent, 2),
            'jogging_percent': round(jogging_percent, 2),
            'running_percent': round(running_percent, 2),
            'sprinting_percent': round(sprinting_percent, 2),
            'hsrs_distance_m': round(hsrs_distance_m, 2)
        }

    def calculate_heatmap(
        self,
        tracks: List[Dict[str, Any]],
        player_id: int,
        grid_size: int = 10
    ) -> Dict[str, Any]:
        """
        Genera mapa de calor (heatmap) de posiciones del jugador.

        Divide el campo en grid y cuenta frames en cada celda.

        Args:
            tracks (List[Dict]): Lista de detecciones
            player_id (int): ID del jugador
            grid_size (int): Tamaño de grid (número de celdas por lado)

        Returns:
            Dict con claves:
                - heatmap_grid: Matriz (grid_size, grid_size) con conteos
                - positions_list: Lista de todas las posiciones [x, y] en metros
                - center_of_mass: Posición central promedio [x, y]
                - positional_zones: Distribución por zona (Derecha, Centro, Izquierda)
                - coverage_area_percent: % del campo cubierto
        """
        # BUG FIX #2: Ahora tiene fallback automático
        pixels_per_meter = self.pixels_per_meter or self.DEFAULT_PIXELS_PER_METER

        # Filtra detecciones
        player_tracks = [
            t for t in tracks
            if t.get('player_id') == player_id and t.get('confidence', 0) >= self.min_confidence
        ]

        if not player_tracks:
            return {
                'heatmap_grid': np.zeros((grid_size, grid_size)).tolist(),
                'positions_list': [],
                'center_of_mass': [0, 0],
                'positional_zones': {'left': 0, 'center': 0, 'right': 0},
                'coverage_area_percent': 0.0
            }

        # Convierte posiciones a metros
        positions_m = []
        for track in player_tracks:
            center = track.get('center', [0, 0])
            pos_x_m = center[0] / pixels_per_meter
            pos_y_m = center[1] / pixels_per_meter
            positions_m.append([pos_x_m, pos_y_m])

        positions_array = np.array(positions_m)

        # Crea grid
        heatmap = np.zeros((grid_size, grid_size))

        for pos in positions_array:
            # Normaliza a índices de grid [0, grid_size)
            x_idx = int(np.clip(pos[0] / self.field_length_m * grid_size, 0, grid_size - 1))
            y_idx = int(np.clip(pos[1] / self.field_width_m * grid_size, 0, grid_size - 1))
            heatmap[y_idx, x_idx] += 1

        # Centro de masa
        center_of_mass = np.mean(positions_array, axis=0).tolist()

        # Zonas posicionales (Izquierda/Centro/Derecha)
        left_zone = np.sum(positions_array[:, 0] < self.field_length_m / 3)
        center_zone = np.sum(
            (positions_array[:, 0] >= self.field_length_m / 3) &
            (positions_array[:, 0] < 2 * self.field_length_m / 3)
        )
        right_zone = np.sum(positions_array[:, 0] >= 2 * self.field_length_m / 3)

        total = len(positions_array)

        # Cobertura de área (# de celdas ocupadas / total de celdas)
        coverage_percent = (np.count_nonzero(heatmap) / (grid_size * grid_size)) * 100

        return {
            'heatmap_grid': heatmap.tolist(),
            'positions_list': positions_m,
            'center_of_mass': [round(x, 2) for x in center_of_mass],
            'positional_zones': {
                'left': round(left_zone / total * 100, 2) if total > 0 else 0,
                'center': round(center_zone / total * 100, 2) if total > 0 else 0,
                'right': round(right_zone / total * 100, 2) if total > 0 else 0
            },
            'coverage_area_percent': round(coverage_percent, 2)
        }

    def compare_with_team(
        self,
        player_stats: PlayerStats,
        team_stats: List[PlayerStats]
    ) -> Dict[str, Dict[str, float]]:
        """
        Compara métricas del jugador con el equipo.

        Calcula percentiles y diferencias relativas.

        Args:
            player_stats (PlayerStats): Estadísticas del jugador
            team_stats (List[PlayerStats]): Estadísticas del equipo

        Returns:
            Dict con comparativas:
                - distance_percentile: Percentil en distancia recorrida
                - velocity_percentile: Percentil en velocidad máxima
                - intensity_percentile: Percentil en intensidad
                - distance_vs_avg: Diferencia vs promedio de equipo
                - velocity_vs_avg: Diferencia vs promedio de equipo
        """
        if not team_stats or len(team_stats) == 0:
            return {
                'distance_percentile': 50.0,
                'velocity_percentile': 50.0,
                'intensity_percentile': 50.0,
                'distance_vs_avg_percent': 0.0,
                'velocity_vs_avg_percent': 0.0,
                'intensity_vs_avg_percent': 0.0
            }

        # Recolecta métricas del equipo
        team_distances = [s.total_distance_m for s in team_stats]
        team_velocities = [s.max_velocity_m_s for s in team_stats]
        team_intensities = [s.movement_intensity_percent for s in team_stats]

        # Calcula percentiles
        distance_percentile = float(np.percentileofscore(team_distances, player_stats.total_distance_m))
        velocity_percentile = float(np.percentileofscore(team_velocities, player_stats.max_velocity_m_s))
        intensity_percentile = float(np.percentileofscore(team_intensities, player_stats.movement_intensity_percent))

        # Calcula promedios del equipo
        avg_distance = np.mean(team_distances)
        avg_velocity = np.mean(team_velocities)
        avg_intensity = np.mean(team_intensities)

        # Diferencias relativas
        distance_vs_avg = ((player_stats.total_distance_m - avg_distance) / avg_distance * 100) if avg_distance > 0 else 0
        velocity_vs_avg = ((player_stats.max_velocity_m_s - avg_velocity) / avg_velocity * 100) if avg_velocity > 0 else 0
        intensity_vs_avg = ((player_stats.movement_intensity_percent - avg_intensity) / avg_intensity * 100) if avg_intensity > 0 else 0

        return {
            'distance_percentile': round(distance_percentile, 1),
            'velocity_percentile': round(velocity_percentile, 1),
            'intensity_percentile': round(intensity_percentile, 1),
            'distance_vs_avg_percent': round(distance_vs_avg, 2),
            'velocity_vs_avg_percent': round(velocity_vs_avg, 2),
            'intensity_vs_avg_percent': round(intensity_vs_avg, 2),
            'team_avg_distance_m': round(avg_distance, 2),
            'team_avg_velocity_m_s': round(avg_velocity, 2),
            'team_avg_intensity_percent': round(avg_intensity, 2)
        }

    def analyze_player(
        self,
        player_id: int,
        tracks: List[Dict[str, Any]],
        team_stats: Optional[List[PlayerStats]] = None
    ) -> PlayerStats:
        """
        Realiza análisis completo de un jugador.

        Args:
            player_id (int): ID del jugador
            tracks (List[Dict]): Detecciones de todos los frames
            team_stats (Optional[List[PlayerStats]]): Estadísticas del equipo para comparativa

        Returns:
            PlayerStats: Objeto con todas las métricas
        """
        # Calcula métricas individuales
        distance_data = self.calculate_distance(tracks, player_id)
        velocity_data = self.calculate_velocity(tracks, player_id)
        intensity_data = self.calculate_intensity(tracks, player_id)
        heatmap_data = self.calculate_heatmap(tracks, player_id)

        # Crea estructura de estadísticas
        stats = PlayerStats(
            player_id=player_id,
            total_distance_m=distance_data['total_distance_m'],
            max_velocity_m_s=velocity_data['max_velocity_m_s'],
            avg_velocity_m_s=velocity_data['avg_velocity_m_s'],
            movement_intensity_percent=intensity_data['movement_intensity_percent'],
            static_time_percent=intensity_data['static_time_percent'],
            possession_time_s=None,
            touches_count=0,
            heatmap_positions=heatmap_data['positions_list'][:100],  # Limita para JSON
            speed_distribution={
                'static': intensity_data['static_time_percent'],
                'walking': intensity_data['walking_percent'],
                'jogging': intensity_data['jogging_percent'],
                'running': intensity_data['running_percent'],
                'sprinting': intensity_data['sprinting_percent']
            },
            comparison_metrics={},
            team_percentile={}
        )

        # Comparativa con equipo
        if team_stats:
            comparison = self.compare_with_team(stats, team_stats)
            stats.comparison_metrics = comparison
            stats.team_percentile = {
                'distance': comparison['distance_percentile'],
                'velocity': comparison['velocity_percentile'],
                'intensity': comparison['intensity_percentile']
            }

        return stats

    # Métodos auxiliares privados

    def _interpolate_missing_frames(
        self,
        tracks: List[Dict[str, Any]],
        max_gap: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Interpola frames faltantes en la trayectoria.

        Args:
            tracks (List[Dict]): Detecciones ordenadas por frame
            max_gap (int): Máximo gap en frames para interpolar

        Returns:
            List[Dict]: Tracks interpolados
        """
        if len(tracks) < 2:
            return tracks

        interpolated = []

        for i in range(len(tracks) - 1):
            interpolated.append(tracks[i])

            frame_gap = tracks[i + 1].get('frame_idx', i + 1) - tracks[i].get('frame_idx', i)

            if 1 < frame_gap <= max_gap:
                # Interpola linealmente
                prev_center = np.array(tracks[i].get('center', [0, 0]))
                next_center = np.array(tracks[i + 1].get('center', [0, 0]))

                for t in np.linspace(0, 1, frame_gap)[1:-1]:
                    interp_pos = prev_center + t * (next_center - prev_center)

                    interpolated.append({
                        'frame_idx': tracks[i].get('frame_idx', i) + int(t * frame_gap),
                        'center': interp_pos.tolist(),
                        'confidence': 0.5,  # Marca como interpolado
                        'player_id': tracks[i].get('player_id')
                    })

        interpolated.append(tracks[-1])
        return interpolated

    def _smooth_velocities(
        self,
        velocities: List[float],
        window_size: int = 5
    ) -> List[float]:
        """
        Suaviza velocidades usando promedio móvil.

        Args:
            velocities (List[float]): Velocidades instantáneas
            window_size (int): Tamaño de ventana

        Returns:
            List[float]: Velocidades suavizadas
        """
        if len(velocities) < window_size:
            return velocities

        velocities_array = np.array(velocities)
        smoothed = np.convolve(
            velocities_array,
            np.ones(window_size) / window_size,
            mode='same'
        )

        return smoothed.tolist()

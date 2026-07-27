"""
player_stats_aggregator.py - Consolidador de estadísticas de jugadores

Propósito: Unificar todos los cálculos de estadísticas en una estructura cohesiva.
Consolida métricas de distancia, velocidad, intensidad, análisis de zonas y
genera reportes comparativos contra el equipo.

Características:
  - Agregación de múltiples métricas en formato standar
  - Validación y manejo de valores faltantes
  - Cálculo de percentiles versus equipo
  - Timestamps ISO 8601
  - Exportación a múltiples formatos (JSON, CSV)
  - Generación de reportes ejecutivos
"""

import json
import csv
from pathlib import Path
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from collections import defaultdict
from enum import Enum


class IntensityCategory(Enum):
    """Categorías de intensidad de movimiento"""
    STATIC = "static"           # < 0.5 m/s
    WALKING = "walking"         # 0.5 - 2.0 m/s
    JOGGING = "jogging"         # 2.0 - 4.0 m/s
    RUNNING = "running"         # 4.0 - 6.0 m/s
    SPRINTING = "sprinting"     # >= 6.0 m/s


class MovementProfile(Enum):
    """Perfiles de movimiento del jugador"""
    STATIC_PLAYER = "static"              # Mayoría en posición estática
    LOW_INTENSITY = "low_intensity"       # Movimiento lento y controlado
    BALANCED = "balanced"                 # Balance entre actividad e inactividad
    HIGH_INTENSITY = "high_intensity"     # Movimiento constante
    EXPLOSIVE = "explosive"               # Ráfagas de alta intensidad


@dataclass
class ZoneStats:
    """Estadísticas por zona del campo"""
    zone_id: int                          # 1-9 (cuadrícula 3x3)
    zone_name: str                        # "Left-Forward", "Center-Mid", etc.
    time_percent: float                   # % de tiempo en esta zona
    distance_m: float                     # Distancia recorrida en zona
    avg_velocity_m_s: float              # Velocidad promedio en zona
    max_velocity_m_s: float              # Velocidad máxima en zona


@dataclass
class VelocityMetrics:
    """Métricas detalladas de velocidad"""
    max_m_s: float                        # Velocidad máxima
    avg_m_s: float                        # Promedio
    median_m_s: float                     # Mediana
    percentile_90_m_s: float             # Percentil 90
    percentile_95_m_s: float             # Percentil 95
    std_m_s: float                        # Desviación estándar
    variance_m_s_sq: float               # Varianza


@dataclass
class IntensityMetrics:
    """Métricas detalladas de intensidad"""
    total_percent: float                  # % tiempo en movimiento
    static_percent: float                 # % estático
    walking_percent: float                # % caminando
    jogging_percent: float                # % trotando
    running_percent: float                # % corriendo
    sprinting_percent: float              # % aceleración
    high_speed_distance_m: float         # Distancia en alta velocidad (>=6m/s)


@dataclass
class DistanceMetrics:
    """Métricas detalladas de distancia"""
    total_m: float                        # Distancia total en metros
    total_km: float                       # Distancia total en km
    by_period: Dict[str, float] = field(default_factory=dict)  # Por periodo
    interpolated_frames: int = 0          # Frames interpolados


@dataclass
class PlayerStats:
    """Estructura unificada de estadísticas del jugador"""
    # Identifiers
    player_id: int
    player_number: int
    team_id: str
    player_name: str
    position: str

    # Distance metrics
    distance_total_m: float
    distance_total_km: float

    # Velocity metrics
    velocity_max: float                   # m/s
    velocity_avg: float                   # m/s
    velocity_median: float                # m/s
    velocity_percentile_90: float        # m/s
    velocity_percentile_95: float        # m/s
    velocity_std: float                   # m/s

    # Intensity metrics
    intensity_pct: float                  # % tiempo en movimiento
    high_intensity_distance: float        # Metros en alta intensidad
    sprints_count: int                    # Número de sprints
    directional_changes: int              # Cambios de dirección

    # Zone analysis
    zones_visited: List[str]              # Lista de zonas visitadas
    dominant_zone: str                    # Zona con más tiempo
    zone_concentration_pct: float        # % tiempo en zona dominante

    # Movement profile
    movement_profile: str                 # Categoría de movimiento

    # Heatmap
    heatmap_path: Optional[str] = None    # Ruta a imagen PNG

    # Team comparison
    distance_percentile: float = 0.0      # Percentil vs equipo
    velocity_percentile: float = 0.0      # Percentil vs equipo
    intensity_percentile: float = 0.0     # Percentil vs equipo

    # Metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    format_version: str = "1.0"
    analysis_frames: int = 0              # Frames analizados

    # Detailed breakdowns
    intensity_breakdown: Dict[str, float] = field(default_factory=dict)
    zone_stats: List[ZoneStats] = field(default_factory=list)
    speed_categories: Dict[str, float] = field(default_factory=dict)
    comparison_vs_team: Dict[str, float] = field(default_factory=dict)


class PlayerStatsAggregator:
    """
    Agregador de estadísticas de jugadores.

    Consolida múltiples fuentes de cálculos en estadísticas unificadas,
    con validación, imputación de valores faltantes y comparativas versus equipo.
    """

    def __init__(self, team_id: str, team_size: int = 11):
        """
        Inicializa el agregador.

        Args:
            team_id: Identificador del equipo
            team_size: Tamaño del equipo (default 11 para fútbol)
        """
        self.team_id = team_id
        self.team_size = team_size
        self.players_stats: Dict[int, PlayerStats] = {}
        self.team_stats_summary: Dict[str, float] = {}

    def aggregate_player_stats(
        self,
        player_id: int,
        player_number: int,
        player_name: str,
        position: str,
        distance_metrics: Dict[str, float],
        velocity_metrics: Dict[str, float],
        intensity_metrics: Dict[str, float],
        zones_data: Optional[Dict[str, Any]] = None,
        heatmap_path: Optional[str] = None,
        analysis_frames: int = 0
    ) -> PlayerStats:
        """
        Agrega todas las métricas de un jugador.

        Args:
            player_id: ID único del jugador
            player_number: Número de camiseta
            player_name: Nombre del jugador
            position: Posición (GK, DEF, MID, FWD)
            distance_metrics: Dict con total_distance_m, distance_by_period, etc.
            velocity_metrics: Dict con max_velocity_m_s, avg_velocity_m_s, etc.
            intensity_metrics: Dict con movement_intensity_percent, etc.
            zones_data: Dict con información de zonas (opcional)
            heatmap_path: Ruta al archivo de heatmap PNG
            analysis_frames: Cantidad de frames analizados

        Returns:
            PlayerStats unificado
        """
        # Extraer y validar distancia
        distance_m = self._validate_float(
            distance_metrics.get('total_distance_m', 0.0),
            min_val=0.0, default=0.0
        )
        distance_km = distance_m / 1000.0

        # Extraer y validar velocidad
        vel_max = self._validate_float(
            velocity_metrics.get('max_velocity_m_s', 0.0),
            min_val=0.0, default=0.0
        )
        vel_avg = self._validate_float(
            velocity_metrics.get('avg_velocity_m_s', 0.0),
            min_val=0.0, default=0.0
        )
        vel_median = self._validate_float(
            velocity_metrics.get('median_velocity_m_s', vel_avg),
            min_val=0.0, default=vel_avg
        )
        vel_p90 = self._validate_float(
            velocity_metrics.get('percentile_90_m_s', vel_max * 0.9),
            min_val=0.0, default=vel_max * 0.9
        )
        vel_p95 = self._validate_float(
            velocity_metrics.get('percentile_95_m_s', vel_max * 0.95),
            min_val=0.0, default=vel_max * 0.95
        )
        vel_std = self._validate_float(
            velocity_metrics.get('std_velocity_m_s', 0.0),
            min_val=0.0, default=0.0
        )

        # Extraer y validar intensidad
        intensity_pct = self._validate_float(
            intensity_metrics.get('movement_intensity_percent', 0.0),
            min_val=0.0, max_val=100.0, default=0.0
        )
        high_intensity_dist = self._validate_float(
            intensity_metrics.get('hsrs_distance_m', 0.0),
            min_val=0.0, default=0.0
        )
        sprints_count = self._validate_int(
            intensity_metrics.get('sprints_count', 0),
            min_val=0, default=0
        )
        directional_changes = self._validate_int(
            intensity_metrics.get('directional_changes', 0),
            min_val=0, default=0
        )

        # Procesar zonas
        zones_visited, dominant_zone, zone_concentration = \
            self._process_zones(zones_data or {})
        zone_stats = self._calculate_zone_stats(zones_data or {})

        # Determinar perfil de movimiento
        movement_profile = self._determine_movement_profile(
            intensity_pct, vel_avg, sprints_count
        )

        # Crear breakdown de intensidad
        intensity_breakdown = self._create_intensity_breakdown(intensity_metrics)

        # Crear categorías de velocidad
        speed_categories = self._create_speed_categories(velocity_metrics)

        # Crear objeto PlayerStats
        stats = PlayerStats(
            player_id=player_id,
            player_number=player_number,
            team_id=self.team_id,
            player_name=player_name,
            position=position,
            distance_total_m=distance_m,
            distance_total_km=distance_km,
            velocity_max=vel_max,
            velocity_avg=vel_avg,
            velocity_median=vel_median,
            velocity_percentile_90=vel_p90,
            velocity_percentile_95=vel_p95,
            velocity_std=vel_std,
            intensity_pct=intensity_pct,
            high_intensity_distance=high_intensity_dist,
            sprints_count=sprints_count,
            directional_changes=directional_changes,
            zones_visited=zones_visited,
            dominant_zone=dominant_zone,
            zone_concentration_pct=zone_concentration,
            movement_profile=movement_profile,
            heatmap_path=heatmap_path,
            analysis_frames=analysis_frames,
            intensity_breakdown=intensity_breakdown,
            zone_stats=zone_stats,
            speed_categories=speed_categories
        )

        # Almacenar
        self.players_stats[player_id] = stats
        return stats

    def calculate_team_percentiles(self) -> None:
        """
        Calcula percentiles de cada jugador versus el equipo.
        Actualiza los campos *_percentile en cada PlayerStats.
        """
        if len(self.players_stats) < 2:
            return

        players_list = list(self.players_stats.values())

        # Extraer métricas
        distances = [p.distance_total_m for p in players_list]
        velocities = [p.velocity_avg for p in players_list]
        intensities = [p.intensity_pct for p in players_list]

        # Calcular percentiles para cada jugador
        for player_stats in players_list:
            player_stats.distance_percentile = self._calculate_percentile(
                player_stats.distance_total_m, distances
            )
            player_stats.velocity_percentile = self._calculate_percentile(
                player_stats.velocity_avg, velocities
            )
            player_stats.intensity_percentile = self._calculate_percentile(
                player_stats.intensity_pct, intensities
            )

            # Agregar comparativa
            player_stats.comparison_vs_team = {
                'distance_percentile': player_stats.distance_percentile,
                'velocity_percentile': player_stats.velocity_percentile,
                'intensity_percentile': player_stats.intensity_percentile,
                'distance_vs_avg': player_stats.distance_total_m - np.mean(distances),
                'velocity_vs_avg': player_stats.velocity_avg - np.mean(velocities),
                'intensity_vs_avg': player_stats.intensity_pct - np.mean(intensities),
            }

    def get_player_stats(self, player_id: int) -> Optional[PlayerStats]:
        """Obtiene las estadísticas de un jugador específico."""
        return self.players_stats.get(player_id)

    def get_all_stats(self) -> List[PlayerStats]:
        """Obtiene todas las estadísticas de jugadores."""
        return list(self.players_stats.values())

    def get_team_summary(self) -> Dict[str, float]:
        """
        Genera resumen estadístico del equipo.

        Returns:
            Dict con promedio, máximo, mínimo de métricas clave
        """
        if not self.players_stats:
            return {}

        players_list = self.get_all_stats()

        summary = {
            'team_id': self.team_id,
            'players_count': len(players_list),

            # Distancia
            'distance_avg_m': np.mean([p.distance_total_m for p in players_list]),
            'distance_max_m': np.max([p.distance_total_m for p in players_list]),
            'distance_min_m': np.min([p.distance_total_m for p in players_list]),
            'distance_avg_km': np.mean([p.distance_total_km for p in players_list]),

            # Velocidad
            'velocity_avg_m_s': np.mean([p.velocity_avg for p in players_list]),
            'velocity_max_m_s': np.max([p.velocity_max for p in players_list]),
            'velocity_min_m_s': np.min([p.velocity_avg for p in players_list]),

            # Intensidad
            'intensity_avg_pct': np.mean([p.intensity_pct for p in players_list]),
            'intensity_max_pct': np.max([p.intensity_pct for p in players_list]),
            'intensity_min_pct': np.min([p.intensity_pct for p in players_list]),

            # Sprints
            'sprints_total': sum(p.sprints_count for p in players_list),
            'sprints_avg': np.mean([p.sprints_count for p in players_list]),
        }

        self.team_stats_summary = summary
        return summary

    # ====== Métodos privados de validación ======

    @staticmethod
    def _validate_float(
        value: Any,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        default: float = 0.0
    ) -> float:
        """Valida y convierte a float con límites opcionales."""
        try:
            val = float(value)
        except (TypeError, ValueError):
            return default

        if min_val is not None and val < min_val:
            return min_val
        if max_val is not None and val > max_val:
            return max_val

        return round(val, 3)

    @staticmethod
    def _validate_int(
        value: Any,
        min_val: Optional[int] = None,
        max_val: Optional[int] = None,
        default: int = 0
    ) -> int:
        """Valida y convierte a int con límites opcionales."""
        try:
            val = int(value)
        except (TypeError, ValueError):
            return default

        if min_val is not None and val < min_val:
            return min_val
        if max_val is not None and val > max_val:
            return max_val

        return val

    @staticmethod
    def _calculate_percentile(value: float, values_list: List[float]) -> float:
        """Calcula el percentil de un valor en una lista."""
        if not values_list:
            return 0.0
        return round(100.0 * np.sum(np.array(values_list) <= value) / len(values_list), 1)

    def _process_zones(
        self,
        zones_data: Dict[str, Any]
    ) -> Tuple[List[str], str, float]:
        """
        Procesa datos de zonas.

        Returns:
            (zonas_visitadas, zona_dominante, concentración_%)
        """
        if not zones_data:
            return [], "Unknown", 0.0

        zones_visited = zones_data.get('zones_visited', [])
        dominant_zone = zones_data.get('dominant_zone', 'Unknown')
        concentration = self._validate_float(
            zones_data.get('zone_concentration_pct', 0.0),
            min_val=0.0, max_val=100.0
        )

        return zones_visited, dominant_zone, concentration

    @staticmethod
    def _calculate_zone_stats(zones_data: Dict[str, Any]) -> List[ZoneStats]:
        """Calcula estadísticas detalladas por zona."""
        zone_stats_list = []
        zone_details = zones_data.get('zone_details', {})

        for zone_id, details in zone_details.items():
            if isinstance(details, dict):
                zone = ZoneStats(
                    zone_id=int(zone_id) if zone_id.isdigit() else 0,
                    zone_name=details.get('zone_name', f'Zone-{zone_id}'),
                    time_percent=float(details.get('time_percent', 0.0)),
                    distance_m=float(details.get('distance_m', 0.0)),
                    avg_velocity_m_s=float(details.get('avg_velocity_m_s', 0.0)),
                    max_velocity_m_s=float(details.get('max_velocity_m_s', 0.0))
                )
                zone_stats_list.append(zone)

        return zone_stats_list

    @staticmethod
    def _determine_movement_profile(
        intensity_pct: float,
        avg_velocity: float,
        sprints_count: int
    ) -> str:
        """Determina el perfil de movimiento basado en métricas."""
        if intensity_pct < 20.0:
            return MovementProfile.STATIC_PLAYER.value
        elif intensity_pct < 40.0 and avg_velocity < 2.0:
            return MovementProfile.LOW_INTENSITY.value
        elif intensity_pct < 70.0:
            return MovementProfile.BALANCED.value
        elif sprints_count > 10:
            return MovementProfile.EXPLOSIVE.value
        else:
            return MovementProfile.HIGH_INTENSITY.value

    @staticmethod
    def _create_intensity_breakdown(
        intensity_metrics: Dict[str, float]
    ) -> Dict[str, float]:
        """Crea breakdown de categorías de intensidad."""
        return {
            'static': intensity_metrics.get('static_time_percent', 0.0),
            'walking': intensity_metrics.get('walking_percent', 0.0),
            'jogging': intensity_metrics.get('jogging_percent', 0.0),
            'running': intensity_metrics.get('running_percent', 0.0),
            'sprinting': intensity_metrics.get('sprinting_percent', 0.0),
        }

    @staticmethod
    def _create_speed_categories(
        velocity_metrics: Dict[str, float]
    ) -> Dict[str, float]:
        """Crea categorización de velocidades."""
        return {
            'max_m_s': velocity_metrics.get('max_velocity_m_s', 0.0),
            'avg_m_s': velocity_metrics.get('avg_velocity_m_s', 0.0),
            'median_m_s': velocity_metrics.get('median_velocity_m_s', 0.0),
            'p90_m_s': velocity_metrics.get('percentile_90_m_s', 0.0),
            'p95_m_s': velocity_metrics.get('percentile_95_m_s', 0.0),
        }


class StatsExporter:
    """
    Exportador de estadísticas en múltiples formatos.

    Soporta JSON, CSV, y reportes comparativos.
    """

    def __init__(self, output_dir: str = "data/exports"):
        """
        Inicializa el exportador.

        Args:
            output_dir: Directorio base para exportaciones
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def export_json(
        self,
        player_stats: PlayerStats,
        filename: Optional[str] = None
    ) -> Path:
        """
        Exporta estadísticas de un jugador a JSON.

        Args:
            player_stats: Objeto PlayerStats
            filename: Nombre del archivo (default: player_{id}.json)

        Returns:
            Ruta del archivo exportado
        """
        if filename is None:
            filename = f"player_{player_stats.player_number}.json"

        filepath = self.output_dir / filename

        # Convertir dataclass a dict con manejo especial de zone_stats
        stats_dict = asdict(player_stats)

        # Convertir ZoneStats a dicts si es necesario
        if stats_dict.get('zone_stats'):
            zone_stats_list = stats_dict['zone_stats']
            converted_zones = []
            for z in zone_stats_list:
                if isinstance(z, ZoneStats):
                    converted_zones.append(asdict(z))
                elif isinstance(z, dict):
                    converted_zones.append(z)
            stats_dict['zone_stats'] = converted_zones

        with open(filepath, 'w') as f:
            json.dump(stats_dict, f, indent=2)

        return filepath

    def export_csv(
        self,
        players_stats: List[PlayerStats],
        filename: str = "jugadores.csv"
    ) -> Path:
        """
        Exporta múltiples jugadores a CSV.

        Args:
            players_stats: Lista de PlayerStats
            filename: Nombre del archivo CSV

        Returns:
            Ruta del archivo exportado
        """
        filepath = self.output_dir / filename

        if not players_stats:
            raise ValueError("Lista de jugadores vacía")

        # Campos a exportar
        fields = [
            'player_id', 'player_number', 'team_id', 'player_name', 'position',
            'distance_total_m', 'distance_total_km',
            'velocity_max', 'velocity_avg', 'velocity_median',
            'velocity_percentile_90', 'velocity_percentile_95',
            'intensity_pct', 'high_intensity_distance',
            'sprints_count', 'directional_changes',
            'dominant_zone', 'zone_concentration_pct',
            'movement_profile',
            'distance_percentile', 'velocity_percentile', 'intensity_percentile',
            'analysis_frames', 'timestamp'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()

            for stats in players_stats:
                row = {field: getattr(stats, field, '') for field in fields}
                writer.writerow(row)

        return filepath

    def export_comparison_json(
        self,
        players_stats: List[PlayerStats],
        team_summary: Dict[str, float],
        filename: str = "comparativa.json"
    ) -> Path:
        """
        Exporta comparativa de jugadores versus equipo.

        Args:
            players_stats: Lista de PlayerStats
            team_summary: Resumen del equipo
            filename: Nombre del archivo

        Returns:
            Ruta del archivo exportado
        """
        filepath = self.output_dir / filename

        comparison = {
            'timestamp': datetime.utcnow().isoformat(),
            'team_summary': team_summary,
            'players': []
        }

        for stats in players_stats:
            player_comparison = {
                'player_id': stats.player_id,
                'player_number': stats.player_number,
                'player_name': stats.player_name,
                'position': stats.position,
                'metrics': {
                    'distance': {
                        'value_m': stats.distance_total_m,
                        'percentile': stats.distance_percentile,
                        'vs_team_avg': stats.comparison_vs_team.get('distance_vs_avg', 0.0)
                    },
                    'velocity': {
                        'value_m_s': stats.velocity_avg,
                        'percentile': stats.velocity_percentile,
                        'vs_team_avg': stats.comparison_vs_team.get('velocity_vs_avg', 0.0)
                    },
                    'intensity': {
                        'value_pct': stats.intensity_pct,
                        'percentile': stats.intensity_percentile,
                        'vs_team_avg': stats.comparison_vs_team.get('intensity_vs_avg', 0.0)
                    }
                }
            }
            comparison['players'].append(player_comparison)

        with open(filepath, 'w') as f:
            json.dump(comparison, f, indent=2)

        return filepath

    def generate_summary(
        self,
        players_stats: List[PlayerStats],
        team_summary: Dict[str, float],
        filename: str = "resumen_ejecutivo.json"
    ) -> Path:
        """
        Genera resumen ejecutivo de la sesión.

        Args:
            players_stats: Lista de PlayerStats
            team_summary: Resumen del equipo
            filename: Nombre del archivo

        Returns:
            Ruta del archivo exportado
        """
        filepath = self.output_dir / filename

        # Clasificar jugadores por perfil
        profiles_count = defaultdict(int)
        for stats in players_stats:
            profiles_count[stats.movement_profile] += 1

        # Top performers
        top_distance = sorted(
            players_stats,
            key=lambda x: x.distance_total_m,
            reverse=True
        )[:3]

        top_intensity = sorted(
            players_stats,
            key=lambda x: x.intensity_pct,
            reverse=True
        )[:3]

        top_velocity = sorted(
            players_stats,
            key=lambda x: x.velocity_max,
            reverse=True
        )[:3]

        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'format_version': '1.0',
            'team_summary': team_summary,
            'movement_profiles': dict(profiles_count),
            'top_performers': {
                'distance': [
                    {
                        'player_number': p.player_number,
                        'player_name': p.player_name,
                        'value_km': round(p.distance_total_km, 2),
                        'percentile': p.distance_percentile
                    }
                    for p in top_distance
                ],
                'intensity': [
                    {
                        'player_number': p.player_number,
                        'player_name': p.player_name,
                        'value_pct': round(p.intensity_pct, 1),
                        'percentile': p.intensity_percentile
                    }
                    for p in top_intensity
                ],
                'velocity': [
                    {
                        'player_number': p.player_number,
                        'player_name': p.player_name,
                        'value_m_s': round(p.velocity_max, 2),
                        'percentile': p.velocity_percentile
                    }
                    for p in top_velocity
                ]
            },
            'statistics': {
                'total_players_analyzed': len(players_stats),
                'average_distance_km': round(team_summary.get('distance_avg_km', 0.0), 2),
                'total_team_distance_km': round(
                    sum(p.distance_total_km for p in players_stats), 2
                ),
                'average_intensity_pct': round(team_summary.get('intensity_avg_pct', 0.0), 1),
                'total_sprints': team_summary.get('sprints_total', 0),
            }
        }

        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)

        return filepath

    def export_all(
        self,
        aggregator: PlayerStatsAggregator,
        prefix: str = ""
    ) -> Dict[str, Path]:
        """
        Exporta todas las estadísticas en todos los formatos.

        Args:
            aggregator: PlayerStatsAggregator con datos
            prefix: Prefijo para nombres de archivos

        Returns:
            Dict con rutas de todos los archivos exportados
        """
        players_stats = aggregator.get_all_stats()
        team_summary = aggregator.get_team_summary()

        exports = {}

        # Exportar JSON individual por jugador
        for stats in players_stats:
            filename = f"{prefix}player_{stats.player_number}.json" if prefix else None
            exports[f"player_{stats.player_number}_json"] = \
                self.export_json(stats, filename)

        # Exportar CSV consolidado
        csv_filename = f"{prefix}jugadores.csv" if prefix else "jugadores.csv"
        exports["csv"] = self.export_csv(players_stats, csv_filename)

        # Exportar comparativa
        comp_filename = f"{prefix}comparativa.json" if prefix else "comparativa.json"
        exports["comparison"] = self.export_comparison_json(
            players_stats, team_summary, comp_filename
        )

        # Exportar resumen ejecutivo
        summary_filename = f"{prefix}resumen_ejecutivo.json" if prefix else "resumen_ejecutivo.json"
        exports["summary"] = self.generate_summary(
            players_stats, team_summary, summary_filename
        )

        return exports

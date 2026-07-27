"""
test_stats_aggregation.py - Tests para el módulo de agregación de estadísticas

Prueba cobertura completa del PlayerStatsAggregator, PlayerStats, y utilidades
asociadas, incluyendo validación de datos, cálculos de percentiles, y manejo
de valores faltantes.
"""

import pytest
import json
import csv
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime
import numpy as np

from core.player_stats_aggregator import (
    PlayerStatsAggregator,
    PlayerStats,
    StatsExporter,
    IntensityCategory,
    MovementProfile,
    ZoneStats,
    VelocityMetrics,
    IntensityMetrics,
    DistanceMetrics,
)


# ===== Fixtures =====

@pytest.fixture
def temp_export_dir(tmp_path):
    """Directorio temporal para exportaciones."""
    return str(tmp_path)


@pytest.fixture
def aggregator():
    """Crea un agregador para el equipo A."""
    return PlayerStatsAggregator(team_id="A", team_size=11)


@pytest.fixture
def distance_metrics_valid():
    """Métricas de distancia válidas."""
    return {
        'total_distance_m': 10500.0,
        'distance_by_period': {'first_half': 5250.0, 'second_half': 5250.0},
        'num_samples': 1800,
        'interpolated_frames': 10
    }


@pytest.fixture
def velocity_metrics_valid():
    """Métricas de velocidad válidas."""
    return {
        'max_velocity_m_s': 9.5,
        'avg_velocity_m_s': 4.2,
        'median_velocity_m_s': 3.8,
        'percentile_90_m_s': 8.5,
        'percentile_95_m_s': 9.0,
        'std_velocity_m_s': 2.1,
    }


@pytest.fixture
def intensity_metrics_valid():
    """Métricas de intensidad válidas."""
    return {
        'movement_intensity_percent': 75.0,
        'static_time_percent': 25.0,
        'walking_percent': 15.0,
        'jogging_percent': 30.0,
        'running_percent': 20.0,
        'sprinting_percent': 10.0,
        'hsrs_distance_m': 2100.0,  # High-speed running/sprinting
        'sprints_count': 12,
        'directional_changes': 45,
    }


@pytest.fixture
def zones_data_valid():
    """Datos de zonas válidos."""
    return {
        'zones_visited': ['Left-Forward', 'Center-Mid', 'Right-Forward'],
        'dominant_zone': 'Center-Mid',
        'zone_concentration_pct': 42.5,
        'zone_details': {
            '5': {
                'zone_name': 'Center-Mid',
                'time_percent': 42.5,
                'distance_m': 4462.5,
                'avg_velocity_m_s': 3.8,
                'max_velocity_m_s': 9.5,
            },
            '2': {
                'zone_name': 'Left-Forward',
                'time_percent': 28.3,
                'distance_m': 2971.5,
                'avg_velocity_m_s': 4.5,
                'max_velocity_m_s': 8.2,
            },
            '8': {
                'zone_name': 'Right-Forward',
                'time_percent': 29.2,
                'distance_m': 3066.0,
                'avg_velocity_m_s': 4.8,
                'max_velocity_m_s': 9.1,
            }
        }
    }


# ===== Tests: PlayerStatsAggregator - Validación Básica =====

class TestPlayerStatsAggregatorInit:
    """Tests de inicialización."""

    def test_init_default_parameters(self):
        """Verifica inicialización con parámetros default."""
        agg = PlayerStatsAggregator(team_id="A")
        assert agg.team_id == "A"
        assert agg.team_size == 11
        assert len(agg.players_stats) == 0

    def test_init_custom_team_size(self):
        """Verifica inicialización con tamaño de equipo customizado."""
        agg = PlayerStatsAggregator(team_id="B", team_size=15)
        assert agg.team_id == "B"
        assert agg.team_size == 15

    def test_multiple_aggregators(self):
        """Verifica que múltiples agregadores son independientes."""
        agg_a = PlayerStatsAggregator(team_id="A")
        agg_b = PlayerStatsAggregator(team_id="B")
        assert agg_a.team_id != agg_b.team_id
        assert agg_a.players_stats is not agg_b.players_stats


class TestAggregatePlayerStats:
    """Tests de agregación de estadísticas."""

    def test_aggregate_valid_stats(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Agrega estadísticas válidas exitosamente."""
        stats = aggregator.aggregate_player_stats(
            player_id=7,
            player_number=7,
            player_name="Cristiano",
            position="FWD",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        assert stats.player_id == 7
        assert stats.player_number == 7
        assert stats.player_name == "Cristiano"
        assert stats.position == "FWD"
        assert stats.distance_total_m == 10500.0
        assert stats.distance_total_km == 10.5

    def test_aggregate_multiple_players(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Agrega múltiples jugadores."""
        for player_id in range(1, 12):
            aggregator.aggregate_player_stats(
                player_id=player_id,
                player_number=player_id,
                player_name=f"Player {player_id}",
                position="DEF",
                distance_metrics=distance_metrics_valid,
                velocity_metrics=velocity_metrics_valid,
                intensity_metrics=intensity_metrics_valid,
            )

        assert len(aggregator.players_stats) == 11
        assert aggregator.get_player_stats(1) is not None
        assert aggregator.get_player_stats(11) is not None

    def test_aggregate_with_zones(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid, zones_data_valid
    ):
        """Agrega estadísticas incluyendo datos de zonas."""
        stats = aggregator.aggregate_player_stats(
            player_id=10,
            player_number=10,
            player_name="Messi",
            position="MID",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
            zones_data=zones_data_valid,
        )

        assert stats.dominant_zone == "Center-Mid"
        assert stats.zone_concentration_pct == 42.5
        assert len(stats.zones_visited) == 3
        assert len(stats.zone_stats) == 3

    def test_aggregate_with_heatmap(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Agrega estadísticas con ruta de heatmap."""
        heatmap_path = "/data/heatmaps/player_7.png"
        stats = aggregator.aggregate_player_stats(
            player_id=7,
            player_number=7,
            player_name="Ronaldo",
            position="FWD",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
            heatmap_path=heatmap_path,
        )

        assert stats.heatmap_path == heatmap_path

    def test_aggregate_with_analysis_frames(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Agrega con información de frames analizados."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Goalkeeper",
            position="GK",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
            analysis_frames=1800,
        )

        assert stats.analysis_frames == 1800


# ===== Tests: Validación de Datos =====

class TestDataValidation:
    """Tests de validación y manejo de datos faltantes."""

    def test_validate_float_valid(self, aggregator):
        """Valida float válido."""
        assert aggregator._validate_float(5.5) == 5.5
        assert aggregator._validate_float(0.0) == 0.0

    def test_validate_float_invalid_type(self, aggregator):
        """Maneja tipos inválidos."""
        assert aggregator._validate_float("invalid") == 0.0
        assert aggregator._validate_float(None) == 0.0

    def test_validate_float_with_limits(self, aggregator):
        """Respeta límites mínimo y máximo."""
        assert aggregator._validate_float(-5.0, min_val=0.0) == 0.0
        assert aggregator._validate_float(150.0, max_val=100.0) == 100.0
        assert aggregator._validate_float(50.0, min_val=0.0, max_val=100.0) == 50.0

    def test_validate_float_custom_default(self, aggregator):
        """Usa valor default personalizado."""
        assert aggregator._validate_float("bad", default=10.0) == 10.0

    def test_validate_int_valid(self, aggregator):
        """Valida int válido."""
        assert aggregator._validate_int(5) == 5
        assert aggregator._validate_int(0) == 0

    def test_validate_int_from_float(self, aggregator):
        """Convierte float a int."""
        assert aggregator._validate_int(5.9) == 5

    def test_validate_int_invalid_type(self, aggregator):
        """Maneja tipos inválidos."""
        assert aggregator._validate_int("invalid") == 0
        assert aggregator._validate_int(None) == 0

    def test_validate_int_with_limits(self, aggregator):
        """Respeta límites."""
        assert aggregator._validate_int(-5, min_val=0) == 0
        assert aggregator._validate_int(150, max_val=100) == 100

    def test_missing_distance_metrics(
        self, aggregator, velocity_metrics_valid, intensity_metrics_valid
    ):
        """Maneja métricas de distancia faltantes."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics={},
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        assert stats.distance_total_m == 0.0
        assert stats.distance_total_km == 0.0

    def test_missing_velocity_metrics(
        self, aggregator, distance_metrics_valid, intensity_metrics_valid
    ):
        """Maneja métricas de velocidad faltantes."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics=distance_metrics_valid,
            velocity_metrics={},
            intensity_metrics=intensity_metrics_valid,
        )

        assert stats.velocity_max == 0.0
        assert stats.velocity_avg == 0.0

    def test_missing_intensity_metrics(
        self, aggregator, distance_metrics_valid, velocity_metrics_valid
    ):
        """Maneja métricas de intensidad faltantes."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics={},
        )

        assert stats.intensity_pct == 0.0
        assert stats.sprints_count == 0

    def test_intensity_percentage_bounds(
        self, aggregator, distance_metrics_valid, velocity_metrics_valid
    ):
        """Asegura que intensidad está entre 0-100%."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics={'movement_intensity_percent': 150.0},
        )

        assert stats.intensity_pct == 100.0


# ===== Tests: Cálculo de Percentiles =====

class TestPercentileCalculation:
    """Tests de cálculo de percentiles."""

    def test_calculate_percentile_min(self, aggregator):
        """Calcula percentil para valor mínimo."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        percentile = aggregator._calculate_percentile(10.0, values)
        assert percentile == 20.0  # 1 de 5 = 20%

    def test_calculate_percentile_max(self, aggregator):
        """Calcula percentil para valor máximo."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        percentile = aggregator._calculate_percentile(50.0, values)
        assert percentile == 100.0

    def test_calculate_percentile_middle(self, aggregator):
        """Calcula percentil para valor medio."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        percentile = aggregator._calculate_percentile(30.0, values)
        assert percentile == 60.0  # 3 de 5 = 60%

    def test_calculate_percentile_empty_list(self, aggregator):
        """Maneja lista vacía."""
        percentile = aggregator._calculate_percentile(10.0, [])
        assert percentile == 0.0

    def test_calculate_team_percentiles(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Calcula percentiles para todos los jugadores."""
        # Agregar 3 jugadores con diferentes distancias
        for i in range(3):
            distance_metrics = {**distance_metrics_valid,
                              'total_distance_m': 8000 + (i * 1000)}
            aggregator.aggregate_player_stats(
                player_id=i+1,
                player_number=i+1,
                player_name=f"Player {i+1}",
                position="MID",
                distance_metrics=distance_metrics,
                velocity_metrics=velocity_metrics_valid,
                intensity_metrics=intensity_metrics_valid,
            )

        aggregator.calculate_team_percentiles()

        # Verificar que cada jugador tiene percentiles calculados
        for player_stats in aggregator.get_all_stats():
            assert player_stats.distance_percentile >= 0.0
            assert player_stats.distance_percentile <= 100.0
            assert player_stats.velocity_percentile >= 0.0
            assert player_stats.intensity_percentile >= 0.0

    def test_team_percentiles_three_players(
        self, aggregator, velocity_metrics_valid, intensity_metrics_valid
    ):
        """Verifica percentiles específicos con 3 jugadores."""
        # Jugador 1: 5000m
        aggregator.aggregate_player_stats(
            player_id=1, player_number=1, player_name="P1", position="DEF",
            distance_metrics={'total_distance_m': 5000},
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        # Jugador 2: 10000m
        aggregator.aggregate_player_stats(
            player_id=2, player_number=2, player_name="P2", position="MID",
            distance_metrics={'total_distance_m': 10000},
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        # Jugador 3: 8000m
        aggregator.aggregate_player_stats(
            player_id=3, player_number=3, player_name="P3", position="FWD",
            distance_metrics={'total_distance_m': 8000},
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        aggregator.calculate_team_percentiles()

        p1 = aggregator.get_player_stats(1)
        p2 = aggregator.get_player_stats(2)
        p3 = aggregator.get_player_stats(3)

        # Jugador 1 debe tener percentil bajo
        assert p1.distance_percentile < p3.distance_percentile < p2.distance_percentile


# ===== Tests: Determinación de Perfil =====

class TestMovementProfileDetermination:
    """Tests de determinación de perfil de movimiento."""

    def test_profile_static_player(self, aggregator):
        """Identifica jugador estático."""
        profile = aggregator._determine_movement_profile(10.0, 0.5, 0)
        assert profile == MovementProfile.STATIC_PLAYER.value

    def test_profile_low_intensity(self, aggregator):
        """Identifica baja intensidad."""
        profile = aggregator._determine_movement_profile(30.0, 1.5, 0)
        assert profile == MovementProfile.LOW_INTENSITY.value

    def test_profile_balanced(self, aggregator):
        """Identifica movimiento balanceado."""
        profile = aggregator._determine_movement_profile(50.0, 3.0, 2)
        assert profile == MovementProfile.BALANCED.value

    def test_profile_high_intensity(self, aggregator):
        """Identifica alta intensidad."""
        profile = aggregator._determine_movement_profile(80.0, 5.0, 5)
        assert profile == MovementProfile.HIGH_INTENSITY.value

    def test_profile_explosive(self, aggregator):
        """Identifica movimiento explosivo."""
        profile = aggregator._determine_movement_profile(70.0, 4.0, 15)
        assert profile == MovementProfile.EXPLOSIVE.value


# ===== Tests: Procesamiento de Zonas =====

class TestZoneProcessing:
    """Tests de procesamiento de datos de zonas."""

    def test_process_zones_empty(self, aggregator):
        """Maneja datos de zonas vacíos."""
        zones_visited, dominant_zone, concentration = aggregator._process_zones({})
        assert zones_visited == []
        assert dominant_zone == "Unknown"
        assert concentration == 0.0

    def test_process_zones_valid(self, aggregator, zones_data_valid):
        """Procesa datos de zonas válidos."""
        zones_visited, dominant_zone, concentration = \
            aggregator._process_zones(zones_data_valid)

        assert len(zones_visited) == 3
        assert dominant_zone == "Center-Mid"
        assert concentration == 42.5

    def test_calculate_zone_stats_empty(self, aggregator):
        """Calcula estadísticas de zonas vacías."""
        stats = aggregator._calculate_zone_stats({})
        assert stats == []

    def test_calculate_zone_stats_valid(self, aggregator, zones_data_valid):
        """Calcula estadísticas de zonas válidas."""
        stats = aggregator._calculate_zone_stats(zones_data_valid)

        assert len(stats) == 3
        assert all(isinstance(z, ZoneStats) for z in stats)

        # Verificar zona Center-Mid
        center_zone = next((z for z in stats if z.zone_name == 'Center-Mid'), None)
        assert center_zone is not None
        assert center_zone.time_percent == 42.5
        assert center_zone.distance_m == 4462.5


# ===== Tests: Team Summary =====

class TestTeamSummary:
    """Tests de generación de resumen del equipo."""

    def test_team_summary_empty(self, aggregator):
        """Maneja equipo sin jugadores."""
        summary = aggregator.get_team_summary()
        assert summary == {}

    def test_team_summary_single_player(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Genera resumen con un solo jugador."""
        aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        summary = aggregator.get_team_summary()

        assert summary['team_id'] == "A"
        assert summary['players_count'] == 1
        assert summary['distance_avg_m'] == 10500.0

    def test_team_summary_multiple_players(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Genera resumen con múltiples jugadores."""
        for i in range(11):
            aggregator.aggregate_player_stats(
                player_id=i+1,
                player_number=i+1,
                player_name=f"Player {i+1}",
                position="MID",
                distance_metrics=distance_metrics_valid,
                velocity_metrics=velocity_metrics_valid,
                intensity_metrics=intensity_metrics_valid,
            )

        summary = aggregator.get_team_summary()

        assert summary['players_count'] == 11
        assert summary['distance_avg_m'] > 0
        assert summary['velocity_avg_m_s'] > 0
        assert summary['intensity_avg_pct'] > 0
        assert summary['sprints_total'] == 132  # 11 * 12


# ===== Tests: Getters =====

class TestGetters:
    """Tests de métodos de obtención de datos."""

    def test_get_player_stats(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Obtiene estadísticas de jugador específico."""
        aggregator.aggregate_player_stats(
            player_id=7,
            player_number=7,
            player_name="Test",
            position="MID",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        stats = aggregator.get_player_stats(7)
        assert stats is not None
        assert stats.player_id == 7

    def test_get_player_stats_nonexistent(self, aggregator):
        """Retorna None para jugador inexistente."""
        stats = aggregator.get_player_stats(999)
        assert stats is None

    def test_get_all_stats_empty(self, aggregator):
        """Retorna lista vacía sin jugadores."""
        stats = aggregator.get_all_stats()
        assert stats == []

    def test_get_all_stats_multiple(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Retorna todos los jugadores."""
        for i in range(3):
            aggregator.aggregate_player_stats(
                player_id=i+1,
                player_number=i+1,
                player_name=f"P{i+1}",
                position="DEF",
                distance_metrics=distance_metrics_valid,
                velocity_metrics=velocity_metrics_valid,
                intensity_metrics=intensity_metrics_valid,
            )

        stats = aggregator.get_all_stats()
        assert len(stats) == 3


# ===== Tests: StatsExporter - JSON =====

class TestStatsExporterJSON:
    """Tests de exportación a JSON."""

    def test_export_json_creates_file(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Crea archivo JSON exitosamente."""
        aggregator = PlayerStatsAggregator(team_id="A")
        stats = aggregator.aggregate_player_stats(
            player_id=7,
            player_number=7,
            player_name="Test",
            position="FWD",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        exporter = StatsExporter(output_dir=temp_export_dir)
        filepath = exporter.export_json(stats)

        assert filepath.exists()
        assert filepath.suffix == '.json'

    def test_export_json_content(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Verifica contenido del archivo JSON."""
        aggregator = PlayerStatsAggregator(team_id="A")
        stats = aggregator.aggregate_player_stats(
            player_id=7,
            player_number=7,
            player_name="Ronaldo",
            position="FWD",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        exporter = StatsExporter(output_dir=temp_export_dir)
        filepath = exporter.export_json(stats)

        with open(filepath, 'r') as f:
            data = json.load(f)

        assert data['player_name'] == "Ronaldo"
        assert data['player_number'] == 7
        assert data['team_id'] == "A"
        assert data['distance_total_m'] == 10500.0

    def test_export_json_custom_filename(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Usa nombre de archivo personalizado."""
        aggregator = PlayerStatsAggregator(team_id="A")
        stats = aggregator.aggregate_player_stats(
            player_id=7,
            player_number=7,
            player_name="Test",
            position="FWD",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        exporter = StatsExporter(output_dir=temp_export_dir)
        filepath = exporter.export_json(stats, filename="custom_name.json")

        assert filepath.name == "custom_name.json"


# ===== Tests: StatsExporter - CSV =====

class TestStatsExporterCSV:
    """Tests de exportación a CSV."""

    def test_export_csv_creates_file(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Crea archivo CSV exitosamente."""
        aggregator = PlayerStatsAggregator(team_id="A")
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Player 1",
            position="DEF",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        exporter = StatsExporter(output_dir=temp_export_dir)
        filepath = exporter.export_csv([stats])

        assert filepath.exists()
        assert filepath.suffix == '.csv'

    def test_export_csv_content(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Verifica contenido del archivo CSV."""
        aggregator = PlayerStatsAggregator(team_id="A")
        stats = aggregator.aggregate_player_stats(
            player_id=7,
            player_number=7,
            player_name="Messi",
            position="MID",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        exporter = StatsExporter(output_dir=temp_export_dir)
        filepath = exporter.export_csv([stats])

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]['player_name'] == "Messi"
        assert rows[0]['player_number'] == "7"

    def test_export_csv_multiple_players(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Exporta múltiples jugadores a CSV."""
        aggregator = PlayerStatsAggregator(team_id="A")
        all_stats = []

        for i in range(5):
            stats = aggregator.aggregate_player_stats(
                player_id=i+1,
                player_number=i+1,
                player_name=f"Player {i+1}",
                position="MID",
                distance_metrics=distance_metrics_valid,
                velocity_metrics=velocity_metrics_valid,
                intensity_metrics=intensity_metrics_valid,
            )
            all_stats.append(stats)

        exporter = StatsExporter(output_dir=temp_export_dir)
        filepath = exporter.export_csv(all_stats)

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 5

    def test_export_csv_empty_list_raises(self, temp_export_dir):
        """Lanza excepción con lista vacía."""
        exporter = StatsExporter(output_dir=temp_export_dir)
        with pytest.raises(ValueError):
            exporter.export_csv([])


# ===== Tests: StatsExporter - Comparativa =====

class TestStatsExporterComparison:
    """Tests de exportación de comparativa."""

    def test_export_comparison_json(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Exporta comparativa JSON exitosamente."""
        aggregator = PlayerStatsAggregator(team_id="A")
        stats = aggregator.aggregate_player_stats(
            player_id=7,
            player_number=7,
            player_name="Test",
            position="FWD",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        aggregator.calculate_team_percentiles()
        team_summary = aggregator.get_team_summary()

        exporter = StatsExporter(output_dir=temp_export_dir)
        filepath = exporter.export_comparison_json(
            [stats], team_summary
        )

        assert filepath.exists()

        with open(filepath, 'r') as f:
            data = json.load(f)

        assert 'timestamp' in data
        assert 'team_summary' in data
        assert 'players' in data


# ===== Tests: StatsExporter - Summary =====

class TestStatsExporterSummary:
    """Tests de exportación de resumen ejecutivo."""

    def test_generate_summary(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Genera resumen ejecutivo exitosamente."""
        aggregator = PlayerStatsAggregator(team_id="A")

        for i in range(5):
            aggregator.aggregate_player_stats(
                player_id=i+1,
                player_number=i+1,
                player_name=f"Player {i+1}",
                position="MID",
                distance_metrics=distance_metrics_valid,
                velocity_metrics=velocity_metrics_valid,
                intensity_metrics=intensity_metrics_valid,
            )

        aggregator.calculate_team_percentiles()
        team_summary = aggregator.get_team_summary()

        exporter = StatsExporter(output_dir=temp_export_dir)
        filepath = exporter.generate_summary(
            aggregator.get_all_stats(), team_summary
        )

        assert filepath.exists()

        with open(filepath, 'r') as f:
            data = json.load(f)

        assert 'timestamp' in data
        assert 'format_version' in data
        assert 'top_performers' in data
        assert 'statistics' in data


# ===== Tests: StatsExporter - Export All =====

class TestStatsExporterExportAll:
    """Tests de exportación completa."""

    def test_export_all(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Exporta todos los formatos exitosamente."""
        aggregator = PlayerStatsAggregator(team_id="A")

        for i in range(3):
            aggregator.aggregate_player_stats(
                player_id=i+1,
                player_number=i+1,
                player_name=f"Player {i+1}",
                position="MID",
                distance_metrics=distance_metrics_valid,
                velocity_metrics=velocity_metrics_valid,
                intensity_metrics=intensity_metrics_valid,
            )

        aggregator.calculate_team_percentiles()

        exporter = StatsExporter(output_dir=temp_export_dir)
        exports = exporter.export_all(aggregator)

        # Verificar que se crearon todos los archivos
        assert 'csv' in exports
        assert 'comparison' in exports
        assert 'summary' in exports
        assert all(path.exists() for path in exports.values())

    def test_export_all_with_prefix(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Exporta con prefijo personalizado."""
        aggregator = PlayerStatsAggregator(team_id="A")
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        exporter = StatsExporter(output_dir=temp_export_dir)
        exports = exporter.export_all(aggregator, prefix="match_")

        # Verificar que los prefijos están en los nombres
        csv_file = exports['csv']
        assert csv_file.name.startswith('match_')


# ===== Tests: Edge Cases =====

class TestEdgeCases:
    """Tests de casos límite."""

    def test_aggregate_zero_values(
        self, aggregator
    ):
        """Maneja todas las métricas en cero."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Injured",
            position="DEF",
            distance_metrics={'total_distance_m': 0.0},
            velocity_metrics={},
            intensity_metrics={},
        )

        assert stats.distance_total_m == 0.0
        assert stats.velocity_avg == 0.0
        assert stats.intensity_pct == 0.0

    def test_very_large_values(
        self, aggregator
    ):
        """Maneja valores muy grandes."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics={'total_distance_m': 99999.99},
            velocity_metrics={'max_velocity_m_s': 99.99},
            intensity_metrics={'movement_intensity_percent': 100.0},
        )

        assert stats.distance_total_m == 99999.99
        assert stats.velocity_max == 99.99

    def test_negative_values_rejected(
        self, aggregator
    ):
        """Rechaza valores negativos."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics={'total_distance_m': -100.0},
            velocity_metrics={'max_velocity_m_s': -5.0},
            intensity_metrics={},
        )

        # Los valores negativos deben convertirse a 0 (por validación)
        assert stats.distance_total_m == 0.0
        assert stats.velocity_max == 0.0

    def test_timestamp_iso8601_format(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Verifica que timestamp está en formato ISO 8601."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        # Validar que es ISO 8601
        try:
            datetime.fromisoformat(stats.timestamp)
            valid = True
        except ValueError:
            valid = False

        assert valid

    def test_format_version(
        self, aggregator, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid
    ):
        """Verifica versión del formato."""
        stats = aggregator.aggregate_player_stats(
            player_id=1,
            player_number=1,
            player_name="Test",
            position="DEF",
            distance_metrics=distance_metrics_valid,
            velocity_metrics=velocity_metrics_valid,
            intensity_metrics=intensity_metrics_valid,
        )

        assert stats.format_version == "1.0"


# ===== Marker Tests =====

@pytest.mark.integration
class TestIntegration:
    """Tests de integración completa."""

    def test_full_workflow(
        self, temp_export_dir, distance_metrics_valid,
        velocity_metrics_valid, intensity_metrics_valid, zones_data_valid
    ):
        """Tests flujo completo: agregación -> percentiles -> exportación."""
        aggregator = PlayerStatsAggregator(team_id="HomeTeam", team_size=11)

        # Agregar jugadores
        for i in range(11):
            agg_dist = {**distance_metrics_valid,
                       'total_distance_m': 8000 + (i * 500)}
            aggregator.aggregate_player_stats(
                player_id=i+1,
                player_number=i+1,
                player_name=f"Player {i+1}",
                position=["GK", "DEF", "DEF", "DEF", "MID", "MID", "MID", "MID", "FWD", "FWD", "FWD"][i],
                distance_metrics=agg_dist,
                velocity_metrics=velocity_metrics_valid,
                intensity_metrics=intensity_metrics_valid,
                zones_data=zones_data_valid if i % 2 == 0 else None,
            )

        # Calcular percentiles
        aggregator.calculate_team_percentiles()

        # Exportar todo
        exporter = StatsExporter(output_dir=temp_export_dir)
        exports = exporter.export_all(aggregator)

        # Verificar que todo se exportó
        assert len(exports) >= 4  # Al menos CSV, comparison, summary, y player JSONs

        # Verificar CSV
        with open(exports['csv'], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 11

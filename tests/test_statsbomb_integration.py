"""
test_statsbomb_integration.py - Tests completos de integración StatsBomb

Tests de validación end-to-end para integración con datos StatsBomb.
Cubre: carga de datos, validación, comparativas, dashboard y edge cases.

Total: 18 tests cubriendo todos los aspectos de la integración.
"""

import pytest
import json
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from core.statsbomb_integration import (
    StatsBombIntegration,
    StatsBombBenchmark,
    ComparisonResult,
    ComparisonLevel,
    StatsBombData,
)


class TestStatsBombIntegrationInitialization:
    """Tests de inicialización de la integración StatsBomb"""

    def test_init_default_path(self):
        """Inicializa con ruta default"""
        integrator = StatsBombIntegration()
        assert integrator.data_path == Path("data/statsbomb")
        assert integrator.data is not None

    def test_init_custom_path(self, tmp_path):
        """Inicializa con ruta personalizada"""
        custom_path = str(tmp_path / "custom_statsbomb")
        integrator = StatsBombIntegration(data_path=custom_path)
        assert integrator.data_path == Path(custom_path)

    def test_init_loads_default_benchmarks(self):
        """Carga benchmarks por defecto"""
        integrator = StatsBombIntegration()

        assert "distance" in integrator.data.benchmarks
        assert "velocity" in integrator.data.benchmarks
        assert "intensity" in integrator.data.benchmarks

    def test_benchmarks_have_all_positions(self):
        """Verifica que todos los benchmarks incluyen todas las posiciones"""
        integrator = StatsBombIntegration()

        expected_positions = ["GK", "DEF", "MID", "FWD"]

        for metric, benchmarks in integrator.data.benchmarks.items():
            for position in expected_positions:
                assert position in benchmarks, f"Position {position} missing in {metric}"


class TestBenchmarkRetrieval:
    """Tests de recuperación de benchmarks"""

    def test_get_benchmark_valid(self):
        """Obtiene benchmark válido"""
        integrator = StatsBombIntegration()

        benchmark = integrator.get_benchmark("MID", "distance")
        assert benchmark is not None
        assert benchmark.position == "MID"
        assert benchmark.metric_name == "distance_m"

    def test_get_benchmark_all_positions(self):
        """Obtiene benchmarks para todas las posiciones"""
        integrator = StatsBombIntegration()

        positions = ["GK", "DEF", "MID", "FWD"]
        metrics = ["distance", "velocity", "intensity"]

        for position in positions:
            for metric in metrics:
                benchmark = integrator.get_benchmark(position, metric)
                assert benchmark is not None
                assert benchmark.position == position

    def test_get_benchmark_invalid_position(self):
        """Retorna None para posición inválida"""
        integrator = StatsBombIntegration()

        benchmark = integrator.get_benchmark("INVALID", "distance")
        assert benchmark is None

    def test_get_benchmark_invalid_metric(self):
        """Retorna None para métrica inválida"""
        integrator = StatsBombIntegration()

        benchmark = integrator.get_benchmark("MID", "invalid_metric")
        assert benchmark is None

    def test_benchmark_statistical_validity(self):
        """Verifica validez estadística de benchmarks"""
        integrator = StatsBombIntegration()

        benchmark = integrator.get_benchmark("MID", "distance")

        # Percentiles deben estar en orden creciente
        assert benchmark.percentile_10 < benchmark.percentile_25
        assert benchmark.percentile_25 < benchmark.percentile_50
        assert benchmark.percentile_50 < benchmark.percentile_75
        assert benchmark.percentile_75 < benchmark.percentile_90

        # Min/max deben estar en los extremos
        assert benchmark.min_value < benchmark.percentile_10
        assert benchmark.percentile_90 < benchmark.max_value

        # Media debe estar cerca de la mediana
        assert abs(benchmark.mean - benchmark.percentile_50) < benchmark.std * 0.5


class TestPlayerDataValidation:
    """Tests de validación de datos de jugador"""

    def test_validate_player_data_valid(self):
        """Valida datos correctos"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test Player",
            "position": "MID",
            "distance_m": 11000.0,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 75.0
        }

        is_valid, errors = integrator.validate_player_data(player_data)
        assert is_valid
        assert len(errors) == 0

    def test_validate_player_data_missing_fields(self):
        """Detecta campos faltantes"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test Player",
            # Faltan position, distance_m, etc.
        }

        is_valid, errors = integrator.validate_player_data(player_data)
        assert not is_valid
        assert len(errors) > 0

    def test_validate_player_data_invalid_position(self):
        """Rechaza posición inválida"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test Player",
            "position": "INVALID",
            "distance_m": 11000.0,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 75.0
        }

        is_valid, errors = integrator.validate_player_data(player_data)
        assert not is_valid
        assert any("Invalid position" in e for e in errors)

    def test_validate_player_data_negative_distance(self):
        """Rechaza distancia negativa"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test Player",
            "position": "MID",
            "distance_m": -1000.0,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 75.0
        }

        is_valid, errors = integrator.validate_player_data(player_data)
        assert not is_valid
        assert any("non-negative" in e for e in errors)

    def test_validate_player_data_negative_velocity(self):
        """Rechaza velocidad negativa"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test Player",
            "position": "MID",
            "distance_m": 11000.0,
            "max_velocity_m_s": -5.0,
            "intensity_percent": 75.0
        }

        is_valid, errors = integrator.validate_player_data(player_data)
        assert not is_valid
        assert any("non-negative" in e for e in errors)

    def test_validate_player_data_invalid_intensity(self):
        """Rechaza intensidad fuera de rango"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test Player",
            "position": "MID",
            "distance_m": 11000.0,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 150.0  # Mayor a 100%
        }

        is_valid, errors = integrator.validate_player_data(player_data)
        assert not is_valid
        assert any("between 0 and 100" in e for e in errors)


class TestPlayerComparisons:
    """Tests de comparación de jugadores con benchmarks"""

    def test_compare_player_distance_above_average(self):
        """Compara jugador con distancia por encima del promedio"""
        integrator = StatsBombIntegration()

        result = integrator.compare_player_distance(
            player_id=1,
            player_name="Quick Player",
            position="MID",
            distance_m=13000.0  # Por encima del promedio (~11500)
        )

        assert isinstance(result, ComparisonResult)
        assert result.player_value == 13000.0
        assert result.is_above_average
        assert result.percentile_rank > 50

    def test_compare_player_distance_below_average(self):
        """Compara jugador con distancia por debajo del promedio"""
        integrator = StatsBombIntegration()

        result = integrator.compare_player_distance(
            player_id=2,
            player_name="Slow Player",
            position="MID",
            distance_m=9500.0  # Por debajo del promedio
        )

        assert not result.is_above_average
        assert result.percentile_rank < 50

    def test_compare_player_velocity_exceptional(self):
        """Identifica velocidad excepcional"""
        integrator = StatsBombIntegration()

        result = integrator.compare_player_velocity(
            player_id=3,
            player_name="Fast Player",
            position="FWD",
            max_velocity_m_s=12.0  # Muy por encima del promedio (~10.2)
        )

        assert result.strength_level == "exceptional"
        assert result.percentile_rank >= 90

    def test_compare_player_intensity_average(self):
        """Compara jugador con intensidad promedio"""
        integrator = StatsBombIntegration()

        result = integrator.compare_player_intensity(
            player_id=4,
            player_name="Average Player",
            position="DEF",
            intensity_percent=75.0  # Promedio para DEF
        )

        assert result.strength_level == "average"
        assert 40 < result.percentile_rank < 60

    def test_compare_different_positions(self):
        """Compara misma métrica en diferentes posiciones"""
        integrator = StatsBombIntegration()

        # Goalkeeper a 5000m (normal para GK)
        gk_result = integrator.compare_player_distance(
            player_id=10,
            player_name="Goalkeeper",
            position="GK",
            distance_m=5000.0
        )

        # Midfielder a 5000m (bajo para MID)
        mid_result = integrator.compare_player_distance(
            player_id=11,
            player_name="Midfielder",
            position="MID",
            distance_m=5000.0
        )

        # Ambos deberían tener percentiles diferentes
        assert gk_result.percentile_rank > mid_result.percentile_rank


class TestComparisonReports:
    """Tests de generación de reportes de comparación"""

    def test_generate_comparison_report_valid_data(self):
        """Genera reporte completo con datos válidos"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 7,
            "player_name": "Cristiano",
            "position": "FWD",
            "distance_m": 10500.0,
            "max_velocity_m_s": 10.5,
            "intensity_percent": 80.0
        }

        report = integrator.generate_comparison_report(player_data)

        assert report["valid"]
        assert report["player_id"] == 7
        assert report["player_name"] == "Cristiano"
        assert "comparisons" in report
        assert "distance" in report["comparisons"]
        assert "velocity" in report["comparisons"]
        assert "intensity" in report["comparisons"]

    def test_comparison_report_includes_percentiles(self):
        """Verifica que el reporte incluye percentiles"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test",
            "position": "MID",
            "distance_m": 11500.0,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 80.0
        }

        report = integrator.generate_comparison_report(player_data)

        assert "overall_percentile" in report
        assert 0 <= report["overall_percentile"] <= 100

    def test_comparison_report_includes_summary(self):
        """Verifica que el reporte incluye resumen textual"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test",
            "position": "MID",
            "distance_m": 11500.0,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 80.0
        }

        report = integrator.generate_comparison_report(player_data)

        assert "summary" in report
        assert isinstance(report["summary"], str)
        assert len(report["summary"]) > 0

    def test_comparison_report_invalid_data(self):
        """Retorna error para datos inválidos"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            # Faltan campos requeridos
        }

        report = integrator.generate_comparison_report(player_data)

        assert not report["valid"]
        assert "errors" in report

    def test_comparison_report_elite_player(self):
        """Genera reporte para jugador de elite"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Elite",
            "position": "MID",
            "distance_m": 13500.0,  # Top percentile
            "max_velocity_m_s": 11.5,  # Top percentile
            "intensity_percent": 90.0  # Top percentile
        }

        report = integrator.generate_comparison_report(player_data)

        assert report["overall_percentile"] > 80
        assert "elite" in report["summary"].lower()

    def test_comparison_report_struggling_player(self):
        """Genera reporte para jugador con dificultades"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Struggling",
            "position": "MID",
            "distance_m": 8000.0,  # Bajo
            "max_velocity_m_s": 7.5,  # Bajo
            "intensity_percent": 40.0  # Bajo
        }

        report = integrator.generate_comparison_report(player_data)

        assert report["overall_percentile"] < 20


class TestExportFunctionality:
    """Tests de funcionalidad de exportación"""

    def test_export_comparison_json(self, tmp_path):
        """Exporta comparación a JSON correctamente"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test",
            "position": "MID",
            "distance_m": 11500.0,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 80.0
        }

        output_path = tmp_path / "comparison.json"
        result_path = integrator.export_comparison_json(player_data, output_path)

        assert result_path.exists()
        assert result_path.suffix == ".json"

    def test_export_json_content(self, tmp_path):
        """Verifica contenido del JSON exportado"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 5,
            "player_name": "Test Player",
            "position": "DEF",
            "distance_m": 10000.0,
            "max_velocity_m_s": 9.8,
            "intensity_percent": 75.0
        }

        output_path = tmp_path / "comparison.json"
        integrator.export_comparison_json(player_data, output_path)

        with open(output_path, 'r') as f:
            data = json.load(f)

        assert data["player_id"] == 5
        assert data["valid"]
        assert "comparisons" in data

    def test_export_creates_directory(self, tmp_path):
        """Crea directorio si no existe"""
        integrator = StatsBombIntegration()

        player_data = {
            "player_id": 1,
            "player_name": "Test",
            "position": "MID",
            "distance_m": 11500.0,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 80.0
        }

        nested_path = tmp_path / "nested" / "deep" / "path"
        output_path = nested_path / "comparison.json"

        integrator.export_comparison_json(player_data, output_path)

        assert nested_path.exists()
        assert output_path.exists()


class TestEdgeCasesAndErrors:
    """Tests de casos límite y manejo de errores"""

    def test_compare_with_zero_distance(self):
        """Maneja distancia de cero"""
        integrator = StatsBombIntegration()

        # Debería ser válido pero muy bajo
        result = integrator.compare_player_distance(
            player_id=1,
            player_name="Injured",
            position="MID",
            distance_m=0.0
        )

        assert result.percentile_rank < 1

    def test_compare_with_extreme_distance(self):
        """Maneja distancias extremas"""
        integrator = StatsBombIntegration()

        # Distancia muy alta (más que el máximo benchmark)
        result = integrator.compare_player_distance(
            player_id=1,
            player_name="Untiring",
            position="MID",
            distance_m=20000.0
        )

        assert result.percentile_rank > 99

    def test_benchmark_consistency_across_calls(self):
        """Verifica consistencia de benchmarks entre llamadas"""
        integrator = StatsBombIntegration()

        benchmark1 = integrator.get_benchmark("MID", "distance")
        benchmark2 = integrator.get_benchmark("MID", "distance")

        assert benchmark1.mean == benchmark2.mean
        assert benchmark1.std == benchmark2.std
        assert benchmark1.max_value == benchmark2.max_value

    def test_percentile_monotonicity(self):
        """Verifica que percentiles son monótonos crecientes"""
        integrator = StatsBombIntegration()

        distances = [8000, 10000, 12000, 14000]
        percentiles = []

        for distance in distances:
            result = integrator.compare_player_distance(
                player_id=1,
                player_name="Test",
                position="MID",
                distance_m=distance
            )
            percentiles.append(result.percentile_rank)

        # Percentiles deben ser monótonos crecientes
        for i in range(len(percentiles) - 1):
            assert percentiles[i] <= percentiles[i + 1]


class TestIntegrationWithPipeline:
    """Tests de integración con pipeline de análisis"""

    def test_compare_multiple_players(self, tmp_path):
        """Compara múltiples jugadores exitosamente"""
        integrator = StatsBombIntegration()

        players = [
            {
                "player_id": 1,
                "player_name": "Player 1",
                "position": "DEF",
                "distance_m": 9500.0,
                "max_velocity_m_s": 9.5,
                "intensity_percent": 72.0
            },
            {
                "player_id": 7,
                "player_name": "Player 7",
                "position": "FWD",
                "distance_m": 10000.0,
                "max_velocity_m_s": 10.5,
                "intensity_percent": 78.0
            },
            {
                "player_id": 11,
                "player_name": "Player 11",
                "position": "GK",
                "distance_m": 4500.0,
                "max_velocity_m_s": 7.5,
                "intensity_percent": 60.0
            },
        ]

        reports = []
        for player in players:
            report = integrator.generate_comparison_report(player)
            reports.append(report)
            assert report["valid"]

        # Exportar todos
        export_dir = tmp_path / "exports"
        for i, report in enumerate(reports):
            output_path = export_dir / f"player_{i}.json"
            integrator.export_comparison_json(players[i], output_path)

        assert (export_dir / "player_0.json").exists()
        assert (export_dir / "player_1.json").exists()
        assert (export_dir / "player_2.json").exists()

    def test_generate_team_comparison(self):
        """Genera comparativa de equipo completo"""
        integrator = StatsBombIntegration()

        # Simular equipo completo (11 jugadores)
        team_data = [
            # Defensa
            {"player_id": 1, "player_name": "Def1", "position": "DEF",
             "distance_m": 9500, "max_velocity_m_s": 9.5, "intensity_percent": 75},
            {"player_id": 2, "player_name": "Def2", "position": "DEF",
             "distance_m": 9800, "max_velocity_m_s": 9.8, "intensity_percent": 76},
            {"player_id": 3, "player_name": "Def3", "position": "DEF",
             "distance_m": 9600, "max_velocity_m_s": 9.6, "intensity_percent": 75},
            {"player_id": 4, "player_name": "Def4", "position": "DEF",
             "distance_m": 9700, "max_velocity_m_s": 9.7, "intensity_percent": 75},
            # Mediocampo
            {"player_id": 5, "player_name": "Mid1", "position": "MID",
             "distance_m": 11500, "max_velocity_m_s": 10.0, "intensity_percent": 80},
            {"player_id": 6, "player_name": "Mid2", "position": "MID",
             "distance_m": 11800, "max_velocity_m_s": 10.2, "intensity_percent": 81},
            {"player_id": 7, "player_name": "Mid3", "position": "MID",
             "distance_m": 11400, "max_velocity_m_s": 10.1, "intensity_percent": 80},
            {"player_id": 8, "player_name": "Mid4", "position": "MID",
             "distance_m": 11600, "max_velocity_m_s": 10.0, "intensity_percent": 80},
            # Delanteros
            {"player_id": 9, "player_name": "Fwd1", "position": "FWD",
             "distance_m": 9800, "max_velocity_m_s": 10.3, "intensity_percent": 75},
            {"player_id": 10, "player_name": "Fwd2", "position": "FWD",
             "distance_m": 10000, "max_velocity_m_s": 10.5, "intensity_percent": 76},
            # Arquero
            {"player_id": 11, "player_name": "Keeper", "position": "GK",
             "distance_m": 4500, "max_velocity_m_s": 7.8, "intensity_percent": 60},
        ]

        reports = [integrator.generate_comparison_report(p) for p in team_data]

        # Verificaciones
        assert len(reports) == 11
        assert all(r["valid"] for r in reports)

        # Calcular promedios del equipo
        team_avg_percentile = np.mean([r["overall_percentile"] for r in reports])
        assert 0 <= team_avg_percentile <= 100

        # Verificar que hay variedad en los percentiles
        percentiles = [r["overall_percentile"] for r in reports]
        assert max(percentiles) > min(percentiles)


class TestStatsBombBenchmarkStructure:
    """Tests de estructura de benchmarks de StatsBomb"""

    def test_benchmark_has_required_fields(self):
        """Verifica que benchmarks tienen campos requeridos"""
        integrator = StatsBombIntegration()

        benchmark = integrator.get_benchmark("MID", "distance")

        required_fields = [
            'position', 'metric_name', 'min_value', 'percentile_10',
            'percentile_25', 'percentile_50', 'percentile_75', 'percentile_90',
            'max_value', 'mean', 'std', 'sample_size', 'league', 'season'
        ]

        for field in required_fields:
            assert hasattr(benchmark, field)
            assert getattr(benchmark, field) is not None

    def test_benchmark_data_source(self):
        """Verifica que benchmarks indican su fuente"""
        integrator = StatsBombIntegration()

        benchmark = integrator.get_benchmark("MID", "distance")
        assert benchmark.data_source == "StatsBomb"

    def test_benchmark_league_and_season(self):
        """Verifica que benchmarks incluyen liga y temporada"""
        integrator = StatsBombIntegration()

        benchmark = integrator.get_benchmark("FWD", "velocity")
        assert benchmark.league == "Premier League"
        assert benchmark.season == 2024



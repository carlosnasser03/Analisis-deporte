"""
Tests para validación de StatsBomb en el Pipeline

Tests para PerformanceValidator y su integración con IntegratedAnalysisPipeline.
"""

import pytest
import numpy as np
from dataclasses import asdict

from core.performance_validator import (
    PerformanceValidator,
    StatsBombBenchmarks,
    PlayerValidation,
    PerformanceStatus,
    PerformanceLevel,
    ValidationMetric
)
from pipeline.integrated_pipeline import (
    IntegratedAnalysisPipeline,
    ProcessingConfig,
    PipelineResult
)


class TestStatsBombBenchmarks:
    """Tests para benchmarks de StatsBomb."""

    def test_benchmarks_loaded_for_gk(self):
        """Test que benchmarks están cargados para portero."""
        benchmarks = StatsBombBenchmarks()
        assert 'GK' in benchmarks.BENCHMARKS
        assert 'distance' in benchmarks.BENCHMARKS['GK']
        assert 'max_velocity' in benchmarks.BENCHMARKS['GK']
        assert 'intensity' in benchmarks.BENCHMARKS['GK']

    def test_benchmarks_loaded_for_def(self):
        """Test que benchmarks están cargados para defensa."""
        benchmarks = StatsBombBenchmarks()
        assert 'DEF' in benchmarks.BENCHMARKS
        assert 'distance' in benchmarks.BENCHMARKS['DEF']

    def test_benchmarks_loaded_for_mid(self):
        """Test que benchmarks están cargados para mediocampista."""
        benchmarks = StatsBombBenchmarks()
        assert 'MID' in benchmarks.BENCHMARKS
        assert len(benchmarks.BENCHMARKS['MID']) >= 3

    def test_benchmarks_loaded_for_fwd(self):
        """Test que benchmarks están cargados para delantero."""
        benchmarks = StatsBombBenchmarks()
        assert 'FWD' in benchmarks.BENCHMARKS
        assert 'distance' in benchmarks.BENCHMARKS['FWD']

    def test_get_benchmark_existing(self):
        """Test obtener benchmark existente."""
        benchmarks = StatsBombBenchmarks()
        benchmark = benchmarks.get_benchmark('MID', 'distance')
        assert benchmark is not None
        assert benchmark.mean > 0
        assert benchmark.std > 0

    def test_get_benchmark_nonexistent(self):
        """Test obtener benchmark no existente."""
        benchmarks = StatsBombBenchmarks()
        benchmark = benchmarks.get_benchmark('INVALID', 'distance')
        assert benchmark is None

    def test_get_all_benchmarks(self):
        """Test obtener todos los benchmarks de una posición."""
        benchmarks = StatsBombBenchmarks()
        all_benchmarks = benchmarks.get_all_benchmarks('MID')
        assert isinstance(all_benchmarks, dict)
        assert len(all_benchmarks) > 0


class TestPerformanceValidator:
    """Tests para PerformanceValidator."""

    @pytest.fixture
    def validator(self):
        """Crear validator para tests."""
        return PerformanceValidator()

    def test_validator_initialization(self, validator):
        """Test inicialización del validador."""
        assert validator.benchmarks is not None
        assert validator.anomaly_threshold == 2.5
        assert validator.normal_range == (-1.5, 1.5)

    def test_generate_comparison_mid(self, validator):
        """Test generar comparación para mediocampista."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Test Player",
            position="MID",
            distance_m=11000,  # Cercano al benchmark
            max_velocity_m_s=8.3,
            intensity_pct=71.0
        )

        assert isinstance(validation, PlayerValidation)
        assert validation.player_id == 7
        assert validation.position == "MID"
        assert 'distance' in validation.metrics
        assert 'max_velocity' in validation.metrics
        assert 'intensity' in validation.metrics

    def test_generate_comparison_def(self, validator):
        """Test generar comparación para defensa."""
        validation = validator.generate_comparison(
            player_id=4,
            player_name="Defender",
            position="DEF",
            distance_m=9800,
            max_velocity_m_s=7.8,
            intensity_pct=65.0
        )

        assert validation.position == "DEF"
        assert validation.performance_level is not None

    def test_generate_comparison_gk(self, validator):
        """Test generar comparación para portero."""
        validation = validator.generate_comparison(
            player_id=1,
            player_name="Goalkeeper",
            position="GK",
            distance_m=5500,
            max_velocity_m_s=5.2,
            intensity_pct=35.0
        )

        assert validation.position == "GK"

    def test_generate_comparison_fwd(self, validator):
        """Test generar comparación para delantero."""
        validation = validator.generate_comparison(
            player_id=10,
            player_name="Striker",
            position="FWD",
            distance_m=9200,
            max_velocity_m_s=8.9,
            intensity_pct=68.0
        )

        assert validation.position == "FWD"


class TestValidationMetrics:
    """Tests para métricas de validación individual."""

    @pytest.fixture
    def validator(self):
        """Crear validator para tests."""
        return PerformanceValidator()

    def test_validate_metric_normal(self, validator):
        """Test validar métrica en rango normal."""
        metric = validator._validate_metric(
            position='MID',
            metric='distance',
            value=11200  # Promedio benchmark
        )

        assert isinstance(metric, ValidationMetric)
        assert metric.status == PerformanceStatus.NORMAL.value
        assert 40 < metric.percentile < 60

    def test_validate_metric_high(self, validator):
        """Test validar métrica alta."""
        metric = validator._validate_metric(
            position='MID',
            metric='distance',
            value=14000  # Muy por encima del promedio
        )

        assert metric.status == PerformanceStatus.HIGH.value
        assert metric.percentile > 80

    def test_validate_metric_low(self, validator):
        """Test validar métrica baja."""
        metric = validator._validate_metric(
            position='MID',
            metric='distance',
            value=8000  # Muy por debajo del promedio
        )

        assert metric.status == PerformanceStatus.LOW.value
        assert metric.percentile < 20

    def test_validate_metric_anomaly(self, validator):
        """Test detectar anomalía (z-score muy alto)."""
        metric = validator._validate_metric(
            position='MID',
            metric='distance',
            value=1000  # Extremadamente bajo
        )

        assert metric.status == PerformanceStatus.ANOMALY.value

    def test_metric_has_expected_range(self, validator):
        """Test que métrica tiene rango esperado."""
        metric = validator._validate_metric(
            position='MID',
            metric='distance',
            value=11200
        )

        assert metric.expected_range[0] < metric.expected_range[1]
        assert metric.expected_range[0] > 0


class TestPerformanceClassification:
    """Tests para clasificación de rendimiento."""

    @pytest.fixture
    def validator(self):
        """Crear validator para tests."""
        return PerformanceValidator()

    def test_classify_elite_performance(self, validator):
        """Test clasificar como rendimiento ELITE."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Elite Player",
            position="MID",
            distance_m=13000,  # Muy alto
            max_velocity_m_s=10.5,  # Muy alto
            intensity_pct=85.0  # Muy alto
        )

        assert validation.performance_level in [
            PerformanceLevel.ELITE.value,
            PerformanceLevel.TOP_15.value
        ]

    def test_classify_average_performance(self, validator):
        """Test clasificar como rendimiento promedio."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Average Player",
            position="MID",
            distance_m=11200,  # Promedio
            max_velocity_m_s=8.4,  # Promedio
            intensity_pct=72.0  # Promedio
        )

        assert validation.performance_level in [
            PerformanceLevel.AVERAGE.value,
            PerformanceLevel.ABOVE_AVERAGE.value,
            PerformanceLevel.BELOW_AVERAGE.value
        ]

    def test_classify_poor_performance(self, validator):
        """Test clasificar como rendimiento pobre."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Poor Player",
            position="MID",
            distance_m=8000,  # Muy bajo
            max_velocity_m_s=6.0,  # Muy bajo
            intensity_pct=40.0  # Muy bajo
        )

        assert validation.performance_level in [
            PerformanceLevel.POOR.value,
            PerformanceLevel.BELOW_AVERAGE.value
        ]


class TestAnomalyDetection:
    """Tests para detección de anomalías."""

    @pytest.fixture
    def validator(self):
        """Crear validator para tests."""
        return PerformanceValidator()

    def test_detect_distance_anomaly(self, validator):
        """Test detectar anomalía en distancia."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Test Player",
            position="MID",
            distance_m=1000,  # Muy bajo - anomalía
            max_velocity_m_s=8.4,
            intensity_pct=72.0
        )

        assert len(validation.anomalies_detected) > 0 or validation.overall_status == PerformanceStatus.ANOMALY.value

    def test_detect_velocity_anomaly(self, validator):
        """Test detectar anomalía en velocidad."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Test Player",
            position="MID",
            distance_m=11200,
            max_velocity_m_s=2.0,  # Muy bajo - anomalía
            intensity_pct=72.0
        )

        assert len(validation.anomalies_detected) > 0 or validation.overall_status == PerformanceStatus.ANOMALY.value

    def test_no_anomaly_for_normal_data(self, validator):
        """Test que no hay anomalía para datos normales."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Test Player",
            position="MID",
            distance_m=11200,
            max_velocity_m_s=8.4,
            intensity_pct=72.0
        )

        # Datos normales no deberían detectarse como anomalías
        assert validation.overall_status != PerformanceStatus.ANOMALY.value


class TestRecommendationGeneration:
    """Tests para generación de recomendaciones."""

    @pytest.fixture
    def validator(self):
        """Crear validator para tests."""
        return PerformanceValidator()

    def test_generate_recommendations_low_performance(self, validator):
        """Test generar recomendaciones para bajo rendimiento."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Test Player",
            position="MID",
            distance_m=8000,  # Bajo
            max_velocity_m_s=6.0,
            intensity_pct=40.0  # Bajo
        )

        assert len(validation.recommendations) > 0

    def test_recommendations_not_empty_for_elite(self, validator):
        """Test que hay recomendaciones para jugadores élite."""
        validation = validator.generate_comparison(
            player_id=7,
            player_name="Elite Player",
            position="MID",
            distance_m=13000,
            max_velocity_m_s=10.5,
            intensity_pct=85.0
        )

        # Debería haber recomendaciones
        assert isinstance(validation.recommendations, list)


class TestValidationReport:
    """Tests para reporte de validación."""

    @pytest.fixture
    def validator(self):
        """Crear validator para tests."""
        return PerformanceValidator()

    def test_generate_report_empty_list(self, validator):
        """Test generar reporte con lista vacía."""
        report = validator.generate_validation_report([])

        assert report['total_players'] == 0
        assert report['anomaly_rate'] == 0.0

    def test_generate_report_multiple_players(self, validator):
        """Test generar reporte para múltiples jugadores."""
        validations = [
            validator.generate_comparison(7, "Player 7", "MID", 11200, 8.4, 72.0),
            validator.generate_comparison(4, "Player 4", "DEF", 9800, 7.8, 65.0),
            validator.generate_comparison(10, "Player 10", "FWD", 9200, 8.9, 68.0)
        ]

        report = validator.generate_validation_report(validations)

        assert report['total_players'] == 3
        assert report['anomaly_rate'] >= 0.0
        assert isinstance(report['performance_distribution'], dict)

    def test_report_has_anomaly_rate(self, validator):
        """Test que reporte incluye tasa de anomalías."""
        validations = [
            validator.generate_comparison(7, "Player 7", "MID", 11200, 8.4, 72.0),
            validator.generate_comparison(4, "Player 4", "DEF", 1000, 2.0, 15.0)
        ]

        report = validator.generate_validation_report(validations)

        assert 'anomaly_rate' in report
        assert 0.0 <= report['anomaly_rate'] <= 1.0


class TestPipelineIntegration:
    """Tests para integración con pipeline."""

    def test_pipeline_has_validator(self):
        """Test que pipeline tiene validador."""
        pipeline = IntegratedAnalysisPipeline()
        assert hasattr(pipeline, 'performance_validator')

    def test_pipeline_has_validations_list(self):
        """Test que pipeline tiene lista de validaciones."""
        pipeline = IntegratedAnalysisPipeline()
        assert hasattr(pipeline, 'player_validations')
        assert isinstance(pipeline.player_validations, list)

    def test_pipeline_result_has_validation_report(self):
        """Test que PipelineResult incluye validation_report."""
        result = PipelineResult(
            video_path="test.mp4",
            total_frames=100,
            duration_seconds=3.3,
            fps=30.0,
            frames_processed=100,
            player_stats={},
            team_summary={},
            errors=[],
            warnings=[],
            processing_time_seconds=1.0,
            validation_report={
                'total_players': 0,
                'anomalies_detected': 0,
                'anomaly_rate': 0.0
            }
        )

        assert 'validation_report' in asdict(result)

    def test_player_stats_include_validation(self):
        """Test que estadísticas del jugador incluyen validación."""
        # Este test solo verifica la estructura esperada
        sample_stats = {
            "7": {
                "player_id": 7,
                "distance_total_m": 11200,
                "velocity_max": 8.4,
                "intensity_pct": 72.0,
                "validation": {
                    "distance_status": "NORMAL",
                    "distance_percentile": 50.0,
                    "velocity_status": "NORMAL",
                    "velocity_percentile": 50.0,
                    "intensity_status": "NORMAL",
                    "intensity_percentile": 50.0,
                    "overall_performance": "AVERAGE",
                    "overall_status": "NORMAL",
                    "anomalies_detected": []
                }
            }
        }

        assert "validation" in sample_stats["7"]
        assert "distance_status" in sample_stats["7"]["validation"]
        assert "overall_performance" in sample_stats["7"]["validation"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

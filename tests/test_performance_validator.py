"""
test_performance_validator.py - Tests exhaustivos para PerformanceValidator

Cubre:
- Validación de distancia, velocidad e intensidad
- Detección de anomalías con z-score
- Cálculo de percentiles
- Generación de comparativas
- Manejo de casos edge y excepciones
"""

import pytest
from core.performance_validator import (
    PerformanceValidator,
    StatsBombBenchmarks,
    PlayerValidation,
    PerformanceStatus,
)


class TestPerformanceValidatorInitialization:
    """Tests de inicialización del validador."""

    def test_init_without_benchmarks_file(self):
        """Test inicialización sin archivo de benchmarks."""
        validator = PerformanceValidator()
        assert validator is not None
        assert validator.anomaly_threshold == 2.5
        assert validator.normal_range == (-1.5, 1.5)
        assert validator.benchmarks_file is None

    def test_init_with_benchmarks_file(self):
        """Test inicialización con archivo de benchmarks."""
        validator = PerformanceValidator(benchmarks_file="custom_benchmarks.json")
        assert validator.benchmarks_file == "custom_benchmarks.json"


class TestValidateDistance:
    """Tests para método validate_distance."""

    def test_validate_distance_normal_midfielder(self):
        """Test distancia normal para centrocampista."""
        validator = PerformanceValidator()
        result = validator.validate_distance(11200.0, 'MID')

        assert result['measured'] == 11200.0
        assert result['expected'] == 11200.0
        assert result['status'] == 'NORMAL'
        assert 0.0 <= result['confidence'] <= 1.0
        assert 0.0 <= result['percentile'] <= 100.0
        assert 'interpretation' in result
        assert isinstance(result['variance_percent'], float)

    def test_validate_distance_high_defender(self):
        """Test distancia alta para defensa."""
        validator = PerformanceValidator()
        result = validator.validate_distance(12500.0, 'DEF')

        assert result['status'] == 'ALTO'
        assert result['percentile'] > 50.0
        assert 'encima' in result['interpretation'] or 'superior' in result['interpretation']

    def test_validate_distance_low_goalkeeper(self):
        """Test distancia baja para portero."""
        validator = PerformanceValidator()
        result = validator.validate_distance(3500.0, 'GK')

        assert result['status'] == 'BAJO'
        assert result['percentile'] < 50.0
        assert 'debajo' in result['interpretation'] or 'inferior' in result['interpretation']

    def test_validate_distance_anomaly_forward(self):
        """Test distancia anómala para delantero."""
        validator = PerformanceValidator()
        result = validator.validate_distance(20000.0, 'FWD')

        assert result['status'] == 'ANOMALIA'
        assert result['confidence'] == 0.95
        assert 'investigación' in result['interpretation'] or 'Requiere' in result['interpretation']

    def test_validate_distance_invalid_position(self):
        """Test con posición inválida."""
        validator = PerformanceValidator()
        result = validator.validate_distance(10000.0, 'INVALID')

        assert result['status'] == 'DESCONOCIDO'
        assert result['expected'] == 0.0

    def test_validate_distance_zero_value(self):
        """Test con valor cero."""
        validator = PerformanceValidator()
        result = validator.validate_distance(0.0, 'MID')

        assert result['measured'] == 0.0
        assert result['status'] in ['BAJO', 'ANOMALIA']  # Muy bajo, puede ser anomalía

    def test_validate_distance_negative_value(self):
        """Test con valor negativo (caso edge)."""
        validator = PerformanceValidator()
        result = validator.validate_distance(-1000.0, 'MID')

        assert result['measured'] == -1000.0
        assert result['status'] in ['BAJO', 'ANOMALIA']

    def test_validate_distance_all_positions(self):
        """Test validación para todas las posiciones."""
        validator = PerformanceValidator()
        positions = ['GK', 'DEF', 'MID', 'FWD']

        for position in positions:
            result = validator.validate_distance(10000.0, position)
            assert 'measured' in result
            assert 'expected' in result
            assert 'status' in result


class TestValidateVelocity:
    """Tests para método validate_velocity."""

    def test_validate_velocity_normal_midfielder(self):
        """Test velocidad normal para centrocampista."""
        validator = PerformanceValidator()
        result = validator.validate_velocity(8.4, 'MID')

        assert result['measured'] == 8.4
        assert result['expected'] == 8.4
        assert result['status'] == 'NORMAL'
        assert 0.0 <= result['confidence'] <= 1.0
        assert 0.0 <= result['percentile'] <= 100.0

    def test_validate_velocity_high_forward(self):
        """Test velocidad alta para delantero."""
        validator = PerformanceValidator()
        result = validator.validate_velocity(11.5, 'FWD')

        assert result['status'] in ['ALTO', 'NORMAL']  # Podría ser NORMAL si está en rango
        assert result['percentile'] >= 50.0

    def test_validate_velocity_low_goalkeeper(self):
        """Test velocidad baja para portero."""
        validator = PerformanceValidator()
        result = validator.validate_velocity(3.5, 'GK')

        assert result['status'] in ['BAJO', 'ANOMALIA']  # Muy bajo
        assert result['percentile'] < 50.0

    def test_validate_velocity_anomaly_defender(self):
        """Test velocidad anómala para defensa."""
        validator = PerformanceValidator()
        result = validator.validate_velocity(15.0, 'DEF')

        assert result['status'] == 'ANOMALIA'
        assert result['confidence'] == 0.95

    def test_validate_velocity_invalid_position(self):
        """Test con posición inválida."""
        validator = PerformanceValidator()
        result = validator.validate_velocity(8.0, 'UNKNOWN')

        assert result['status'] == 'DESCONOCIDO'


class TestValidateIntensity:
    """Tests para método validate_intensity."""

    def test_validate_intensity_normal_defender(self):
        """Test intensidad normal para defensa."""
        validator = PerformanceValidator()
        result = validator.validate_intensity(65.0, 'DEF')

        assert result['measured'] == 65.0
        assert result['expected'] == 65.0
        assert result['status'] == 'NORMAL'

    def test_validate_intensity_high_midfielder(self):
        """Test intensidad alta para centrocampista."""
        validator = PerformanceValidator()
        result = validator.validate_intensity(100.0, 'MID')

        assert result['status'] in ['ALTO', 'NORMAL']  # Podría ser NORMAL
        assert result['percentile'] > 50.0

    def test_validate_intensity_low_goalkeeper(self):
        """Test intensidad baja para portero."""
        validator = PerformanceValidator()
        result = validator.validate_intensity(10.0, 'GK')

        assert result['status'] == 'BAJO'

    def test_validate_intensity_anomaly(self):
        """Test intensidad anómala."""
        validator = PerformanceValidator()
        result = validator.validate_intensity(130.0, 'MID')

        assert result['status'] == 'ANOMALIA'

    def test_validate_intensity_edge_zero(self):
        """Test intensidad en cero."""
        validator = PerformanceValidator()
        result = validator.validate_intensity(0.0, 'FWD')

        assert result['measured'] == 0.0
        assert result['status'] in ['BAJO', 'ANOMALIA']  # Muy bajo, puede ser anomalía

    def test_validate_intensity_edge_hundred(self):
        """Test intensidad en 100."""
        validator = PerformanceValidator()
        result = validator.validate_intensity(100.0, 'MID')

        assert result['measured'] == 100.0


class TestGetPerformancePercentile:
    """Tests para método get_performance_percentile."""

    def test_percentile_median_distance(self):
        """Test percentil en la mediana (distancia)."""
        validator = PerformanceValidator()
        # Usando el valor medio de MID = 11200
        percentile = validator.get_performance_percentile(11200.0, 'MID', 'distance')

        assert 48.0 <= percentile <= 52.0  # Debe estar cerca del 50%

    def test_percentile_high_velocity(self):
        """Test percentil alto (velocidad)."""
        validator = PerformanceValidator()
        # Valor por encima de la media
        percentile = validator.get_performance_percentile(10.0, 'MID', 'max_velocity')

        assert percentile > 50.0

    def test_percentile_low_velocity(self):
        """Test percentil bajo (velocidad)."""
        validator = PerformanceValidator()
        # Valor por debajo de la media
        percentile = validator.get_performance_percentile(5.0, 'MID', 'max_velocity')

        assert percentile < 50.0

    def test_percentile_invalid_position(self):
        """Test con posición inválida."""
        validator = PerformanceValidator()

        with pytest.raises(ValueError):
            validator.get_performance_percentile(100.0, 'INVALID', 'distance')

    def test_percentile_invalid_metric_type(self):
        """Test con tipo de métrica inválido."""
        validator = PerformanceValidator()

        with pytest.raises(ValueError):
            validator.get_performance_percentile(100.0, 'MID', 'invalid_metric')

    def test_percentile_all_positions_distance(self):
        """Test percentil para todas posiciones (distancia)."""
        validator = PerformanceValidator()
        positions = ['GK', 'DEF', 'MID', 'FWD']

        for position in positions:
            percentile = validator.get_performance_percentile(10000.0, position, 'distance')
            assert 0.1 <= percentile <= 99.9

    def test_percentile_all_metric_types(self):
        """Test percentil para todos tipos de métrica."""
        validator = PerformanceValidator()
        metric_types = ['distance', 'max_velocity', 'intensity']

        for metric_type in metric_types:
            percentile = validator.get_performance_percentile(
                50.0 if metric_type == 'intensity' else 8000.0,
                'MID',
                metric_type
            )
            assert 0.1 <= percentile <= 99.9


class TestDetectAnomalies:
    """Tests para método detect_anomalies."""

    def test_detect_anomalies_no_anomalies(self):
        """Test sin anomalías."""
        validator = PerformanceValidator()
        player_data = {
            'position': 'MID',
            'distance': 11200.0,
            'velocity': 8.4,
            'intensity': 72.0,
            'player_id': 1,
            'player_name': 'Test Player'
        }

        anomalies = validator.detect_anomalies(player_data)

        assert isinstance(anomalies, list)
        assert len(anomalies) == 0

    def test_detect_anomalies_single_anomaly_distance(self):
        """Test con una anomalía de distancia."""
        validator = PerformanceValidator()
        player_data = {
            'position': 'MID',
            'distance': 25000.0,  # Muy alto
            'velocity': 8.4,
            'intensity': 72.0
        }

        anomalies = validator.detect_anomalies(player_data)

        assert len(anomalies) >= 1
        distance_anomaly = [a for a in anomalies if a['metric'] == 'distance']
        assert len(distance_anomaly) > 0
        assert 'z_score' in distance_anomaly[0]
        assert 'severity' in distance_anomaly[0]
        assert 'description' in distance_anomaly[0]

    def test_detect_anomalies_single_anomaly_velocity(self):
        """Test con una anomalía de velocidad."""
        validator = PerformanceValidator()
        player_data = {
            'position': 'DEF',
            'distance': 9800.0,
            'velocity': 15.0,  # Muy alto
            'intensity': 65.0
        }

        anomalies = validator.detect_anomalies(player_data)

        assert len(anomalies) >= 1
        velocity_anomaly = [a for a in anomalies if a['metric'] == 'velocity']
        assert len(velocity_anomaly) > 0

    def test_detect_anomalies_single_anomaly_intensity(self):
        """Test con una anomalía de intensidad."""
        validator = PerformanceValidator()
        player_data = {
            'position': 'FWD',
            'distance': 9200.0,
            'velocity': 8.9,
            'intensity': 150.0  # Muy alto
        }

        anomalies = validator.detect_anomalies(player_data)

        assert len(anomalies) >= 1
        intensity_anomaly = [a for a in anomalies if a['metric'] == 'intensity']
        assert len(intensity_anomaly) > 0

    def test_detect_anomalies_multiple_anomalies(self):
        """Test con múltiples anomalías."""
        validator = PerformanceValidator()
        player_data = {
            'position': 'GK',
            'distance': 20000.0,  # Anomalía
            'velocity': 12.0,      # Anomalía
            'intensity': 10.0      # Normal/bajo pero no anomalía
        }

        anomalies = validator.detect_anomalies(player_data)

        assert len(anomalies) >= 2

    def test_detect_anomalies_missing_required_field(self):
        """Test con campo requerido faltante."""
        validator = PerformanceValidator()
        player_data = {
            'position': 'MID',
            'distance': 11200.0,
            # Falta 'velocity'
            'intensity': 72.0
        }

        with pytest.raises(ValueError):
            validator.detect_anomalies(player_data)

    def test_detect_anomalies_severity_levels(self):
        """Test que las severidades se calculan correctamente."""
        validator = PerformanceValidator()
        player_data = {
            'position': 'MID',
            'distance': 50000.0,  # Extremadamente alto
            'velocity': 8.4,
            'intensity': 72.0
        }

        anomalies = validator.detect_anomalies(player_data)

        # Debería tener al menos una anomalía crítica
        assert any(a['severity'] in ['CRÍTICA', 'ALTA', 'MEDIA'] for a in anomalies)

    def test_detect_anomalies_all_positions(self):
        """Test detect_anomalies para todas las posiciones."""
        validator = PerformanceValidator()
        positions = ['GK', 'DEF', 'MID', 'FWD']

        for position in positions:
            player_data = {
                'position': position,
                'distance': 30000.0,  # Anómalo
                'velocity': 8.0,
                'intensity': 70.0
            }
            anomalies = validator.detect_anomalies(player_data)
            # Debería detectar al menos la anomalía de distancia
            assert len(anomalies) >= 1


class TestGenerateComparison:
    """Tests para método generate_comparison."""

    def test_generate_comparison_normal_player(self):
        """Test comparativa con jugador normal."""
        validator = PerformanceValidator()
        validation = validator.generate_comparison(
            player_id=1,
            player_name='Test Player',
            position='MID',
            distance_m=11200.0,
            max_velocity_m_s=8.4,
            intensity_pct=72.0
        )

        assert isinstance(validation, PlayerValidation)
        assert validation.player_id == 1
        assert validation.player_name == 'Test Player'
        assert validation.position == 'MID'
        assert len(validation.metrics) == 3
        assert validation.overall_status == 'NORMAL'

    def test_generate_comparison_elite_player(self):
        """Test comparativa con jugador elite."""
        validator = PerformanceValidator()
        validation = validator.generate_comparison(
            player_id=2,
            player_name='Elite Player',
            position='MID',
            distance_m=14000.0,
            max_velocity_m_s=11.0,
            intensity_pct=95.0
        )

        assert validation.performance_level == 'ELITE'

    def test_generate_comparison_has_recommendations(self):
        """Test que las recomendaciones se generan."""
        validator = PerformanceValidator()
        validation = validator.generate_comparison(
            player_id=3,
            player_name='Below Average',
            position='DEF',
            distance_m=7000.0,  # Bajo
            max_velocity_m_s=5.5,  # Bajo
            intensity_pct=40.0   # Bajo
        )

        assert len(validation.recommendations) > 0
        assert any('Increase' in rec or 'mejorar' in rec.lower() for rec in validation.recommendations)

    def test_generate_comparison_has_timestamp(self):
        """Test que tiene timestamp de validación."""
        validator = PerformanceValidator()
        validation = validator.generate_comparison(
            player_id=4,
            player_name='Test',
            position='FWD',
            distance_m=9200.0,
            max_velocity_m_s=8.9,
            intensity_pct=68.0
        )

        assert validation.validation_timestamp is not None
        assert len(validation.validation_timestamp) > 0


class TestEdgeCasesAndRobustness:
    """Tests para casos edge y robustez."""

    def test_extreme_high_values(self):
        """Test con valores extremadamente altos."""
        validator = PerformanceValidator()

        dist_result = validator.validate_distance(999999.0, 'MID')
        assert dist_result['status'] == 'ANOMALIA'

        vel_result = validator.validate_velocity(100.0, 'GK')
        assert vel_result['status'] == 'ANOMALIA'

        int_result = validator.validate_intensity(1000.0, 'DEF')
        assert int_result['status'] == 'ANOMALIA'

    def test_extreme_negative_values(self):
        """Test con valores extremadamente negativos."""
        validator = PerformanceValidator()

        dist_result = validator.validate_distance(-999999.0, 'MID')
        assert dist_result['status'] in ['BAJO', 'ANOMALIA']

    def test_float_precision(self):
        """Test que se mantiene precisión de floats."""
        validator = PerformanceValidator()

        result = validator.validate_distance(11234.567, 'MID')
        assert result['measured'] == 11234.57  # Redondeado a 2 decimales

    def test_response_structure_consistency(self):
        """Test que la estructura de respuesta es consistente."""
        validator = PerformanceValidator()

        responses = [
            validator.validate_distance(11200.0, 'MID'),
            validator.validate_velocity(8.4, 'MID'),
            validator.validate_intensity(72.0, 'MID')
        ]

        for response in responses:
            assert 'measured' in response
            assert 'expected' in response
            assert 'variance_percent' in response
            assert 'status' in response
            assert 'confidence' in response
            assert 'percentile' in response
            assert 'interpretation' in response

    def test_percentile_bounds(self):
        """Test que percentiles siempre están en rango válido."""
        validator = PerformanceValidator()

        # Test con muchos valores diferentes
        test_values = [0.1, 100, 1000, 10000, 50000, 100000]

        for value in test_values:
            percentile = validator.get_performance_percentile(value, 'MID', 'distance')
            assert 0.0 <= percentile <= 100.0

    def test_confidence_bounds(self):
        """Test que confianza siempre está entre 0 y 1."""
        validator = PerformanceValidator()

        test_distances = [0, 5000, 11200, 20000, 50000]

        for distance in test_distances:
            result = validator.validate_distance(distance, 'MID')
            assert 0.0 <= result['confidence'] <= 1.0


class TestStatsBombBenchmarks:
    """Tests para la clase StatsBombBenchmarks."""

    def test_get_benchmark_valid(self):
        """Test obtener benchmark válido."""
        benchmark = StatsBombBenchmarks.get_benchmark('MID', 'distance')

        assert benchmark is not None
        assert benchmark.position == 'MID'
        assert benchmark.mean == 11200
        assert benchmark.std > 0

    def test_get_benchmark_invalid_position(self):
        """Test obtener benchmark con posición inválida."""
        benchmark = StatsBombBenchmarks.get_benchmark('INVALID', 'distance')

        assert benchmark is None

    def test_get_all_benchmarks(self):
        """Test obtener todos los benchmarks para una posición."""
        benchmarks = StatsBombBenchmarks.get_all_benchmarks('FWD')

        assert 'distance' in benchmarks
        assert 'max_velocity' in benchmarks
        assert 'intensity' in benchmarks
        assert len(benchmarks) == 3

    def test_all_positions_have_benchmarks(self):
        """Test que todas las posiciones tienen benchmarks."""
        positions = ['GK', 'DEF', 'MID', 'FWD']

        for position in positions:
            benchmarks = StatsBombBenchmarks.get_all_benchmarks(position)
            assert len(benchmarks) == 3
            assert all(metric in benchmarks for metric in ['distance', 'max_velocity', 'intensity'])


class TestIntegration:
    """Tests de integración."""

    def test_full_player_analysis_workflow(self):
        """Test flujo completo de análisis de jugador."""
        validator = PerformanceValidator()

        # Paso 1: Crear datos del jugador
        player_data = {
            'player_id': 10,
            'player_name': 'John Doe',
            'position': 'MID',
            'distance': 11200.0,
            'velocity': 8.4,
            'intensity': 72.0
        }

        # Paso 2: Detectar anomalías
        anomalies = validator.detect_anomalies(player_data)
        assert isinstance(anomalies, list)

        # Paso 3: Generar comparativa
        validation = validator.generate_comparison(
            player_data['player_id'],
            player_data['player_name'],
            player_data['position'],
            player_data['distance'],
            player_data['velocity'],
            player_data['intensity']
        )

        assert validation is not None
        assert len(validation.metrics) == 3

        # Paso 4: Verificar percentiles
        for metric_name in ['distance', 'max_velocity', 'intensity']:
            metric = validation.metrics[metric_name]
            assert 0.0 <= metric.percentile <= 100.0

    def test_multiple_players_comparison(self):
        """Test análisis de múltiples jugadores."""
        validator = PerformanceValidator()

        players = [
            {'position': 'GK', 'distance': 5500, 'velocity': 5.2, 'intensity': 35},
            {'position': 'DEF', 'distance': 9800, 'velocity': 7.8, 'intensity': 65},
            {'position': 'MID', 'distance': 11200, 'velocity': 8.4, 'intensity': 72},
            {'position': 'FWD', 'distance': 9200, 'velocity': 8.9, 'intensity': 68},
        ]

        for idx, player in enumerate(players, 1):
            validation = validator.generate_comparison(
                player_id=idx,
                player_name=f'Player {idx}',
                position=player['position'],
                distance_m=player['distance'],
                max_velocity_m_s=player['velocity'],
                intensity_pct=player['intensity']
            )

            assert validation is not None
            assert validation.player_id == idx


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

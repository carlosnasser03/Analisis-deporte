"""
test_fase4_complete.py - Tests E2E completos para Fase 4: Análisis Individual de Jugadores

OBJETIVO: Integración y pruebas completas de todos los componentes
- Tests de integración para análisis de jugadores
- Tests de precisión de métricas
- Validación de salidas razonables
- Comparación con estándares reales de fútbol

Estructura de tests:
1. Tests de Integración
   - test_complete_player_analysis()
   - test_distance_accuracy()
   - test_velocity_metrics()
   - test_intensity_calculation()
   - test_heatmap_generation()

2. Tests de Precisión
   - test_precision_with_synthetic_data()
   - test_precision_with_realistic_data()

3. Tests de Validación
   - test_output_data_structure()
   - test_performance_benchmarks()
"""

import pytest
import numpy as np
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Tuple
import tempfile
import sys
from datetime import datetime

# Agregar ruta del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.player_analyzer import PlayerAnalyzer, PlayerStats
from core.metrics import DetectionMetrics
from core.report_generator import ReportGenerator


# ============================================================================
# FIXTURES PARA FASE 4
# ============================================================================

@pytest.fixture
def analyzer_with_calibration():
    """Crea un analizador calibrado para tests"""
    analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)
    return analyzer


@pytest.fixture
def synthetic_soccer_tracks() -> List[Dict[str, Any]]:
    """
    Genera tracks sintéticos realistas para pruebas.

    Simula:
    - 50 jugadores
    - 500 frames (≈16 segundos a 30 FPS)
    - Movimientos realistas de fútbol
    """
    tracks = []
    num_players = 50
    num_frames = 500

    for player_id in range(1, num_players + 1):
        # Posición inicial aleatoria del jugador
        base_x = np.random.uniform(100, 1800)
        base_y = np.random.uniform(100, 1000)

        # Velocidad promedio del jugador (m/s) - típico de fútbol
        player_velocity = np.random.uniform(0.5, 7.0)  # 0.5-7 m/s es realista

        for frame_idx in range(0, num_frames, 2):  # No todos los frames
            # Movimiento browniano (random walk) suavizado
            angle = np.random.uniform(0, 2 * np.pi)
            distance = player_velocity * 2  # Aproximadamente píxeles por frame

            x = base_x + distance * np.cos(angle)
            y = base_y + distance * np.sin(angle)

            # Actualiza posición base para siguiente frame
            base_x = x
            base_y = y

            # Confianza realista (85-98%)
            confidence = np.random.uniform(0.85, 0.98)

            tracks.append({
                'frame_idx': frame_idx,
                'player_id': player_id,
                'bbox': [x-25, y-50, x+25, y+50],
                'center': [x, y],
                'confidence': confidence
            })

    return sorted(tracks, key=lambda t: (t['frame_idx'], t['player_id']))


@pytest.fixture
def realistic_soccer_data() -> Dict[str, Any]:
    """
    Datos realistas de fútbol basados en estudios científicos.

    Referencias:
    - Elite Soccer Players: 10-13.5 km distancia
    - Average velocity: 6-7 m/s
    - Intensity: 75-85% movimiento
    """
    return {
        'expected_distance_range': (8000, 13500),  # metros
        'expected_velocity_range': (4.0, 9.0),    # m/s
        'expected_intensity': (70, 90),            # porcentaje
        'expected_hsr_distance': (1000, 4000),     # High Speed Running
        'num_players': 22,
        'num_frames': 2700,  # 90 minutos a 30 FPS
        'fps': 30
    }


@pytest.fixture
def temp_report_dir():
    """Crea directorio temporal para reportes"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ============================================================================
# TESTS DE INTEGRACIÓN - ANÁLISIS COMPLETO DE JUGADORES
# ============================================================================

class TestCompletePlayerAnalysis:
    """Tests de integración para análisis completo de jugadores"""

    def test_complete_player_analysis(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Análisis completo de jugador con 50 jugadores y 500 frames

        Valida:
        - Se calculan todas las métricas
        - Los valores están en rangos razonables
        - No hay excepciones
        """
        analyzer = analyzer_with_calibration

        # Seleccionar algunos jugadores para prueba
        for player_id in [1, 10, 25, 50]:
            # Calcular distancia
            distance_result = analyzer.calculate_distance(
                synthetic_soccer_tracks,
                player_id=player_id
            )

            assert distance_result['total_distance_m'] >= 0
            assert distance_result['num_samples'] > 0
            assert distance_result['interpolated_frames'] >= 0

            # Calcular velocidad
            velocity_result = analyzer.calculate_velocity(
                synthetic_soccer_tracks,
                player_id=player_id
            )

            # Validación de velocidades
            assert velocity_result['max_velocity_m_s'] >= 0
            assert velocity_result['avg_velocity_m_s'] >= 0
            assert velocity_result['max_velocity_m_s'] >= velocity_result['avg_velocity_m_s']
            assert velocity_result['percentile_90_m_s'] >= velocity_result['avg_velocity_m_s']
            assert velocity_result['percentile_95_m_s'] >= velocity_result['percentile_90_m_s']

            # Calcular intensidad
            intensity_result = analyzer.calculate_intensity(
                synthetic_soccer_tracks,
                player_id=player_id
            )

            # Validación de intensidad
            assert 0 <= intensity_result['movement_intensity_percent'] <= 100
            assert 0 <= intensity_result['static_time_percent'] <= 100
            assert abs(
                intensity_result['movement_intensity_percent'] +
                intensity_result['static_time_percent'] - 100
            ) < 1  # Suma debe ser ~100%

            # Validar distribución de categorías
            total_percent = (
                intensity_result['walking_percent'] +
                intensity_result['jogging_percent'] +
                intensity_result['running_percent'] +
                intensity_result['sprinting_percent']
            )
            assert 99 <= total_percent <= 101, \
                f"Distribución debe sumar ~100%, obtuvo {total_percent}%"

    def test_multiple_players_consistency(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Consistencia de análisis entre múltiples jugadores

        Valida:
        - Todos los jugadores se analizan sin errores
        - Las métricas varían razonablemente
        """
        analyzer = analyzer_with_calibration

        # Extraer IDs únicos de jugadores
        player_ids = set(t['player_id'] for t in synthetic_soccer_tracks)

        results = {}
        for player_id in player_ids:
            try:
                distance = analyzer.calculate_distance(
                    synthetic_soccer_tracks,
                    player_id=player_id
                )
                velocity = analyzer.calculate_velocity(
                    synthetic_soccer_tracks,
                    player_id=player_id
                )
                intensity = analyzer.calculate_intensity(
                    synthetic_soccer_tracks,
                    player_id=player_id
                )

                results[player_id] = {
                    'distance': distance['total_distance_m'],
                    'velocity': velocity['max_velocity_m_s'],
                    'intensity': intensity['movement_intensity_percent']
                }
            except Exception as e:
                pytest.fail(f"Error analizando jugador {player_id}: {e}")

        # Validaciones estadísticas
        distances = [r['distance'] for r in results.values() if r['distance'] > 0]
        velocities = [r['velocity'] for r in results.values()]
        intensities = [r['intensity'] for r in results.values()]

        assert len(distances) > 0, "Se requieren jugadores con distancia > 0"

        # Distancia: debe variar entre jugadores
        distance_std = np.std(distances)
        assert distance_std > 0, "Las distancias deben variar entre jugadores"

        # Velocidad: máxima debe ser mayor que promedio
        assert np.max(velocities) >= np.mean(velocities)


# ============================================================================
# TESTS DE PRECISIÓN - EXACTITUD DE MÉTRICAS
# ============================================================================

class TestDistanceAccuracy:
    """Tests para validación de precisión en cálculo de distancia"""

    def test_distance_vs_euclidean_lower_bound(self, analyzer_with_calibration):
        """
        Test: Distancia recorrida ≥ distancia euclidiana directa

        La distancia a lo largo de una trayectoria siempre debe ser mayor
        o igual a la línea recta entre inicio y fin.

        Validación matemática: |path| >= |direct_distance|
        """
        analyzer = analyzer_with_calibration

        # Crear trayectoria simple: línea recta de 100 píxeles
        tracks = [
            {'frame_idx': i, 'player_id': 1, 'center': [100 + i, 200], 'confidence': 0.95}
            for i in range(0, 100, 10)
        ]

        result = analyzer.calculate_distance(tracks, player_id=1)
        total_distance = result['total_distance_m']

        # Distancia euclidiana directa
        direct_distance = 100 / analyzer_with_calibration.pixels_per_meter

        # La distancia recorrida debe ser ≥ distancia directa
        assert total_distance >= direct_distance * 0.95, \
            f"Distancia {total_distance} < distancia directa {direct_distance}"

    def test_distance_calculation_manual_verification(self, analyzer_with_calibration):
        """
        Test: Validación manual del cálculo de distancia

        Con conocimiento previo de coordenadas, verificar que
        el cálculo es correcto.
        """
        analyzer = analyzer_with_calibration
        # pixels_per_meter = 10

        # Crear trayectoria conocida: (0,0) -> (100,0) -> (100,100)
        # Distancia esperada: 100 píxeles + 100 píxeles = 200 píxeles = 20 metros
        tracks = [
            {'frame_idx': 0, 'player_id': 1, 'center': [0, 0], 'confidence': 0.95},
            {'frame_idx': 1, 'player_id': 1, 'center': [100, 0], 'confidence': 0.95},
            {'frame_idx': 2, 'player_id': 1, 'center': [100, 100], 'confidence': 0.95},
        ]

        result = analyzer.calculate_distance(tracks, player_id=1)

        # Distancia esperada = (100 + 100 píxeles) / 10 píxeles_per_meter = 20 m
        expected_distance = 20.0

        assert abs(result['total_distance_m'] - expected_distance) < 0.5, \
            f"Distancia calculada {result['total_distance_m']} != esperada {expected_distance}"


class TestVelocityMetrics:
    """Tests para validación de métricas de velocidad"""

    def test_velocity_ordering_invariant(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Validación de relaciones entre velocidades

        Invariante: v_max >= v_p95 >= v_p90 >= v_median >= v_avg >= 0
        """
        analyzer = analyzer_with_calibration

        for player_id in range(1, 11):  # Primeros 10 jugadores
            result = analyzer.calculate_velocity(
                synthetic_soccer_tracks,
                player_id=player_id
            )

            v_max = result['max_velocity_m_s']
            v_p95 = result['percentile_95_m_s']
            v_p90 = result['percentile_90_m_s']
            v_median = result['median_velocity_m_s']
            v_avg = result['avg_velocity_m_s']

            # Validar orden
            assert v_max >= v_p95, f"v_max ({v_max}) debe ser >= v_p95 ({v_p95})"
            assert v_p95 >= v_p90, f"v_p95 ({v_p95}) debe ser >= v_p90 ({v_p90})"
            assert v_p90 >= v_median, f"v_p90 ({v_p90}) debe ser >= v_median ({v_median})"
            assert v_median >= v_avg, f"v_median ({v_median}) debe ser >= v_avg ({v_avg})"
            assert v_avg >= 0, f"v_avg debe ser >= 0, obtuvo {v_avg}"

    def test_velocity_realistic_soccer_ranges(self, analyzer_with_calibration, realistic_soccer_data, synthetic_soccer_tracks):
        """
        Test: Validar que velocidades están en rangos realistas

        Datos reales de fútbol profesional:
        - Promedio: 6-7 m/s
        - Máximo: 8-12 m/s (según posición)
        - Mínimo: 0-2 m/s (jugadores defensivos)
        """
        analyzer = analyzer_with_calibration
        expected_v_range = realistic_soccer_data['expected_velocity_range']

        velocities = []
        for player_id in range(1, 21):  # 20 jugadores
            result = analyzer.calculate_velocity(
                synthetic_soccer_tracks,
                player_id=player_id
            )
            if result['avg_velocity_m_s'] > 0:
                velocities.append(result['avg_velocity_m_s'])

        if velocities:
            avg_velocity = np.mean(velocities)
            # La velocidad promedio debe estar en rango realista
            assert expected_v_range[0] <= avg_velocity <= expected_v_range[1], \
                f"Velocidad promedio {avg_velocity} fuera de rango {expected_v_range}"


class TestIntensityCalculation:
    """Tests para validación de cálculo de intensidad"""

    def test_intensity_percentage_bounds(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Intensidad debe estar entre 0-100%

        Todos los componentes de intensidad deben ser porcentajes válidos
        """
        analyzer = analyzer_with_calibration

        for player_id in range(1, 26):  # 25 jugadores
            result = analyzer.calculate_intensity(
                synthetic_soccer_tracks,
                player_id=player_id
            )

            # Validar rangos
            assert 0 <= result['movement_intensity_percent'] <= 100
            assert 0 <= result['static_time_percent'] <= 100
            assert 0 <= result['walking_percent'] <= 100
            assert 0 <= result['jogging_percent'] <= 100
            assert 0 <= result['running_percent'] <= 100
            assert 0 <= result['sprinting_percent'] <= 100

    def test_intensity_distribution_reasonableness(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Distribución de categorías debe ser razonable

        Esperado en fútbol: 75% movimiento, 25% estático
        """
        analyzer = analyzer_with_calibration

        total_intensity = []

        for player_id in range(1, 31):  # 30 jugadores
            result = analyzer.calculate_intensity(
                synthetic_soccer_tracks,
                player_id=player_id
            )

            intensity = result['movement_intensity_percent']
            total_intensity.append(intensity)

        if total_intensity:
            avg_intensity = np.mean(total_intensity)
            # Promedio debe estar alrededor de 70-80% (estándar de fútbol)
            assert 50 <= avg_intensity <= 90, \
                f"Intensidad promedio {avg_intensity}% fuera de rango esperado"


class TestHeatmapGeneration:
    """Tests para validación de generación de heatmaps"""

    def test_heatmap_generation(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Generación de heatmap para jugador

        Valida:
        - Matriz de heatmap se genera
        - Dimensiones correctas
        - Valores son no-negativos
        """
        analyzer = analyzer_with_calibration

        result = analyzer.calculate_heatmap(
            synthetic_soccer_tracks,
            player_id=1,
            grid_size=10
        )

        # Validar estructura
        assert 'heatmap_grid' in result
        assert 'positions_list' in result
        assert 'center_of_mass' in result

        heatmap = np.array(result['heatmap_grid'])

        # Validar dimensiones
        assert heatmap.shape == (10, 10), \
            f"Heatmap debe ser 10x10, obtuvo {heatmap.shape}"

        # Validar que hay conteos > 0
        assert np.sum(heatmap) > 0, "Heatmap debe tener conteos"

        # Validar que todos los valores son >= 0
        assert np.all(heatmap >= 0), "Heatmap no debe tener valores negativos"

    def test_heatmap_hot_zones_coloring(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Zonas de alta actividad tienen valores altos

        Las regiones donde el jugador pasó más tiempo deben
        tener valores más altos en el heatmap
        """
        analyzer = analyzer_with_calibration

        result = analyzer.calculate_heatmap(
            synthetic_soccer_tracks,
            player_id=1,
            grid_size=10
        )

        heatmap = np.array(result['heatmap_grid'])

        # Validar que hay una distribución (no uniforme)
        max_val = np.max(heatmap)
        min_val = np.min(heatmap)

        # Debe haber variación en el heatmap
        assert max_val > min_val, "Heatmap debe tener zonas con diferente actividad"


# ============================================================================
# TESTS DE VALIDACIÓN - ESTRUCTURA DE DATOS Y RENDIMIENTO
# ============================================================================

class TestOutputDataStructure:
    """Tests para validar estructura de salida"""

    def test_player_stats_dataclass_structure(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Estructura de PlayerStats es válida

        Valida que todos los campos requeridos están presentes
        """
        analyzer = analyzer_with_calibration

        # Recopilar métricas
        player_id = 1
        distance = analyzer.calculate_distance(synthetic_soccer_tracks, player_id)
        velocity = analyzer.calculate_velocity(synthetic_soccer_tracks, player_id)
        intensity = analyzer.calculate_intensity(synthetic_soccer_tracks, player_id)
        heatmap = analyzer.calculate_heatmap(synthetic_soccer_tracks, player_id)

        # Validar que las claves esperadas existen
        expected_distance_keys = ['total_distance_m', 'num_samples']
        expected_velocity_keys = ['max_velocity_m_s', 'avg_velocity_m_s']
        expected_intensity_keys = ['movement_intensity_percent', 'static_time_percent']

        for key in expected_distance_keys:
            assert key in distance, f"Falta clave {key} en distancia"

        for key in expected_velocity_keys:
            assert key in velocity, f"Falta clave {key} en velocidad"

        for key in expected_intensity_keys:
            assert key in intensity, f"Falta clave {key} en intensidad"


class TestReportGeneration:
    """Tests para generación de reportes"""

    def test_metrics_logger_export(self, temp_report_dir):
        """
        Test: Exportación de métricas a CSV/JSON

        Valida que los logs se generan correctamente
        """
        metrics = DetectionMetrics(
            output_dir=str(temp_report_dir),
            video_name="test_video"
        )

        # Registrar algunos frames
        for frame_idx in range(10):
            metrics.log_frame(frame_idx, {
                'player_confidence': 0.9 + np.random.uniform(-0.1, 0.1),
                'player_count': np.random.randint(15, 25),
                'ball_confidence': 0.85 + np.random.uniform(-0.1, 0.1),
                'pitch_confidence': 0.88 + np.random.uniform(-0.1, 0.1),
                'homography_quality': 0.92 + np.random.uniform(-0.1, 0.1),
                'team_accuracy': 0.88 + np.random.uniform(-0.1, 0.1)
            })

        # Exportar
        csv_path = metrics.export_csv()
        json_path = metrics.export_summary()

        # Validar que archivos existen
        assert csv_path.exists(), f"CSV no generado: {csv_path}"
        assert json_path.exists(), f"JSON no generado: {json_path}"

        # Validar contenido
        summary = metrics.get_summary()
        assert summary['total_frames'] == 10
        assert 'failures' in summary


# ============================================================================
# TESTS DE BENCHMARKING Y RENDIMIENTO
# ============================================================================

class TestPerformanceBenchmarks:
    """Tests para validación de rendimiento"""

    def test_analysis_speed(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Tiempo de análisis es razonable

        Para 50 jugadores, análisis debe completarse en tiempo aceptable
        """
        import time

        analyzer = analyzer_with_calibration

        start_time = time.time()

        for player_id in range(1, 51):  # 50 jugadores
            analyzer.calculate_distance(synthetic_soccer_tracks, player_id)
            analyzer.calculate_velocity(synthetic_soccer_tracks, player_id)
            analyzer.calculate_intensity(synthetic_soccer_tracks, player_id)

        elapsed_time = time.time() - start_time

        # Análisis de 50 jugadores debe completarse en < 5 segundos
        assert elapsed_time < 5.0, \
            f"Análisis tomó {elapsed_time:.2f}s, máximo esperado: 5s"

    def test_heatmap_generation_speed(self, analyzer_with_calibration, synthetic_soccer_tracks):
        """
        Test: Generación de heatmap es rápida

        Para 25 jugadores, heatmaps deben generarse rápidamente
        """
        import time

        analyzer = analyzer_with_calibration

        start_time = time.time()

        for player_id in range(1, 26):  # 25 jugadores
            analyzer.calculate_heatmap(synthetic_soccer_tracks, player_id, grid_size=10)

        elapsed_time = time.time() - start_time

        # Generación de 25 heatmaps debe ser < 2 segundos
        assert elapsed_time < 2.0, \
            f"Heatmaps tomaron {elapsed_time:.2f}s, máximo esperado: 2s"


# ============================================================================
# TESTS DE REGRESIÓN
# ============================================================================

class TestRegressionPrevention:
    """Tests para prevenir regresiones"""

    def test_empty_input_handling(self, analyzer_with_calibration):
        """
        Test: Manejo de entradas vacías

        No debe lanzar excepciones, sino retornar valores por defecto
        """
        analyzer = analyzer_with_calibration

        # Distancia vacía
        result = analyzer.calculate_distance([], player_id=1)
        assert result['total_distance_m'] == 0.0
        assert result['num_samples'] == 0

        # Velocidad vacía
        result = analyzer.calculate_velocity([], player_id=1)
        assert result['max_velocity_m_s'] == 0.0
        assert result['avg_velocity_m_s'] == 0.0

        # Intensidad vacía
        result = analyzer.calculate_intensity([], player_id=1)
        assert result['movement_intensity_percent'] == 0.0
        assert result['static_time_percent'] == 100.0

    def test_single_detection_handling(self, analyzer_with_calibration):
        """
        Test: Manejo de un solo frame de detección

        No debe causar división por cero u otros errores
        """
        analyzer = analyzer_with_calibration

        tracks = [
            {'frame_idx': 0, 'player_id': 1, 'center': [100, 100], 'confidence': 0.95}
        ]

        # No debe lanzar excepción
        distance = analyzer.calculate_distance(tracks, player_id=1)
        velocity = analyzer.calculate_velocity(tracks, player_id=1)
        intensity = analyzer.calculate_intensity(tracks, player_id=1)

        assert isinstance(distance, dict)
        assert isinstance(velocity, dict)
        assert isinstance(intensity, dict)


# ============================================================================
# PARAMETRIZACIÓN PARA MÚLTIPLES ESCENARIOS
# ============================================================================

@pytest.mark.parametrize("fps,expected_range", [
    (25, (4.0, 9.0)),
    (30, (4.0, 9.0)),
    (60, (4.0, 9.0)),  # FPS diferente debe producir rangos similares
])
def test_fps_independence(fps, expected_range):
    """
    Test: Velocidades deben ser independientes de FPS

    Diferentes FPS deben producir velocidades similares (escala correcta)
    """
    analyzer = PlayerAnalyzer(fps=fps, pixels_per_meter=10.0)

    # Crear tracks a velocidad conocida
    # Con 10 píxeles/metro y 10 píxeles de distancia = 1 metro
    tracks = []
    for frame_idx in range(0, 30, 3):  # Cada 3 frames
        tracks.append({
            'frame_idx': frame_idx,
            'player_id': 1,
            'center': [100 + frame_idx * 10, 200],
            'confidence': 0.95
        })

    result = analyzer.calculate_velocity(tracks, player_id=1)

    # Velocidad debe estar en rango esperado
    assert expected_range[0] <= result['avg_velocity_m_s'] <= expected_range[1], \
        f"FPS={fps}, velocidad {result['avg_velocity_m_s']} fuera de rango"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

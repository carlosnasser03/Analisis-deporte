"""
test_intensity_calculation.py - Tests para el módulo de análisis de intensidad

Tests para:
- IntensityCalculator
- MovementIntensity
- AdvancedMetrics
- IntensityAnalyzer
- Exportación y visualización
"""

import pytest
import numpy as np
import json
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile

from core.intensity_analyzer import (
    IntensityCalculator,
    MovementIntensity,
    AdvancedMetrics,
    IntensityAnalyzer,
    IntensityMetrics,
    MovementCategory
)


class TestIntensityCalculator:
    """Tests para IntensityCalculator"""

    def test_calculate_intensity_basic(self):
        """Test básico de cálculo de intensidad"""
        # 3 de 5 velocidades están > 2.0
        velocities = np.array([0.5, 2.1, 3.5, 0.8, 5.0])
        intensity = IntensityCalculator.calculate_intensity(velocities, threshold=2.0)
        assert intensity == 60.0

    def test_calculate_intensity_all_active(self):
        """Test cuando todas las velocidades son activas"""
        velocities = np.array([3.0, 4.0, 5.0, 6.0])
        intensity = IntensityCalculator.calculate_intensity(velocities, threshold=2.0)
        assert intensity == 100.0

    def test_calculate_intensity_no_active(self):
        """Test cuando ninguna velocidad es activa"""
        velocities = np.array([0.5, 1.0, 1.5, 0.8])
        intensity = IntensityCalculator.calculate_intensity(velocities, threshold=2.0)
        assert intensity == 0.0

    def test_calculate_intensity_empty_array(self):
        """Test con array vacío"""
        velocities = np.array([])
        intensity = IntensityCalculator.calculate_intensity(velocities, threshold=2.0)
        assert intensity == 0.0

    def test_calculate_intensity_custom_threshold(self):
        """Test con threshold personalizado"""
        velocities = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        # 1 de 5 velocidades > 4.0 (solo 5.0)
        intensity = IntensityCalculator.calculate_intensity(velocities, threshold=4.0)
        assert intensity == 20.0

    def test_calculate_intensity_single_frame(self):
        """Test con un solo frame"""
        velocities = np.array([3.0])
        intensity = IntensityCalculator.calculate_intensity(velocities, threshold=2.0)
        assert intensity == 100.0


class TestMovementIntensity:
    """Tests para MovementIntensity"""

    def test_categorize_movements_basic(self):
        """Test básico de categorización"""
        velocities = np.array([0.5, 1.5, 3.5, 6.0, 9.0, 2.0])
        categories = MovementIntensity.categorize_movements(velocities, fps=30)

        assert 'estatico' in categories
        assert 'caminando' in categories
        assert 'trotando' in categories
        assert 'corriendo' in categories
        assert 'aceleracion' in categories

        # Verificar que los conteos suman el total
        total_frames = sum(cat.frame_count for cat in categories.values())
        assert total_frames == 6

    def test_categorize_movements_distribution(self):
        """Test de distribución de movimientos"""
        velocities = np.array([0.5] * 50 + [2.0] * 30 + [4.0] * 20)
        categories = MovementIntensity.categorize_movements(velocities, fps=30)

        assert categories['estatico'].frame_count == 50
        assert categories['caminando'].frame_count == 30
        assert categories['trotando'].frame_count == 20

    def test_categorize_movements_percentages(self):
        """Test de cálculo de porcentajes"""
        velocities = np.array([0.5] * 50 + [2.0] * 50)
        categories = MovementIntensity.categorize_movements(velocities, fps=30)

        assert categories['estatico'].percentage == 50.0
        assert categories['caminando'].percentage == 50.0

    def test_categorize_movements_duration(self):
        """Test de cálculo de duración"""
        velocities = np.array([0.5] * 30)  # 30 frames a 30 fps = 1 segundo
        categories = MovementIntensity.categorize_movements(velocities, fps=30)

        assert categories['estatico'].duration_seconds == 1.0

    def test_movement_intensity_distribution(self):
        """Test de obtener distribución de intensidades"""
        velocities = np.array([0.5] * 25 + [2.0] * 50 + [4.0] * 25)
        categories = MovementIntensity.categorize_movements(velocities, fps=30)
        distribution = MovementIntensity.get_movement_intensity_distribution(categories)

        assert 'estatico' in distribution
        assert distribution['estatico'] == 25.0
        assert distribution['caminando'] == 50.0


class TestAdvancedMetrics:
    """Tests para AdvancedMetrics"""

    def test_calculate_acceleration_basic(self):
        """Test básico de aceleración"""
        velocities = np.array([1.0, 2.0, 3.0, 4.0])
        acceleration, avg_accel, max_accel = AdvancedMetrics.calculate_acceleration(
            velocities, fps=1
        )

        # Con dt=1, aceleración = cambio de velocidad
        assert len(acceleration) == 3
        assert avg_accel > 0
        assert max_accel >= avg_accel

    def test_calculate_acceleration_empty(self):
        """Test con array vacío"""
        velocities = np.array([])
        acceleration, avg_accel, max_accel = AdvancedMetrics.calculate_acceleration(
            velocities, fps=30
        )

        assert len(acceleration) == 0
        assert avg_accel == 0.0
        assert max_accel == 0.0

    def test_detect_sprints_basic(self):
        """Test básico de detección de sprints"""
        # Sprint simulado: velocidades >8 m/s durante varios frames
        # Necesita al menos 5 frames para ser considerado sprint (min_sprint_frames=5)
        velocities = np.array([3.0, 2.0, 9.0, 9.5, 8.5, 9.0, 8.5, 3.0, 10.0, 10.0, 10.0, 10.0, 10.0, 2.0])
        sprints = AdvancedMetrics.detect_sprints(velocities, sprint_threshold=8.0, min_sprint_frames=5)

        assert len(sprints) >= 1
        assert all('start_frame' in s for s in sprints)
        assert all('distance' in s for s in sprints)

    def test_detect_sprints_no_sprints(self):
        """Test cuando no hay sprints"""
        velocities = np.array([1.0, 2.0, 1.5, 0.8, 2.5])
        sprints = AdvancedMetrics.detect_sprints(velocities, sprint_threshold=8.0)

        assert len(sprints) == 0

    def test_detect_sprints_multiple(self):
        """Test con múltiples sprints"""
        # Dos sprints separados
        velocities = np.array([
            9.0, 9.5, 8.5, 2.0,  # Sprint 1
            3.0, 2.0,             # Recuperación
            9.0, 9.0, 8.5, 2.0    # Sprint 2
        ])
        sprints = AdvancedMetrics.detect_sprints(velocities, sprint_threshold=8.0, min_sprint_frames=3)

        assert len(sprints) == 2

    def test_calculate_direction_changes_basic(self):
        """Test básico de cambios de dirección"""
        # Posiciones que forman cambios de dirección
        positions = [
            (0, 0), (1, 0), (2, 0),  # Movimiento en X
            (2, 1), (2, 2),           # Cambio a Y (90°)
            (3, 2), (4, 2)            # Cambio a X (90°)
        ]

        changes, avg_angle, sharp_changes = AdvancedMetrics.calculate_direction_changes(
            positions, min_angle_threshold=45.0
        )

        assert changes >= 0
        assert sharp_changes >= 0

    def test_calculate_direction_changes_no_changes(self):
        """Test sin cambios de dirección"""
        # Línea recta - sin cambios
        positions = [(i, 0) for i in range(10)]

        changes, avg_angle, sharp_changes = AdvancedMetrics.calculate_direction_changes(
            positions, min_angle_threshold=45.0
        )

        assert changes == 0

    def test_calculate_recovery_time_basic(self):
        """Test básico de tiempo de recuperación"""
        velocities = np.array([
            9.0, 9.5, 8.5,  # Sprint
            0.5, 0.8, 1.0,  # Recuperación
            2.0, 3.0         # Actividad normal
        ])
        sprints = [{'end_frame': 3, 'distance': 27.0}]

        total_recovery, avg_recovery, attempts = AdvancedMetrics.calculate_recovery_time(
            velocities, sprints, recovery_threshold=1.5, fps=30
        )

        assert total_recovery >= 0
        assert attempts >= 0

    def test_calculate_high_intensity_distance_basic(self):
        """Test básico de distancia en alta intensidad"""
        velocities = np.array([3.0, 4.0, 7.0, 2.0, 8.0])
        # 7.0 + 8.0 = 15.0 en alta intensidad (>6), total = 24.0
        high_int_dist, high_int_pct = AdvancedMetrics.calculate_high_intensity_distance(
            velocities, high_intensity_threshold=6.0
        )

        assert high_int_dist > 0
        assert high_int_pct > 0
        assert high_int_pct <= 100.0

    def test_calculate_high_intensity_distance_zero(self):
        """Test cuando no hay alta intensidad"""
        velocities = np.array([1.0, 2.0, 1.5, 0.8])
        high_int_dist, high_int_pct = AdvancedMetrics.calculate_high_intensity_distance(
            velocities, high_intensity_threshold=6.0
        )

        assert high_int_dist == 0.0
        assert high_int_pct == 0.0


class TestIntensityAnalyzer:
    """Tests para IntensityAnalyzer"""

    @pytest.fixture
    def analyzer(self):
        """Fixture para crear un analizador"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield IntensityAnalyzer(fps=30.0, output_dir=tmpdir)

    @pytest.fixture
    def sample_velocities(self):
        """Fixture con velocidades de prueba"""
        # Mix de actividades: 30% estático, 30% caminando, 20% trotando, 20% corriendo
        return np.array([
            *[0.5] * 30,  # Estático
            *[2.0] * 30,  # Caminando
            *[4.0] * 20,  # Trotando
            *[7.0] * 20   # Corriendo
        ])

    def test_analyzer_initialization(self, analyzer):
        """Test de inicialización del analizador"""
        assert analyzer.fps == 30.0
        assert analyzer.output_dir.exists()

    def test_analyze_basic(self, analyzer, sample_velocities):
        """Test básico de análisis"""
        metrics = analyzer.analyze(sample_velocities)

        assert metrics.total_frames == len(sample_velocities)
        assert metrics.total_duration_seconds > 0
        assert metrics.fps == 30.0
        assert metrics.average_velocity > 0
        assert metrics.max_velocity > metrics.average_velocity

    def test_analyze_intensity_percentage(self, analyzer, sample_velocities):
        """Test del porcentaje de intensidad"""
        metrics = analyzer.analyze(sample_velocities)

        # Con threshold 2.0, deberían contar los trotando y corriendo
        assert metrics.active_movement_percentage > 0
        assert metrics.active_movement_percentage <= 100

    def test_analyze_movement_categories(self, analyzer, sample_velocities):
        """Test de categorías de movimiento"""
        metrics = analyzer.analyze(sample_velocities)

        assert len(metrics.movement_categories) == 5
        total_frames = sum(cat.frame_count for cat in metrics.movement_categories.values())
        assert total_frames == len(sample_velocities)

    def test_analyze_with_position_history(self, analyzer, sample_velocities):
        """Test de análisis con historial de posiciones"""
        positions = [(i, i*0.5) for i in range(len(sample_velocities))]

        metrics = analyzer.analyze(
            sample_velocities,
            position_history=positions
        )

        assert metrics.direction_changes_count >= 0

    def test_analyze_sprints(self, analyzer):
        """Test de detección de sprints"""
        # Crear velocidades con sprints claros
        velocities = np.array([
            *[2.0] * 10,  # Calentamiento
            *[9.0] * 5,   # Sprint 1
            *[2.0] * 10,  # Recuperación
            *[10.0] * 5,  # Sprint 2
            *[1.0] * 10   # Enfriamiento
        ])

        metrics = analyzer.analyze(velocities)

        assert metrics.sprint_count >= 1
        assert metrics.total_sprint_distance > 0

    def test_analyze_custom_config(self, analyzer, sample_velocities):
        """Test con configuración personalizada"""
        custom_config = {
            'velocity_threshold': 3.0,
            'sprint_threshold': 7.0,
            'high_intensity_threshold': 5.0
        }

        metrics = analyzer.analyze(sample_velocities, config=custom_config)

        assert metrics.velocity_threshold == 3.0
        assert metrics.sprint_threshold == 7.0
        assert metrics.high_intensity_threshold == 5.0

    def test_export_json(self, analyzer, sample_velocities):
        """Test de exportación JSON"""
        metrics = analyzer.analyze(sample_velocities)
        filepath = analyzer.export_json(metrics, "test_intensity.json")

        assert filepath.exists()
        with open(filepath) as f:
            data = json.load(f)
            assert 'total_frames' in data
            assert 'movement_categories' in data

    def test_export_summary_text(self, analyzer, sample_velocities):
        """Test de exportación de resumen"""
        metrics = analyzer.analyze(sample_velocities)
        filepath = analyzer.export_summary_text(metrics, "test_summary.txt")

        assert filepath.exists()
        with open(filepath, encoding='utf-8') as f:
            content = f.read()
            assert 'ANÁLISIS DE INTENSIDAD' in content
            assert 'INTENSIDAD Y VELOCIDAD' in content

    def test_export_default_filenames(self, analyzer, sample_velocities):
        """Test de exportación con nombres por defecto"""
        metrics = analyzer.analyze(sample_velocities)

        json_path = analyzer.export_json(metrics)
        assert json_path.name == "intensity_analysis.json"

        text_path = analyzer.export_summary_text(metrics)
        assert text_path.name == "intensity_summary.txt"

    def test_print_summary(self, analyzer, sample_velocities, capsys):
        """Test de impresión de resumen"""
        metrics = analyzer.analyze(sample_velocities)
        analyzer.print_summary(metrics)

        captured = capsys.readouterr()
        assert 'ANÁLISIS DE INTENSIDAD' in captured.out
        assert 'RESUMEN GENERAL' in captured.out


class TestIntensityMetrics:
    """Tests para la dataclass IntensityMetrics"""

    def test_intensity_metrics_initialization(self):
        """Test de inicialización de IntensityMetrics"""
        metrics = IntensityMetrics()

        assert metrics.total_frames == 0
        assert metrics.total_duration_seconds == 0.0
        assert metrics.fps == 30.0
        assert metrics.sprint_count == 0

    def test_intensity_metrics_to_dict(self):
        """Test de conversión a diccionario"""
        metrics = IntensityMetrics(
            total_frames=100,
            total_duration_seconds=3.33,
            sprint_count=5
        )

        data = metrics.to_dict()

        assert isinstance(data, dict)
        assert data['total_frames'] == 100
        assert data['sprint_count'] == 5
        assert 'movement_categories' in data

    def test_movement_category_to_dict(self):
        """Test de MovementCategory a diccionario"""
        category = MovementCategory(
            name='prueba',
            velocity_min=1.0,
            velocity_max=2.0,
            frame_count=50,
            duration_seconds=1.67,
            distance_covered=75.0,
            percentage=10.0
        )

        data = category.to_dict()

        assert data['name'] == 'prueba'
        assert data['frame_count'] == 50
        assert isinstance(data, dict)


class TestIntegration:
    """Tests de integración"""

    def test_full_workflow(self):
        """Test del flujo completo"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crear analizador
            analyzer = IntensityAnalyzer(fps=30.0, output_dir=tmpdir)

            # Crear datos realistas
            velocities = np.array([
                *[0.5] * 100,    # Estático
                *[2.5] * 100,    # Caminando
                *[4.5] * 100,    # Trotando
                *[7.0] * 50,     # Corriendo
                *[9.5] * 30,     # Sprint
                *[2.0] * 100     # Recuperación
            ])

            positions = [(i*0.5, i*0.3) for i in range(len(velocities))]

            # Analizar
            metrics = analyzer.analyze(velocities, positions)

            # Verificar resultados
            assert metrics.total_frames == len(velocities)
            assert metrics.sprint_count > 0
            assert metrics.total_distance > 0
            assert len(metrics.movement_categories) == 5

            # Exportar
            json_path = analyzer.export_json(metrics)
            text_path = analyzer.export_summary_text(metrics)

            # Verificar archivos
            assert json_path.exists()
            assert text_path.exists()

            with open(json_path) as f:
                data = json.load(f)
                assert data['sprint_count'] == metrics.sprint_count
                assert data['total_frames'] == metrics.total_frames

    def test_realistic_football_match(self):
        """Test con datos más realistas de partido de fútbol"""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = IntensityAnalyzer(fps=25.0, output_dir=tmpdir)

            # Simular 90 minutos de juego (25 fps)
            total_frames = 90 * 60 * 25

            # Distribución realista de actividades en fútbol
            velocities = np.concatenate([
                np.random.normal(0.8, 0.3, total_frames//3),   # Movimiento lento (1/3)
                np.random.normal(3.5, 0.8, total_frames//3),   # Movimiento medio (1/3)
                np.random.normal(6.5, 2.0, total_frames//3),   # Movimiento activo (1/3)
            ])
            velocities = np.abs(velocities)  # Sin velocidades negativas

            # Analizar
            metrics = analyzer.analyze(velocities)

            # Verificaciones realistas
            assert metrics.total_duration_seconds == pytest.approx(5400, rel=1)  # 90 minutos
            assert metrics.average_velocity > 0
            assert metrics.sprint_count > 0
            assert metrics.active_movement_percentage > 30  # Al menos 30% activo


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

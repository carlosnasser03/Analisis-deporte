"""
test_heatmap_generation.py - Tests para generador de heatmaps

Pruebas unitarias e integración para:
- HeatmapGenerator: generación con kernel gaussiano
- ZoneAnalyzer: análisis por zonas
- PositionalHeatmap: grid 10x10
- HeatmapExporter: exportación a PNG
- HeatmapManager: orquestación completa
"""

import pytest
import numpy as np
from pathlib import Path
import json
import tempfile

# Importar módulos a testear
from core.heatmap_generator import (
    HeatmapGenerator,
    ZoneAnalyzer,
    PositionalHeatmap,
    HeatmapExporter,
    HeatmapManager,
    HeatmapConfig,
    HeatmapData,
    ZoneStats,
)


class TestHeatmapGenerator:
    """Tests para HeatmapGenerator"""

    @pytest.fixture
    def generator(self):
        """Crea instancia de HeatmapGenerator"""
        return HeatmapGenerator(
            canvas_size=(1280, 720),
            gaussian_sigma=15.0,
            normalize=True
        )

    @pytest.fixture
    def sample_tracks(self):
        """Genera tracks de ejemplo"""
        # Círculo de posiciones
        angles = np.linspace(0, 2*np.pi, 50)
        center_x, center_y = 640, 360
        radius = 200
        tracks = [
            (center_x + radius * np.cos(a), center_y + radius * np.sin(a))
            for a in angles
        ]
        return tracks

    def test_init_default_params(self):
        """Test inicialización con parámetros default"""
        gen = HeatmapGenerator()
        assert gen.width == 1280
        assert gen.height == 720
        assert gen.gaussian_sigma == 15.0
        assert gen.normalize is True

    def test_init_custom_params(self):
        """Test inicialización con parámetros custom"""
        gen = HeatmapGenerator(
            canvas_size=(640, 480),
            gaussian_sigma=25.0,
            normalize=False
        )
        assert gen.width == 640
        assert gen.height == 480
        assert gen.gaussian_sigma == 25.0
        assert gen.normalize is False

    def test_generate_heatmap_output_shape(self, generator, sample_tracks):
        """Test que output tiene forma correcta"""
        heatmap = generator.generate_heatmap(sample_tracks)
        assert heatmap.shape == (720, 1280)
        assert heatmap.dtype == np.float32

    def test_generate_heatmap_value_range(self, generator, sample_tracks):
        """Test que valores están en rango [0, 1]"""
        heatmap = generator.generate_heatmap(sample_tracks)
        assert heatmap.min() >= 0
        assert heatmap.max() <= 1

    def test_generate_heatmap_empty_tracks(self, generator):
        """Test que tracks vacío lanza ValueError"""
        with pytest.raises(ValueError):
            generator.generate_heatmap([])

    def test_generate_heatmap_insufficient_tracks(self, generator):
        """Test que tracks insuficientes lanzan ValueError"""
        with pytest.raises(ValueError):
            generator.generate_heatmap([(100, 100)])

    def test_generate_heatmap_normalized(self, generator, sample_tracks):
        """Test que normalización funciona"""
        heatmap = generator.generate_heatmap(sample_tracks, fps=30)
        assert heatmap.max() <= 1.0
        assert heatmap.min() >= 0.0

    def test_generate_heatmap_not_normalized(self):
        """Test heatmap sin normalización"""
        gen = HeatmapGenerator(normalize=False)
        tracks = [(640, 360)] * 100
        heatmap = gen.generate_heatmap(tracks)
        # Sin normalización, el suavizado gaussiano sigue distribuyendo valores
        # pero no se fuerza a [0, 1]
        assert heatmap.max() >= 0.01  # Debe tener actividad

    def test_apply_colormap_hot(self, generator, sample_tracks):
        """Test colormap 'hot' (rojo)"""
        heatmap_gray = generator.generate_heatmap(sample_tracks)
        colored = generator.apply_colormap(heatmap_gray, colormap="hot")

        assert colored.shape == (720, 1280, 3)
        assert colored.dtype == np.float32
        assert colored.max() <= 1.0

    def test_apply_colormap_cold(self, generator, sample_tracks):
        """Test colormap 'cold' (azul)"""
        heatmap_gray = generator.generate_heatmap(sample_tracks)
        colored = generator.apply_colormap(heatmap_gray, colormap="cold")

        assert colored.shape == (720, 1280, 3)
        assert colored.dtype == np.float32

    def test_apply_colormap_viridis(self, generator, sample_tracks):
        """Test colormap 'viridis'"""
        heatmap_gray = generator.generate_heatmap(sample_tracks)
        colored = generator.apply_colormap(heatmap_gray, colormap="viridis")

        assert colored.shape == (720, 1280, 3)
        assert colored.dtype == np.float32

    def test_apply_colormap_default(self, generator, sample_tracks):
        """Test colormap desconocido retorna escala gris"""
        heatmap_gray = generator.generate_heatmap(sample_tracks)
        colored = generator.apply_colormap(heatmap_gray, colormap="unknown")

        # Debe ser escala gris (R=G=B)
        assert np.allclose(colored[..., 0], colored[..., 1])
        assert np.allclose(colored[..., 1], colored[..., 2])


class TestZoneAnalyzer:
    """Tests para ZoneAnalyzer"""

    @pytest.fixture
    def analyzer(self):
        """Crea instancia de ZoneAnalyzer"""
        return ZoneAnalyzer(
            field_width=1280,
            field_height=720,
            fps=30
        )

    @pytest.fixture
    def center_tracks(self):
        """Posiciones en centro del campo"""
        return [(640, 360)] * 100

    def test_init_zones_created(self, analyzer):
        """Test que se crean 6 zonas"""
        assert len(analyzer.zones) == 6
        assert all('id' in z for z in analyzer.zones)
        assert all('name' in z for z in analyzer.zones)

    def test_analyze_zones_returns_6_stats(self, analyzer, center_tracks):
        """Test que retorna 6 estadísticas"""
        stats = analyzer.analyze_zones(center_tracks)
        assert len(stats) == 6
        assert all(isinstance(s, ZoneStats) for s in stats)

    def test_analyze_zones_total_percentage_100(self, analyzer, center_tracks):
        """Test que porcentajes suman ~100%"""
        stats = analyzer.analyze_zones(center_tracks)
        total_percentage = sum(s.percentage for s in stats)
        assert 99 < total_percentage <= 100

    def test_analyze_zones_time_seconds_correct(self, analyzer, center_tracks):
        """Test que tiempo en segundos es correcto"""
        stats = analyzer.analyze_zones(center_tracks)
        total_time = sum(s.time_seconds for s in stats)
        expected_time = len(center_tracks) / analyzer.fps
        assert abs(total_time - expected_time) < 0.01

    def test_analyze_zones_with_speeds(self, analyzer, center_tracks):
        """Test análisis con velocidades"""
        speeds = [1.5] * len(center_tracks)
        stats = analyzer.analyze_zones(center_tracks, speeds=speeds)

        # Verificar que se calcularon velocidades
        zone_with_data = next((s for s in stats if s.avg_speed_ms is not None), None)
        assert zone_with_data is not None
        assert abs(zone_with_data.avg_speed_ms - 1.5) < 0.01

    def test_analyze_zones_frame_count_distribution(self, analyzer):
        """Test distribución de frames en zonas"""
        # Tracks alternados: izquierda y derecha
        tracks = [(100, 360)] * 50 + [(1200, 360)] * 50
        stats = analyzer.analyze_zones(tracks)

        # Zonas laterales deben tener más frames
        lateral_left = next(s for s in stats if "Izquierda" in s.zone_name)
        lateral_right = next(s for s in stats if "Derecha" in s.zone_name)

        assert lateral_left.frame_count >= 40
        assert lateral_right.frame_count >= 40


class TestPositionalHeatmap:
    """Tests para PositionalHeatmap"""

    @pytest.fixture
    def positional(self):
        """Crea instancia de PositionalHeatmap"""
        return PositionalHeatmap(
            field_width=1280,
            field_height=720,
            grid_size=10
        )

    @pytest.fixture
    def corner_tracks(self):
        """Tracks en esquinas para pruebas"""
        return (
            [(64, 36)] * 50 +     # Top-left (celda 0,0)
            [(1216, 36)] * 50 +   # Top-right (celda 0,9)
            [(64, 684)] * 50 +    # Bottom-left (celda 9,0)
            [(1216, 684)] * 50    # Bottom-right (celda 9,9)
        )

    def test_grid_initialization(self, positional):
        """Test inicialización de grid"""
        assert positional.grid_size == 10
        assert abs(positional.cell_width - 128.0) < 1.0
        assert abs(positional.cell_height - 72.0) < 1.0

    def test_generate_grid_heatmap_output_shape(self, positional, corner_tracks):
        """Test que output tiene formas correctas"""
        grid, image = positional.generate_grid_heatmap(corner_tracks)

        assert grid.shape == (10, 10)
        assert image.shape == (10, 10, 3)

    def test_generate_grid_heatmap_normalized(self, positional, corner_tracks):
        """Test que grid está normalizado"""
        grid, _ = positional.generate_grid_heatmap(corner_tracks)
        assert grid.max() <= 1.0
        assert grid.min() >= 0.0

    def test_generate_grid_heatmap_corner_distribution(self, positional, corner_tracks):
        """Test distribución correcta en esquinas"""
        grid, _ = positional.generate_grid_heatmap(corner_tracks)

        # Esquinas deben tener valores altos
        assert grid[0, 0] > 0  # Top-left
        assert grid[0, 9] > 0  # Top-right
        assert grid[9, 0] > 0  # Bottom-left
        assert grid[9, 9] > 0  # Bottom-right

    def test_get_coverage_percentage(self, positional, corner_tracks):
        """Test cálculo de cobertura"""
        grid, _ = positional.generate_grid_heatmap(corner_tracks)
        coverage = positional.get_coverage_percentage(grid)

        assert 0 <= coverage <= 100
        assert coverage > 0  # Debe haber cobertura

    def test_get_peak_cell(self, positional, corner_tracks):
        """Test identificación de celda pico"""
        grid, _ = positional.generate_grid_heatmap(corner_tracks)
        row, col, val = positional.get_peak_cell(grid)

        assert 0 <= row < 10
        assert 0 <= col < 10
        assert val > 0

    def test_grid_to_rgb_gradient(self, positional):
        """Test que RGB tiene gradiente azul-rojo"""
        # Grid con valores crecientes
        grid = np.linspace(0, 1, 10).reshape(1, 10)
        image = positional._grid_to_rgb(grid)

        # Verificar que rojo crece y azul decrece
        assert image[0, 0, 0] < image[0, 9, 0]  # Rojo crece
        assert image[0, 0, 2] > image[0, 9, 2]  # Azul decrece


class TestHeatmapExporter:
    """Tests para HeatmapExporter"""

    @pytest.fixture
    def temp_dir(self):
        """Directorio temporal para exportaciones"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def exporter(self, temp_dir):
        """Crea exportador con directorio temporal"""
        return HeatmapExporter(output_dir=temp_dir)

    @pytest.fixture
    def sample_image(self):
        """Imagen de ejemplo"""
        return np.random.rand(720, 1280, 3).astype(np.float32)

    def test_exporter_init(self, temp_dir):
        """Test inicialización del exportador"""
        exp = HeatmapExporter(output_dir=temp_dir)
        assert exp.output_dir.exists()

    def test_export_png_creates_file(self, exporter, sample_image, temp_dir):
        """Test que export_png crea archivo"""
        try:
            path = exporter.export_png(sample_image, "test_heatmap.png")
            assert path.exists()
            assert path.suffix == ".png"
        except ImportError:
            pytest.skip("opencv-python no instalado")

    def test_add_annotations(self, exporter, sample_image):
        """Test que se pueden añadir anotaciones"""
        zone_stats = [
            ZoneStats(0, "Zone 1", 100, 3.33, 33.3),
            ZoneStats(1, "Zone 2", 100, 3.33, 33.3),
        ]
        try:
            annotated = exporter.add_annotations(sample_image, zone_stats)
            assert annotated.shape == sample_image.shape
        except ImportError:
            pytest.skip("PIL no instalado")


class TestHeatmapManager:
    """Tests para HeatmapManager (orquestación)"""

    @pytest.fixture
    def temp_dir(self):
        """Directorio temporal"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, temp_dir):
        """Crea gestor con configuración default"""
        config = HeatmapConfig(
            canvas_width=1280,
            canvas_height=720,
            export_png=False  # No exportar durante tests
        )
        return HeatmapManager(config=config, output_dir=temp_dir)

    @pytest.fixture
    def circular_tracks(self):
        """Tracks en movimiento circular"""
        angles = np.linspace(0, 2*np.pi, 100)
        center_x, center_y = 640, 360
        radius = 150
        tracks = [
            (center_x + radius * np.cos(a), center_y + radius * np.sin(a))
            for a in angles
        ]
        return tracks

    def test_manager_init(self, manager):
        """Test inicialización del gestor"""
        assert manager.generator is not None
        assert manager.zone_analyzer is not None
        assert manager.positional is not None
        assert manager.exporter is not None

    def test_generate_complete_analysis(self, manager, circular_tracks):
        """Test análisis completo"""
        analysis = manager.generate_complete_analysis(
            tracks=circular_tracks,
            player_id=1,
            fps=30
        )

        assert isinstance(analysis, HeatmapData)
        assert analysis.heatmap_image.shape == (720, 1280, 3)
        assert len(analysis.zone_stats) == 6
        assert analysis.grid_histogram.shape == (10, 10)
        assert 0 <= analysis.coverage_percentage <= 100
        assert 0 <= analysis.peak_intensity <= 1

    def test_generate_complete_analysis_with_speeds(self, manager, circular_tracks):
        """Test análisis con velocidades"""
        speeds = [2.5] * len(circular_tracks)
        analysis = manager.generate_complete_analysis(
            tracks=circular_tracks,
            player_id=1,
            speeds=speeds
        )

        # Zonas deben tener velocidades calculadas
        zones_with_speed = [z for z in analysis.zone_stats if z.avg_speed_ms is not None]
        assert len(zones_with_speed) > 0

    def test_save_analysis_json(self, manager, circular_tracks, temp_dir):
        """Test guardado en JSON"""
        analysis = manager.generate_complete_analysis(
            tracks=circular_tracks,
            player_id=7
        )

        path = manager.save_analysis_json(analysis, player_id=7)

        assert path.exists()
        with open(path) as f:
            data = json.load(f)

        assert data['player_id'] == 7
        assert 'zones' in data
        assert 'grid_histogram' in data
        assert 'peak_position' in data
        assert 'coverage_percentage' in data

    def test_analysis_consistency(self, manager, circular_tracks):
        """Test consistencia entre componentes"""
        analysis = manager.generate_complete_analysis(
            tracks=circular_tracks,
            player_id=1
        )

        # Grid debe ser consistente con cobertura
        non_zero_cells = np.count_nonzero(analysis.grid_histogram)
        max_possible = analysis.grid_histogram.size
        calculated_coverage = (non_zero_cells / max_possible) * 100

        assert abs(calculated_coverage - analysis.coverage_percentage) < 0.1


class TestHeatmapIntegration:
    """Tests de integración de flujo completo"""

    @pytest.fixture
    def temp_dir(self):
        """Directorio temporal"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_full_pipeline(self, temp_dir):
        """Test pipeline completo: generación -> análisis -> export"""
        # Simular tracks de video
        np.random.seed(42)
        n_frames = 200

        # Jugador se mueve de izquierda a derecha
        x_positions = np.linspace(200, 1100, n_frames) + np.random.normal(0, 10, n_frames)
        y_positions = 360 + np.random.normal(0, 30, n_frames)
        tracks = list(zip(x_positions, y_positions))

        # Crear gestor
        config = HeatmapConfig(
            canvas_width=1280,
            canvas_height=720,
            export_png=False
        )
        manager = HeatmapManager(config=config, output_dir=temp_dir)

        # Ejecutar análisis
        analysis = manager.generate_complete_analysis(
            tracks=tracks,
            player_id=10,
            fps=30
        )

        # Guardar análisis
        json_path = manager.save_analysis_json(analysis, player_id=10)

        # Verificaciones
        assert analysis.heatmap_image is not None
        # Línea recta izquierda-derecha: cobertura limitada (no cubre todo el grid)
        assert analysis.coverage_percentage > 5
        assert json_path.exists()

        # Verificar contenido JSON
        with open(json_path) as f:
            data = json.load(f)
        assert data['player_id'] == 10
        assert len(data['zones']) == 6


class TestHeatmapEdgeCases:
    """Tests para casos borde"""

    def test_single_point_repeated(self):
        """Test tracks con un solo punto repetido"""
        tracks = [(640, 360)] * 100
        gen = HeatmapGenerator()
        heatmap = gen.generate_heatmap(tracks)

        assert heatmap.shape == (720, 1280)
        assert heatmap.max() > 0

    def test_tracks_at_boundaries(self):
        """Test tracks en límites del campo"""
        tracks = (
            [(1, 1)] * 20 +
            [(1279, 1)] * 20 +
            [(1, 719)] * 20 +
            [(1279, 719)] * 20
        )
        gen = HeatmapGenerator()
        heatmap = gen.generate_heatmap(tracks)

        assert heatmap.shape == (720, 1280)

    def test_very_high_gaussian_sigma(self):
        """Test con sigma muy alto (suavizado extremo)"""
        gen = HeatmapGenerator(gaussian_sigma=100.0)
        tracks = [(640, 360)] * 50
        heatmap = gen.generate_heatmap(tracks)

        assert heatmap.max() > 0
        assert heatmap.min() >= 0

    def test_zones_coverage_complete(self):
        """Verificar que cada zona cubre un área y que no hay huecos grandes"""
        analyzer = ZoneAnalyzer(field_width=1280, field_height=720)

        # Verificar que tenemos 6 zonas definidas
        assert len(analyzer.zones) == 6

        # Verificar que cada zona tiene área válida
        for zone in analyzer.zones:
            assert zone['x_max'] > zone['x_min']
            assert zone['y_max'] > zone['y_min']
            assert zone['x_min'] >= 0
            assert zone['y_min'] >= 0
            assert zone['x_max'] <= 1280
            assert zone['y_max'] <= 720

        # Verificar que las zonas cubren aproximadamente el campo completo
        # Muestrear puntos aleatorios y verificar que están en al menos una zona
        np.random.seed(42)
        test_points = np.random.uniform([0, 0], [1280, 720], (100, 2))

        covered = 0
        for x, y in test_points:
            found = False
            for zone in analyzer.zones:
                if (zone['x_min'] <= x < zone['x_max'] and
                    zone['y_min'] <= y < zone['y_max']):
                    found = True
                    break
            if found:
                covered += 1

        # Al menos 90% de puntos deben estar en alguna zona
        assert covered >= 90

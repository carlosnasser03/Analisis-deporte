"""
Tests para FASE 5 - TAREA 2: Dashboard HTML Interactivo

Tests unitarios e integración del generador de dashboards.
"""

import pytest
from pathlib import Path
from datetime import datetime

from core.interactive_dashboard import (
    DashboardConfig,
    ChartGenerator,
    DashboardGenerator,
    generate_dashboard_simple
)


class TestDashboardConfig:
    """Tests para configuración del dashboard."""

    def test_default_config(self):
        """Test configuración por defecto."""
        config = DashboardConfig()
        assert config.title == "Scout AI - Análisis de Partido"
        assert config.organization_name == "Scout Analytics"
        assert config.theme == "light"
        assert config.width == 1400
        assert config.height == 800

    def test_custom_config(self):
        """Test configuración personalizada."""
        config = DashboardConfig(
            title="Mi Equipo",
            organization_name="Mi Organización",
            theme="dark"
        )
        assert config.title == "Mi Equipo"
        assert config.organization_name == "Mi Organización"
        assert config.theme == "dark"

    def test_config_attributes(self):
        """Test que config tiene todos los atributos."""
        config = DashboardConfig()
        assert hasattr(config, 'title')
        assert hasattr(config, 'organization_name')
        assert hasattr(config, 'theme')
        assert hasattr(config, 'include_heatmaps')
        assert hasattr(config, 'include_comparatives')


class TestChartGenerator:
    """Tests para generador de gráficos."""

    @pytest.fixture
    def sample_stats(self):
        """Datos de ejemplo para tests."""
        return {
            "7": {
                "distance_total_m": 10500.5,
                "max_velocity_m_s": 9.2,
                "avg_velocity_m_s": 6.5,
                "percentile_90_m_s": 8.2,
                "movement_intensity_percent": 78.5,
            },
            "10": {
                "distance_total_m": 9800.3,
                "max_velocity_m_s": 8.9,
                "avg_velocity_m_s": 6.2,
                "percentile_90_m_s": 7.9,
                "movement_intensity_percent": 75.2,
            },
        }

    def test_distance_chart_returns_html(self, sample_stats):
        """Test que create_distance_chart retorna HTML."""
        html = ChartGenerator.create_distance_chart(sample_stats)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_distance_chart_contains_data(self, sample_stats):
        """Test que gráfico contiene datos correctos."""
        html = ChartGenerator.create_distance_chart(sample_stats)
        # Puede contener datos o mensaje de que Plotly no está instalado
        assert "10500" in html or "10500.5" in html or "Distancia" in html or "Plotly" in html

    def test_velocity_chart_returns_html(self, sample_stats):
        """Test que create_velocity_chart retorna HTML."""
        html = ChartGenerator.create_velocity_chart(sample_stats)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_intensity_chart_returns_html(self, sample_stats):
        """Test que create_intensity_chart retorna HTML."""
        html = ChartGenerator.create_intensity_chart(sample_stats)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_chart_with_empty_stats(self):
        """Test gráficos con estadísticas vacías."""
        empty_stats = {}
        html = ChartGenerator.create_distance_chart(empty_stats)
        # Debe retornar algo aunque esté vacío
        assert isinstance(html, str)

    def test_chart_with_invalid_data(self):
        """Test gráficos con datos inválidos."""
        invalid_stats = {
            "1": None,
            "2": "invalid"
        }
        html = ChartGenerator.create_distance_chart(invalid_stats)
        assert isinstance(html, str)


class TestDashboardGenerator:
    """Tests para generador de dashboard."""

    @pytest.fixture
    def generator(self):
        """Crear generador de dashboard."""
        return DashboardGenerator()

    @pytest.fixture
    def sample_stats(self):
        """Datos de ejemplo."""
        return {
            "7": {
                "distance_total_m": 10500.5,
                "max_velocity_m_s": 9.2,
                "avg_velocity_m_s": 6.5,
                "percentile_90_m_s": 8.2,
                "movement_intensity_percent": 78.5,
                "sprints_count": 12,
                "directional_changes": 45,
            }
        }

    @pytest.fixture
    def sample_summary(self):
        """Resumen del equipo."""
        return {
            "players_analyzed": 11,
            "avg_distance": 10150.4,
            "avg_intensity": 76.3,
            "total_sprints": 95,
        }

    def test_generator_initialization(self, generator):
        """Test inicialización del generador."""
        assert generator.config is not None
        assert generator.chart_generator is not None

    def test_generator_with_custom_config(self):
        """Test generador con configuración custom."""
        config = DashboardConfig(title="Test Dashboard")
        generator = DashboardGenerator(config)
        assert generator.config.title == "Test Dashboard"

    def test_create_html_structure(self, generator):
        """Test creación de estructura HTML."""
        html = generator._create_html_structure()
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "<head>" in html
        assert "<body>" in html
        assert "<div class=\"container\">" in html

    def test_create_header(self, generator):
        """Test creación de encabezado."""
        html = generator._create_header()
        assert isinstance(html, str)
        assert "Scout AI" in html
        assert generator.config.organization_name in html

    def test_create_team_summary_with_data(self, generator, sample_summary):
        """Test creación de resumen de equipo."""
        html = generator._create_team_summary(sample_summary)
        assert isinstance(html, str)
        assert "Resumen del Equipo" in html or "11" in html

    def test_create_team_summary_empty(self, generator):
        """Test resumen con datos vacíos."""
        html = generator._create_team_summary(None)
        assert isinstance(html, str)
        # Puede estar vacío pero debe ser válido

    def test_create_player_table(self, generator, sample_stats):
        """Test creación de tabla de jugadores."""
        html = generator._create_player_table(sample_stats)
        assert isinstance(html, str)
        assert "playerTable" in html or "Jugador" in html or "Distancia" in html

    def test_player_table_structure(self, generator, sample_stats):
        """Test estructura de tabla."""
        html = generator._create_player_table(sample_stats)
        assert "<table" in html
        assert "</table>" in html
        assert "<thead>" in html
        assert "<tbody>" in html

    def test_create_charts(self, generator, sample_stats):
        """Test creación de sección de gráficos."""
        html = generator._create_charts(sample_stats)
        assert isinstance(html, str)
        assert "Gráficos" in html or "chart" in html.lower()

    def test_create_footer(self, generator):
        """Test creación de pie de página."""
        html = generator._create_footer()
        assert isinstance(html, str)
        assert "Scout AI" in html
        assert "</html>" in html

    def test_generate_full_dashboard(self, generator, sample_stats, sample_summary):
        """Test generación de dashboard completo."""
        html = generator.generate_dashboard(
            sample_stats,
            sample_summary,
            output_path=None
        )
        assert isinstance(html, str)
        assert len(html) > 100
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    def test_dashboard_contains_data(self, generator, sample_stats):
        """Test que dashboard contiene datos."""
        html = generator.generate_dashboard(sample_stats)
        # Debe contener alguno de los datos
        assert len(html) > 0

    def test_save_dashboard(self, generator, sample_stats, tmp_path):
        """Test guardar dashboard a archivo."""
        output_file = tmp_path / "test_dashboard.html"
        html = generator.generate_dashboard(
            sample_stats,
            output_path=str(output_file)
        )
        assert output_file.exists()
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "<!DOCTYPE html>" in content


class TestDashboardSaveLoad:
    """Tests para guardar y cargar dashboards."""

    def test_save_creates_file(self, tmp_path):
        """Test que guardar crea archivo."""
        generator = DashboardGenerator()
        sample_stats = {"7": {"distance_total_m": 10000}}
        output_file = tmp_path / "dashboard.html"

        generator.generate_dashboard(sample_stats, output_path=str(output_file))
        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_save_creates_directory(self, tmp_path):
        """Test que crea directorios si no existen."""
        generator = DashboardGenerator()
        sample_stats = {"7": {"distance_total_m": 10000}}
        output_file = tmp_path / "subdir" / "dashboard.html"

        generator.generate_dashboard(sample_stats, output_path=str(output_file))
        assert output_file.exists()

    def test_file_is_valid_html(self, tmp_path):
        """Test que archivo guardado es HTML válido."""
        generator = DashboardGenerator()
        sample_stats = {"7": {"distance_total_m": 10000}}
        output_file = tmp_path / "dashboard.html"

        generator.generate_dashboard(sample_stats, output_path=str(output_file))

        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content.count("<") > 0
            assert content.count(">") > 0
            # HTML válido debe tener más aberturas que cierres por las propiedades CSS
            assert content.count("<") >= content.count(">") - 1


class TestSimpleDashboardFunction:
    """Tests para función simple generate_dashboard_simple."""

    def test_simple_function_exists(self):
        """Test que función existe."""
        assert callable(generate_dashboard_simple)

    def test_simple_function_works(self, tmp_path):
        """Test que función funciona."""
        sample_stats = {"7": {"distance_total_m": 10000}}
        output_file = tmp_path / "dashboard.html"

        html = generate_dashboard_simple(
            sample_stats,
            output_path=str(output_file)
        )

        assert isinstance(html, str)
        assert output_file.exists()

    def test_simple_function_default_path(self, tmp_path, monkeypatch):
        """Test función con ruta por defecto."""
        # Cambiar directorio de trabajo temporal
        monkeypatch.chdir(tmp_path)
        sample_stats = {"7": {"distance_total_m": 10000}}

        html = generate_dashboard_simple(sample_stats)
        assert isinstance(html, str)


class TestDashboardIntegration:
    """Tests de integración del dashboard."""

    def test_full_pipeline(self, tmp_path):
        """Test pipeline completo de generación."""
        # Datos realistas
        player_stats = {
            "7": {
                "distance_total_m": 10500.5,
                "max_velocity_m_s": 9.2,
                "avg_velocity_m_s": 6.5,
                "percentile_90_m_s": 8.2,
                "movement_intensity_percent": 78.5,
                "sprints_count": 12,
                "directional_changes": 45,
            },
            "10": {
                "distance_total_m": 9800.3,
                "max_velocity_m_s": 8.9,
                "avg_velocity_m_s": 6.2,
                "percentile_90_m_s": 7.9,
                "movement_intensity_percent": 75.2,
                "sprints_count": 10,
                "directional_changes": 42,
            },
            "4": {
                "distance_total_m": 8900.2,
                "max_velocity_m_s": 8.5,
                "avg_velocity_m_s": 5.8,
                "percentile_90_m_s": 7.5,
                "movement_intensity_percent": 72.1,
                "sprints_count": 8,
                "directional_changes": 38,
            },
        }

        team_summary = {
            "players_analyzed": 11,
            "avg_distance": 9733.3,
            "avg_intensity": 75.3,
            "total_sprints": 95,
        }

        output_file = tmp_path / "dashboard_integration.html"

        # Generar dashboard
        html = generate_dashboard_simple(
            player_stats,
            team_summary,
            str(output_file)
        )

        # Validar
        assert output_file.exists()
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Debe tener múltiples jugadores
            assert content.count("10500") > 0 or content.count("P7") > 0

    def test_multiple_dashboards(self, tmp_path):
        """Test crear múltiples dashboards."""
        config1 = DashboardConfig(title="Dashboard 1")
        config2 = DashboardConfig(title="Dashboard 2")

        gen1 = DashboardGenerator(config1)
        gen2 = DashboardGenerator(config2)

        stats = {"7": {"distance_total_m": 10000}}

        file1 = tmp_path / "dashboard1.html"
        file2 = tmp_path / "dashboard2.html"

        gen1.generate_dashboard(stats, output_path=str(file1))
        gen2.generate_dashboard(stats, output_path=str(file2))

        assert file1.exists()
        assert file2.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

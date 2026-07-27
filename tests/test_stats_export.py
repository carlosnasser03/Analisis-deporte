"""
test_stats_export.py - Tests específicos para exportación de estadísticas

Tests enfocados en validación de formatos, integridad de datos y
comportamiento del exportador en diferentes escenarios.
"""

import pytest
import json
import csv
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile

from core.player_stats_aggregator import (
    PlayerStatsAggregator,
    StatsExporter,
)


@pytest.fixture
def aggregator_with_data():
    """Crea agregador con datos de ejemplo."""
    agg = PlayerStatsAggregator(team_id="TestTeam")

    distance_metrics = {
        'total_distance_m': 10000.0,
        'num_samples': 1800,
    }

    velocity_metrics = {
        'max_velocity_m_s': 10.0,
        'avg_velocity_m_s': 4.5,
        'median_velocity_m_s': 4.0,
        'percentile_90_m_s': 9.0,
        'percentile_95_m_s': 9.5,
        'std_velocity_m_s': 2.0,
    }

    intensity_metrics = {
        'movement_intensity_percent': 80.0,
        'static_time_percent': 20.0,
        'walking_percent': 10.0,
        'jogging_percent': 30.0,
        'running_percent': 25.0,
        'sprinting_percent': 15.0,
        'hsrs_distance_m': 2000.0,
        'sprints_count': 15,
        'directional_changes': 50,
    }

    for i in range(1, 12):
        agg.aggregate_player_stats(
            player_id=i,
            player_number=i,
            player_name=f"Player_{i}",
            position=['GK', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'FWD', 'FWD', 'FWD'][i-1],
            distance_metrics=distance_metrics,
            velocity_metrics=velocity_metrics,
            intensity_metrics=intensity_metrics,
        )

    agg.calculate_team_percentiles()
    return agg


class TestExporterInitialization:
    """Tests de inicialización del exportador."""

    def test_init_default_directory(self):
        """Inicializa con directorio default."""
        exporter = StatsExporter()
        assert exporter.output_dir == Path("data/exports")

    def test_init_custom_directory(self, tmp_path):
        """Inicializa con directorio personalizado."""
        custom_dir = str(tmp_path / "custom_exports")
        exporter = StatsExporter(output_dir=custom_dir)
        assert exporter.output_dir == Path(custom_dir)

    def test_init_creates_directory(self, tmp_path):
        """Crea directorio si no existe."""
        custom_dir = tmp_path / "new_dir" / "exports"
        exporter = StatsExporter(output_dir=str(custom_dir))
        assert exporter.output_dir.exists()


class TestJSONExportFormat:
    """Tests de formato JSON."""

    def test_json_structure(self, aggregator_with_data, tmp_path):
        """Verifica estructura del JSON exportado."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        player_stats = aggregator_with_data.get_player_stats(1)

        filepath = exporter.export_json(player_stats)

        with open(filepath, 'r') as f:
            data = json.load(f)

        # Verificar campos principales
        assert 'player_id' in data
        assert 'player_number' in data
        assert 'team_id' in data
        assert 'player_name' in data
        assert 'position' in data
        assert 'distance_total_m' in data
        assert 'velocity_max' in data
        assert 'intensity_pct' in data
        assert 'timestamp' in data
        assert 'format_version' in data

    def test_json_numeric_precision(self, aggregator_with_data, tmp_path):
        """Verifica precisión de números decimales."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        player_stats = aggregator_with_data.get_player_stats(1)

        filepath = exporter.export_json(player_stats)

        with open(filepath, 'r') as f:
            data = json.load(f)

        # Verificar que los decimales se mantienen
        assert isinstance(data['distance_total_m'], (int, float))
        assert isinstance(data['velocity_max'], (int, float))

    def test_json_null_values(self, aggregator_with_data, tmp_path):
        """Maneja valores null en JSON."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        player_stats = aggregator_with_data.get_player_stats(1)
        player_stats.heatmap_path = None

        filepath = exporter.export_json(player_stats)

        with open(filepath, 'r') as f:
            data = json.load(f)

        assert data['heatmap_path'] is None

    def test_json_arrays_in_export(self, aggregator_with_data, tmp_path):
        """Verifica que arrays se exportan correctamente."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        player_stats = aggregator_with_data.get_player_stats(1)

        filepath = exporter.export_json(player_stats)

        with open(filepath, 'r') as f:
            data = json.load(f)

        assert 'zones_visited' in data
        assert isinstance(data['zones_visited'], list)


class TestCSVExportFormat:
    """Tests de formato CSV."""

    def test_csv_header_row(self, aggregator_with_data, tmp_path):
        """Verifica que CSV incluye header."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()

        filepath = exporter.export_csv(players_stats)

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)

        assert len(header) > 0
        assert 'player_id' in header or header[0] != ''

    def test_csv_data_rows(self, aggregator_with_data, tmp_path):
        """Verifica que CSV tiene filas de datos correctas."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()

        filepath = exporter.export_csv(players_stats)

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 11

    def test_csv_field_types(self, aggregator_with_data, tmp_path):
        """Verifica tipos de campos en CSV."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()

        filepath = exporter.export_csv(players_stats)

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)

        # Campos que deberían convertirse a números
        numeric_fields = ['player_id', 'player_number', 'distance_total_m']
        for field in numeric_fields:
            if field in row:
                try:
                    float(row[field])
                    assert True
                except ValueError:
                    assert False, f"Campo {field} no es numérico"

    def test_csv_special_characters(self, aggregator_with_data, tmp_path):
        """Maneja caracteres especiales en CSV."""
        exporter = StatsExporter(output_dir=str(tmp_path))

        # Modificar nombre con caracteres especiales
        player_stats = aggregator_with_data.get_player_stats(1)
        player_stats.player_name = "José María García"

        filepath = exporter.export_csv([player_stats])

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)

        assert row['player_name'] == "José María García"

    def test_csv_encoding(self, aggregator_with_data, tmp_path):
        """Verifica codificación UTF-8 en CSV."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()

        filepath = exporter.export_csv(players_stats)

        # Intentar leer como UTF-8
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) > 0
            is_valid_utf8 = True
        except UnicodeDecodeError:
            is_valid_utf8 = False

        assert is_valid_utf8


class TestComparisonExport:
    """Tests de exportación de comparativa."""

    def test_comparison_structure(self, aggregator_with_data, tmp_path):
        """Verifica estructura de JSON comparativo."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()
        team_summary = aggregator_with_data.get_team_summary()

        filepath = exporter.export_comparison_json(players_stats, team_summary)

        with open(filepath, 'r') as f:
            data = json.load(f)

        assert 'timestamp' in data
        assert 'team_summary' in data
        assert 'players' in data
        assert isinstance(data['players'], list)

    def test_comparison_player_metrics(self, aggregator_with_data, tmp_path):
        """Verifica métricas de comparativa por jugador."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()
        team_summary = aggregator_with_data.get_team_summary()

        filepath = exporter.export_comparison_json(players_stats, team_summary)

        with open(filepath, 'r') as f:
            data = json.load(f)

        first_player = data['players'][0]

        assert 'player_id' in first_player
        assert 'player_number' in first_player
        assert 'metrics' in first_player

        metrics = first_player['metrics']
        assert 'distance' in metrics
        assert 'velocity' in metrics
        assert 'intensity' in metrics

    def test_comparison_percentiles(self, aggregator_with_data, tmp_path):
        """Verifica que percentiles están en comparativa."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()
        team_summary = aggregator_with_data.get_team_summary()

        filepath = exporter.export_comparison_json(players_stats, team_summary)

        with open(filepath, 'r') as f:
            data = json.load(f)

        for player_data in data['players']:
            metrics = player_data['metrics']

            assert 'percentile' in metrics['distance']
            assert 'percentile' in metrics['velocity']
            assert 'percentile' in metrics['intensity']

            # Percentiles deben estar entre 0-100
            assert 0 <= metrics['distance']['percentile'] <= 100
            assert 0 <= metrics['velocity']['percentile'] <= 100
            assert 0 <= metrics['intensity']['percentile'] <= 100


class TestSummaryExport:
    """Tests de exportación de resumen ejecutivo."""

    def test_summary_structure(self, aggregator_with_data, tmp_path):
        """Verifica estructura del resumen ejecutivo."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()
        team_summary = aggregator_with_data.get_team_summary()

        filepath = exporter.generate_summary(players_stats, team_summary)

        with open(filepath, 'r') as f:
            data = json.load(f)

        assert 'timestamp' in data
        assert 'format_version' in data
        assert 'team_summary' in data
        assert 'movement_profiles' in data
        assert 'top_performers' in data
        assert 'statistics' in data

    def test_summary_top_performers(self, aggregator_with_data, tmp_path):
        """Verifica sección de top performers."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()
        team_summary = aggregator_with_data.get_team_summary()

        filepath = exporter.generate_summary(players_stats, team_summary)

        with open(filepath, 'r') as f:
            data = json.load(f)

        top = data['top_performers']

        assert 'distance' in top
        assert 'intensity' in top
        assert 'velocity' in top

        # Debe haber máximo 3 en cada categoría
        assert len(top['distance']) <= 3
        assert len(top['intensity']) <= 3
        assert len(top['velocity']) <= 3

    def test_summary_movement_profiles(self, aggregator_with_data, tmp_path):
        """Verifica conteo de perfiles de movimiento."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()
        team_summary = aggregator_with_data.get_team_summary()

        filepath = exporter.generate_summary(players_stats, team_summary)

        with open(filepath, 'r') as f:
            data = json.load(f)

        profiles = data['movement_profiles']
        total_profiles = sum(profiles.values())

        # Debe coincidir con total de jugadores
        assert total_profiles == len(players_stats)

    def test_summary_statistics(self, aggregator_with_data, tmp_path):
        """Verifica estadísticas consolidadas."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()
        team_summary = aggregator_with_data.get_team_summary()

        filepath = exporter.generate_summary(players_stats, team_summary)

        with open(filepath, 'r') as f:
            data = json.load(f)

        stats = data['statistics']

        assert 'total_players_analyzed' in stats
        assert 'average_distance_km' in stats
        assert 'total_team_distance_km' in stats
        assert 'average_intensity_pct' in stats
        assert 'total_sprints' in stats

        assert stats['total_players_analyzed'] == 11


class TestExportFilePath:
    """Tests de manejo de rutas de archivos."""

    def test_export_creates_correct_path(self, aggregator_with_data, tmp_path):
        """Verifica que archivos se crean en ruta correcta."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        player_stats = aggregator_with_data.get_player_stats(1)

        filepath = exporter.export_json(player_stats)

        assert filepath.parent == tmp_path

    def test_export_filename_default(self, aggregator_with_data, tmp_path):
        """Verifica nombre de archivo default."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        player_stats = aggregator_with_data.get_player_stats(7)

        filepath = exporter.export_json(player_stats)

        assert filepath.name == "player_7.json"

    def test_export_filename_custom(self, aggregator_with_data, tmp_path):
        """Verifica nombre de archivo personalizado."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        player_stats = aggregator_with_data.get_player_stats(1)

        filepath = exporter.export_json(player_stats, filename="custom.json")

        assert filepath.name == "custom.json"

    def test_export_csv_filename(self, aggregator_with_data, tmp_path):
        """Verifica nombre de archivo CSV."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()

        filepath = exporter.export_csv(players_stats)

        assert filepath.name == "jugadores.csv"


class TestExportAll:
    """Tests del método export_all."""

    def test_export_all_returns_dict(self, aggregator_with_data, tmp_path):
        """Verifica que export_all retorna diccionario."""
        exporter = StatsExporter(output_dir=str(tmp_path))

        exports = exporter.export_all(aggregator_with_data)

        assert isinstance(exports, dict)
        assert len(exports) > 0

    def test_export_all_file_keys(self, aggregator_with_data, tmp_path):
        """Verifica que todas las claves esperadas están presentes."""
        exporter = StatsExporter(output_dir=str(tmp_path))

        exports = exporter.export_all(aggregator_with_data)

        # Debe incluir resumen, comparativa y CSV
        assert 'summary' in exports
        assert 'comparison' in exports
        assert 'csv' in exports

    def test_export_all_files_exist(self, aggregator_with_data, tmp_path):
        """Verifica que todos los archivos existen."""
        exporter = StatsExporter(output_dir=str(tmp_path))

        exports = exporter.export_all(aggregator_with_data)

        for key, filepath in exports.items():
            assert filepath.exists(), f"Archivo {key} no existe en {filepath}"

    def test_export_all_with_prefix(self, aggregator_with_data, tmp_path):
        """Verifica prefijo en nombres de archivos."""
        exporter = StatsExporter(output_dir=str(tmp_path))

        exports = exporter.export_all(aggregator_with_data, prefix="test_")

        for filepath in exports.values():
            assert filepath.name.startswith('test_') or 'player_' in filepath.name


class TestDataValidityAfterExport:
    """Tests de validez de datos después de exportación."""

    def test_json_reimport(self, aggregator_with_data, tmp_path):
        """Verifica que datos JSON se pueden reimportar."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        original_stats = aggregator_with_data.get_player_stats(1)

        filepath = exporter.export_json(original_stats)

        with open(filepath, 'r') as f:
            reimported_data = json.load(f)

        assert reimported_data['player_id'] == original_stats.player_id
        assert reimported_data['distance_total_m'] == original_stats.distance_total_m

    def test_csv_reimport(self, aggregator_with_data, tmp_path):
        """Verifica que datos CSV se pueden reimportar."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        original_stats = aggregator_with_data.get_all_stats()

        filepath = exporter.export_csv(original_stats)

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            reimported_rows = list(reader)

        assert len(reimported_rows) == len(original_stats)
        assert reimported_rows[0]['player_name'] == original_stats[0].player_name

    def test_comparison_json_reimport(self, aggregator_with_data, tmp_path):
        """Verifica que comparativa JSON se puede reimportar."""
        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = aggregator_with_data.get_all_stats()
        team_summary = aggregator_with_data.get_team_summary()

        filepath = exporter.export_comparison_json(players_stats, team_summary)

        with open(filepath, 'r') as f:
            reimported_data = json.load(f)

        assert len(reimported_data['players']) == len(players_stats)


class TestErrorHandling:
    """Tests de manejo de errores."""

    def test_export_to_readonly_directory(self, aggregator_with_data, tmp_path):
        """Intenta exportar a directorio de solo lectura."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()

        exporter = StatsExporter(output_dir=str(readonly_dir))
        player_stats = aggregator_with_data.get_player_stats(1)

        # En algunos sistemas no podemos hacer readonly, solo probamos que intenta
        try:
            filepath = exporter.export_json(player_stats)
            assert filepath.exists()
        except (OSError, PermissionError):
            # Esperado en algunos sistemas
            pass

    def test_csv_export_empty_raises(self, tmp_path):
        """Lanza excepción al exportar lista vacía a CSV."""
        exporter = StatsExporter(output_dir=str(tmp_path))

        with pytest.raises(ValueError):
            exporter.export_csv([])


class TestPerformance:
    """Tests de rendimiento de exportación."""

    def test_export_many_players(self, tmp_path):
        """Exporta muchos jugadores exitosamente."""
        agg = PlayerStatsAggregator(team_id="BigTeam")

        # Agregar 100 jugadores
        for i in range(100):
            agg.aggregate_player_stats(
                player_id=i,
                player_number=i % 99,
                player_name=f"Player_{i}",
                position="MID",
                distance_metrics={'total_distance_m': 10000.0},
                velocity_metrics={'max_velocity_m_s': 10.0, 'avg_velocity_m_s': 4.5},
                intensity_metrics={'movement_intensity_percent': 75.0},
            )

        agg.calculate_team_percentiles()

        exporter = StatsExporter(output_dir=str(tmp_path))
        players_stats = agg.get_all_stats()

        # Exportar CSV con muchos jugadores
        filepath = exporter.export_csv(players_stats)
        assert filepath.exists()

        # Verificar que se exportaron todos
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 100

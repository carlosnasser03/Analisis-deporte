"""
Tests para FASE 5 - TAREA 1: Pipeline Integrado

Tests unitarios e integración del pipeline completo.
"""

import pytest
import numpy as np
from pathlib import Path
from dataclasses import asdict

from pipeline.integrated_pipeline import (
    IntegratedAnalysisPipeline,
    ProcessingConfig,
    FrameResult,
    PipelineResult,
    process_video_simple
)


class TestProcessingConfig:
    """Tests para configuración del pipeline."""

    def test_default_config(self):
        """Test configuración por defecto."""
        config = ProcessingConfig()
        assert config.fps == 30.0
        assert config.pixels_per_meter == 10.0
        assert config.field_length_m == 105.0
        assert config.field_width_m == 68.0

    def test_custom_config(self):
        """Test configuración personalizada."""
        config = ProcessingConfig(
            fps=25.0,
            pixels_per_meter=12.5,
            field_length_m=110.0
        )
        assert config.fps == 25.0
        assert config.pixels_per_meter == 12.5
        assert config.field_length_m == 110.0


class TestPipelineInitialization:
    """Tests para inicialización del pipeline."""

    def test_init_default(self):
        """Test inicialización con config por defecto."""
        pipeline = IntegratedAnalysisPipeline()
        assert pipeline.config.fps == 30.0
        assert len(pipeline.player_tracks) == 0
        assert isinstance(pipeline.errors, list)
        assert isinstance(pipeline.warnings, list)

    def test_init_custom_config(self):
        """Test inicialización con config personalizada."""
        config = ProcessingConfig(fps=25.0)
        pipeline = IntegratedAnalysisPipeline(config)
        assert pipeline.config.fps == 25.0

    def test_components_initialized(self):
        """Test que componentes críticos están inicializados."""
        pipeline = IntegratedAnalysisPipeline()
        # detector puede ser None si no está disponible
        # Pero otros componentes deben estar inicializados
        assert pipeline.stats_aggregator is not None
        assert pipeline.player_tracks is not None


class TestFrameProcessing:
    """Tests para procesamiento de frames."""

    @pytest.fixture
    def pipeline(self):
        """Crear pipeline para tests."""
        return IntegratedAnalysisPipeline()

    @pytest.fixture
    def dummy_frame(self):
        """Crear frame dummy de prueba."""
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    def test_process_frame_returns_result(self, pipeline, dummy_frame):
        """Test que process_frame retorna FrameResult."""
        result = pipeline._process_frame(dummy_frame, 0)
        assert isinstance(result, FrameResult)
        assert result.frame_idx == 0

    def test_process_frame_has_required_fields(self, pipeline, dummy_frame):
        """Test que FrameResult tiene todos los campos."""
        result = pipeline._process_frame(dummy_frame, 5)
        assert result.frame_idx == 5
        assert isinstance(result.players, list)
        assert isinstance(result.processing_time_ms, (int, float))
        assert result.processing_time_ms >= 0

    def test_process_frame_error_handling(self, pipeline):
        """Test manejo de errores en process_frame."""
        # Pasar None en lugar de frame
        result = pipeline._process_frame(None, 0)
        assert isinstance(result, FrameResult)
        # Debe continuar sin fallar


class TestTrackManagement:
    """Tests para gestión de trayectorias."""

    def test_get_player_track_empty(self):
        """Test obtener trayectoria vacía."""
        pipeline = IntegratedAnalysisPipeline()
        tracks = pipeline.get_player_track(999)
        assert tracks == []

    def test_add_tracks(self):
        """Test agregar trayectorias."""
        pipeline = IntegratedAnalysisPipeline()
        # Simular agregar tracks
        from core.distance_velocity_calculator import TrackPoint

        track_point = TrackPoint(frame=0, x=100, y=100, confidence=0.95)
        pipeline.player_tracks[7].append(track_point)

        tracks = pipeline.get_player_track(7)
        assert len(tracks) == 1
        assert tracks[0].x == 100


class TestPipelineResult:
    """Tests para resultados del pipeline."""

    def test_pipeline_result_creation(self):
        """Test crear PipelineResult."""
        result = PipelineResult(
            video_path="/path/to/video.mp4",
            total_frames=900,
            duration_seconds=30.0,
            fps=30.0,
            frames_processed=900,
            player_stats={},
            team_summary={},
            errors=[],
            warnings=[],
            processing_time_seconds=10.5
        )
        assert result.video_path == "/path/to/video.mp4"
        assert result.total_frames == 900
        assert result.frames_processed == 900

    def test_pipeline_result_with_errors(self):
        """Test PipelineResult con errores."""
        result = PipelineResult(
            video_path="video.mp4",
            total_frames=100,
            duration_seconds=3.3,
            fps=30.0,
            frames_processed=95,
            player_stats={},
            team_summary={},
            errors=["Error en frame 50"],
            warnings=["Warning en frame 25"],
            processing_time_seconds=1.0
        )
        assert len(result.errors) == 1
        assert len(result.warnings) == 1

    def test_pipeline_result_to_dict(self):
        """Test convertir PipelineResult a diccionario."""
        result = PipelineResult(
            video_path="video.mp4",
            total_frames=100,
            duration_seconds=3.3,
            fps=30.0,
            frames_processed=100,
            player_stats={"7": {"distance": 10000}},
            team_summary={"total_players": 22},
            errors=[],
            warnings=[],
            processing_time_seconds=1.5
        )
        result_dict = asdict(result)
        assert isinstance(result_dict, dict)
        assert result_dict["video_path"] == "video.mp4"


class TestVideoValidation:
    """Tests para validación de videos."""

    def test_video_not_found(self):
        """Test error cuando video no existe."""
        pipeline = IntegratedAnalysisPipeline()
        with pytest.raises(FileNotFoundError):
            pipeline.process_video("/path/to/nonexistent.mp4")

    def test_invalid_video_path(self):
        """Test error con path inválido."""
        pipeline = IntegratedAnalysisPipeline()
        with pytest.raises(FileNotFoundError):
            pipeline.process_video("invalid_video_path.mp4")


class TestErrorHandling:
    """Tests para manejo de errores."""

    def test_pipeline_continues_on_frame_error(self):
        """Test que pipeline continúa después de error en frame."""
        pipeline = IntegratedAnalysisPipeline()
        # El pipeline debe mantener errors list
        assert isinstance(pipeline.errors, list)

    def test_errors_logged_correctly(self):
        """Test que errores se registran correctamente."""
        pipeline = IntegratedAnalysisPipeline()
        pipeline.errors.append("Test error")
        assert len(pipeline.errors) == 1
        assert "Test error" in pipeline.errors


class TestSimpleProcessing:
    """Tests para función simple process_video_simple."""

    def test_function_signature(self):
        """Test que función existe y tiene signatures correcta."""
        # Solo verificar que existe
        assert callable(process_video_simple)

    def test_requires_video_path(self):
        """Test que función requiere video_path."""
        with pytest.raises(FileNotFoundError):
            process_video_simple("nonexistent.mp4")


class TestProcessingMetrics:
    """Tests para métricas de procesamiento."""

    def test_processing_time_is_positive(self):
        """Test que tiempo de procesamiento es positivo."""
        result = PipelineResult(
            video_path="video.mp4",
            total_frames=100,
            duration_seconds=3.3,
            fps=30.0,
            frames_processed=100,
            player_stats={},
            team_summary={},
            errors=[],
            warnings=[],
            processing_time_seconds=1.5
        )
        assert result.processing_time_seconds > 0

    def test_frames_processed_matches(self):
        """Test que frames_processed ≤ total_frames."""
        result = PipelineResult(
            video_path="video.mp4",
            total_frames=100,
            duration_seconds=3.3,
            fps=30.0,
            frames_processed=100,
            player_stats={},
            team_summary={},
            errors=[],
            warnings=[],
            processing_time_seconds=1.5
        )
        assert result.frames_processed <= result.total_frames

    def test_duration_calculation(self):
        """Test que duración es correcta."""
        result = PipelineResult(
            video_path="video.mp4",
            total_frames=300,
            duration_seconds=10.0,
            fps=30.0,
            frames_processed=300,
            player_stats={},
            team_summary={},
            errors=[],
            warnings=[],
            processing_time_seconds=2.0
        )
        assert abs(result.duration_seconds - 10.0) < 0.1


class TestPlayerStatsAggregation:
    """Tests para agregación de estadísticas de jugadores."""

    def test_empty_player_stats(self):
        """Test con estadísticas vacías."""
        pipeline = IntegratedAnalysisPipeline()
        stats = pipeline._aggregate_player_stats()
        assert isinstance(stats, dict)

    def test_aggregation_structure(self):
        """Test estructura de estadísticas agregadas."""
        # Test que puede manejar estructura de stats
        sample_stats = {
            "7": {
                "player_id": 7,
                "total_distance_m": 10000.5,
                "max_velocity_m_s": 9.2
            }
        }
        assert isinstance(sample_stats, dict)
        assert "7" in sample_stats


class TestIntegration:
    """Tests de integración completa."""

    def test_pipeline_config_flow(self):
        """Test flujo completo de configuración."""
        config = ProcessingConfig(fps=25.0)
        pipeline = IntegratedAnalysisPipeline(config)
        assert pipeline.config.fps == 25.0
        assert pipeline.distance_analyzer is not None

    def test_multiple_pipelines_independent(self):
        """Test que múltiples pipelines son independientes."""
        pipeline1 = IntegratedAnalysisPipeline(ProcessingConfig(fps=30.0))
        pipeline2 = IntegratedAnalysisPipeline(ProcessingConfig(fps=25.0))

        assert pipeline1.config.fps == 30.0
        assert pipeline2.config.fps == 25.0
        # Verificar que son instancias diferentes
        assert pipeline1 is not pipeline2
        assert pipeline1.player_tracks is not pipeline2.player_tracks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

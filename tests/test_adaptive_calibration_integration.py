"""
Tests para FASE 6 - TAREA 1: Calibración Adaptativa Integrada

Tests para calibración adaptativa automática del pipeline.
"""

import pytest
import numpy as np
from dataclasses import asdict

from core.adaptive_calibration import (
    VideoQualityAnalyzer,
    AdaptiveCalibration,
    VideoQualityMetrics,
    ProcessingConfig,
    VideoQuality,
    LightingCondition,
    WeatherCondition,
)
from pipeline.integrated_pipeline import (
    IntegratedAnalysisPipeline,
    ProcessingConfig as PipelineProcessingConfig,
    PipelineResult,
)


class TestVideoQualityAnalyzerMethods:
    """Tests para métodos de VideoQualityAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Crear analizador."""
        return VideoQualityAnalyzer(sample_frames=5)

    def test_calculate_brightness(self, analyzer):
        """Test cálculo de brillo."""
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 127
        brightness = analyzer._calculate_brightness(frame)
        assert 0 <= brightness <= 255
        assert 120 < brightness < 135

    def test_detect_blur(self, analyzer):
        """Test detección de blur."""
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 127
        blur = analyzer._detect_blur(frame)
        assert 0 <= blur <= 1

    def test_classify_lighting_dark(self, analyzer):
        """Test clasificación oscura."""
        condition = analyzer._classify_lighting(40, 10)
        assert condition == LightingCondition.DARK

    def test_classify_lighting_normal(self, analyzer):
        """Test clasificación normal."""
        condition = analyzer._classify_lighting(120, 20)
        assert condition == LightingCondition.NORMAL

    def test_classify_quality_poor(self, analyzer):
        """Test clasificación pobre."""
        quality = analyzer._classify_quality(30, 0.8, 0.5, 0.9)
        assert quality == VideoQuality.POOR

    def test_classify_quality_excellent(self, analyzer):
        """Test clasificación excelente."""
        quality = analyzer._classify_quality(140, 0.2, 0.1, 0.3)
        assert quality == VideoQuality.EXCELLENT


class TestAdaptiveCalibrationCore:
    """Tests para lógica central de calibración."""

    @pytest.fixture
    def calibrator(self):
        """Crear calibrador."""
        return AdaptiveCalibration()

    def test_calibration_initialization(self, calibrator):
        """Test inicialización."""
        assert calibrator is not None
        assert isinstance(calibrator, AdaptiveCalibration)

    def test_get_optimal_config_poor_quality(self, calibrator):
        """Test config para calidad pobre."""
        metrics = VideoQualityMetrics(
            brightness=45,
            brightness_std=30,
            blur_level=0.7,
            motion_blur=0.1,
            occlusion_rate=0.2,
            lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.FOG,
            crowd_density=0.5,
            video_quality=VideoQuality.POOR,
            analysis_frames=10,
            frame_rate=25.0
        )

        config = calibrator.get_optimal_config(metrics)

        assert isinstance(config, ProcessingConfig)
        assert config.confidence_threshold < AdaptiveCalibration.DEFAULT_CONFIDENCE_THRESHOLD
        assert config.quality_report is not None

    def test_get_optimal_config_excellent_quality(self, calibrator):
        """Test config para calidad excelente."""
        metrics = VideoQualityMetrics(
            brightness=140,
            brightness_std=20,
            blur_level=0.2,
            motion_blur=0.05,
            occlusion_rate=0.1,
            lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR,
            crowd_density=0.3,
            video_quality=VideoQuality.EXCELLENT,
            analysis_frames=10,
            frame_rate=25.0
        )

        config = calibrator.get_optimal_config(metrics)

        assert isinstance(config, ProcessingConfig)
        assert config.quality_report is not None

    def test_config_values_clamped(self, calibrator):
        """Test que valores se clampen."""
        metrics = VideoQualityMetrics(
            brightness=30,
            brightness_std=50,
            blur_level=0.9,
            motion_blur=0.8,
            occlusion_rate=0.7,
            lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.RAIN,
            crowd_density=0.9,
            video_quality=VideoQuality.POOR,
            analysis_frames=10,
            frame_rate=25.0
        )

        config = calibrator.get_optimal_config(metrics)

        assert 0.45 <= config.confidence_threshold <= 0.75
        assert 0.8 <= config.gk_sensitivity <= 1.3
        assert 50 <= config.tracker_max_distance <= 150
        assert 1 <= config.skip_frames <= 5

    def test_dict_to_metrics(self, calibrator):
        """Test conversión de dict a metrics."""
        data = {
            'brightness': 120,
            'brightness_std': 25,
            'blur_level': 0.3,
            'motion_blur': 0.1,
            'occlusion_rate': 0.15,
            'lighting_condition': 'NORMAL',
            'weather_condition': 'CLEAR',
            'crowd_density': 0.4,
            'video_quality': 'GOOD',
            'analysis_frames': 10,
            'frame_rate': 25.0
        }

        metrics = calibrator._dict_to_metrics(data)
        assert isinstance(metrics, VideoQualityMetrics)
        assert metrics.brightness == 120


class TestPipelineIntegration:
    """Tests de integración con pipeline."""

    def test_pipeline_initialization(self):
        """Test inicialización del pipeline."""
        pipeline = IntegratedAnalysisPipeline()
        assert pipeline is not None
        assert hasattr(pipeline, 'quality_analyzer')
        assert hasattr(pipeline, 'adaptive_calibration')
        assert hasattr(pipeline, 'quality_metrics')
        assert hasattr(pipeline, 'applied_adaptive_config')

    def test_pipeline_config_has_tracker_max_distance(self):
        """Test que config tiene tracker_max_distance."""
        config = PipelineProcessingConfig()
        assert hasattr(config, 'tracker_max_distance')
        assert config.tracker_max_distance == 50.0

    def test_pipeline_config_custom_values(self):
        """Test config con valores customizados."""
        config = PipelineProcessingConfig(
            tracker_max_distance=75.0,
            confidence_threshold=0.6
        )
        assert config.tracker_max_distance == 75.0
        assert config.confidence_threshold == 0.6

    def test_pipeline_result_quality_metrics(self):
        """Test PipelineResult con quality_metrics."""
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
            processing_time_seconds=1.0,
            quality_metrics={
                'video_quality': VideoQuality.EXCELLENT.value,
                'brightness': 150.0,
            },
            adaptive_config={
                'confidence_threshold': 0.6,
                'tracker_max_distance': 75.0,
            }
        )

        assert result.quality_metrics is not None
        assert result.adaptive_config is not None

    def test_pipeline_result_to_dict(self):
        """Test convertir resultado a dict."""
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
            processing_time_seconds=1.0,
            quality_metrics={'video_quality': 'GOOD'},
            adaptive_config={'confidence_threshold': 0.5}
        )

        result_dict = asdict(result)
        assert 'quality_metrics' in result_dict
        assert 'adaptive_config' in result_dict


class TestAdaptiveCalibrationScenarios:
    """Tests de escenarios realistas."""

    @pytest.fixture
    def calibrator(self):
        """Crear calibrador."""
        return AdaptiveCalibration()

    def test_night_match_scenario(self, calibrator):
        """Test escenario: partido de noche."""
        metrics = VideoQualityMetrics(
            brightness=50,
            brightness_std=35,
            blur_level=0.5,
            motion_blur=0.2,
            occlusion_rate=0.3,
            lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.CLEAR,
            crowd_density=0.6,
            video_quality=VideoQuality.FAIR,
            analysis_frames=10,
            frame_rate=25.0
        )

        config = calibrator.get_optimal_config(metrics)
        assert config.skip_frames >= 1
        assert config.confidence_threshold < 0.6

    def test_rainy_day_scenario(self, calibrator):
        """Test escenario: día lluvioso."""
        metrics = VideoQualityMetrics(
            brightness=100,
            brightness_std=40,
            blur_level=0.6,
            motion_blur=0.4,
            occlusion_rate=0.25,
            lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.RAIN,
            crowd_density=0.5,
            video_quality=VideoQuality.FAIR,
            analysis_frames=10,
            frame_rate=25.0
        )

        config = calibrator.get_optimal_config(metrics)
        assert config.tracker_max_distance > AdaptiveCalibration.DEFAULT_TRACKER_MAX_DISTANCE

    def test_high_density_crowd_scenario(self, calibrator):
        """Test escenario: multitud densa."""
        metrics = VideoQualityMetrics(
            brightness=130,
            brightness_std=25,
            blur_level=0.35,
            motion_blur=0.25,
            occlusion_rate=0.3,
            lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR,
            crowd_density=0.8,
            video_quality=VideoQuality.GOOD,
            analysis_frames=10,
            frame_rate=25.0
        )

        config = calibrator.get_optimal_config(metrics)
        assert isinstance(config, ProcessingConfig)
        assert config.gk_sensitivity > AdaptiveCalibration.DEFAULT_GK_SENSITIVITY

    def test_perfect_conditions_scenario(self, calibrator):
        """Test escenario: condiciones perfectas."""
        metrics = VideoQualityMetrics(
            brightness=150,
            brightness_std=15,
            blur_level=0.15,
            motion_blur=0.05,
            occlusion_rate=0.08,
            lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR,
            crowd_density=0.4,
            video_quality=VideoQuality.EXCELLENT,
            analysis_frames=10,
            frame_rate=25.0
        )

        config = calibrator.get_optimal_config(metrics)
        # En condiciones perfectas, usar valores cercanos a defaults
        assert abs(config.confidence_threshold - AdaptiveCalibration.DEFAULT_CONFIDENCE_THRESHOLD) <= 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

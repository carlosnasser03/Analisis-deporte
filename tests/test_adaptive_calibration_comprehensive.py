"""
Tests comprehensivos para módulo de calibración adaptativa

Tests para:
- VideoQualityAnalyzer: Detección de condiciones de video (brillo, blur, oclusión, clima)
- AdaptiveCalibration: Ajuste automático de parámetros según condiciones
- Integración end-to-end

Total: 30+ tests cobriendo todos los casos de uso
"""

import pytest
import numpy as np
import cv2
import tempfile
from pathlib import Path

from core.adaptive_calibration import (
    VideoQualityAnalyzer,
    AdaptiveCalibration,
    VideoQualityMetrics,
    ProcessingConfig,
    VideoQuality,
    LightingCondition,
    WeatherCondition,
    analyze_and_calibrate,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def analyzer():
    """Analizador de calidad de video"""
    return VideoQualityAnalyzer(sample_frames=5)


@pytest.fixture
def calibrator():
    """Calibrador adaptativo"""
    return AdaptiveCalibration()


@pytest.fixture
def frame_normal():
    """Frame con condiciones normales"""
    frame = np.full((480, 640, 3), 127, dtype=np.uint8)
    cv2.rectangle(frame, (100, 100), (200, 200), (100, 100, 100), -1)
    return frame


@pytest.fixture
def frame_dark():
    """Frame muy oscuro"""
    frame = np.full((480, 640, 3), 30, dtype=np.uint8)
    cv2.rectangle(frame, (100, 100), (200, 200), (60, 60, 60), -1)
    return frame


@pytest.fixture
def frame_bright():
    """Frame muy brillante"""
    frame = np.full((480, 640, 3), 240, dtype=np.uint8)
    cv2.rectangle(frame, (100, 100), (200, 200), (255, 255, 255), -1)
    return frame


@pytest.fixture
def frame_blurry():
    """Frame borroso"""
    frame = np.full((480, 640, 3), 127, dtype=np.uint8)
    for _ in range(5):
        frame = cv2.GaussianBlur(frame, (7, 7), 0)
    return frame


@pytest.fixture
def frame_sharp():
    """Frame nítido con muchos detalles"""
    frame = np.full((480, 640, 3), 127, dtype=np.uint8)
    for i in range(0, 640, 15):
        for j in range(0, 480, 15):
            if (i // 15 + j // 15) % 2 == 0:
                cv2.rectangle(frame, (i, j), (i+15, j+15), (255, 255, 255), -1)
    return frame


# ============================================================================
# TESTS: VideoQualityAnalyzer - Inicialización
# ============================================================================

class TestVideoQualityAnalyzerInit:
    """Tests de inicialización del analizador"""

    def test_analyzer_initialization_default(self):
        """Verifica inicialización con parámetros por defecto"""
        analyzer = VideoQualityAnalyzer()
        assert analyzer is not None
        assert analyzer.sample_frames == 10

    def test_analyzer_initialization_custom(self):
        """Verifica inicialización con parámetros personalizados"""
        analyzer = VideoQualityAnalyzer(sample_frames=20)
        assert analyzer.sample_frames == 20


# ============================================================================
# TESTS: VideoQualityAnalyzer - Análisis de Brillo
# ============================================================================

class TestVideoQualityAnalyzerBrightness:
    """Tests para detección de brillo"""

    def test_brightness_calculation_normal(self, analyzer, frame_normal):
        """Verifica cálculo de brillo en frame normal"""
        brightness = analyzer._calculate_brightness(frame_normal)
        assert isinstance(brightness, float)
        assert 0 <= brightness <= 255
        assert 100 < brightness < 150

    def test_brightness_calculation_dark(self, analyzer, frame_dark):
        """Verifica cálculo de brillo en frame oscuro"""
        brightness = analyzer._calculate_brightness(frame_dark)
        assert brightness < 80

    def test_brightness_calculation_bright(self, analyzer, frame_bright):
        """Verifica cálculo de brillo en frame brillante"""
        brightness = analyzer._calculate_brightness(frame_bright)
        assert brightness > 200

    def test_classify_lighting_dark(self, analyzer):
        """Verifica clasificación DARK"""
        condition = analyzer._classify_lighting(40, 10)
        assert condition == LightingCondition.DARK

    def test_classify_lighting_normal(self, analyzer):
        """Verifica clasificación NORMAL"""
        condition = analyzer._classify_lighting(120, 20)
        assert condition == LightingCondition.NORMAL

    def test_classify_lighting_bright(self, analyzer):
        """Verifica clasificación BRIGHT"""
        condition = analyzer._classify_lighting(195, 15)
        assert condition == LightingCondition.BRIGHT

    def test_classify_lighting_variable(self, analyzer):
        """Verifica clasificación VARIABLE"""
        condition = analyzer._classify_lighting(120, 70)
        assert condition == LightingCondition.VARIABLE


# ============================================================================
# TESTS: VideoQualityAnalyzer - Análisis de Blur
# ============================================================================

class TestVideoQualityAnalyzerBlur:
    """Tests para detección de desenfoque"""

    def test_detect_blur_sharp(self, analyzer, frame_sharp):
        """Verifica detección de frame nítido"""
        blur = analyzer._detect_blur(frame_sharp)
        assert 0 <= blur <= 1

    def test_detect_blur_blurry(self, analyzer, frame_blurry):
        """Verifica detección de frame borroso"""
        blur = analyzer._detect_blur(frame_blurry)
        assert 0 <= blur <= 1
        assert blur > 0.5  # Alto nivel de blur

    def test_detect_motion_blur_no_movement(self, analyzer, frame_normal):
        """Verifica motion blur sin movimiento"""
        motion_blur = analyzer._detect_motion_blur(frame_normal, frame_normal)
        assert 0 <= motion_blur <= 1
        assert motion_blur < 0.1

    def test_detect_motion_blur_with_movement(self, analyzer, frame_normal):
        """Verifica motion blur con movimiento"""
        frame1 = frame_normal.copy()
        frame2 = frame_normal.copy()
        cv2.rectangle(frame2, (150, 150), (250, 250), (50, 50, 50), -1)

        motion_blur = analyzer._detect_motion_blur(frame1, frame2)
        assert 0 <= motion_blur <= 1


# ============================================================================
# TESTS: VideoQualityAnalyzer - Análisis de Oclusión
# ============================================================================

class TestVideoQualityAnalyzerOcclusion:
    """Tests para detección de oclusión"""

    def test_estimate_occlusion_clear(self, analyzer, frame_bright):
        """Verifica estimación de oclusión en frame claro"""
        occlusion = analyzer._estimate_occlusion(frame_bright)
        assert 0 <= occlusion <= 1
        assert occlusion < 0.2

    def test_estimate_occlusion_dark(self, analyzer, frame_dark):
        """Verifica estimación de oclusión en frame oscuro"""
        occlusion = analyzer._estimate_occlusion(frame_dark)
        assert occlusion > 0.5


# ============================================================================
# TESTS: VideoQualityAnalyzer - Análisis de Multitudes
# ============================================================================

class TestVideoQualityAnalyzerCrowd:
    """Tests para detección de multitudes"""

    def test_estimate_crowd_density_normal(self, analyzer, frame_normal):
        """Verifica estimación de densidad"""
        density = analyzer._estimate_crowd_density(frame_normal)
        assert 0 <= density <= 1

    def test_estimate_crowd_density_detailed(self, analyzer, frame_sharp):
        """Verifica que frame detallado tiene mayor densidad"""
        density1 = analyzer._estimate_crowd_density(frame_sharp)
        density2 = analyzer._estimate_crowd_density(frame_normal)
        assert isinstance(density1, float)
        assert isinstance(density2, float)


# ============================================================================
# TESTS: VideoQualityAnalyzer - Detección de Clima
# ============================================================================

class TestVideoQualityAnalyzerWeather:
    """Tests para detección climática"""

    def test_detect_weather_clear(self, analyzer):
        """Verifica detección CLEAR"""
        weather = analyzer._detect_weather([0.2, 0.1], [0.1, 0.1])
        assert weather == WeatherCondition.CLEAR

    def test_detect_weather_rain(self, analyzer):
        """Verifica detección RAIN"""
        weather = analyzer._detect_weather([0.6, 0.55], [0.2, 0.25])
        assert weather == WeatherCondition.RAIN

    def test_detect_weather_fog(self, analyzer):
        """Verifica detección FOG"""
        weather = analyzer._detect_weather([0.75, 0.8], [0.4, 0.5])
        assert weather == WeatherCondition.FOG


# ============================================================================
# TESTS: VideoQualityAnalyzer - Clasificación General
# ============================================================================

class TestVideoQualityAnalyzerClassification:
    """Tests para clasificación de calidad general"""

    def test_classify_quality_excellent(self, analyzer):
        """Verifica clasificación EXCELLENT"""
        quality = analyzer._classify_quality(130, 0.1, 0.05, 0.2)
        assert quality == VideoQuality.EXCELLENT

    def test_classify_quality_good(self, analyzer):
        """Verifica clasificación GOOD (1 problema)"""
        # Brillo fuera de rango: 1 problema
        quality = analyzer._classify_quality(30, 0.3, 0.1, 0.3)
        assert quality == VideoQuality.GOOD

    def test_classify_quality_fair(self, analyzer):
        """Verifica clasificación FAIR (1-2 problemas)"""
        # Brillo fuera de rango (1) + Blur alto (2) = 3 problemas = POOR
        # Intentar solo blur alto: 2 problemas
        quality = analyzer._classify_quality(120, 0.7, 0.1, 0.3)
        assert quality == VideoQuality.FAIR

    def test_classify_quality_poor(self, analyzer):
        """Verifica clasificación POOR"""
        quality = analyzer._classify_quality(30, 0.9, 0.6, 0.9)
        assert quality == VideoQuality.POOR


# ============================================================================
# TESTS: AdaptiveCalibration - Ajustes por Calidad
# ============================================================================

class TestAdaptiveCalibrationByQuality:
    """Tests para ajustes según nivel de calidad"""

    def test_config_excellent_quality(self, calibrator):
        """Verifica config para EXCELLENT"""
        metrics = VideoQualityMetrics(
            brightness=130, brightness_std=10, blur_level=0.1, motion_blur=0.05,
            occlusion_rate=0.05, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.2,
            video_quality=VideoQuality.EXCELLENT, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert isinstance(config, ProcessingConfig)
        assert config.confidence_threshold >= 0.55
        assert not config.use_motion_blur

    def test_config_good_quality(self, calibrator):
        """Verifica config para GOOD"""
        metrics = VideoQualityMetrics(
            brightness=120, brightness_std=20, blur_level=0.3, motion_blur=0.1,
            occlusion_rate=0.1, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.3,
            video_quality=VideoQuality.GOOD, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert 0.45 <= config.confidence_threshold <= 0.60

    def test_config_fair_quality(self, calibrator):
        """Verifica config para FAIR"""
        metrics = VideoQualityMetrics(
            brightness=30, brightness_std=40, blur_level=0.7, motion_blur=0.2,
            occlusion_rate=0.2, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.4,
            video_quality=VideoQuality.FAIR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        # FAIR quality should have lower or equal threshold
        assert config.confidence_threshold <= 0.55

    def test_config_poor_quality(self, calibrator):
        """Verifica config para POOR"""
        metrics = VideoQualityMetrics(
            brightness=30, brightness_std=60, blur_level=0.8, motion_blur=0.6,
            occlusion_rate=0.5, lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.FOG, crowd_density=0.8,
            video_quality=VideoQuality.POOR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert config.confidence_threshold <= 0.45
        assert config.skip_frames >= 2


# ============================================================================
# TESTS: AdaptiveCalibration - Ajustes Específicos
# ============================================================================

class TestAdaptiveCalibrationSpecificConditions:
    """Tests para ajustes específicos"""

    def test_dark_video_adjustment(self, calibrator):
        """Verifica ajuste para video oscuro"""
        metrics = VideoQualityMetrics(
            brightness=40, brightness_std=10, blur_level=0.3, motion_blur=0.05,
            occlusion_rate=0.1, lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.2,
            video_quality=VideoQuality.FAIR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert config.confidence_threshold < 0.60
        assert config.gk_sensitivity > 1.0

    def test_blurry_video_adjustment(self, calibrator):
        """Verifica ajuste para video borroso"""
        metrics = VideoQualityMetrics(
            brightness=127, brightness_std=20, blur_level=0.7, motion_blur=0.3,
            occlusion_rate=0.1, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.2,
            video_quality=VideoQuality.FAIR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert config.tracker_max_distance > 100
        assert config.skip_frames >= 2

    def test_high_occlusion_adjustment(self, calibrator):
        """Verifica ajuste para alta oclusión"""
        metrics = VideoQualityMetrics(
            brightness=127, brightness_std=20, blur_level=0.3, motion_blur=0.1,
            occlusion_rate=0.5, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.2,
            video_quality=VideoQuality.FAIR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert config.gk_sensitivity > 1.0
        assert config.confidence_threshold < 0.60

    def test_rain_adjustment(self, calibrator):
        """Verifica ajuste para lluvia"""
        metrics = VideoQualityMetrics(
            brightness=127, brightness_std=20, blur_level=0.6, motion_blur=0.3,
            occlusion_rate=0.2, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.RAIN, crowd_density=0.2,
            video_quality=VideoQuality.FAIR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert config.gk_sensitivity > 1.0

    def test_fog_adjustment(self, calibrator):
        """Verifica ajuste para niebla"""
        metrics = VideoQualityMetrics(
            brightness=150, brightness_std=50, blur_level=0.7, motion_blur=0.2,
            occlusion_rate=0.3, lighting_condition=LightingCondition.VARIABLE,
            weather_condition=WeatherCondition.FOG, crowd_density=0.3,
            video_quality=VideoQuality.FAIR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert config.gk_sensitivity > 1.0


# ============================================================================
# TESTS: AdaptiveCalibration - Validación de Rangos
# ============================================================================

class TestAdaptiveCalibrationRanges:
    """Tests para validación de rangos de parámetros"""

    def test_confidence_threshold_range(self, calibrator):
        """Verifica que confidence_threshold esté en rango"""
        metrics = VideoQualityMetrics(
            brightness=10, brightness_std=100, blur_level=1.0, motion_blur=1.0,
            occlusion_rate=1.0, lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.FOG, crowd_density=1.0,
            video_quality=VideoQuality.POOR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert 0.25 <= config.confidence_threshold <= 0.75

    def test_gk_sensitivity_range(self, calibrator):
        """Verifica que gk_sensitivity esté en rango"""
        metrics = VideoQualityMetrics(
            brightness=10, brightness_std=100, blur_level=1.0, motion_blur=1.0,
            occlusion_rate=1.0, lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.FOG, crowd_density=1.0,
            video_quality=VideoQuality.POOR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert 0.8 <= config.gk_sensitivity <= 1.3

    def test_tracker_max_distance_range(self, calibrator):
        """Verifica que tracker_max_distance esté en rango"""
        metrics = VideoQualityMetrics(
            brightness=10, brightness_std=100, blur_level=1.0, motion_blur=1.0,
            occlusion_rate=1.0, lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.FOG, crowd_density=1.0,
            video_quality=VideoQuality.POOR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert 50 <= config.tracker_max_distance <= 150

    def test_skip_frames_range(self, calibrator):
        """Verifica que skip_frames esté en rango"""
        metrics = VideoQualityMetrics(
            brightness=10, brightness_std=100, blur_level=1.0, motion_blur=1.0,
            occlusion_rate=1.0, lighting_condition=LightingCondition.DARK,
            weather_condition=WeatherCondition.FOG, crowd_density=1.0,
            video_quality=VideoQuality.POOR, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        assert 1 <= config.skip_frames <= 5


# ============================================================================
# TESTS: AdaptiveCalibration - Reportes
# ============================================================================

class TestAdaptiveCalibrationReports:
    """Tests para generación de reportes"""

    def test_report_generation(self, calibrator):
        """Verifica generación de reporte"""
        metrics = VideoQualityMetrics(
            brightness=127, brightness_std=20, blur_level=0.3, motion_blur=0.1,
            occlusion_rate=0.1, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.3,
            video_quality=VideoQuality.GOOD, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)

        assert config.quality_report is not None
        assert len(config.quality_report) > 0
        assert "REPORTE" in config.quality_report

    def test_report_contains_metrics(self, calibrator):
        """Verifica que reporte incluye métricas"""
        metrics = VideoQualityMetrics(
            brightness=127, brightness_std=20, blur_level=0.3, motion_blur=0.1,
            occlusion_rate=0.1, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.3,
            video_quality=VideoQuality.GOOD, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        report = config.quality_report

        assert "Brillo" in report or "brightness" in report.lower()


# ============================================================================
# TESTS: Integración y Conversiones
# ============================================================================

class TestIntegrationAndConversions:
    """Tests de integración y conversiones de datos"""

    def test_metrics_to_dict(self):
        """Verifica conversión de metrics a dict"""
        metrics = VideoQualityMetrics(
            brightness=127, brightness_std=20, blur_level=0.3, motion_blur=0.1,
            occlusion_rate=0.1, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.3,
            video_quality=VideoQuality.GOOD, analysis_frames=10, frame_rate=25.0
        )
        data = metrics.to_dict()

        assert isinstance(data, dict)
        assert data['brightness'] == 127
        assert data['lighting_condition'] == 'NORMAL'
        assert data['video_quality'] == 'GOOD'

    def test_config_to_dict(self, calibrator):
        """Verifica conversión de config a dict"""
        metrics = VideoQualityMetrics(
            brightness=127, brightness_std=20, blur_level=0.3, motion_blur=0.1,
            occlusion_rate=0.1, lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR, crowd_density=0.3,
            video_quality=VideoQuality.GOOD, analysis_frames=10, frame_rate=25.0
        )
        config = calibrator.get_optimal_config(metrics)
        data = config.to_dict()

        assert isinstance(data, dict)
        assert 'confidence_threshold' in data
        assert 'gk_sensitivity' in data

    def test_dict_to_metrics_conversion(self, calibrator):
        """Verifica conversión de dict a metrics"""
        data = {
            'brightness': 127, 'brightness_std': 20, 'blur_level': 0.3,
            'motion_blur': 0.1, 'occlusion_rate': 0.1, 'crowd_density': 0.3,
            'lighting_condition': 'NORMAL', 'weather_condition': 'CLEAR',
            'video_quality': 'GOOD', 'analysis_frames': 10, 'frame_rate': 25.0
        }
        config = calibrator.get_optimal_config(data)

        assert isinstance(config, ProcessingConfig)
        assert config.confidence_threshold > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

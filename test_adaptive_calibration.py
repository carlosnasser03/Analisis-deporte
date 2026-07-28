#!/usr/bin/env python3
"""
test_adaptive_calibration.py - Script de prueba para módulo de calibración adaptativa

Valida que las clases VideoQualityAnalyzer y AdaptiveCalibration funcionen correctamente.
"""

import sys
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] - %(name)s: %(message)s'
)

# Importar módulo
from core.adaptive_calibration import (
    VideoQualityAnalyzer,
    AdaptiveCalibration,
    VideoQualityMetrics,
    LightingCondition,
    WeatherCondition,
    VideoQuality,
    analyze_and_calibrate,
)


def test_with_sample_video():
    """Prueba con un video real si existe"""
    # Buscar videos de prueba
    video_dirs = [
        Path("data"),
        Path("videos"),
        Path("examples"),
    ]

    video_path = None
    for dir_path in video_dirs:
        if dir_path.exists():
            for video_file in dir_path.glob("*.mp4"):
                video_path = video_file
                break
            if video_path:
                break

    if not video_path:
        print("\n⚠️  No se encontró video de prueba en data/, videos/ o examples/")
        print("Usando test con métricas simuladas...\n")
        return False

    print(f"\n✓ Encontrado video: {video_path}")
    print("=" * 70)

    try:
        metrics, config = analyze_and_calibrate(str(video_path))

        print("\n📊 MÉTRICAS OBTENIDAS:")
        print(f"  Brillo: {metrics.brightness:.1f} (±{metrics.brightness_std:.1f})")
        print(f"  Blur: {metrics.blur_level:.3f}")
        print(f"  Motion blur: {metrics.motion_blur:.3f}")
        print(f"  Oclusión: {metrics.occlusion_rate:.2f}")
        print(f"  Iluminación: {metrics.lighting_condition.value}")
        print(f"  Clima: {metrics.weather_condition.value}")
        print(f"  Densidad de multitud: {metrics.crowd_density:.2f}")
        print(f"  Calidad: {metrics.video_quality.value}")

        print("\n⚙️  CONFIGURACIÓN CALIBRADA:")
        print(f"  confidence_threshold: {config.confidence_threshold:.3f}")
        print(f"  gk_sensitivity: {config.gk_sensitivity:.3f}")
        print(f"  tracker_max_distance: {config.tracker_max_distance:.1f}px")
        print(f"  skip_frames: {config.skip_frames}")
        print(f"  use_motion_blur: {config.use_motion_blur}")

        print("\n📋 REPORTE:")
        print(config.quality_report)

        return True

    except Exception as e:
        print(f"❌ Error analizando video: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_simulated_metrics():
    """Prueba con métricas simuladas"""
    print("\n" + "=" * 70)
    print("PRUEBA CON MÉTRICAS SIMULADAS")
    print("=" * 70)

    test_cases = [
        {
            "name": "Video de EXCELENTE calidad",
            "metrics": VideoQualityMetrics(
                brightness=150.0,
                brightness_std=20.0,
                blur_level=0.1,
                motion_blur=0.05,
                occlusion_rate=0.05,
                lighting_condition=LightingCondition.NORMAL,
                weather_condition=WeatherCondition.CLEAR,
                crowd_density=0.2,
                video_quality=VideoQuality.EXCELLENT,
                analysis_frames=10,
                frame_rate=30.0,
            ),
        },
        {
            "name": "Video OSCURO con mucho blur",
            "metrics": VideoQualityMetrics(
                brightness=40.0,
                brightness_std=15.0,
                blur_level=0.7,
                motion_blur=0.4,
                occlusion_rate=0.35,
                lighting_condition=LightingCondition.DARK,
                weather_condition=WeatherCondition.FOG,
                crowd_density=0.5,
                video_quality=VideoQuality.POOR,
                analysis_frames=10,
                frame_rate=30.0,
            ),
        },
        {
            "name": "Video con ILUMINACIÓN VARIABLE",
            "metrics": VideoQualityMetrics(
                brightness=120.0,
                brightness_std=70.0,  # Alta variabilidad
                blur_level=0.35,
                motion_blur=0.3,
                occlusion_rate=0.2,
                lighting_condition=LightingCondition.VARIABLE,
                weather_condition=WeatherCondition.CLEAR,
                crowd_density=0.4,
                video_quality=VideoQuality.FAIR,
                analysis_frames=10,
                frame_rate=30.0,
            ),
        },
        {
            "name": "Video con lluvia y oclusión",
            "metrics": VideoQualityMetrics(
                brightness=110.0,
                brightness_std=35.0,
                blur_level=0.55,
                motion_blur=0.35,
                occlusion_rate=0.45,
                lighting_condition=LightingCondition.NORMAL,
                weather_condition=WeatherCondition.RAIN,
                crowd_density=0.6,
                video_quality=VideoQuality.FAIR,
                analysis_frames=10,
                frame_rate=30.0,
            ),
        },
    ]

    calibrator = AdaptiveCalibration()

    for test_case in test_cases:
        print(f"\n{'─' * 70}")
        print(f"CASO DE PRUEBA: {test_case['name']}")
        print(f"{'─' * 70}")

        metrics = test_case["metrics"]
        config = calibrator.get_optimal_config(metrics)

        print("\n📊 Métricas:")
        print(f"  Brillo: {metrics.brightness:.1f} (±{metrics.brightness_std:.1f})")
        print(f"  Blur: {metrics.blur_level:.3f}")
        print(f"  Oclusión: {metrics.occlusion_rate:.2f}")
        print(f"  Iluminación: {metrics.lighting_condition.value}")
        print(f"  Clima: {metrics.weather_condition.value}")
        print(f"  Calidad: {metrics.video_quality.value}")

        print("\n⚙️  Configuración:")
        print(f"  confidence_threshold: {config.confidence_threshold:.3f}")
        print(f"  gk_sensitivity: {config.gk_sensitivity:.3f}")
        print(f"  tracker_max_distance: {config.tracker_max_distance:.1f}px")
        print(f"  skip_frames: {config.skip_frames}")
        print(f"  use_motion_blur: {config.use_motion_blur}")

        print("\n📋 Reporte:")
        print(config.quality_report)


def test_dataclass_serialization():
    """Prueba serialización a/desde diccionario"""
    print("\n" + "=" * 70)
    print("PRUEBA DE SERIALIZACIÓN")
    print("=" * 70)

    metrics = VideoQualityMetrics(
        brightness=120.0,
        brightness_std=25.0,
        blur_level=0.25,
        motion_blur=0.1,
        occlusion_rate=0.15,
        lighting_condition=LightingCondition.NORMAL,
        weather_condition=WeatherCondition.CLEAR,
        crowd_density=0.3,
        video_quality=VideoQuality.GOOD,
        analysis_frames=10,
        frame_rate=30.0,
    )

    # Convertir a diccionario
    metrics_dict = metrics.to_dict()
    print("\n✓ Métricas convertidas a diccionario:")
    for key, value in metrics_dict.items():
        print(f"  {key}: {value}")

    # Deserializar
    calibrator = AdaptiveCalibration()
    config = calibrator.get_optimal_config(metrics_dict)

    print("\n✓ Configuración obtenida desde diccionario:")
    config_dict = config.to_dict()
    for key, value in config_dict.items():
        if key != 'quality_report':  # El reporte es muy largo
            print(f"  {key}: {value}")


def main():
    """Ejecuta todas las pruebas"""
    print("\n" + "=" * 70)
    print("PRUEBAS DEL MÓDULO: adaptive_calibration.py")
    print("=" * 70)

    # Prueba 1: Con video real si existe
    test_with_sample_video()

    # Prueba 2: Con métricas simuladas
    test_with_simulated_metrics()

    # Prueba 3: Serialización
    test_dataclass_serialization()

    print("\n" + "=" * 70)
    print("✅ PRUEBAS COMPLETADAS")
    print("=" * 70)
    print("\nNota: El módulo está listo para usar en pipeline de procesamiento")
    print("Importar: from core.adaptive_calibration import analyze_and_calibrate")


if __name__ == "__main__":
    main()

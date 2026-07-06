"""
run_fase3_tests.py - Script para ejecutar tests FASE 3 y generar reportes

Ejecuta los tests end-to-end y genera reportes de rendimiento y validación.

Author: Scout AI - FASE 3
Date: 2026-07-06
"""

import subprocess
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
import time
import psutil

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def setup_paths():
    """Configura rutas necesarias"""
    project_root = Path(__file__).parent
    data_dir = project_root / "data"
    logs_dir = data_dir / "logs"

    logs_dir.mkdir(parents=True, exist_ok=True)

    return {
        'project_root': project_root,
        'data_dir': data_dir,
        'logs_dir': logs_dir,
        'tests_dir': project_root / "tests"
    }


def run_pytest_tests(test_file: str, markers: str = "fase3") -> dict:
    """
    Ejecuta tests con pytest.

    Args:
        test_file: Ruta al archivo de tests
        markers: Marcas de pytest a usar

    Returns:
        dict: Resultado de ejecución
    """
    logger.info(f"Ejecutando tests: {test_file}")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        test_file,
        "-v",
        "-m",
        markers,
        "--tb=short",
        "--color=yes"
    ]

    start_time = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - start_time

    return {
        'returncode': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'elapsed_time': elapsed,
        'success': result.returncode == 0
    }


def get_system_info() -> dict:
    """Obtiene información del sistema"""
    try:
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'memory_available_gb': psutil.virtual_memory().available / (1024**3),
            'python_version': sys.version,
        }
    except Exception as e:
        logger.warning(f"No se pudo obtener info del sistema: {e}")
        return {}


def generate_test_report(paths: dict, results: dict) -> Path:
    """
    Genera reporte de tests.

    Args:
        paths: Diccionario de rutas
        results: Resultados de tests

    Returns:
        Path: Ruta al archivo de reporte
    """
    report = {
        'timestamp': datetime.now().isoformat(),
        'test_results': results,
        'system_info': get_system_info(),
    }

    report_path = paths['logs_dir'] / f"test_report_fase3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Reporte guardado: {report_path}")
    return report_path


def generate_validation_report(paths: dict) -> Path:
    """
    Genera reporte de validación del pipeline.

    Args:
        paths: Diccionario de rutas

    Returns:
        Path: Ruta al archivo de validación
    """
    logger.info("Generando reporte de validación...")

    validation = {
        'timestamp': datetime.now().isoformat(),
        'fase': 'FASE 3',
        'components': {
            'video_processor_fase3': {
                'status': 'implemented',
                'features': [
                    'Team classification mejorada',
                    'Tracking mejorado',
                    'Jersey detection',
                    'Logging detallado',
                    'Benchmarking de rendimiento',
                    'Perfilado de CPU',
                    'Monitoreo de memoria'
                ]
            },
            'tests': {
                'status': 'comprehensive',
                'coverage': [
                    'test_complete_video_processing',
                    'test_team_classification_accuracy',
                    'test_tracking_stability',
                    'test_jersey_detection_accuracy',
                    'test_performance_benchmarks'
                ]
            }
        },
        'benchmarks': {
            'targets': {
                'fps_processed': '15+ FPS en CPU',
                'frame_processing_time': '<2s por frame',
                'tracker_performance': '<50ms por track',
                'team_classifier_performance': '<200ms',
                'memory_usage': '<2GB'
            }
        }
    }

    report_path = paths['logs_dir'] / "pipeline_validation_fase3.json"

    with open(report_path, 'w') as f:
        json.dump(validation, f, indent=2)

    logger.info(f"Reporte de validación guardado: {report_path}")
    return report_path


def print_summary(results: dict):
    """Imprime resumen de resultados"""
    logger.info("\n" + "=" * 70)
    logger.info("RESUMEN DE EJECUCIÓN - FASE 3")
    logger.info("=" * 70)

    for test_name, result in results.items():
        status = "✓ PASSED" if result['success'] else "✗ FAILED"
        logger.info(f"{test_name}: {status} ({result['elapsed_time']:.2f}s)")

    logger.info("=" * 70 + "\n")


def main():
    """Función principal"""
    logger.info("Iniciando tests FASE 3...")

    # Setup
    paths = setup_paths()
    logger.info(f"Project root: {paths['project_root']}")

    # Verificar archivos de tests
    test_file = paths['tests_dir'] / "test_end_to_end_fase3.py"
    if not test_file.exists():
        logger.error(f"Archivo de tests no encontrado: {test_file}")
        sys.exit(1)

    logger.info(f"Archivo de tests: {test_file}")

    # Ejecutar tests
    results = {}

    logger.info("\nEjecutando tests FASE 3...")
    results['fase3_tests'] = run_pytest_tests(str(test_file), markers="fase3")

    # Generar reportes
    logger.info("\nGenerando reportes...")
    test_report = generate_test_report(paths, results)
    validation_report = generate_validation_report(paths)

    # Imprimir resumen
    print_summary(results)

    # Información final
    logger.info("Reportes generados:")
    logger.info(f"  - Test Report: {test_report}")
    logger.info(f"  - Validation Report: {validation_report}")

    # Exit code
    all_passed = all(r['success'] for r in results.values())
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

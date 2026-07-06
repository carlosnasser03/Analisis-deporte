#!/usr/bin/env python3
"""
run_tests.py - Script para ejecutar la suite de tests de Scout AI FASE 2

Proporciona interfaz amigable para ejecutar tests con diferentes configuraciones.
Uso:
    python run_tests.py                    # Ejecutar todos los tests
    python run_tests.py --coverage         # Con reporte de cobertura
    python run_tests.py --integration      # Solo tests de integración
    python run_tests.py --parallel         # Ejecución paralela
"""

import subprocess
import sys
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Ejecuta comando y maneja errores"""
    if description:
        print(f"\n{'='*70}")
        print(f"▶ {description}")
        print(f"{'='*70}\n")

    try:
        result = subprocess.run(cmd, shell=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"✗ Error ejecutando comando: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Scout AI FASE 2 - Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python run_tests.py                    # Ejecutar todos los tests
  python run_tests.py --coverage         # Con reporte de cobertura HTML
  python run_tests.py --core             # Solo tests de core modules
  python run_tests.py --pipeline         # Solo tests de pipeline
  python run_tests.py --utils            # Solo tests de utils
  python run_tests.py --integration      # Solo tests de integración
  python run_tests.py --edge-case        # Solo edge case tests
  python run_tests.py --parallel         # Ejecución paralela (rápido)
  python run_tests.py --verbose          # Salida muy detallada
  python run_tests.py --quick            # Sin tests lentos (rápido)
        """
    )

    parser.add_argument("--coverage", action="store_true", help="Generar reporte de cobertura")
    parser.add_argument("--core", action="store_true", help="Solo tests de core modules")
    parser.add_argument("--pipeline", action="store_true", help="Solo tests de pipeline modules")
    parser.add_argument("--utils", action="store_true", help="Solo tests de utils modules")
    parser.add_argument("--integration", action="store_true", help="Solo tests de integración")
    parser.add_argument("--edge-case", action="store_true", help="Solo edge case tests")
    parser.add_argument("--parallel", action="store_true", help="Ejecución paralela")
    parser.add_argument("--verbose", action="store_true", help="Salida muy detallada")
    parser.add_argument("--quick", action="store_true", help="Sin tests lentos")
    parser.add_argument("--fix-validation", action="store_true", help="Validar fixes específicos")
    parser.add_argument("--no-opengl", action="store_true", help="Sin tests que requieren OpenCV real")

    args = parser.parse_args()

    # Comando base
    cmd_base = "pytest tests/"

    # Determinar qué tests ejecutar
    if args.core:
        cmd_base += " tests/test_core_modules.py"
    elif args.pipeline:
        cmd_base += " tests/test_pipeline_modules.py"
    elif args.utils:
        cmd_base += " tests/test_utils_modules.py"
    elif args.integration:
        cmd_base += " tests/test_integration.py"
    elif args.edge_case:
        cmd_base = "pytest tests/ -m edge_case"
    elif args.fix_validation:
        # Tests específicos para validar fixes
        cmd_base = "pytest tests/ -k 'basicconfig or valid_classes or persistence or calibration or ocr'"

    # Opciones adicionales
    if args.verbose:
        cmd_base += " -v -s"
    else:
        cmd_base += " -v"

    if args.parallel:
        cmd_base += " -n auto"

    if args.quick or args.no_opengl:
        cmd_base += " -m 'not slow'"

    if args.no_opengl:
        cmd_base += " -m 'not requires_opencv'"

    if args.coverage:
        cmd_base += " --cov=. --cov-report=html --cov-report=term-missing"

    # Ejecutar tests
    success = run_command(cmd_base, "Ejecutando Suite de Tests - Scout AI FASE 2")

    # Información adicional
    if success:
        print("\n" + "="*70)
        print("✓ TESTS COMPLETADOS EXITOSAMENTE")
        print("="*70)

        if args.coverage:
            print("\n📊 Reporte de cobertura generado en: htmlcov/index.html")
            print("   Abre el archivo en tu navegador para ver el detalle.")

        print("\n📋 Para más información:")
        print("   - Ver TESTS_README.md")
        print("   - Ver data/logs/test_suite_summary.json")

        return 0
    else:
        print("\n" + "="*70)
        print("✗ ALGUNOS TESTS FALLARON")
        print("="*70)
        print("\nVerifica los errores arriba y ejecuta nuevamente.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

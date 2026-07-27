"""
test_distance_velocity.py - Tests y ejemplos del Distance Velocity Calculator

Ejecuta independientemente sin dependencias del __init__.py
"""

import sys
from pathlib import Path
import json
import numpy as np

# Importar directamente el módulo
sys.path.insert(0, str(Path(__file__).parent / "core"))

from distance_velocity_calculator import (
    DistanceVelocityAnalyzer,
    TrackPoint,
    DistanceCalculator,
    VelocityCalculator,
    MovementAnalyzer
)


def generate_sample_trajectory():
    """Genera una trayectoria de ejemplo realista."""
    frames = []
    for i in range(120):
        # Movimiento sinusoidal para simular carrera
        x = 100 + 50 * np.sin(i * np.pi / 30)
        y = 100 + 100 * (i / 120)
        frames.append(TrackPoint(
            frame=i,
            x=float(x),
            y=float(y),
            confidence=0.95
        ))
    return frames


def main():
    print("\n" + "="*70)
    print("DISTANCE & VELOCITY CALCULATOR - TEST & EXAMPLE GENERATION")
    print("="*70)

    # Generar trayectoria de ejemplo
    print("\n[1/5] Generando trayectoria de ejemplo...")
    trajectory = generate_sample_trajectory()
    print(f"    [OK] Trayectoria generada: {len(trajectory)} frames")

    # Crear analizador
    print("\n[2/5] Inicializando analizador...")
    analyzer = DistanceVelocityAnalyzer(
        fps=30.0,
        pixels_per_meter=10.0,
        max_jump_distance=5.0
    )
    print("    [OK] Analizador inicializado")

    # Realizar análisis completo
    print("\n[3/5] Realizando análisis...")
    analysis = analyzer.analyze_player_trajectory(
        trajectory,
        field_width=1280,
        field_height=720
    )
    print("    [OK] Análisis completado")

    # Generar y mostrar reporte
    print("\n[4/5] Generando reporte...")
    report = analyzer.generate_report(analysis)
    print(report)

    # Exportar a JSON
    print("\n[5/5] Exportando a JSON...")
    output_path = Path(__file__).parent / "data" / "logs" / "distance_velocity_analysis.json"
    analyzer.export_analysis_json(analysis, output_path)
    print(f"    [OK] Análisis exportado a: {output_path}")

    # Mostrar contenido del JSON generado
    print("\n" + "-"*70)
    print("CONTENIDO DEL ARCHIVO JSON GENERADO:")
    print("-"*70)
    with open(output_path, 'r') as f:
        json_content = json.load(f)
        print(json.dumps(json_content, indent=2))

    print("\n" + "="*70)
    print("[OK] TEST COMPLETADO EXITOSAMENTE")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

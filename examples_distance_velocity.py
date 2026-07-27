"""
examples_distance_velocity.py - Ejemplos de uso del DistanceVelocityCalculator

Demuestra cómo usar el módulo de cálculo de distancia y velocidad
con datos de trayectorias de jugadores.
"""

import sys
from pathlib import Path
import json

# Agregar core al path
sys.path.insert(0, str(Path(__file__).parent))

from core.distance_velocity_calculator import (
    DistanceVelocityAnalyzer,
    TrackPoint,
    DistanceCalculator,
    VelocityCalculator,
    MovementAnalyzer
)


def example_1_basic_distance_calculation():
    """
    Ejemplo 1: Cálculo básico de distancia.

    Demuestra cómo calcular la distancia total recorrida por un jugador.
    """
    print("\n" + "="*60)
    print("EJEMPLO 1: Cálculo Básico de Distancia")
    print("="*60)

    # Crear una trayectoria de ejemplo (movimiento diagonal)
    trajectory = [
        TrackPoint(frame=0, x=100, y=100, confidence=0.95),
        TrackPoint(frame=1, x=105, y=105, confidence=0.95),
        TrackPoint(frame=2, x=110, y=110, confidence=0.95),
        TrackPoint(frame=3, x=115, y=115, confidence=0.95),
        TrackPoint(frame=4, x=120, y=120, confidence=0.95),
    ]

    # Crear calculador con calibración (10 píxeles = 1 metro)
    calc = DistanceCalculator(pixels_per_meter=10.0, frame_rate=30.0)

    # Calcular distancia
    metrics, processed = calc.calculate_total_distance(trajectory)

    print(f"Distancia total: {metrics.total_distance:.2f} metros")
    print(f"Frames procesados: {len(processed)}")
    print(f"Confianza promedio: {metrics.confidence_avg:.3f}")


def example_2_velocity_metrics():
    """
    Ejemplo 2: Cálculo de métricas de velocidad.

    Demuestra el cálculo de velocidad máxima, promedio, mediana y percentiles.
    """
    print("\n" + "="*60)
    print("EJEMPLO 2: Métricas de Velocidad")
    print("="*60)

    # Simular distancias por frame (en metros)
    distances = [
        0.5,   # Frame 0-1
        0.6,   # Frame 1-2
        0.7,   # Frame 2-3
        0.8,   # Frame 3-4
        0.9,   # Frame 4-5
        1.0,   # Frame 5-6 (máxima)
        0.8,   # Frame 6-7
        0.6,   # Frame 7-8
        0.4,   # Frame 8-9
        0.2,   # Frame 9-10
    ]

    # Crear calculador de velocidad (30 FPS)
    vel_calc = VelocityCalculator(fps=30.0)

    # Calcular métricas
    metrics = vel_calc.calculate_velocity_metrics(distances)

    print(f"Velocidad máxima: {metrics.max_velocity:.2f} m/s")
    print(f"Velocidad mínima: {metrics.min_velocity:.2f} m/s")
    print(f"Velocidad promedio: {metrics.average_velocity:.2f} m/s")
    print(f"Velocidad mediana: {metrics.median_velocity:.2f} m/s")
    print(f"Std Dev: {metrics.std_velocity:.2f} m/s")
    print(f"\nPercentiles:")
    print(f"  P90: {metrics.percentile_90:.2f} m/s")
    print(f"  P95: {metrics.percentile_95:.2f} m/s")
    print(f"  P99: {metrics.percentile_99:.2f} m/s")


def example_3_movement_analysis():
    """
    Ejemplo 3: Análisis de movimiento avanzado.

    Demuestra cálculo de aceleración, desaceleración y cambios de dirección.
    """
    print("\n" + "="*60)
    print("EJEMPLO 3: Análisis de Movimiento")
    print("="*60)

    # Crear trayectoria con cambios de dirección
    trajectory = [
        TrackPoint(frame=0, x=100, y=100, confidence=0.95),
        TrackPoint(frame=1, x=110, y=100, confidence=0.95),  # Derecha
        TrackPoint(frame=2, x=120, y=100, confidence=0.95),  # Derecha
        TrackPoint(frame=3, x=120, y=110, confidence=0.95),  # Abajo (cambio)
        TrackPoint(frame=4, x=110, y=120, confidence=0.95),  # Diagonal (cambio)
        TrackPoint(frame=5, x=100, y=120, confidence=0.95),  # Izquierda (cambio)
    ]

    # Velocidades simuladas
    velocities = [2.0, 2.5, 3.0, 2.8, 2.5, 2.0]

    # Analizar movimiento
    mov_analyzer = MovementAnalyzer(fps=30.0)
    accelerations = mov_analyzer.calculate_acceleration(velocities)
    changes, angles = mov_analyzer.calculate_directional_changes(trajectory)

    print(f"Aceleraciones calculadas: {len(accelerations)}")
    print(f"Cambios de dirección detectados: {changes}")
    print(f"Ángulos de dirección: {len(angles)}")
    if angles:
        print(f"  Ángulos: {[f'{a:.1f}°' for a in angles[:3]]}...")


def example_4_complete_analysis():
    """
    Ejemplo 4: Análisis completo de trayectoria.

    Demuestra el análisis integral combinando distancia, velocidad y movimiento.
    """
    print("\n" + "="*60)
    print("EJEMPLO 4: Análisis Completo de Trayectoria")
    print("="*60)

    # Simular trayectoria realista (120 frames de movimiento)
    import numpy as np

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

    # Crear analizador
    analyzer = DistanceVelocityAnalyzer(
        fps=30.0,
        pixels_per_meter=10.0,
        max_jump_distance=5.0
    )

    # Realizar análisis
    analysis = analyzer.analyze_player_trajectory(
        frames,
        field_width=1280,
        field_height=720
    )

    # Mostrar resultados
    print(analyzer.generate_report(analysis))

    # Exportar a JSON
    output_path = Path(__file__).parent / "data" / "logs" / "distance_velocity_analysis.json"
    analyzer.export_analysis_json(analysis, output_path)
    print(f"\nAnálisis exportado a: {output_path}")


def example_5_occlusion_handling():
    """
    Ejemplo 5: Manejo de oclusiones.

    Demuestra cómo el sistema detecta y maneja saltos en la trayectoria.
    """
    print("\n" + "="*60)
    print("EJEMPLO 5: Detección de Oclusiones")
    print("="*60)

    # Trayectoria con oclusión (salto grande)
    trajectory = [
        TrackPoint(frame=0, x=100, y=100, confidence=0.95),
        TrackPoint(frame=1, x=105, y=105, confidence=0.95),
        TrackPoint(frame=2, x=110, y=110, confidence=0.95),
        # OCLUSIÓN: jugador desaparece
        TrackPoint(frame=15, x=250, y=250, confidence=0.95),  # Salto de ~212 píxeles
        TrackPoint(frame=16, x=255, y=255, confidence=0.95),
    ]

    calc = DistanceCalculator(pixels_per_meter=10.0, frame_rate=30.0)
    metrics, _ = calc.calculate_total_distance(trajectory)

    print(f"Saltos detectados: {len(metrics.jump_detections)}")
    for jump in metrics.jump_detections:
        print(f"  - Frames {jump['frame_from']}-{jump['frame_to']}: "
              f"{jump['distance_meters']:.2f}m "
              f"(severidad: {jump['severity']:.2f}x)")

    print(f"\nDistancia total (saltos filtrados): {metrics.total_distance:.2f}m")


def example_6_calibration():
    """
    Ejemplo 6: Calibración automática de píxeles a metros.

    Demuestra cómo calibrar usando una distancia de referencia conocida.
    """
    print("\n" + "="*60)
    print("EJEMPLO 6: Calibración de Píxeles a Metros")
    print("="*60)

    calc = DistanceCalculator(frame_rate=30.0)

    print("Antes de calibración: pixels_per_meter =", calc.pixels_per_meter)

    # Calibrar usando distancia conocida
    # En el video, medimos que el campo mide 100 píxeles de ancho
    # Sabemos que un campo de fútbol mide 100 metros
    calc.calibrate_pixels_per_meter(
        reference_distance_pixels=100.0,
        reference_distance_meters=100.0
    )

    print(f"Después de calibración: pixels_per_meter = {calc.pixels_per_meter:.4f}")

    # Probar conversión
    dist_pixels = 50
    dist_meters = calc.pixels_to_meters(dist_pixels)
    print(f"\n{dist_pixels} píxeles = {dist_meters:.2f} metros")

    # Conversión inversa
    dist_meters2 = 25
    dist_pixels2 = calc.meters_to_pixels(dist_meters2)
    print(f"{dist_meters2} metros = {dist_pixels2:.2f} píxeles")


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# EJEMPLOS DE USO: Distance & Velocity Calculator")
    print("#"*60)

    # Ejecutar todos los ejemplos
    example_1_basic_distance_calculation()
    example_2_velocity_metrics()
    example_3_movement_analysis()
    example_4_complete_analysis()
    example_5_occlusion_handling()
    example_6_calibration()

    print("\n" + "#"*60)
    print("# Ejemplos completados exitosamente")
    print("#"*60 + "\n")

#!/usr/bin/env python
"""
example_performance_validator.py - Ejemplos de uso del módulo PerformanceValidator

Demuestra:
- Validación individual de métricas
- Detección de anomalías
- Análisis completo de jugadores
- Generación de comparativas
"""

from core.performance_validator import PerformanceValidator
import json


def print_section(title):
    """Imprimir título de sección."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def format_dict(data, indent=2):
    """Formatear diccionario para imprimir."""
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)


def example_1_basic_validation():
    """Ejemplo 1: Validación básica de métricas individuales."""
    print_section("EJEMPLO 1: Validación Básica de Métricas Individuales")

    validator = PerformanceValidator()

    # Validar distancia para diferentes posiciones
    print("1.1 Validación de Distancia\n")

    positions_distance = [
        ('GK', 5500.0, "Portero - distancia normal"),
        ('DEF', 12000.0, "Defensa - distancia alta"),
        ('MID', 11200.0, "Centrocampista - distancia normal"),
        ('FWD', 9200.0, "Delantero - distancia normal"),
    ]

    for position, distance, description in positions_distance:
        result = validator.validate_distance(distance, position)
        print(f"  {description}")
        print(f"    - Medido: {result['measured']} m")
        print(f"    - Esperado: {result['expected']} m")
        print(f"    - Varianza: {result['variance_percent']}%")
        print(f"    - Status: {result['status']}")
        print(f"    - Percentil: {result['percentile']:.1f}%")
        print()

    # Validar velocidad
    print("1.2 Validación de Velocidad\n")

    positions_velocity = [
        ('GK', 5.2, "Portero - velocidad normal"),
        ('MID', 9.0, "Centrocampista - velocidad superior"),
        ('FWD', 7.0, "Delantero - velocidad baja"),
    ]

    for position, velocity, description in positions_velocity:
        result = validator.validate_velocity(velocity, position)
        print(f"  {description}")
        print(f"    - Medido: {result['measured']} m/s")
        print(f"    - Esperado: {result['expected']} m/s")
        print(f"    - Status: {result['status']}")
        print(f"    - Confianza: {result['confidence']:.0%}")
        print()


def example_2_anomaly_detection():
    """Ejemplo 2: Detección de anomalías en datos de jugador."""
    print_section("EJEMPLO 2: Detección de Anomalías")

    validator = PerformanceValidator()

    # Caso 1: Sin anomalías
    print("2.1 Jugador Normal (Sin Anomalías)\n")

    normal_player = {
        'player_id': 1,
        'player_name': 'Marco Verratti',
        'position': 'MID',
        'distance': 11200.0,
        'velocity': 8.4,
        'intensity': 72.0
    }

    anomalies = validator.detect_anomalies(normal_player)
    print(f"  Jugador: {normal_player['player_name']}")
    print(f"  Posición: {normal_player['position']}")
    print(f"  Anomalías detectadas: {len(anomalies)}")

    if not anomalies:
        print("  ✓ Todas las métricas son normales")
    print()

    # Caso 2: Múltiples anomalías
    print("2.2 Jugador Anómalo (Múltiples Anomalías)\n")

    anomalous_player = {
        'player_id': 2,
        'player_name': 'Jugador Sospechoso',
        'position': 'DEF',
        'distance': 25000.0,  # Muy alto
        'velocity': 15.0,      # Muy alto
        'intensity': 40.0      # Normal
    }

    anomalies = validator.detect_anomalies(anomalous_player)
    print(f"  Jugador: {anomalous_player['player_name']}")
    print(f"  Posición: {anomalous_player['position']}")
    print(f"  Anomalías detectadas: {len(anomalies)}\n")

    for anomaly in anomalies:
        print(f"  Anomalía: {anomaly['metric'].upper()}")
        print(f"    - Valor: {anomaly['value']}")
        print(f"    - Z-Score: {anomaly['z_score']:.2f}")
        print(f"    - Severidad: {anomaly['severity']}")
        print(f"    - Descripción: {anomaly['description']}\n")


def example_3_full_analysis():
    """Ejemplo 3: Análisis completo de jugador."""
    print_section("EJEMPLO 3: Análisis Completo de Jugador")

    validator = PerformanceValidator()

    # Analizar jugador
    validation = validator.generate_comparison(
        player_id=10,
        player_name='Kylian Mbappé',
        position='FWD',
        distance_m=10500.0,
        max_velocity_m_s=10.5,
        intensity_pct=85.0
    )

    print(f"JUGADOR: {validation.player_name}")
    print(f"ID: {validation.player_id}")
    print(f"Posición: {validation.position}")
    print(f"Timestamp: {validation.validation_timestamp}\n")

    print("MÉTRICAS INDIVIDUALES:")
    for metric_name, metric in validation.metrics.items():
        print(f"\n  {metric_name.upper()}")
        print(f"    - Valor: {metric.value:.1f}")
        print(f"    - Media: {metric.benchmark_mean:.1f}")
        print(f"    - Z-Score: {metric.z_score:.2f}")
        print(f"    - Status: {metric.status}")
        print(f"    - Percentil: {metric.percentile:.1f}%")
        print(f"    - Rango esperado: [{metric.expected_range[0]:.1f}, {metric.expected_range[1]:.1f}]")
        print(f"    - Válido: {'✓' if metric.is_valid else '✗'}")

    print(f"\nESTADO GENERAL: {validation.overall_status}")
    print(f"NIVEL DE RENDIMIENTO: {validation.performance_level}")

    if validation.anomalies_detected:
        print(f"\nANOMALÍAS DETECTADAS:")
        for anomaly in validation.anomalies_detected:
            print(f"  - {anomaly}")

    if validation.recommendations:
        print(f"\nRECOMENDACIONES:")
        for rec in validation.recommendations:
            print(f"  - {rec}")


def example_4_percentiles():
    """Ejemplo 4: Cálculo de percentiles."""
    print_section("EJEMPLO 4: Cálculo de Percentiles")

    validator = PerformanceValidator()

    print("Percentiles para diferentes valores de distancia en posición MID:\n")

    distances = [8000, 10000, 11200, 12000, 14000, 16000]

    for distance in distances:
        try:
            percentile = validator.get_performance_percentile(
                distance, 'MID', 'distance'
            )
            print(f"  Distancia {distance:>5} m → Percentil {percentile:>6.1f}%")
        except ValueError as e:
            print(f"  Error: {e}")

    print("\n\nPercentiles para diferentes velocidades máximas en posición FWD:\n")

    velocities = [6.0, 7.5, 8.9, 10.0, 11.5, 13.0]

    for velocity in velocities:
        try:
            percentile = validator.get_performance_percentile(
                velocity, 'FWD', 'max_velocity'
            )
            print(f"  Velocidad {velocity:>4.1f} m/s → Percentil {percentile:>6.1f}%")
        except ValueError as e:
            print(f"  Error: {e}")


def example_5_team_analysis():
    """Ejemplo 5: Análisis de equipo completo."""
    print_section("EJEMPLO 5: Análisis de Equipo Completo")

    validator = PerformanceValidator()

    # Datos de equipo
    team_data = [
        {
            'id': 1,
            'name': 'Donnarumma',
            'position': 'GK',
            'distance': 5500.0,
            'velocity': 5.2,
            'intensity': 35.0
        },
        {
            'id': 2,
            'name': 'Piqué',
            'position': 'DEF',
            'distance': 9800.0,
            'velocity': 7.8,
            'intensity': 65.0
        },
        {
            'id': 3,
            'name': 'Busquets',
            'position': 'MID',
            'distance': 11200.0,
            'velocity': 8.4,
            'intensity': 72.0
        },
        {
            'id': 4,
            'name': 'Haaland',
            'position': 'FWD',
            'distance': 10500.0,
            'velocity': 10.0,
            'intensity': 88.0
        },
    ]

    print("ANÁLISIS DE RENDIMIENTO DEL EQUIPO\n")
    print(f"{'Jugador':<15} {'Posición':<5} {'Rendimiento':<15} {'Recomendación'}")
    print("-" * 70)

    for player in team_data:
        validation = validator.generate_comparison(
            player_id=player['id'],
            player_name=player['name'],
            position=player['position'],
            distance_m=player['distance'],
            max_velocity_m_s=player['velocity'],
            intensity_pct=player['intensity']
        )

        recommendation = "✓ OK" if not validation.anomalies_detected else "⚠ Revisar"

        print(
            f"{player['name']:<15} "
            f"{player['position']:<5} "
            f"{validation.performance_level:<15} "
            f"{recommendation}"
        )

    print("\n" + "=" * 70)


def main():
    """Ejecutar todos los ejemplos."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "EJEMPLOS: PerformanceValidator" + " " * 23 + "║")
    print("║" + " " * 8 + "Validación de Rendimiento contra Benchmarks de StatsBomb" + " " * 2 + "║")
    print("╚" + "═" * 68 + "╝")

    example_1_basic_validation()
    example_2_anomaly_detection()
    example_3_full_analysis()
    example_4_percentiles()
    example_5_team_analysis()

    print("\n" + "=" * 70)
    print("Ejemplos completados exitosamente")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()

"""
statsbomb_example.py - Ejemplo de uso de la integración StatsBomb

Demuestra cómo comparar datos locales con benchmarks de Premier League.

Uso:
    python examples/statsbomb_example.py
    o
    cd .. && python examples/statsbomb_example.py
"""

import json
import sys
from pathlib import Path

# Agregar ruta del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.statsbomb_integration import StatsBombIntegration


def example_single_player():
    """Ejemplo: Comparar un jugador individual"""
    print("\n" + "="*70)
    print("EJEMPLO 1: Comparar un Jugador Individual")
    print("="*70)

    # Datos del jugador (como si vinieran del análisis de video)
    player_data = {
        "player_id": 7,
        "player_name": "Cristiano",
        "position": "FWD",
        "distance_m": 10500.0,
        "max_velocity_m_s": 10.5,
        "intensity_percent": 80.0
    }

    # Crear integrador
    integrator = StatsBombIntegration()

    # Generar reporte
    report = integrator.generate_comparison_report(player_data)

    # Mostrar resultados
    print(f"\nJugador: {report['player_name']} (#{report['player_id']})")
    print(f"Posición: {report['position']}")
    print(f"Timestamp: {report['timestamp']}")
    print(f"\nPercentil General: {report['overall_percentile']:.1f}")
    print(f"Resumen: {report['summary']}")

    # Detalles por métrica
    print("\n" + "-"*70)
    print("DETALLES POR MÉTRICA:")
    print("-"*70)

    for metric_name, comparison in report['comparisons'].items():
        print(f"\n{metric_name.upper()}:")
        print(f"  Tu jugador:     {comparison['player_value']:.1f}")
        print(f"  Promedio PL:    {comparison['benchmark_mean']:.1f}")
        print(f"  Desv. Estándar: {comparison['benchmark_std']:.1f}")
        print(f"  Z-Score:        {comparison['z_score']:.2f}")
        print(f"  Percentil:      {comparison['percentile_rank']:.1f}")
        print(f"  Nivel:          {comparison['strength_level'].upper()}")
        print(f"  Recomendación:  {comparison['recommendation']}")


def example_team_comparison():
    """Ejemplo: Comparar todo el equipo"""
    print("\n" + "="*70)
    print("EJEMPLO 2: Comparar Todo el Equipo")
    print("="*70)

    # Datos del equipo completo (11 jugadores)
    team_data = [
        {
            "player_id": 1,
            "player_name": "Def 1",
            "position": "DEF",
            "distance_m": 9500,
            "max_velocity_m_s": 9.5,
            "intensity_percent": 75
        },
        {
            "player_id": 2,
            "player_name": "Def 2",
            "position": "DEF",
            "distance_m": 10000,
            "max_velocity_m_s": 10.0,
            "intensity_percent": 76
        },
        {
            "player_id": 5,
            "player_name": "Mid 1",
            "position": "MID",
            "distance_m": 12000,
            "max_velocity_m_s": 10.5,
            "intensity_percent": 82
        },
        {
            "player_id": 7,
            "player_name": "Forward",
            "position": "FWD",
            "distance_m": 10500,
            "max_velocity_m_s": 11.0,
            "intensity_percent": 80
        },
        {
            "player_id": 11,
            "player_name": "Keeper",
            "position": "GK",
            "distance_m": 4500,
            "max_velocity_m_s": 7.8,
            "intensity_percent": 60
        },
    ]

    integrator = StatsBombIntegration()

    # Generar reportes para todos
    reports = []
    for player in team_data:
        report = integrator.generate_comparison_report(player)
        reports.append(report)

    # Mostrar ranking
    print("\nRANKING DEL EQUIPO (vs Premier League):")
    print("-"*70)

    # Ordenar por percentil
    sorted_reports = sorted(
        reports,
        key=lambda r: r['overall_percentile'],
        reverse=True
    )

    for rank, report in enumerate(sorted_reports, 1):
        percentile = report['overall_percentile']
        # Categorizar
        if percentile >= 85:
            category = "🏆 ÉLITE"
        elif percentile >= 70:
            category = "⭐ ARRIBA DEL PROMEDIO"
        elif percentile >= 50:
            category = "✓ PROMEDIO"
        else:
            category = "⚠️ POR DEBAJO"

        print(f"{rank}. {report['player_name']:15} | "
              f"Percentil: {percentile:5.1f} | {category}")

    # Estadísticas del equipo
    print("\n" + "-"*70)
    print("ESTADÍSTICAS DEL EQUIPO:")
    print("-"*70)

    percentiles = [r['overall_percentile'] for r in reports]
    print(f"Promedio:       {sum(percentiles) / len(percentiles):.1f}")
    print(f"Máximo:         {max(percentiles):.1f}")
    print(f"Mínimo:         {min(percentiles):.1f}")
    print(f"Total jugadores: {len(reports)}")


def example_export_json():
    """Ejemplo: Exportar resultados a JSON"""
    print("\n" + "="*70)
    print("EJEMPLO 3: Exportar a JSON")
    print("="*70)

    from pathlib import Path

    player_data = {
        "player_id": 10,
        "player_name": "Test Player",
        "position": "MID",
        "distance_m": 11800,
        "max_velocity_m_s": 10.2,
        "intensity_percent": 81
    }

    integrator = StatsBombIntegration()

    # Exportar a JSON
    output_path = Path("/tmp/statsbomb_example.json")
    integrator.export_comparison_json(player_data, output_path)

    print(f"\nArchivo exportado: {output_path}")

    # Leer y mostrar JSON
    with open(output_path, 'r') as f:
        data = json.load(f)

    print("\nContenido del JSON:")
    print(json.dumps(data, indent=2, default=str)[:500] + "...")


def example_validation():
    """Ejemplo: Validar datos de entrada"""
    print("\n" + "="*70)
    print("EJEMPLO 4: Validación de Datos")
    print("="*70)

    integrator = StatsBombIntegration()

    # Datos válidos
    valid_data = {
        "player_id": 1,
        "player_name": "Valid Player",
        "position": "MID",
        "distance_m": 11500,
        "max_velocity_m_s": 10.0,
        "intensity_percent": 80
    }

    is_valid, errors = integrator.validate_player_data(valid_data)
    print(f"\nDatos válidos: {is_valid}")
    if errors:
        print(f"Errores: {errors}")

    # Datos inválidos
    invalid_data = {
        "player_id": 1,
        "player_name": "Invalid Player",
        "position": "INVALID",  # Posición inválida
        "distance_m": -1000,  # Distancia negativa
        "max_velocity_m_s": 10.0,
        "intensity_percent": 150  # Más del 100%
    }

    is_valid, errors = integrator.validate_player_data(invalid_data)
    print(f"\nDatos inválidos: {is_valid}")
    if errors:
        print("Errores encontrados:")
        for error in errors:
            print(f"  - {error}")


def example_benchmarks():
    """Ejemplo: Ver benchmarks disponibles"""
    print("\n" + "="*70)
    print("EJEMPLO 5: Benchmarks Disponibles")
    print("="*70)

    integrator = StatsBombIntegration()

    print("\nBENHCMARKS DE DISTANCIA (metros):")
    print("-"*70)

    for position in ["GK", "DEF", "MID", "FWD"]:
        benchmark = integrator.get_benchmark(position, "distance")
        print(f"\n{position}:")
        print(f"  Rango:   {benchmark.min_value:,.0f} - {benchmark.max_value:,.0f} m")
        print(f"  Promedio: {benchmark.mean:,.0f} ± {benchmark.std:.0f} m")
        print(f"  P50:     {benchmark.percentile_50:,.0f} m")
        print(f"  P90:     {benchmark.percentile_90:,.0f} m")
        print(f"  Muestra: {benchmark.sample_size} jugadores")

    print("\n\nBENCHMARKS DE VELOCIDAD MÁXIMA (m/s):")
    print("-"*70)

    for position in ["GK", "DEF", "MID", "FWD"]:
        benchmark = integrator.get_benchmark(position, "velocity")
        print(f"\n{position}:")
        print(f"  Rango:    {benchmark.min_value:.1f} - {benchmark.max_value:.1f} m/s")
        print(f"  Promedio: {benchmark.mean:.1f} ± {benchmark.std:.1f} m/s")
        print(f"  P50:      {benchmark.percentile_50:.1f} m/s")
        print(f"  P90:      {benchmark.percentile_90:.1f} m/s")


def main():
    """Ejecuta todos los ejemplos"""
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  EJEMPLOS DE INTEGRACIÓN STATSBOMB - SCOUT AI".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)

    try:
        example_single_player()
        example_team_comparison()
        example_benchmarks()
        example_validation()
        example_export_json()

        print("\n" + "="*70)
        print("✓ Todos los ejemplos ejecutados exitosamente")
        print("="*70)
        print("\nPara más información, lee: STATSBOMB_INTEGRATION.md")

    except Exception as e:
        print(f"\n✗ Error durante ejecución: {e}")
        raise


if __name__ == "__main__":
    main()

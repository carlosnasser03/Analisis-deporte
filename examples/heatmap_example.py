"""
heatmap_example.py - Ejemplo de uso del generador de heatmaps

Demuestra cómo:
1. Generar heatmaps a partir de tracks de jugadores
2. Analizar movimiento por zonas
3. Exportar a PNG
4. Guardar análisis en JSON
"""

import numpy as np
from pathlib import Path
import sys

# Añadir ruta del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.heatmap_generator import (
    HeatmapGenerator,
    ZoneAnalyzer,
    PositionalHeatmap,
    HeatmapManager,
    HeatmapConfig,
)


def example_1_basic_heatmap_generation():
    """Ejemplo 1: Generar heatmap básico"""
    print("\n=== Ejemplo 1: Generación básica de heatmap ===\n")

    # Crear generador
    gen = HeatmapGenerator(canvas_size=(1280, 720))

    # Simular movimiento circular del jugador
    angles = np.linspace(0, 2*np.pi, 100)
    center_x, center_y = 640, 360
    radius = 200
    tracks = [
        (center_x + radius * np.cos(a), center_y + radius * np.sin(a))
        for a in angles
    ]

    # Generar heatmap en escala de grises
    heatmap_gray = gen.generate_heatmap(tracks, fps=30)
    print(f"✓ Heatmap generado: {heatmap_gray.shape}")
    print(f"  - Rango de valores: [{heatmap_gray.min():.3f}, {heatmap_gray.max():.3f}]")
    print(f"  - Tipo de dato: {heatmap_gray.dtype}")

    # Aplicar colormap 'hot' (rojo para actividad alta)
    heatmap_colored = gen.apply_colormap(heatmap_gray, colormap="hot")
    print(f"✓ Colormap aplicado: {heatmap_colored.shape}")

    return heatmap_colored, tracks


def example_2_zone_analysis():
    """Ejemplo 2: Análisis por zonas"""
    print("\n=== Ejemplo 2: Análisis de movimiento por zonas ===\n")

    # Crear analizador de zonas
    analyzer = ZoneAnalyzer(field_width=1280, field_height=720, fps=30)

    # Simular tracks con más actividad en centro-ataque
    np.random.seed(42)
    tracks = (
        [(300, 200)] * 30 +    # Centro-defensa
        [(640, 400)] * 100 +   # Centro-ataque (más tiempo)
        [(1100, 300)] * 20     # Lateral derecha
    )

    # Analizar zonas
    zone_stats = analyzer.analyze_zones(tracks)

    print("Distribución de tiempo por zona:")
    print("-" * 60)
    for stat in sorted(zone_stats, key=lambda s: s.percentage, reverse=True):
        bar = "█" * int(stat.percentage / 5)
        print(f"{stat.zone_name:25} {stat.percentage:6.2f}% {bar}")

    return zone_stats


def example_3_positional_grid():
    """Ejemplo 3: Heatmap con grid 10x10"""
    print("\n=== Ejemplo 3: Grid posicional 10x10 ===\n")

    # Crear generador de grid
    positional = PositionalHeatmap(field_width=1280, field_height=720, grid_size=10)

    # Simular movimiento
    np.random.seed(42)
    center_x, center_y = 640, 360
    tracks = [
        (center_x + np.random.normal(0, 100), center_y + np.random.normal(0, 80))
        for _ in range(200)
    ]

    # Generar grid
    grid, grid_image = positional.generate_grid_heatmap(tracks)

    print(f"✓ Grid generado: {grid.shape}")
    print(f"  - Celdas no vacías: {np.count_nonzero(grid)} / {grid.size}")

    # Obtener estadísticas de cobertura
    coverage = positional.get_coverage_percentage(grid)
    peak_row, peak_col, peak_val = positional.get_peak_cell(grid)

    print(f"  - Cobertura: {coverage:.1f}%")
    print(f"  - Celda pico: ({peak_col}, {peak_row}) con intensidad {peak_val:.3f}")

    return grid, grid_image


def example_4_complete_analysis():
    """Ejemplo 4: Análisis completo con HeatmapManager"""
    print("\n=== Ejemplo 4: Análisis completo ===\n")

    # Configuración
    config = HeatmapConfig(
        canvas_width=1280,
        canvas_height=720,
        gaussian_sigma=15.0,
        colormap="hot",
        export_png=False  # No exportar en ejemplo
    )

    # Crear gestor
    manager = HeatmapManager(config=config, output_dir="data/logs")

    # Simular tracks de delantero (movimiento intenso)
    np.random.seed(123)
    n_frames = 300
    x_positions = np.linspace(200, 1100, n_frames) + np.random.normal(0, 20, n_frames)
    y_positions = 360 + np.random.normal(0, 50, n_frames)
    tracks = list(zip(np.clip(x_positions, 0, 1280), np.clip(y_positions, 0, 720)))

    # Velocidades simuladas (m/s)
    speeds = [2.5 + np.random.normal(0, 0.5) for _ in range(len(tracks))]

    # Ejecutar análisis completo
    analysis = manager.generate_complete_analysis(
        tracks=tracks,
        player_id=7,
        fps=30,
        speeds=speeds
    )

    print(f"✓ Análisis generado para Jugador 7")
    print(f"  - Imagen: {analysis.heatmap_image.shape}")
    print(f"  - Cobertura: {analysis.coverage_percentage:.1f}%")
    print(f"  - Intensidad pico: {analysis.peak_intensity:.3f}")
    print(f"  - Zonas analizadas: {len(analysis.zone_stats)}")

    # Mostrar zonas más activas
    print("\nZonas más activas:")
    for stat in sorted(analysis.zone_stats, key=lambda s: s.percentage, reverse=True)[:3]:
        print(f"  - {stat.zone_name}: {stat.percentage:.1f}% ({stat.time_seconds:.2f}s)")

    # Guardar análisis
    json_path = manager.save_analysis_json(analysis, player_id=7)
    print(f"\n✓ Análisis guardado en: {json_path}")

    return analysis, json_path


def example_5_colormaps():
    """Ejemplo 5: Diferentes esquemas de color"""
    print("\n=== Ejemplo 5: Esquemas de color ===\n")

    gen = HeatmapGenerator()

    # Crear heatmap de prueba
    angles = np.linspace(0, 2*np.pi, 80)
    tracks = [(640 + 150 * np.cos(a), 360 + 150 * np.sin(a)) for a in angles]
    heatmap_gray = gen.generate_heatmap(tracks)

    # Aplicar diferentes colormaps
    colormaps = ["hot", "cold", "viridis", "grayscale"]
    print("Colormaps disponibles:")

    for colormap in colormaps:
        if colormap == "grayscale":
            colored = gen.apply_colormap(heatmap_gray, colormap="unknown")
        else:
            colored = gen.apply_colormap(heatmap_gray, colormap=colormap)

        # Verificar que el rango es válido
        print(f"  - {colormap:12} → Rango RGB: [{colored.min():.2f}, {colored.max():.2f}]")

    return heatmap_gray


def example_6_multiple_players():
    """Ejemplo 6: Análisis de múltiples jugadores"""
    print("\n=== Ejemplo 6: Análisis de múltiples jugadores ===\n")

    config = HeatmapConfig(export_png=False)
    manager = HeatmapManager(config=config, output_dir="data/logs")

    # Simular diferentes patrones de movimiento
    np.random.seed(456)
    player_profiles = {
        1: {
            "name": "Portero",
            "center": (200, 360),
            "radius": 50,
            "n_frames": 300
        },
        7: {
            "name": "Delantero",
            "center": (1050, 350),
            "radius": 300,
            "n_frames": 300
        },
        4: {
            "name": "Defensa Central",
            "center": (400, 360),
            "radius": 200,
            "n_frames": 300
        },
    }

    results = {}

    for player_id, profile in player_profiles.items():
        # Generar movimiento circular
        angles = np.linspace(0, 2*np.pi, profile["n_frames"])
        tracks = [
            (
                profile["center"][0] + profile["radius"] * np.cos(a),
                profile["center"][1] + profile["radius"] * np.sin(a)
            )
            for a in angles
        ]

        # Análisis
        analysis = manager.generate_complete_analysis(tracks, player_id)
        results[player_id] = analysis

        print(f"✓ Jugador {player_id} ({profile['name']:18}) " +
              f"- Cobertura: {analysis.coverage_percentage:5.1f}%")

    # Comparación
    print("\nComparación:")
    for player_id, analysis in results.items():
        profile_name = player_profiles[player_id]["name"]
        intensity = analysis.peak_intensity
        print(f"  - {profile_name:18} (ID {player_id}): " +
              f"Intensidad = {intensity:.3f}, Cobertura = {analysis.coverage_percentage:.1f}%")

    return results


def main():
    """Ejecutar todos los ejemplos"""
    print("╔" + "="*68 + "╗")
    print("║" + " EJEMPLOS DE USO: GENERADOR DE HEATMAPS ".center(68) + "║")
    print("╚" + "="*68 + "╝")

    # Ejecutar ejemplos
    example_1_basic_heatmap_generation()
    example_2_zone_analysis()
    example_3_positional_grid()
    example_4_complete_analysis()
    example_5_colormaps()
    example_6_multiple_players()

    print("\n" + "="*70)
    print("✓ Todos los ejemplos ejecutados exitosamente")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()

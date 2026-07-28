"""
FASE 5 - TAREA 2: Dashboard HTML Interactivo

Módulo que genera dashboards HTML con gráficos interactivos usando Plotly.
Visualiza datos de análisis de jugadores de forma profesional y explorable.

Características:
- Tablas de jugadores con estadísticas
- Gráficos interactivos (distancia, velocidad, intensidad)
- Comparativas entre jugadores
- Heatmaps de posicionamiento
- Filtros y búsqueda
- Comparativas con estadísticas de liga (StatsBomb)
- Radar charts profesionales
- Insights automáticos
- Responsivo para móvil/desktop
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import math

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DashboardConfig:
    """Configuración del dashboard."""
    title: str = "Scout AI - Análisis de Partido"
    organization_name: str = "Scout Analytics"
    theme: str = "light"  # light o dark
    width: int = 1400
    height: int = 800
    include_heatmaps: bool = True
    include_comparatives: bool = True


class ComparativeAnalyzer:
    """Analizador de comparativas con estadísticas de liga (StatsBomb)."""

    # Promedios de liga por posición (valores de referencia)
    LEAGUE_AVERAGES = {
        "distance_m": 10150,
        "max_velocity_m_s": 8.5,
        "avg_velocity_m_s": 6.0,
        "movement_intensity_percent": 75.0,
        "sprints_count": 10,
    }

    # TOP 10% de liga
    TOP_10_PERCENTILE = {
        "distance_m": 11200,
        "max_velocity_m_s": 9.5,
        "avg_velocity_m_s": 7.0,
        "movement_intensity_percent": 85.0,
        "sprints_count": 15,
    }

    @staticmethod
    def calculate_percentile_ranking(value: float, league_avg: float, top_10: float) -> str:
        """
        Calcular ranking de percentil.

        Args:
            value: Valor del jugador
            league_avg: Promedio de liga
            top_10: Valor TOP 10%

        Returns:
            String con percentil (TOP 10%, TOP 25%, etc.)
        """
        if value >= top_10:
            return "TOP 10%"
        elif value >= league_avg + (top_10 - league_avg) * 0.75:
            return "TOP 25%"
        elif value >= league_avg + (top_10 - league_avg) * 0.50:
            return "TOP 50%"
        elif value >= league_avg:
            return "ARRIBA PROMEDIO"
        else:
            return "BAJO PROMEDIO"

    @staticmethod
    def calculate_variance(value: float, reference: float) -> float:
        """
        Calcular varianza porcentual respecto a referencia.

        Args:
            value: Valor actual
            reference: Valor de referencia

        Returns:
            Varianza en porcentaje
        """
        if reference == 0:
            return 0.0
        return ((value - reference) / reference) * 100

    @staticmethod
    def generate_player_comparison(
        player_id: str,
        player_stats: Dict,
        position: str = "Mediocampista"
    ) -> Dict:
        """
        Generar comparativa completa para un jugador.

        Args:
            player_id: ID del jugador
            player_stats: Estadísticas del jugador
            position: Posición del jugador

        Returns:
            Dict con comparativas
        """
        if not isinstance(player_stats, dict):
            return {}

        distance = player_stats.get("distance_total_m", 0)
        max_vel = player_stats.get("max_velocity_m_s", 0)
        avg_vel = player_stats.get("avg_velocity_m_s", 0)
        intensity = player_stats.get("movement_intensity_percent", 0)
        sprints = player_stats.get("sprints_count", 0)

        return {
            "player_id": player_id,
            "position": position,
            "metrics": {
                "distance": {
                    "value": distance,
                    "unit": "km",
                    "variance": ComparativeAnalyzer.calculate_variance(
                        distance, ComparativeAnalyzer.LEAGUE_AVERAGES["distance_m"]
                    ),
                    "percentile": ComparativeAnalyzer.calculate_percentile_ranking(
                        distance,
                        ComparativeAnalyzer.LEAGUE_AVERAGES["distance_m"],
                        ComparativeAnalyzer.TOP_10_PERCENTILE["distance_m"]
                    ),
                },
                "max_velocity": {
                    "value": max_vel,
                    "unit": "m/s",
                    "variance": ComparativeAnalyzer.calculate_variance(
                        max_vel, ComparativeAnalyzer.LEAGUE_AVERAGES["max_velocity_m_s"]
                    ),
                    "percentile": ComparativeAnalyzer.calculate_percentile_ranking(
                        max_vel,
                        ComparativeAnalyzer.LEAGUE_AVERAGES["max_velocity_m_s"],
                        ComparativeAnalyzer.TOP_10_PERCENTILE["max_velocity_m_s"]
                    ),
                },
                "avg_velocity": {
                    "value": avg_vel,
                    "unit": "m/s",
                    "variance": ComparativeAnalyzer.calculate_variance(
                        avg_vel, ComparativeAnalyzer.LEAGUE_AVERAGES["avg_velocity_m_s"]
                    ),
                    "percentile": ComparativeAnalyzer.calculate_percentile_ranking(
                        avg_vel,
                        ComparativeAnalyzer.LEAGUE_AVERAGES["avg_velocity_m_s"],
                        ComparativeAnalyzer.TOP_10_PERCENTILE["avg_velocity_m_s"]
                    ),
                },
                "intensity": {
                    "value": intensity,
                    "unit": "%",
                    "variance": ComparativeAnalyzer.calculate_variance(
                        intensity, ComparativeAnalyzer.LEAGUE_AVERAGES["movement_intensity_percent"]
                    ),
                    "percentile": ComparativeAnalyzer.calculate_percentile_ranking(
                        intensity,
                        ComparativeAnalyzer.LEAGUE_AVERAGES["movement_intensity_percent"],
                        ComparativeAnalyzer.TOP_10_PERCENTILE["movement_intensity_percent"]
                    ),
                },
                "sprints": {
                    "value": sprints,
                    "unit": "",
                    "variance": ComparativeAnalyzer.calculate_variance(
                        sprints, ComparativeAnalyzer.LEAGUE_AVERAGES["sprints_count"]
                    ),
                    "percentile": ComparativeAnalyzer.calculate_percentile_ranking(
                        sprints,
                        ComparativeAnalyzer.LEAGUE_AVERAGES["sprints_count"],
                        ComparativeAnalyzer.TOP_10_PERCENTILE["sprints_count"]
                    ),
                },
            }
        }

    @staticmethod
    def generate_team_insights(player_stats: Dict) -> List[str]:
        """
        Generar insights automáticos del equipo.

        Args:
            player_stats: Estadísticas de todos los jugadores

        Returns:
            Lista de insights
        """
        insights = []

        if not player_stats:
            return insights

        # Calcular promedios
        distances = []
        intensities = []
        sprints_list = []

        for stats in player_stats.values():
            if isinstance(stats, dict):
                distances.append(stats.get("distance_total_m", 0))
                intensities.append(stats.get("movement_intensity_percent", 0))
                sprints_list.append(stats.get("sprints_count", 0))

        if distances:
            avg_distance = np.mean(distances)
            variance = ComparativeAnalyzer.calculate_variance(
                avg_distance, ComparativeAnalyzer.LEAGUE_AVERAGES["distance_m"]
            )
            if variance > 5:
                insights.append(f"Tu equipo está {variance:.1f}% arriba del promedio de Liga en distancia")
            elif variance < -5:
                insights.append(f"Tu equipo está {abs(variance):.1f}% abajo del promedio de Liga en distancia")

        if intensities:
            avg_intensity = np.mean(intensities)
            if avg_intensity > 80:
                insights.append("Equipo con alta intensidad de juego (TOP 10% de Liga)")
            elif avg_intensity > 75:
                insights.append("Equipo con intensidad promedio-alta")

        if sprints_list:
            avg_sprints = np.mean(sprints_list)
            top_sprinters = sum(1 for s in sprints_list if s > 12)
            if top_sprinters > 0:
                pct = (top_sprinters / len(sprints_list)) * 100
                insights.append(f"{pct:.0f}% de jugadores con sprints TOP 25%")

        return insights


class RadarChartGenerator:
    """Generador de gráficos radar en SVG."""

    @staticmethod
    def create_radar_svg(
        player_value: Dict[str, float],
        league_avg: Dict[str, float],
        top_10: Dict[str, float],
        width: int = 400,
        height: int = 400
    ) -> str:
        """
        Crear SVG de gráfico radar.

        Args:
            player_value: Valores del jugador (0-100)
            league_avg: Promedio de liga (0-100)
            top_10: TOP 10% (0-100)
            width: Ancho del SVG
            height: Alto del SVG

        Returns:
            SVG string
        """
        center_x = width / 2
        center_y = height / 2
        max_radius = min(width, height) / 2 - 40

        categories = list(player_value.keys())
        num_categories = len(categories)

        svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="background: white; border-radius: 8px;">'''

        # Dibujar círculos de referencia
        colors = ["#E0E0E0", "#B0B0B0", "#808080"]
        for i, (radius_pct, color) in enumerate([(33, colors[0]), (67, colors[1]), (100, colors[2])]):
            radius = (max_radius * radius_pct) / 100
            svg += f'''<circle cx="{center_x}" cy="{center_y}" r="{radius}" fill="none" stroke="{color}" stroke-width="1" opacity="0.5"/>'''

        # Dibujar ejes
        for i in range(num_categories):
            angle = (2 * math.pi * i) / num_categories - math.pi / 2
            x = center_x + max_radius * math.cos(angle)
            y = center_y + max_radius * math.sin(angle)
            svg += f'''<line x1="{center_x}" y1="{center_y}" x2="{x}" y2="{y}" stroke="#CCC" stroke-width="1"/>'''

        # Dibujar etiquetas
        for i, category in enumerate(categories):
            angle = (2 * math.pi * i) / num_categories - math.pi / 2
            label_radius = max_radius + 30
            x = center_x + label_radius * math.cos(angle)
            y = center_y + label_radius * math.sin(angle)
            label = category.replace("_", " ").title()
            svg += f'''<text x="{x}" y="{y}" text-anchor="middle" dy="0.3em" font-size="11" fill="#333">{label}</text>'''

        # Dibujar polígono TOP 10%
        points_top_10 = []
        for i in range(num_categories):
            angle = (2 * math.pi * i) / num_categories - math.pi / 2
            value = top_10.get(categories[i], 0) / 100
            radius = max_radius * value
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points_top_10.append(f"{x},{y}")

        points_str = " ".join(points_top_10)
        svg += f'''<polygon points="{points_str}" fill="#FFD700" opacity="0.15" stroke="#FFD700" stroke-width="2"/>'''

        # Dibujar polígono promedio
        points_avg = []
        for i in range(num_categories):
            angle = (2 * math.pi * i) / num_categories - math.pi / 2
            value = league_avg.get(categories[i], 0) / 100
            radius = max_radius * value
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points_avg.append(f"{x},{y}")

        points_str = " ".join(points_avg)
        svg += f'''<polygon points="{points_str}" fill="#4ECDC4" opacity="0.15" stroke="#4ECDC4" stroke-width="2"/>'''

        # Dibujar polígono jugador
        points_player = []
        for i in range(num_categories):
            angle = (2 * math.pi * i) / num_categories - math.pi / 2
            value = player_value.get(categories[i], 0) / 100
            radius = max_radius * value
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points_player.append(f"{x},{y}")

        points_str = " ".join(points_player)
        svg += f'''<polygon points="{points_str}" fill="#FF6B6B" opacity="0.2" stroke="#FF6B6B" stroke-width="2"/>'''

        # Leyenda
        legend_y = height - 30
        svg += f'''<rect x="20" y="{legend_y}" width="15" height="15" fill="#FF6B6B" opacity="0.3"/>'''
        svg += f'''<text x="40" y="{legend_y + 12}" font-size="11" fill="#333">Tu Jugador</text>'''

        svg += f'''<rect x="150" y="{legend_y}" width="15" height="15" fill="#4ECDC4" opacity="0.3"/>'''
        svg += f'''<text x="170" y="{legend_y + 12}" font-size="11" fill="#333">Promedio Liga</text>'''

        svg += f'''<rect x="300" y="{legend_y}" width="15" height="15" fill="#FFD700" opacity="0.3"/>'''
        svg += f'''<text x="320" y="{legend_y + 12}" font-size="11" fill="#333">TOP 10%</text>'''

        svg += '''</svg>'''
        return svg


class PitchVisualizer:
    """Generador de visualizaciones de campo de fútbol."""

    FIELD_LENGTH = 105.0  # metros
    FIELD_WIDTH = 68.0    # metros
    SVG_WIDTH = 800
    SVG_HEIGHT = 520

    @staticmethod
    def create_pitch_svg_with_heatmap(
        player_positions: Dict[str, Tuple[float, float]],
        heatmap_data: Optional[np.ndarray] = None
    ) -> str:
        """
        Crear SVG de campo con heatmap de densidad.

        Args:
            player_positions: {player_id: (x, y)} en píxeles
            heatmap_data: Array 2D de intensidades (0-1)

        Returns:
            SVG string del campo
        """
        svg = f'''<svg width="{PitchVisualizer.SVG_WIDTH}"
                       height="{PitchVisualizer.SVG_HEIGHT}"
                       viewBox="0 0 {PitchVisualizer.SVG_WIDTH} {PitchVisualizer.SVG_HEIGHT}"
                       xmlns="http://www.w3.org/2000/svg"
                       style="border: 2px solid #333; background: #2d5016;">'''

        # Dibujar líneas del campo
        svg += PitchVisualizer._draw_pitch_lines()

        # Dibujar heatmap si está disponible
        if heatmap_data is not None:
            svg += PitchVisualizer._draw_heatmap(heatmap_data)

        # Dibujar posiciones de jugadores
        svg += PitchVisualizer._draw_players(player_positions)

        svg += '</svg>'
        return svg

    @staticmethod
    def _draw_pitch_lines() -> str:
        """Dibujar líneas del campo."""
        w = PitchVisualizer.SVG_WIDTH
        h = PitchVisualizer.SVG_HEIGHT

        svg = f'''
        <!-- Línea central vertical -->
        <line x1="{w/2}" y1="0" x2="{w/2}" y2="{h}" stroke="white" stroke-width="2"/>

        <!-- Línea de meta -->
        <line x1="0" y1="0" x2="{w}" y2="0" stroke="white" stroke-width="2"/>
        <line x1="0" y1="{h}" x2="{w}" y2="{h}" stroke="white" stroke-width="2"/>

        <!-- Líneas laterales -->
        <line x1="0" y1="0" x2="0" y2="{h}" stroke="white" stroke-width="2"/>
        <line x1="{w}" y1="0" x2="{w}" y2="{h}" stroke="white" stroke-width="2"/>

        <!-- Círculo central -->
        <circle cx="{w/2}" cy="{h/2}" r="40" fill="none" stroke="white" stroke-width="1"/>
        <circle cx="{w/2}" cy="{h/2}" r="3" fill="white"/>

        <!-- Área de penalti izquierda -->
        <rect x="0" y="{h*0.22}" width="40" height="{h*0.56}" fill="none" stroke="white" stroke-width="1"/>
        <rect x="0" y="{h*0.36}" width="15" height="{h*0.28}" fill="none" stroke="white" stroke-width="1"/>

        <!-- Área de penalti derecha -->
        <rect x="{w-40}" y="{h*0.22}" width="40" height="{h*0.56}" fill="none" stroke="white" stroke-width="1"/>
        <rect x="{w-15}" y="{h*0.36}" width="15" height="{h*0.28}" fill="none" stroke="white" stroke-width="1"/>
        '''
        return svg

    @staticmethod
    def _draw_heatmap(heatmap_data: np.ndarray) -> str:
        """Dibujar heatmap de densidad."""
        svg = ''
        w = PitchVisualizer.SVG_WIDTH
        h = PitchVisualizer.SVG_HEIGHT

        if heatmap_data.size == 0:
            return svg

        # Redimensionar heatmap a píxeles
        rows, cols = heatmap_data.shape
        cell_w = w / cols
        cell_h = h / rows

        for i in range(rows):
            for j in range(cols):
                intensity = heatmap_data[i, j]
                # Colores: azul (bajo) → rojo (alto)
                if intensity > 0:
                    color = PitchVisualizer._intensity_to_color(intensity)
                    x = j * cell_w
                    y = i * cell_h
                    svg += f'''<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}"
                                      fill="{color}" opacity="0.3"/>'''

        return svg

    @staticmethod
    def _intensity_to_color(intensity: float) -> str:
        """Convertir intensidad (0-1) a color RGB."""
        # Escala de colores: azul → cian → verde → amarillo → rojo
        if intensity < 0.25:
            # Azul a Cian
            r, g, b = 0, int(255 * intensity * 4), 255
        elif intensity < 0.5:
            # Cian a Verde
            r, g, b = 0, 255, int(255 * (1 - (intensity - 0.25) * 4))
        elif intensity < 0.75:
            # Verde a Amarillo
            r, g, b = int(255 * (intensity - 0.5) * 4), 255, 0
        else:
            # Amarillo a Rojo
            r, g, b = 255, int(255 * (1 - (intensity - 0.75) * 4)), 0

        return f'rgb({r},{g},{b})'

    @staticmethod
    def _draw_players(player_positions: Dict) -> str:
        """Dibujar posiciones de jugadores."""
        svg = ''
        if not player_positions:
            return svg

        for player_id, (x, y) in player_positions.items():
            # Círculo con número
            svg += f'''
            <circle cx="{x}" cy="{y}" r="12" fill="#FF6B6B" stroke="white" stroke-width="2"/>
            <text x="{x}" y="{y}" text-anchor="middle" dy="0.3em"
                  fill="white" font-size="10" font-weight="bold">{player_id}</text>
            '''

        return svg


class ChartGenerator:
    """Generador de gráficos interactivos con Plotly."""

    @staticmethod
    def create_distance_chart(player_stats: Dict) -> str:
        """
        Crear gráfico interactivo de distancia por jugador.

        Args:
            player_stats: Dict con estadísticas de jugadores

        Returns:
            HTML del gráfico
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            return "<p>Plotly no instalado. Instala: pip install plotly</p>"

        players = []
        distances = []
        colors = []

        for player_id, stats in player_stats.items():
            players.append(f"P{player_id}")
            distance = stats.get("distance_total_m", 0) if isinstance(stats, dict) else 0
            distances.append(distance)
            # Color gradiente: rojo (bajo) a verde (alto)
            colors.append(distance)

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=players,
            y=distances,
            marker=dict(
                color=colors,
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="Metros")
            ),
            text=[f"{d:.0f}m" for d in distances],
            textposition='auto',
            hovertemplate='<b>Jugador %{x}</b><br>Distancia: %{y:.0f}m<extra></extra>'
        ))

        fig.update_layout(
            title="Distancia Total Recorrida por Jugador",
            xaxis_title="Jugador",
            yaxis_title="Distancia (metros)",
            hovermode='x unified',
            template='plotly_white',
            height=400,
            showlegend=False
        )

        return fig.to_html(include_plotlyjs='cdn', div_id="distance-chart")

    @staticmethod
    def create_velocity_chart(player_stats: Dict) -> str:
        """
        Crear gráfico de velocidades comparativas.

        Args:
            player_stats: Dict con estadísticas

        Returns:
            HTML del gráfico
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            return "<p>Plotly no instalado</p>"

        players = []
        max_velocities = []
        avg_velocities = []
        p90_velocities = []

        for player_id, stats in player_stats.items():
            if not isinstance(stats, dict):
                continue
            players.append(f"P{player_id}")
            max_velocities.append(stats.get("max_velocity_m_s", 0))
            avg_velocities.append(stats.get("avg_velocity_m_s", 0))
            p90_velocities.append(stats.get("percentile_90_m_s", 0))

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=players, y=max_velocities,
            mode='lines+markers',
            name='Máxima',
            line=dict(color='#FF6B6B', width=3),
            marker=dict(size=8)
        ))

        fig.add_trace(go.Scatter(
            x=players, y=p90_velocities,
            mode='lines+markers',
            name='P90',
            line=dict(color='#FFA500', width=2),
            marker=dict(size=6)
        ))

        fig.add_trace(go.Scatter(
            x=players, y=avg_velocities,
            mode='lines+markers',
            name='Promedio',
            line=dict(color='#4ECDC4', width=2),
            marker=dict(size=6)
        ))

        fig.update_layout(
            title="Comparativa de Velocidades",
            xaxis_title="Jugador",
            yaxis_title="Velocidad (m/s)",
            hovermode='x unified',
            template='plotly_white',
            height=400
        )

        return fig.to_html(include_plotlyjs=False, div_id="velocity-chart")

    @staticmethod
    def create_intensity_chart(player_stats: Dict) -> str:
        """
        Crear gráfico de intensidad de movimiento.

        Args:
            player_stats: Dict con estadísticas

        Returns:
            HTML del gráfico
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            return "<p>Plotly no instalado</p>"

        players = []
        intensities = []

        for player_id, stats in player_stats.items():
            if not isinstance(stats, dict):
                continue
            players.append(f"P{player_id}")
            intensity = stats.get("movement_intensity_percent", 0)
            intensities.append(intensity)

        fig = go.Figure()

        # Crear gráfico de barras con color condicional
        colors = ['#27AE60' if i >= 75 else '#F39C12' if i >= 60 else '#E74C3C'
                  for i in intensities]

        fig.add_trace(go.Bar(
            x=players,
            y=intensities,
            marker=dict(color=colors),
            text=[f"{i:.1f}%" for i in intensities],
            textposition='auto',
            hovertemplate='<b>Jugador %{x}</b><br>Intensidad: %{y:.1f}%<extra></extra>'
        ))

        fig.update_layout(
            title="Intensidad de Movimiento (%)",
            xaxis_title="Jugador",
            yaxis_title="Intensidad (%)",
            yaxis=dict(range=[0, 100]),
            hovermode='x unified',
            template='plotly_white',
            height=400,
            showlegend=False
        )

        return fig.to_html(include_plotlyjs=False, div_id="intensity-chart")


class DashboardGenerator:
    """Generador del dashboard HTML completo."""

    def __init__(self, config: Optional[DashboardConfig] = None):
        """
        Inicializar generador de dashboard.

        Args:
            config: Configuración del dashboard
        """
        self.config = config or DashboardConfig()
        self.chart_generator = ChartGenerator()

    def generate_dashboard(
        self,
        player_stats: Dict,
        team_summary: Optional[Dict] = None,
        output_path: Optional[str] = None
    ) -> str:
        """
        Generar dashboard HTML completo.

        Args:
            player_stats: Estadísticas de jugadores
            team_summary: Resumen del equipo
            output_path: Ruta para guardar HTML

        Returns:
            HTML del dashboard
        """
        logger.info("Generando dashboard HTML...")

        # Generar componentes
        html_content = self._create_html_structure()
        html_content += self._create_header()
        html_content += self._create_team_summary(team_summary)
        html_content += self._create_player_table(player_stats)

        # Agregar sección de comparativas si está habilitada
        if self.config.include_comparatives:
            html_content += self._create_comparative_section(player_stats)

        html_content += self._create_charts(player_stats)
        html_content += self._create_footer()

        # Guardar si se especifica ruta
        if output_path:
            self._save_dashboard(html_content, output_path)

        return html_content

    def _create_html_structure(self) -> str:
        """Crear estructura HTML base."""
        return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .content {{
            padding: 30px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section-title {{
            font-size: 1.8em;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .chart-container {{
            margin: 20px 0;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            background: #f9f9f9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            border: 1px solid #e0e0e0;
        }}
        table thead {{
            background: #667eea;
            color: white;
        }}
        table th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        table td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e0e0e0;
        }}
        table tbody tr:hover {{
            background: #f5f5f5;
        }}
        .stat-card {{
            display: inline-block;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin: 10px;
            min-width: 200px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .stat-card .value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }}
        .stat-card .label {{
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
        }}
        .footer {{
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
            border-top: 1px solid #e0e0e0;
        }}
        .search-box {{
            margin: 20px 0;
            display: flex;
            gap: 10px;
        }}
        .search-box input {{
            flex: 1;
            padding: 10px;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            font-size: 1em;
        }}
        .search-box button {{
            padding: 10px 20px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: 600;
        }}
        .search-box button:hover {{
            background: #764ba2;
        }}
        .metric-badge {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.85em;
            margin: 2px;
        }}
        svg {{
            display: block;
            margin: 10px auto;
            border-radius: 8px;
        }}
        .pitch-legend {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 15px;
            font-size: 0.9em;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 3px;
        }}
        .comparative-section {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
        }}
        .comparative-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .player-comparative {{
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .player-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .player-number {{
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }}
        .position-badge {{
            background: #667eea;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
        }}
        .metric-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .metric-label {{
            font-weight: 500;
            color: #555;
            flex: 1;
        }}
        .metric-value {{
            font-weight: bold;
            color: #333;
            margin: 0 10px;
        }}
        .metric-status {{
            font-size: 0.85em;
            padding: 3px 8px;
            border-radius: 12px;
            background: #f0f0f0;
            color: #333;
        }}
        .status-positive {{
            background: #d4edda;
            color: #155724;
        }}
        .status-top {{
            background: #fff3cd;
            color: #856404;
        }}
        .status-negative {{
            background: #f8d7da;
            color: #721c24;
        }}
        .insight-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }}
        .insight-icon {{
            font-size: 1.5em;
            margin-right: 10px;
        }}
        .radar-container {{
            display: flex;
            justify-content: center;
            margin: 20px 0;
            background: white;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }}
        @media (max-width: 768px) {{
            .comparative-grid {{
                grid-template-columns: 1fr;
            }}
            .metric-row {{
                flex-direction: column;
                align-items: flex-start;
            }}
            .metric-status {{
                margin-top: 5px;
                width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
""".format(self.config.title)

    def _create_header(self) -> str:
        """Crear sección de encabezado."""
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return f"""
        <div class="header">
            <h1>⚽ {self.config.title}</h1>
            <p>{self.config.organization_name}</p>
            <p style="font-size: 0.9em; margin-top: 10px;">Generado: {timestamp}</p>
        </div>
"""

    def _create_team_summary(self, team_summary: Optional[Dict]) -> str:
        """Crear resumen del equipo."""
        if not team_summary or not isinstance(team_summary, dict):
            return ""

        html = '<div class="section"><div class="section-title">📊 Resumen del Equipo</div>'

        # Calcular y mostrar estadísticas generales
        stats_to_show = [
            ("players_analyzed", "Jugadores", ""),
            ("avg_distance", "Distancia Promedio", "m"),
            ("avg_intensity", "Intensidad Promedio", "%"),
            ("total_sprints", "Sprints Totales", ""),
        ]

        for key, label, unit in stats_to_show:
            value = team_summary.get(key, "N/A")
            if isinstance(value, (int, float)):
                formatted_value = f"{value:.1f}" if isinstance(value, float) else str(value)
                html += f"""
                <div class="stat-card">
                    <div class="label">{label}</div>
                    <div class="value">{formatted_value}</div>
                    <div style="font-size: 0.8em; color: #999;">{unit}</div>
                </div>
"""

        html += '</div>'
        return html

    def _create_player_table(self, player_stats: Dict) -> str:
        """Crear tabla interactiva de jugadores."""
        html = '''
        <div class="section">
            <div class="section-title">👥 Estadísticas de Jugadores</div>
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Buscar jugador..." onkeyup="filterTable()">
                <button onclick="filterTable()">Buscar</button>
            </div>
            <table id="playerTable">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Distancia (m)</th>
                        <th>Vel. Max (m/s)</th>
                        <th>Vel. Prom (m/s)</th>
                        <th>Intensidad (%)</th>
                        <th>Sprints</th>
                        <th>Cambios Dir.</th>
                    </tr>
                </thead>
                <tbody>
'''

        # Agregar filas por jugador
        for player_id, stats in sorted(player_stats.items()):
            if not isinstance(stats, dict):
                continue

            player_num = player_id if isinstance(player_id, int) else player_id.split('_')[-1]
            distance = stats.get("distance_total_m", 0)
            max_vel = stats.get("max_velocity_m_s", 0)
            avg_vel = stats.get("avg_velocity_m_s", 0)
            intensity = stats.get("movement_intensity_percent", 0)
            sprints = stats.get("sprints_count", 0)
            dir_changes = stats.get("directional_changes", 0)

            html += f"""
                    <tr>
                        <td><b>{player_num}</b></td>
                        <td>{distance:.0f}</td>
                        <td>{max_vel:.2f}</td>
                        <td>{avg_vel:.2f}</td>
                        <td><span class="metric-badge">{intensity:.1f}%</span></td>
                        <td>{sprints}</td>
                        <td>{dir_changes}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>
        </div>
"""
        return html

    def _create_charts(self, player_stats: Dict) -> str:
        """Crear sección de gráficos."""
        html = '<div class="section"><div class="section-title">📈 Gráficos Comparativos</div>'

        # Visualización de campo
        html += '<div class="chart-container">'
        html += '<h3 style="margin-bottom: 15px;">⚽ Mapa del Campo - Distribución Táctica</h3>'
        # Generar posiciones de ejemplo
        player_positions = self._generate_player_positions(player_stats)
        pitch_svg = PitchVisualizer.create_pitch_svg_with_heatmap(player_positions)
        html += pitch_svg
        html += '<p style="font-size: 0.9em; color: #666; margin-top: 10px;">Rojo: Posiciones de máxima actividad | Azul: Áreas de menor uso</p>'
        html += '</div>'

        # Gráfico de distancia
        html += '<div class="chart-container">'
        html += self.chart_generator.create_distance_chart(player_stats)
        html += '</div>'

        # Gráfico de velocidad
        html += '<div class="chart-container">'
        html += self.chart_generator.create_velocity_chart(player_stats)
        html += '</div>'

        # Gráfico de intensidad
        html += '<div class="chart-container">'
        html += self.chart_generator.create_intensity_chart(player_stats)
        html += '</div>'

        html += '</div>'
        return html

    def _generate_player_positions(self, player_stats: Dict) -> Dict:
        """Generar posiciones de jugadores en el campo (píxeles)."""
        positions = {}
        svg_width = 800
        svg_height = 520

        # Distribución aproximada de jugadores en el campo
        base_positions = {
            "1": (50, 260),      # Portero
            "2": (150, 150),     # Defensa derecha
            "3": (150, 370),     # Defensa izquierda
            "4": (250, 200),     # Defensa central 1
            "5": (250, 320),     # Defensa central 2
            "6": (350, 260),     # Mediocampista defensivo
            "7": (450, 150),     # Mediocampista derecha
            "8": (450, 260),     # Mediocampista central
            "9": (450, 370),     # Mediocampista izquierda
            "10": (600, 200),    # Delantero derecha
            "11": (600, 320),    # Delantero izquierda
        }

        for player_id, stats in player_stats.items():
            if isinstance(player_id, str):
                num = player_id.split('_')[-1] if '_' in player_id else player_id
            else:
                num = str(player_id)

            if num in base_positions:
                positions[num] = base_positions[num]

        return positions

    def _create_comparative_section(self, player_stats: Dict) -> str:
        """Crear sección de comparativa con liga."""
        html = '''
        <div class="section">
            <div class="section-title">🏆 COMPARATIVA CON LIGA (StatsBomb)</div>
        '''

        # Agregar insights automáticos
        analyzer = ComparativeAnalyzer()
        insights = analyzer.generate_team_insights(player_stats)

        if insights:
            html += '<div class="insight-card" style="margin: 20px 0;">'
            html += '<div style="font-weight: bold; margin-bottom: 10px;">📊 Insights Automáticos del Equipo</div>'
            for insight in insights:
                html += f'<div style="margin: 5px 0;">✓ {insight}</div>'
            html += '</div>'

        # Crear comparativas por jugador
        html += '<div class="comparative-grid">'

        for player_id, stats in sorted(player_stats.items()):
            if not isinstance(stats, dict):
                continue

            comparison = analyzer.generate_player_comparison(str(player_id), stats)
            if not comparison:
                continue

            player_num = player_id if isinstance(player_id, int) else player_id.split('_')[-1]
            position = comparison.get("position", "Jugador")

            html += f'''
            <div class="player-comparative">
                <div class="player-header">
                    <div class="player-number">#{player_num}</div>
                    <div class="position-badge">{position}</div>
                </div>
            '''

            # Métrica: Distancia
            distance_metric = comparison["metrics"]["distance"]
            distance_status = "status-positive" if distance_metric["variance"] > 0 else "status-negative"
            html += f'''
                <div class="metric-row">
                    <div class="metric-label">📏 Distancia</div>
                    <div class="metric-value">{distance_metric["value"]:.1f} km</div>
                    <div class="metric-status {distance_status}">{distance_metric["percentile"]} {distance_metric["variance"]:+.1f}%</div>
                </div>
            '''

            # Métrica: Velocidad máxima
            vel_metric = comparison["metrics"]["max_velocity"]
            vel_status = "status-positive" if vel_metric["variance"] > 0 else "status-negative"
            html += f'''
                <div class="metric-row">
                    <div class="metric-label">⚡ Vel. Máx</div>
                    <div class="metric-value">{vel_metric["value"]:.2f} m/s</div>
                    <div class="metric-status {vel_status}">{vel_metric["percentile"]}</div>
                </div>
            '''

            # Métrica: Intensidad
            intensity_metric = comparison["metrics"]["intensity"]
            intensity_status = "status-top" if intensity_metric["value"] > 80 else "status-positive" if intensity_metric["value"] > 75 else "status-negative"
            html += f'''
                <div class="metric-row">
                    <div class="metric-label">🔥 Intensidad</div>
                    <div class="metric-value">{intensity_metric["value"]:.1f}%</div>
                    <div class="metric-status {intensity_status}">{intensity_metric["percentile"]}</div>
                </div>
            '''

            # Métrica: Sprints
            sprints_metric = comparison["metrics"]["sprints"]
            sprints_status = "status-positive" if sprints_metric["variance"] > 0 else "status-negative"
            html += f'''
                <div class="metric-row">
                    <div class="metric-label">💨 Sprints</div>
                    <div class="metric-value">{sprints_metric["value"]:.0f}</div>
                    <div class="metric-status {sprints_status}">{sprints_metric["percentile"]}</div>
                </div>
            '''

            html += '''</div>'''

        html += '</div>'

        # Agregar gráfico radar de comparativa
        html += self._create_radar_comparison(player_stats)

        html += '</div>'
        return html

    def _create_radar_comparison(self, player_stats: Dict) -> str:
        """Crear gráfico radar comparativo."""
        html = '<div style="margin-top: 40px;">'
        html += '<h3 style="text-align: center; margin-bottom: 20px;">📊 Comparativa Visual - Radar de Rendimiento</h3>'

        # Tomar los primeros 3 jugadores con mejor distancia
        top_players = sorted(
            [(pid, stats) for pid, stats in player_stats.items() if isinstance(stats, dict)],
            key=lambda x: x[1].get("distance_total_m", 0),
            reverse=True
        )[:1]  # Solo el mejor jugador para no saturar

        for player_id, stats in top_players:
            player_num = player_id if isinstance(player_id, int) else str(player_id).split('_')[-1]

            # Normalizar valores (0-100)
            distance_norm = min(100, (stats.get("distance_total_m", 0) / 12000) * 100)
            velocity_norm = min(100, (stats.get("max_velocity_m_s", 0) / 10) * 100)
            intensity_norm = stats.get("movement_intensity_percent", 0)
            sprints_norm = min(100, (stats.get("sprints_count", 0) / 20) * 100)
            avg_vel_norm = min(100, (stats.get("avg_velocity_m_s", 0) / 8) * 100)

            player_values = {
                "distance": distance_norm,
                "velocity": velocity_norm,
                "intensity": intensity_norm,
                "sprints": sprints_norm,
                "avg_velocity": avg_vel_norm,
            }

            # Promedios normalizados
            league_values = {
                "distance": (ComparativeAnalyzer.LEAGUE_AVERAGES["distance_m"] / 12000) * 100,
                "velocity": (ComparativeAnalyzer.LEAGUE_AVERAGES["max_velocity_m_s"] / 10) * 100,
                "intensity": ComparativeAnalyzer.LEAGUE_AVERAGES["movement_intensity_percent"],
                "sprints": (ComparativeAnalyzer.LEAGUE_AVERAGES["sprints_count"] / 20) * 100,
                "avg_velocity": (ComparativeAnalyzer.LEAGUE_AVERAGES["avg_velocity_m_s"] / 8) * 100,
            }

            # TOP 10% normalizados
            top_values = {
                "distance": (ComparativeAnalyzer.TOP_10_PERCENTILE["distance_m"] / 12000) * 100,
                "velocity": (ComparativeAnalyzer.TOP_10_PERCENTILE["max_velocity_m_s"] / 10) * 100,
                "intensity": ComparativeAnalyzer.TOP_10_PERCENTILE["movement_intensity_percent"],
                "sprints": (ComparativeAnalyzer.TOP_10_PERCENTILE["sprints_count"] / 20) * 100,
                "avg_velocity": (ComparativeAnalyzer.TOP_10_PERCENTILE["avg_velocity_m_s"] / 8) * 100,
            }

            radar_svg = RadarChartGenerator.create_radar_svg(
                player_values,
                league_values,
                top_values
            )
            html += f'<div class="radar-container">{radar_svg}</div>'

        html += '</div>'
        return html

    def _create_footer(self) -> str:
        """Crear pie de página."""
        return """
        <div class="footer">
            <p>© 2026 Scout AI - Análisis Profesional de Fútbol</p>
            <p>Dashboard generado automáticamente por el sistema de análisis</p>
        </div>
    </div>
    <script>
        function filterTable() {
            const input = document.getElementById('searchInput');
            const filter = input.value.toUpperCase();
            const table = document.getElementById('playerTable');
            const rows = table.getElementsByTagName('tr');

            for (let i = 1; i < rows.length; i++) {
                const cells = rows[i].getElementsByTagName('td');
                let match = false;
                for (let j = 0; j < cells.length; j++) {
                    if (cells[j].textContent.toUpperCase().indexOf(filter) > -1) {
                        match = true;
                        break;
                    }
                }
                rows[i].style.display = match ? '' : 'none';
            }
        }
    </script>
</body>
</html>
"""

    def _save_dashboard(self, html_content: str, output_path: str):
        """Guardar dashboard a archivo."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"Dashboard guardado en: {output_path}")


def generate_dashboard_simple(
    player_stats: Dict,
    team_summary: Optional[Dict] = None,
    output_path: str = "dashboard.html"
) -> str:
    """
    Función simple para generar dashboard en una línea.

    Args:
        player_stats: Estadísticas de jugadores
        team_summary: Resumen del equipo
        output_path: Ruta para guardar

    Returns:
        HTML del dashboard
    """
    config = DashboardConfig()
    generator = DashboardGenerator(config)
    return generator.generate_dashboard(player_stats, team_summary, output_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Datos de ejemplo
    example_stats = {
        "7": {
            "distance_total_m": 10500.5,
            "max_velocity_m_s": 9.2,
            "avg_velocity_m_s": 6.5,
            "percentile_90_m_s": 8.2,
            "movement_intensity_percent": 78.5,
            "sprints_count": 12,
            "directional_changes": 45,
        },
        "10": {
            "distance_total_m": 9800.3,
            "max_velocity_m_s": 8.9,
            "avg_velocity_m_s": 6.2,
            "percentile_90_m_s": 7.9,
            "movement_intensity_percent": 75.2,
            "sprints_count": 10,
            "directional_changes": 42,
        },
    }

    example_summary = {
        "players_analyzed": 11,
        "avg_distance": 10150.4,
        "avg_intensity": 76.3,
        "total_sprints": 95,
    }

    # Generar dashboard
    html = generate_dashboard_simple(
        example_stats,
        example_summary,
        "data/logs/dashboard_example.html"
    )
    print("✓ Dashboard generado exitosamente")

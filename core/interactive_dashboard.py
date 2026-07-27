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
- Responsivo para móvil/desktop
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

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

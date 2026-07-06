"""
report_generator.py - Generación de reportes profesionales y exportación de datos

Propósito: Crear reportes en múltiples formatos (PDF, HTML, JSON, CSV) con gráficos
interactivos y templates profesionales. Incluye dashboards HTML y PDFs individuales/de equipo.
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import numpy as np
from dataclasses import asdict

try:
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak,
        Table, TableStyle, Image, KeepTogether
    )
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


class ReportGenerator:
    """
    Generador de reportes profesionales en múltiples formatos.

    Soporta:
    - PDF individual de jugador
    - PDF de estadísticas del equipo
    - Dashboard HTML interactivo
    - Exportación JSON estructurada
    - Exportación CSV tabulada

    Ejemplo de uso:
        generator = ReportGenerator(output_dir='reports/')
        generator.generate_player_pdf(player_data, 'player_7.pdf')
        generator.generate_html_dashboard(video_data, 'dashboard.html')
    """

    # Estilos de colores para reportes
    COLORS = {
        'primary': '#1f77b4',
        'secondary': '#ff7f0e',
        'success': '#2ca02c',
        'danger': '#d62728',
        'warning': '#ff9800',
        'info': '#17a2b8',
        'light': '#f8f9fa',
        'dark': '#343a40'
    }

    # Umbrales de rendimiento
    PERFORMANCE_THRESHOLDS = {
        'distance_m_min': 8000,
        'distance_m_excellent': 12000,
        'intensity_min': 60,
        'intensity_excellent': 85,
        'velocity_m_s_min': 6.0,
        'velocity_m_s_excellent': 9.0
    }

    def __init__(
        self,
        output_dir: str = 'reports/',
        organization_name: str = 'Scout AI Analytics',
        template_theme: str = 'professional'
    ):
        """
        Inicializa el generador de reportes.

        Args:
            output_dir (str): Directorio de salida para reportes
            organization_name (str): Nombre de la organización en reportes
            template_theme (str): Tema del template ('professional', 'modern', 'minimal')
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        self.organization_name = organization_name
        self.template_theme = template_theme
        self.generation_timestamp = datetime.now()

        # Verifica dependencias
        if not HAS_REPORTLAB:
            print("Advertencia: ReportLab no instalado. PDFs no estarán disponibles.")
        if not HAS_PLOTLY:
            print("Advertencia: Plotly no instalado. Gráficos interactivos no estarán disponibles.")

    def generate_player_pdf(
        self,
        player_data: Dict[str, Any],
        output_filename: Optional[str] = None,
        include_heatmap: bool = True
    ) -> Path:
        """
        Genera PDF individual de estadísticas de jugador.

        Args:
            player_data (Dict): Datos del jugador con estructura:
                {
                    'player_id': int,
                    'name': str,
                    'position': str,
                    'number': int,
                    'total_distance_m': float,
                    'max_velocity_m_s': float,
                    'movement_intensity_percent': float,
                    'team_percentile': Dict,
                    'comparison_metrics': Dict,
                    'heatmap_positions': List
                }
            output_filename (str, optional): Nombre del archivo. Default: player_{id}.pdf
            include_heatmap (bool): Incluir mapa de calor en el PDF

        Returns:
            Path: Ruta del archivo PDF generado
        """
        if not HAS_REPORTLAB:
            raise ImportError("ReportLab required for PDF generation. Install: pip install reportlab")

        output_filename = output_filename or f"player_{player_data.get('player_id', 'unknown')}.pdf"
        output_path = self.output_dir / output_filename

        # Crear documento
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )

        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor(self.COLORS['primary']),
            spaceAfter=12,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor(self.COLORS['dark']),
            spaceAfter=6,
            spaceBefore=6
        )

        # Contenido del documento
        story = []

        # Encabezado
        story.append(Paragraph(f"{self.organization_name}", title_style))
        story.append(Spacer(1, 0.2*inch))

        # Información del jugador
        player_name = player_data.get('name', 'Player Unknown')
        player_number = player_data.get('number', '-')
        player_position = player_data.get('position', 'Unknown')

        info_text = f"<b>Jugador:</b> {player_name} | <b>Número:</b> {player_number} | <b>Posición:</b> {player_position}"
        story.append(Paragraph(info_text, styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

        # Sección de métricas principales
        story.append(Paragraph("Estadísticas Principales", heading_style))

        metrics_data = [
            ['Métrica', 'Valor', 'Equipo Promedio', 'Percentil'],
            [
                'Distancia Recorrida',
                f"{player_data.get('total_distance_m', 0):.1f} m",
                f"{player_data.get('comparison_metrics', {}).get('team_avg_distance_m', 0):.1f} m",
                f"{player_data.get('team_percentile', {}).get('distance', 0):.0f}%"
            ],
            [
                'Velocidad Máxima',
                f"{player_data.get('max_velocity_m_s', 0):.1f} m/s",
                f"{player_data.get('comparison_metrics', {}).get('team_avg_velocity_m_s', 0):.1f} m/s",
                f"{player_data.get('team_percentile', {}).get('velocity', 0):.0f}%"
            ],
            [
                'Intensidad Movimiento',
                f"{player_data.get('movement_intensity_percent', 0):.1f}%",
                f"{player_data.get('comparison_metrics', {}).get('team_avg_intensity_percent', 0):.1f}%",
                f"{player_data.get('team_percentile', {}).get('intensity', 0):.0f}%"
            ]
        ]

        metrics_table = Table(metrics_data, colWidths=[2*inch, 1.5*inch, 1.8*inch, 1.2*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.COLORS['primary'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(metrics_table)
        story.append(Spacer(1, 0.3*inch))

        # Sección de intensidad de movimiento
        story.append(Paragraph("Distribución de Velocidad", heading_style))

        speed_dist = player_data.get('speed_distribution', {})
        speed_data = [
            ['Categoría', 'Tiempo (%)'],
            ['Estático', f"{speed_dist.get('static', 0):.1f}%"],
            ['Caminando', f"{speed_dist.get('walking', 0):.1f}%"],
            ['Trotando', f"{speed_dist.get('jogging', 0):.1f}%"],
            ['Corriendo', f"{speed_dist.get('running', 0):.1f}%"],
            ['Aceleración', f"{speed_dist.get('sprinting', 0):.1f}%"]
        ]

        speed_table = Table(speed_data, colWidths=[2.5*inch, 1.5*inch])
        speed_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.COLORS['secondary'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.lightgrey, colors.white])
        ]))

        story.append(speed_table)
        story.append(Spacer(1, 0.3*inch))

        # Comparativa con equipo
        comparison = player_data.get('comparison_metrics', {})
        if comparison:
            story.append(Paragraph("Comparativa con Equipo", heading_style))

            comp_data = [
                ['Métrica', 'Diferencia vs Promedio'],
                [
                    'Distancia',
                    f"{comparison.get('distance_vs_avg_percent', 0):+.1f}%"
                ],
                [
                    'Velocidad',
                    f"{comparison.get('velocity_vs_avg_percent', 0):+.1f}%"
                ],
                [
                    'Intensidad',
                    f"{comparison.get('intensity_vs_avg_percent', 0):+.1f}%"
                ]
            ]

            comp_table = Table(comp_data, colWidths=[2.5*inch, 1.5*inch])
            comp_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.COLORS['success'])),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))

            story.append(comp_table)

        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            f"<i>Reporte generado: {self.generation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</i>",
            styles['Normal']
        ))

        # Construir PDF
        doc.build(story)

        return output_path

    def generate_team_pdf(
        self,
        team_data: List[Dict[str, Any]],
        output_filename: str = 'team_report.pdf'
    ) -> Path:
        """
        Genera PDF con estadísticas del equipo completo.

        Args:
            team_data (List[Dict]): Lista de datos de jugadores
            output_filename (str): Nombre del archivo PDF

        Returns:
            Path: Ruta del archivo generado
        """
        if not HAS_REPORTLAB:
            raise ImportError("ReportLab required for PDF generation.")

        output_path = self.output_dir / output_filename

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=0.5*inch,
            leftMargin=0.5*inch,
            topMargin=0.5*inch,
            bottomMargin=0.5*inch,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TeamTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor(self.COLORS['primary']),
            alignment=TA_CENTER,
            spaceAfter=12
        )
        heading_style = ParagraphStyle(
            'TeamHeading',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor(self.COLORS['dark']),
            spaceAfter=6
        )

        story = []

        # Título
        story.append(Paragraph(f"{self.organization_name} - Reporte de Equipo", title_style))
        story.append(Spacer(1, 0.2*inch))

        # Tabla con estadísticas de todos los jugadores
        story.append(Paragraph("Estadísticas Generales", heading_style))

        team_table_data = [
            ['Jugador', 'Distancia (m)', 'Vel. Máx (m/s)', 'Intensidad (%)', 'Posición']
        ]

        for player in sorted(team_data, key=lambda x: x.get('total_distance_m', 0), reverse=True):
            team_table_data.append([
                player.get('name', 'Unknown'),
                f"{player.get('total_distance_m', 0):.0f}",
                f"{player.get('max_velocity_m_s', 0):.1f}",
                f"{player.get('movement_intensity_percent', 0):.1f}",
                player.get('position', '-')
            ])

        team_table = Table(team_table_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        team_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(self.COLORS['primary'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.lightgrey, colors.white])
        ]))

        story.append(team_table)
        story.append(Spacer(1, 0.3*inch))

        # Resumen del equipo
        story.append(Paragraph("Resumen del Equipo", heading_style))

        distances = [p.get('total_distance_m', 0) for p in team_data]
        velocities = [p.get('max_velocity_m_s', 0) for p in team_data]
        intensities = [p.get('movement_intensity_percent', 0) for p in team_data]

        summary_text = f"""
        <b>Distancia promedio:</b> {np.mean(distances):.0f} m<br/>
        <b>Velocidad máxima promedio:</b> {np.mean(velocities):.1f} m/s<br/>
        <b>Intensidad promedio:</b> {np.mean(intensities):.1f}%<br/>
        <b>Distancia máxima:</b> {np.max(distances):.0f} m<br/>
        <b>Distancia mínima:</b> {np.min(distances):.0f} m
        """

        story.append(Paragraph(summary_text, styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(
            f"<i>Reporte generado: {self.generation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</i>",
            styles['Normal']
        ))

        doc.build(story)

        return output_path

    def generate_html_dashboard(
        self,
        video_data: Dict[str, Any],
        output_filename: str = 'dashboard.html'
    ) -> Path:
        """
        Genera dashboard HTML interactivo con gráficos Plotly.

        Args:
            video_data (Dict): Datos del video/equipo con estructura:
                {
                    'video_name': str,
                    'duration_s': float,
                    'fps': int,
                    'players': List[Dict],
                    'timestamp': str
                }
            output_filename (str): Nombre del archivo HTML

        Returns:
            Path: Ruta del archivo generado
        """
        if not HAS_PLOTLY:
            raise ImportError("Plotly required for dashboard. Install: pip install plotly")

        output_path = self.output_dir / output_filename

        # Prepara datos
        players = video_data.get('players', [])
        player_names = [p.get('name', f"Player {p.get('player_id')}") for p in players]

        distances = [p.get('total_distance_m', 0) for p in players]
        velocities = [p.get('max_velocity_m_s', 0) for p in players]
        intensities = [p.get('movement_intensity_percent', 0) for p in players]

        # Crea subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Distancia Recorrida',
                'Velocidad Máxima',
                'Intensidad de Movimiento',
                'Distribución de Velocidades'
            ),
            specs=[
                [{'type': 'bar'}, {'type': 'bar'}],
                [{'type': 'bar'}, {'type': 'scatter'}]
            ]
        )

        # Gráfico 1: Distancia
        fig.add_trace(
            go.Bar(
                x=player_names,
                y=distances,
                name='Distancia (m)',
                marker_color='#1f77b4',
                text=[f'{d:.0f}m' for d in distances],
                textposition='auto',
            ),
            row=1, col=1
        )

        # Gráfico 2: Velocidad
        fig.add_trace(
            go.Bar(
                x=player_names,
                y=velocities,
                name='Velocidad Máx (m/s)',
                marker_color='#ff7f0e',
                text=[f'{v:.1f}' for v in velocities],
                textposition='auto',
            ),
            row=1, col=2
        )

        # Gráfico 3: Intensidad
        fig.add_trace(
            go.Bar(
                x=player_names,
                y=intensities,
                name='Intensidad (%)',
                marker_color='#2ca02c',
                text=[f'{i:.1f}%' for i in intensities],
                textposition='auto',
            ),
            row=2, col=1
        )

        # Gráfico 4: Distribución
        if players and 'speed_distribution' in players[0]:
            speed_categories = ['static', 'walking', 'jogging', 'running', 'sprinting']
            for idx, player in enumerate(players[:5]):  # Top 5 jugadores
                dist = player.get('speed_distribution', {})
                values = [
                    dist.get('static', 0),
                    dist.get('walking', 0),
                    dist.get('jogging', 0),
                    dist.get('running', 0),
                    dist.get('sprinting', 0)
                ]
                fig.add_trace(
                    go.Scatter(
                        x=speed_categories,
                        y=values,
                        name=player.get('name', f"Player {player.get('player_id')}"),
                        mode='lines+markers'
                    ),
                    row=2, col=2
                )

        # Actualiza layout
        fig.update_layout(
            height=900,
            title_text=f"Dashboard - {video_data.get('video_name', 'Video')}",
            showlegend=True,
            hovermode='x unified'
        )

        fig.update_yaxes(title_text='Distancia (m)', row=1, col=1)
        fig.update_yaxes(title_text='Velocidad (m/s)', row=1, col=2)
        fig.update_yaxes(title_text='Intensidad (%)', row=2, col=1)
        fig.update_yaxes(title_text='Distribución (%)', row=2, col=2)

        # Guarda HTML
        fig.write_html(str(output_path))

        return output_path

    def export_json(
        self,
        data: Dict[str, Any],
        output_filename: Optional[str] = None,
        pretty: bool = True
    ) -> Path:
        """
        Exporta datos a JSON estructurado.

        Args:
            data (Dict): Datos a exportar
            output_filename (str, optional): Nombre del archivo
            pretty (bool): Formatear JSON con indentación

        Returns:
            Path: Ruta del archivo generado
        """
        output_filename = output_filename or 'data_export.json'
        output_path = self.output_dir / output_filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(
                data,
                f,
                indent=2 if pretty else None,
                ensure_ascii=False,
                default=str
            )

        return output_path

    def export_csv(
        self,
        data: List[Dict[str, Any]],
        output_filename: Optional[str] = None,
        fieldnames: Optional[List[str]] = None
    ) -> Path:
        """
        Exporta datos a CSV.

        Args:
            data (List[Dict]): Lista de registros
            output_filename (str, optional): Nombre del archivo
            fieldnames (List[str], optional): Columnas a incluir

        Returns:
            Path: Ruta del archivo generado
        """
        if not data:
            raise ValueError("Data cannot be empty")

        output_filename = output_filename or 'data_export.csv'
        output_path = self.output_dir / output_filename

        # Detecta campos si no se especifican
        if not fieldnames:
            fieldnames = list(data[0].keys())

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for row in data:
                # Convierte tipos complejos a strings
                clean_row = {}
                for field in fieldnames:
                    value = row.get(field, '')
                    if isinstance(value, (list, dict)):
                        clean_row[field] = json.dumps(value)
                    else:
                        clean_row[field] = value
                writer.writerow(clean_row)

        return output_path

    def export_player_stats_csv(
        self,
        players_data: List[Dict[str, Any]],
        output_filename: str = 'players_stats.csv'
    ) -> Path:
        """
        Exporta estadísticas de jugadores a CSV especializado.

        Args:
            players_data (List[Dict]): Datos de jugadores
            output_filename (str): Nombre del archivo

        Returns:
            Path: Ruta del archivo
        """
        output_path = self.output_dir / output_filename

        fieldnames = [
            'player_id', 'name', 'position', 'number',
            'total_distance_m', 'max_velocity_m_s', 'avg_velocity_m_s',
            'movement_intensity_percent', 'static_time_percent',
            'distance_percentile', 'velocity_percentile', 'intensity_percentile'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for player in players_data:
                row = {
                    'player_id': player.get('player_id'),
                    'name': player.get('name', ''),
                    'position': player.get('position', ''),
                    'number': player.get('number', ''),
                    'total_distance_m': player.get('total_distance_m', ''),
                    'max_velocity_m_s': player.get('max_velocity_m_s', ''),
                    'avg_velocity_m_s': player.get('avg_velocity_m_s', ''),
                    'movement_intensity_percent': player.get('movement_intensity_percent', ''),
                    'static_time_percent': player.get('static_time_percent', ''),
                    'distance_percentile': player.get('team_percentile', {}).get('distance', ''),
                    'velocity_percentile': player.get('team_percentile', {}).get('velocity', ''),
                    'intensity_percentile': player.get('team_percentile', {}).get('intensity', '')
                }
                writer.writerow(row)

        return output_path

    def create_summary_report(
        self,
        video_data: Dict[str, Any],
        output_filename: str = 'summary.json'
    ) -> Path:
        """
        Crea resumen ejecutivo en JSON.

        Args:
            video_data (Dict): Datos del análisis
            output_filename (str): Nombre del archivo

        Returns:
            Path: Ruta del archivo
        """
        summary = {
            'metadata': {
                'organization': self.organization_name,
                'timestamp': self.generation_timestamp.isoformat(),
                'video_name': video_data.get('video_name', 'unknown'),
                'duration_s': video_data.get('duration_s'),
                'fps': video_data.get('fps')
            },
            'team_summary': {},
            'top_performers': {},
            'insights': []
        }

        players = video_data.get('players', [])

        if players:
            # Estadísticas de equipo
            distances = [p.get('total_distance_m', 0) for p in players]
            velocities = [p.get('max_velocity_m_s', 0) for p in players]
            intensities = [p.get('movement_intensity_percent', 0) for p in players]

            summary['team_summary'] = {
                'avg_distance_m': round(np.mean(distances), 1),
                'avg_velocity_m_s': round(np.mean(velocities), 1),
                'avg_intensity_percent': round(np.mean(intensities), 1),
                'max_distance_m': round(np.max(distances), 1),
                'min_distance_m': round(np.min(distances), 1)
            }

            # Top 3 performers
            top_distance = sorted(players, key=lambda x: x.get('total_distance_m', 0), reverse=True)[:3]
            top_velocity = sorted(players, key=lambda x: x.get('max_velocity_m_s', 0), reverse=True)[:3]
            top_intensity = sorted(players, key=lambda x: x.get('movement_intensity_percent', 0), reverse=True)[:3]

            summary['top_performers'] = {
                'distance': [{'name': p.get('name'), 'value': p.get('total_distance_m')} for p in top_distance],
                'velocity': [{'name': p.get('name'), 'value': p.get('max_velocity_m_s')} for p in top_velocity],
                'intensity': [{'name': p.get('name'), 'value': p.get('movement_intensity_percent')} for p in top_intensity]
            }

            # Insights
            summary['insights'] = [
                f"Distancia promedio del equipo: {summary['team_summary']['avg_distance_m']:.0f}m",
                f"Intensidad promedio: {summary['team_summary']['avg_intensity_percent']:.1f}%",
                f"Mejor rendidor en distancia: {top_distance[0].get('name')} ({top_distance[0].get('total_distance_m'):.0f}m)"
            ]

        return self.export_json(summary, output_filename)

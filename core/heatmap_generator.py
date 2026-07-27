"""
heatmap_generator.py - Generador de heatmaps de movimiento de jugadores

Propósito: Crear visualizaciones de densidad de movimiento por jugador,
incluyendo análisis por zonas del campo y generación de imágenes con
gradientes de color normalizados.

Características:
- Kernel gaussiano para suavizado de posiciones
- Análisis de 6 zonas del campo (laterales, centrales, profundidad)
- Grid de 10x10 con normalización automática
- Múltiples esquemas de color (rojo, azul, viridis)
- Export a PNG
- Overlay opcional en campo real
- Anotaciones con percentiles
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from scipy.ndimage import gaussian_filter
from scipy import stats
import warnings

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


@dataclass
class HeatmapConfig:
    """Configuración para generación de heatmaps"""
    canvas_width: int = 1280
    canvas_height: int = 720
    gaussian_sigma: float = 15.0
    min_track_length: int = 5
    normalize: bool = True
    colormap: str = "hot"  # 'hot', 'cold', 'viridis'
    grid_size: int = 10
    export_png: bool = True
    overlay_field: bool = False


@dataclass
class ZoneStats:
    """Estadísticas de movimiento por zona"""
    zone_id: int
    zone_name: str
    frame_count: int
    time_seconds: float
    percentage: float
    avg_speed_ms: Optional[float] = None
    max_speed_ms: Optional[float] = None


@dataclass
class HeatmapData:
    """Contenedor de datos de heatmap generado"""
    heatmap_image: np.ndarray  # Imagen RGB normalizada
    zone_stats: List[ZoneStats]
    grid_histogram: np.ndarray  # Grid de 10x10
    peak_position: Tuple[int, int]
    peak_intensity: float
    coverage_percentage: float


class HeatmapGenerator:
    """
    Generador de heatmaps usando kernel gaussiano.

    Convierte posiciones de jugador por frame en una imagen de densidad
    suavizada, mostrando áreas de mayor actividad en rojo y menores en azul.

    Ejemplo:
        gen = HeatmapGenerator(canvas_size=(1280, 720))
        tracks = [(x1, y1), (x2, y2), ...]  # Posiciones por frame
        heatmap = gen.generate_heatmap(tracks)
    """

    def __init__(
        self,
        canvas_size: Tuple[int, int] = (1280, 720),
        gaussian_sigma: float = 15.0,
        min_track_length: int = 5,
        normalize: bool = True
    ):
        """
        Inicializa generador de heatmaps.

        Args:
            canvas_size: (ancho, alto) en píxeles
            gaussian_sigma: Desviación estándar del kernel gaussiano
            min_track_length: Mínimo de frames para incluir track
            normalize: Si True, normaliza intensidades [0, 1]
        """
        self.width, self.height = canvas_size
        self.gaussian_sigma = gaussian_sigma
        self.min_track_length = min_track_length
        self.normalize = normalize

    def generate_heatmap(
        self,
        tracks: List[Tuple[float, float]],
        fps: int = 30
    ) -> np.ndarray:
        """
        Genera heatmap a partir de posiciones de jugador.

        Args:
            tracks: Lista de (x, y) posiciones por frame
            fps: Fotogramas por segundo (para metadata)

        Returns:
            np.ndarray: Imagen normalizada (H, W) con valores [0, 1]

        Raises:
            ValueError: Si tracks está vacío o < min_track_length
        """
        if not tracks or len(tracks) < self.min_track_length:
            raise ValueError(
                f"Se requieren al menos {self.min_track_length} tracks, "
                f"se recibieron {len(tracks)}"
            )

        # Crear matriz de acumulación
        heatmap = np.zeros((self.height, self.width), dtype=np.float32)

        # Acumular Gaussianas en cada posición
        for x, y in tracks:
            x_int, y_int = int(x), int(y)

            # Validar límites
            if 0 <= x_int < self.width and 0 <= y_int < self.height:
                heatmap[y_int, x_int] += 1.0

        # Aplicar suavizado gaussiano
        heatmap = gaussian_filter(heatmap, sigma=self.gaussian_sigma)

        # Normalizar
        if self.normalize:
            max_val = heatmap.max()
            if max_val > 0:
                heatmap = heatmap / max_val
            heatmap = np.clip(heatmap, 0, 1)

        return heatmap

    def apply_colormap(
        self,
        heatmap: np.ndarray,
        colormap: str = "hot"
    ) -> np.ndarray:
        """
        Aplica esquema de color a heatmap en escala de grises.

        Args:
            heatmap: Matriz (H, W) con valores [0, 1]
            colormap: 'hot' (rojo), 'cold' (azul), 'viridis'

        Returns:
            np.ndarray: Imagen RGB (H, W, 3) con valores [0, 1]
        """
        h, w = heatmap.shape
        colored = np.zeros((h, w, 3), dtype=np.float32)

        if colormap == "hot":
            # Rojo: bajo=azul, alto=rojo
            colored[..., 0] = heatmap  # Canal rojo crece con intensidad
            colored[..., 1] = heatmap * 0.5  # Verde parcial
            colored[..., 2] = (1 - heatmap)  # Azul decrece

        elif colormap == "cold":
            # Azul: bajo=rojo, alto=azul
            colored[..., 0] = (1 - heatmap)  # Rojo decrece
            colored[..., 1] = heatmap * 0.5  # Verde parcial
            colored[..., 2] = heatmap  # Azul crece

        elif colormap == "viridis":
            # Aproximación simple de viridis
            for i in range(h):
                for j in range(w):
                    val = heatmap[i, j]
                    # Viridis: púrpura -> verde -> amarillo
                    if val < 0.33:
                        # Púrpura a verde
                        t = val / 0.33
                        colored[i, j] = [
                            0.27 * (1 - t) + 0.0 * t,
                            0.0 * (1 - t) + 0.67 * t,
                            0.33 * (1 - t) + 0.33 * t
                        ]
                    elif val < 0.67:
                        # Verde a amarillo
                        t = (val - 0.33) / 0.34
                        colored[i, j] = [
                            0.0 * (1 - t) + 1.0 * t,
                            0.67 * (1 - t) + 1.0 * t,
                            0.33 * (1 - t) + 0.0 * t
                        ]
                    else:
                        # Amarillo
                        colored[i, j] = [1.0, 1.0, 0.0]
        else:
            # Default: escala de grises
            colored[..., 0] = heatmap
            colored[..., 1] = heatmap
            colored[..., 2] = heatmap

        return np.clip(colored, 0, 1)


class ZoneAnalyzer:
    """
    Analizador de movimiento por zonas del campo.

    Divide el campo en 6 zonas para análisis granular:
    - 2 zonas laterales (izquierda/derecha)
    - 2 zonas centrales (medio-campo)
    - 2 zonas de profundidad (defensa/ataque)

    Ejemplo:
        analyzer = ZoneAnalyzer(field_width=1280, field_height=720)
        zones = analyzer.analyze_zones(tracks)
    """

    # Definición de zonas: (x_min, x_max, y_min, y_max, nombre)
    ZONE_TEMPLATE = [
        # Zonas laterales
        (0, 0.33, 0, 1, "Lateral Izquierda"),
        (0.67, 1, 0, 1, "Lateral Derecha"),
        # Zonas centrales
        (0.33, 0.67, 0, 0.5, "Centro Defensa"),
        (0.33, 0.67, 0.5, 1, "Centro Ataque"),
        # Zonas de profundidad
        (0.33, 0.67, 0, 0.33, "Profundidad Defensa"),
        (0.33, 0.67, 0.67, 1, "Profundidad Ataque"),
    ]

    def __init__(
        self,
        field_width: int = 1280,
        field_height: int = 720,
        fps: int = 30
    ):
        """
        Inicializa analizador de zonas.

        Args:
            field_width: Ancho del campo en píxeles
            field_height: Alto del campo en píxeles
            fps: Fotogramas por segundo
        """
        self.field_width = field_width
        self.field_height = field_height
        self.fps = fps
        self.frame_duration = 1.0 / fps

        # Convertir plantilla a píxeles
        self.zones = []
        for i, (x_min, x_max, y_min, y_max, name) in enumerate(
            self.ZONE_TEMPLATE
        ):
            zone = {
                'id': i,
                'name': name,
                'x_min': int(x_min * field_width),
                'x_max': int(x_max * field_width),
                'y_min': int(y_min * field_height),
                'y_max': int(y_max * field_height),
            }
            self.zones.append(zone)

    def analyze_zones(
        self,
        tracks: List[Tuple[float, float]],
        speeds: Optional[List[float]] = None
    ) -> List[ZoneStats]:
        """
        Analiza distribución de movimiento por zonas.

        Args:
            tracks: Lista de (x, y) posiciones
            speeds: Lista de velocidades (m/s) alineada con tracks

        Returns:
            List[ZoneStats]: Estadísticas por zona
        """
        zone_counts = {z['id']: 0 for z in self.zones}
        zone_speeds = {z['id']: [] for z in self.zones}

        # Contar frames por zona
        for frame_idx, (x, y) in enumerate(tracks):
            # Encontrar zona sin solapamiento: usar el primero que coincida
            found = False
            for zone in self.zones:
                if (zone['x_min'] <= x < zone['x_max'] and
                    zone['y_min'] <= y < zone['y_max']):
                    zone_counts[zone['id']] += 1
                    found = True

                    # Registrar velocidad si disponible
                    if speeds and frame_idx < len(speeds):
                        zone_speeds[zone['id']].append(speeds[frame_idx])
                    break

            # Si no encontró en límites < max, incluir en último si está en x_max o y_max
            if not found:
                for zone in self.zones:
                    if (zone['x_min'] <= x <= zone['x_max'] and
                        zone['y_min'] <= y <= zone['y_max']):
                        zone_counts[zone['id']] += 1
                        if speeds and frame_idx < len(speeds):
                            zone_speeds[zone['id']].append(speeds[frame_idx])
                        break

        # Generar estadísticas
        total_frames = len(tracks)
        stats_list = []

        for zone in self.zones:
            count = zone_counts[zone['id']]
            percentage = (count / total_frames * 100) if total_frames > 0 else 0
            time_seconds = count * self.frame_duration

            # Estadísticas de velocidad
            speeds_zone = zone_speeds[zone['id']]
            avg_speed = (
                float(np.mean(speeds_zone))
                if speeds_zone else None
            )
            max_speed = (
                float(np.max(speeds_zone))
                if speeds_zone else None
            )

            stats_list.append(ZoneStats(
                zone_id=zone['id'],
                zone_name=zone['name'],
                frame_count=count,
                time_seconds=float(time_seconds),
                percentage=float(percentage),
                avg_speed_ms=avg_speed,
                max_speed_ms=max_speed,
            ))

        return stats_list


class PositionalHeatmap:
    """
    Generador de heatmap con grid de 10x10.

    Divide el campo en una matriz de 10x10 celdas y cuenta frames
    en cada una. Genera imagen RGB con gradientes normalizados.

    Ejemplo:
        phm = PositionalHeatmap(field_width=1280, field_height=720)
        grid, image = phm.generate_grid_heatmap(tracks)
    """

    def __init__(
        self,
        field_width: int = 1280,
        field_height: int = 720,
        grid_size: int = 10
    ):
        """
        Inicializa generador de heatmap posicional.

        Args:
            field_width: Ancho del campo en píxeles
            field_height: Alto del campo en píxeles
            grid_size: Número de celdas por lado (default 10x10)
        """
        self.field_width = field_width
        self.field_height = field_height
        self.grid_size = grid_size
        self.cell_width = field_width / grid_size
        self.cell_height = field_height / grid_size

    def generate_grid_heatmap(
        self,
        tracks: List[Tuple[float, float]]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Genera heatmap en grid de 10x10.

        Args:
            tracks: Lista de (x, y) posiciones

        Returns:
            Tuple[np.ndarray, np.ndarray]:
                - grid: Matriz (10, 10) con conteos normalizados
                - image: Imagen RGB (H, W, 3) con gradiente
        """
        # Crear grid de conteos
        grid = np.zeros((self.grid_size, self.grid_size), dtype=np.float32)

        # Contar frames por celda
        for x, y in tracks:
            col = int(x / self.cell_width)
            row = int(y / self.cell_height)

            # Validar límites
            col = np.clip(col, 0, self.grid_size - 1)
            row = np.clip(row, 0, self.grid_size - 1)

            grid[row, col] += 1

        # Normalizar grid
        if grid.max() > 0:
            grid_normalized = grid / grid.max()
        else:
            grid_normalized = grid

        # Crear imagen con gradiente azul -> rojo
        image = self._grid_to_rgb(grid_normalized)

        return grid_normalized, image

    def _grid_to_rgb(self, grid: np.ndarray) -> np.ndarray:
        """
        Convierte grid normalizado a imagen RGB con gradiente.

        Args:
            grid: Matriz (10, 10) con valores [0, 1]

        Returns:
            np.ndarray: Imagen (H, W, 3) con gradiente azul-rojo
        """
        h, w = grid.shape
        image = np.zeros((h, w, 3), dtype=np.float32)

        # Gradiente: azul (bajo) -> rojo (alto)
        for i in range(h):
            for j in range(w):
                val = grid[i, j]
                # Interpolación: (0,0,1) -> (1,0,0)
                image[i, j, 0] = val  # Rojo crece
                image[i, j, 1] = 0    # Verde es 0
                image[i, j, 2] = 1 - val  # Azul decrece

        return image

    def get_coverage_percentage(self, grid: np.ndarray) -> float:
        """
        Calcula porcentaje de celdas con actividad.

        Args:
            grid: Matriz de conteos normalizados

        Returns:
            float: Porcentaje de celdas con valor > 0
        """
        non_zero = np.count_nonzero(grid)
        total = grid.size
        return (non_zero / total * 100) if total > 0 else 0

    def get_peak_cell(self, grid: np.ndarray) -> Tuple[int, int, float]:
        """
        Encuentra celda con máxima actividad.

        Args:
            grid: Matriz de conteos

        Returns:
            Tuple[int, int, float]: (fila, columna, valor)
        """
        max_idx = np.argmax(grid)
        row, col = np.unravel_index(max_idx, grid.shape)
        return int(row), int(col), float(grid[row, col])


class HeatmapExporter:
    """
    Exportador de heatmaps a diversos formatos.

    Soporta PNG, overlay en campo, anotaciones.
    """

    def __init__(self, output_dir: str = "data/logs"):
        """
        Inicializa exportador.

        Args:
            output_dir: Directorio de salida
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

    def export_png(
        self,
        image: np.ndarray,
        filename: str,
        colorspace: str = "RGB"
    ) -> Path:
        """
        Exporta heatmap a PNG.

        Args:
            image: Imagen normalizada [0, 1]
            filename: Nombre del archivo
            colorspace: 'RGB' o 'BGR'

        Returns:
            Path: Ruta del archivo generado
        """
        if not HAS_CV2:
            raise ImportError("opencv-python no está instalado")

        # Convertir a escala 0-255
        image_uint8 = (image * 255).astype(np.uint8)

        # Convertir colorspace si es necesario
        if colorspace == "BGR":
            image_uint8 = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2BGR)

        # Guardar
        output_path = self.output_dir / filename
        cv2.imwrite(str(output_path), image_uint8)

        return output_path

    def add_annotations(
        self,
        image: np.ndarray,
        zone_stats: List[ZoneStats],
        grid_info: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Añade anotaciones a heatmap (percentiles, zonas).

        Args:
            image: Imagen RGB [0, 1]
            zone_stats: Estadísticas por zona
            grid_info: Info de grid (peak, coverage, etc)

        Returns:
            np.ndarray: Imagen anotada
        """
        if not HAS_PIL:
            warnings.warn(
                "PIL no está instalado, no se pueden añadir anotaciones"
            )
            return image

        # Convertir a PIL
        h, w = image.shape[:2]
        image_uint8 = (image * 255).astype(np.uint8)
        pil_image = Image.fromarray(image_uint8, mode='RGB')
        draw = ImageDraw.Draw(pil_image)

        # Anotación simple: top-left con zonas
        y_offset = 10
        for stat in zone_stats[:3]:  # Solo primeras 3 para no saturar
            text = f"{stat.zone_name}: {stat.percentage:.1f}%"
            draw.text((10, y_offset), text, fill=(255, 255, 255))
            y_offset += 20

        # Convertir de vuelta a numpy
        return np.array(pil_image, dtype=np.float32) / 255.0


class HeatmapManager:
    """
    Gestor central de generación de heatmaps.

    Coordina generador, analizador de zonas, exportador.
    """

    def __init__(
        self,
        config: HeatmapConfig = None,
        output_dir: str = "data/logs"
    ):
        """
        Inicializa gestor de heatmaps.

        Args:
            config: Configuración (default: HeatmapConfig())
            output_dir: Directorio de salida
        """
        self.config = config or HeatmapConfig()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # Inicializar componentes
        self.generator = HeatmapGenerator(
            canvas_size=(self.config.canvas_width, self.config.canvas_height),
            gaussian_sigma=self.config.gaussian_sigma,
            normalize=self.config.normalize
        )
        self.zone_analyzer = ZoneAnalyzer(
            field_width=self.config.canvas_width,
            field_height=self.config.canvas_height
        )
        self.positional = PositionalHeatmap(
            field_width=self.config.canvas_width,
            field_height=self.config.canvas_height,
            grid_size=self.config.grid_size
        )
        self.exporter = HeatmapExporter(str(self.output_dir))

    def generate_complete_analysis(
        self,
        tracks: List[Tuple[float, float]],
        player_id: int,
        fps: int = 30,
        speeds: Optional[List[float]] = None
    ) -> HeatmapData:
        """
        Genera análisis completo de heatmap.

        Args:
            tracks: Posiciones (x, y) por frame
            player_id: ID del jugador
            fps: Fotogramas por segundo
            speeds: Velocidades (opcional)

        Returns:
            HeatmapData: Datos completos del heatmap
        """
        # Generar heatmap base
        heatmap_gray = self.generator.generate_heatmap(tracks, fps=fps)

        # Aplicar colormap
        heatmap_colored = self.generator.apply_colormap(
            heatmap_gray,
            colormap=self.config.colormap
        )

        # Analizar zonas
        zone_stats = self.zone_analyzer.analyze_zones(tracks, speeds)

        # Generar grid
        grid, grid_image = self.positional.generate_grid_heatmap(tracks)

        # Información de grid
        peak_row, peak_col, peak_val = self.positional.get_peak_cell(grid)
        coverage = self.positional.get_coverage_percentage(grid)

        # Exportar si está configurado
        if self.config.export_png:
            filename = f"heatmap_player_{player_id}.png"
            self.exporter.export_png(
                heatmap_colored,
                filename,
                colorspace="RGB"
            )

        return HeatmapData(
            heatmap_image=heatmap_colored,
            zone_stats=zone_stats,
            grid_histogram=grid,
            peak_position=(peak_col, peak_row),
            peak_intensity=float(peak_val),
            coverage_percentage=float(coverage)
        )

    def save_analysis_json(
        self,
        analysis: HeatmapData,
        player_id: int,
        filename: str = "heatmap_analysis.json"
    ) -> Path:
        """
        Guarda análisis en JSON.

        Args:
            analysis: Datos del análisis
            player_id: ID del jugador
            filename: Nombre del archivo

        Returns:
            Path: Ruta del archivo
        """
        data = {
            'player_id': player_id,
            'zones': [asdict(s) for s in analysis.zone_stats],
            'grid_histogram': analysis.grid_histogram.tolist(),
            'peak_position': analysis.peak_position,
            'peak_intensity': analysis.peak_intensity,
            'coverage_percentage': analysis.coverage_percentage,
        }

        output_path = self.output_dir / filename
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        return output_path

"""
Análisis de control espacial (diagrama de Voronoi) para Scout AI.

QUÉ APORTA (y qué NO)
---------------------
A diferencia del resto de mejoras del pipeline (tracking, detección de balón,
clasificación de equipos), este módulo **no mejora la precisión de detección ni
de seguimiento**. No toca el detector, no reduce falsos positivos y no cambia
ninguna métrica de exactitud.

Lo que aporta es una **métrica táctica nueva**: el diagrama de Voronoi divide el
campo en regiones donde cada jugador es el más cercano, es decir, el espacio que
ese jugador "controla" en ese instante. Agregando las regiones por equipo se
obtiene el porcentaje de campo dominado por cada equipo, y su evolución a lo
largo del partido muestra fases de presión alta y de repliegue.

Es una interpretación geométrica estándar en análisis de fútbol, pero es un
modelo simplificado: asume que el control depende únicamente de la distancia
euclídea al jugador (no considera velocidad, orientación, posición del balón ni
tiempo de llegada). No está validado contra datos etiquetados.

MÉTODO
------
Las métricas numéricas se calculan **rasterizando** el campo en una malla de
``grid_resolution x grid_resolution`` celdas y asignando cada celda al jugador
más cercano. Esto evita el problema de las regiones infinitas del diagrama de
Voronoi en los bordes y hace trivial el recorte al rectángulo del campo: el área
total siempre suma exactamente el área del campo.

``scipy.spatial.Voronoi`` se usa solo de forma opcional, para exponer la
geometría exacta de los polígonos a quien la necesite
(:meth:`VoronoiAnalyzer.compute_voronoi_geometry`). El módulo funciona
completamente sin scipy.

SISTEMA DE COORDENADAS
----------------------
Todas las posiciones están en **metros sobre el campo**, no en píxeles::

    x -> a lo largo del campo,  0 .. pitch_length_m  (105 m por defecto)
    y -> a lo ancho del campo,  0 .. pitch_width_m   (68 m por defecto)

Se asume que el equipo 0 ataca hacia +x (usado solo para etiquetar los tercios
defensivo / medio / ofensivo).
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape as _xml_escape

import numpy as np

try:  # dependencia opcional: solo para la geometría exacta de polígonos
    from scipy.spatial import Voronoi as _ScipyVoronoi
    _HAS_SCIPY = True
except ImportError:  # pragma: no cover - depende del entorno
    _ScipyVoronoi = None
    _HAS_SCIPY = False

logger = logging.getLogger(__name__)

# Equipo asignado a jugadores sin 'team_id' válido.
UNKNOWN_TEAM = -1


class VoronoiAnalyzer:
    """
    Calcula el control espacial del campo a partir de posiciones en metros.

    El cálculo numérico se hace por rasterización (malla regular de celdas),
    lo que garantiza que las áreas sumen siempre el área total del campo.

    Args:
        pitch_length_m: Largo del campo en metros (eje x).
        pitch_width_m: Ancho del campo en metros (eje y).
        grid_resolution: Número de celdas por eje. 100 -> 10.000 celdas.
        contested_tolerance_m: Margen en metros para considerar una celda
            "disputada". Una celda se marca como disputada si el jugador más
            cercano de otro equipo está a menos de ``dmin + tolerancia``.
            Por defecto 0.0, es decir, solo empates exactos (comportamiento
            estrictamente Voronoi: cada celda pertenece a un único equipo).
    """

    # Paleta alineada con PitchVisualizer de core/interactive_dashboard.py
    PITCH_COLOR = "#2d5016"
    LINE_COLOR = "#ffffff"
    CONTESTED_COLOR = "#cccccc"
    TEAM_COLORS: Dict[int, str] = {
        0: "#FF6B6B",   # rojo (mismo color de jugador que el dashboard)
        1: "#667eea",   # azul-violeta (color primario del dashboard)
        2: "#FFD93D",
        3: "#6BCB77",
    }
    UNKNOWN_TEAM_COLOR = "#999999"

    def __init__(
        self,
        pitch_length_m: float = 105.0,
        pitch_width_m: float = 68.0,
        grid_resolution: int = 100,
        contested_tolerance_m: float = 0.0,
    ) -> None:
        if not isinstance(grid_resolution, (int, np.integer)):
            raise TypeError("grid_resolution debe ser un entero")
        if grid_resolution < 2:
            raise ValueError("grid_resolution debe ser >= 2")
        if pitch_length_m <= 0 or pitch_width_m <= 0:
            raise ValueError("Las dimensiones del campo deben ser positivas")
        if contested_tolerance_m < 0:
            raise ValueError("contested_tolerance_m no puede ser negativo")

        self.pitch_length_m = float(pitch_length_m)
        self.pitch_width_m = float(pitch_width_m)
        self.grid_resolution = int(grid_resolution)
        self.contested_tolerance_m = float(contested_tolerance_m)

        self.pitch_area_m2 = self.pitch_length_m * self.pitch_width_m
        self.cell_area_m2 = self.pitch_area_m2 / (self.grid_resolution ** 2)

        # Centros de celda (precalculados una sola vez).
        step_x = self.pitch_length_m / self.grid_resolution
        step_y = self.pitch_width_m / self.grid_resolution
        self._cell_x = (np.arange(self.grid_resolution, dtype=np.float64) + 0.5) * step_x
        self._cell_y = (np.arange(self.grid_resolution, dtype=np.float64) + 0.5) * step_y

        # Estadísticas acumuladas
        self._total_computations = 0
        self._total_players_processed = 0
        self._invalid_players_skipped = 0
        self._out_of_bounds_players = 0
        self._last_control: Optional[Dict[str, Any]] = None

        logger.debug(
            "VoronoiAnalyzer inicializado: campo %.1fx%.1f m, malla %dx%d "
            "(%.3f m2/celda), scipy=%s",
            self.pitch_length_m, self.pitch_width_m,
            self.grid_resolution, self.grid_resolution,
            self.cell_area_m2, _HAS_SCIPY,
        )

    # ------------------------------------------------------------------
    # Normalización de entrada
    # ------------------------------------------------------------------
    def _normalize_players(
        self, players: Optional[Sequence[Dict]]
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Validar y normalizar la lista de jugadores.

        Args:
            players: Lista de dicts con 'player_id', 'position' [x_m, y_m] y
                'team_id'.

        Returns:
            (jugadores_normalizados, avisos). Cada jugador normalizado es
            ``{'player_id', 'key', 'x', 'y', 'team_id', 'out_of_bounds'}``.
            ``key`` es único dentro del resultado (los ids duplicados se
            desambiguan) y es la clave usada en los dicts por jugador.
        """
        normalized: List[Dict[str, Any]] = []
        warnings: List[str] = []

        if players is None:
            return normalized, warnings
        if not isinstance(players, (list, tuple)):
            raise TypeError("players debe ser una lista de diccionarios")

        used_keys: set = set()

        for idx, raw in enumerate(players):
            if not isinstance(raw, dict):
                warnings.append(f"indice {idx}: no es un dict, ignorado")
                self._invalid_players_skipped += 1
                continue

            position = raw.get("position")
            try:
                too_short = position is None or len(position) < 2
            except TypeError:
                too_short = True
            if too_short:
                warnings.append(f"indice {idx}: 'position' ausente o incompleta, ignorado")
                self._invalid_players_skipped += 1
                continue

            try:
                x = float(position[0])
                y = float(position[1])
            except (TypeError, ValueError):
                warnings.append(f"indice {idx}: 'position' no numérica, ignorado")
                self._invalid_players_skipped += 1
                continue

            if not (math.isfinite(x) and math.isfinite(y)):
                warnings.append(f"indice {idx}: 'position' con NaN/Inf, ignorado")
                self._invalid_players_skipped += 1
                continue

            team_raw = raw.get("team_id", UNKNOWN_TEAM)
            try:
                team_id = int(team_raw)
            except (TypeError, ValueError):
                team_id = UNKNOWN_TEAM
                warnings.append(f"indice {idx}: 'team_id' inválido, asignado a desconocido")

            player_id = raw.get("player_id", idx)
            key = str(player_id)
            if key in used_keys:
                key = f"{key}__{idx}"
                warnings.append(f"indice {idx}: player_id duplicado, renombrado a '{key}'")
            used_keys.add(key)

            out_of_bounds = not (
                0.0 <= x <= self.pitch_length_m and 0.0 <= y <= self.pitch_width_m
            )
            if out_of_bounds:
                self._out_of_bounds_players += 1
                warnings.append(
                    f"jugador '{key}': posición ({x:.1f}, {y:.1f}) fuera del campo; "
                    "se conserva para el cálculo de distancias, su región se recorta al campo"
                )

            normalized.append({
                "player_id": player_id,
                "key": key,
                "x": x,
                "y": y,
                "team_id": team_id,
                "out_of_bounds": out_of_bounds,
            })

        return normalized, warnings

    def _empty_control(self, warnings: List[str]) -> Dict[str, Any]:
        """Resultado neutro cuando no hay jugadores válidos."""
        empty_int = np.full(
            (self.grid_resolution, self.grid_resolution), -1, dtype=np.int32
        )
        return {
            "valid": False,
            "n_players": 0,
            "grid_resolution": self.grid_resolution,
            "cell_area_m2": self.cell_area_m2,
            "pitch_area_m2": self.pitch_area_m2,
            "pitch_length_m": self.pitch_length_m,
            "pitch_width_m": self.pitch_width_m,
            "owner_grid": empty_int,
            "team_grid": empty_int.copy(),
            "contested_mask": np.zeros(
                (self.grid_resolution, self.grid_resolution), dtype=bool
            ),
            "player_keys": [],
            "player_teams": [],
            "player_positions": [],
            "per_player_cells": {},
            "per_player_area_m2": {},
            "per_player_percent": {},
            "contested_cells": 0,
            "contested_percent": 0.0,
            "teams_present": [],
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def compute_control(self, players: List[Dict]) -> Dict:
        """
        Calcular el control espacial celda a celda.

        Rasteriza el campo y asigna cada celda al jugador más cercano
        (distancia euclídea en metros). Los jugadores fuera de los límites del
        campo se conservan en el cálculo de distancias; su región simplemente
        queda recortada al rectángulo del campo.

        Args:
            players: ``[{'player_id': Any, 'position': [x_m, y_m],
                        'team_id': int}, ...]``

        Returns:
            Dict con, entre otras claves:
                - ``valid``: False si no hay jugadores válidos.
                - ``owner_grid``: array (res, res) int con el índice del jugador
                  dueño de cada celda (-1 si disputada o sin dueño).
                - ``team_grid``: array (res, res) int con el equipo dueño
                  (-1 si disputada / equipo desconocido, ver ``contested_mask``).
                - ``contested_mask``: array (res, res) bool.
                - ``per_player_area_m2`` / ``per_player_percent`` /
                  ``per_player_cells``: dicts indexados por ``player_id``.
                - ``warnings``: lista de avisos de validación.

            Los arrays se indexan ``[fila_y, columna_x]``.
        """
        normalized, warnings = self._normalize_players(players)
        self._total_computations += 1

        if not normalized:
            result = self._empty_control(warnings)
            self._last_control = result
            return result

        self._total_players_processed += len(normalized)

        px = np.array([p["x"] for p in normalized], dtype=np.float64)
        py = np.array([p["y"] for p in normalized], dtype=np.float64)
        teams = np.array([p["team_id"] for p in normalized], dtype=np.int64)

        # Distancias al cuadrado: (n_players, res_y, res_x)
        dx = self._cell_x[np.newaxis, np.newaxis, :] - px[:, np.newaxis, np.newaxis]
        dy = self._cell_y[np.newaxis, :, np.newaxis] - py[:, np.newaxis, np.newaxis]
        dist2 = dx * dx + dy * dy

        owner_grid = np.argmin(dist2, axis=0).astype(np.int32)
        min_dist = np.sqrt(np.min(dist2, axis=0))
        team_grid = teams[owner_grid].astype(np.int32)

        # Celdas disputadas: un jugador de OTRO equipo está dentro de la
        # tolerancia respecto al más cercano.
        contested_mask = np.zeros(team_grid.shape, dtype=bool)
        unique_teams = np.unique(teams)
        if unique_teams.size > 1:
            dist = np.sqrt(dist2)
            threshold = min_dist + self.contested_tolerance_m
            for team in unique_teams:
                members = teams == team
                team_min = np.min(dist[members], axis=0)
                rival_cells = team_grid != team
                contested_mask |= rival_cells & (team_min <= threshold)

        owner_grid[contested_mask] = -1
        team_grid[contested_mask] = -1

        # Conteo por jugador
        per_player_cells: Dict[Any, int] = {}
        per_player_area: Dict[Any, float] = {}
        per_player_percent: Dict[Any, float] = {}
        total_cells = float(self.grid_resolution ** 2)

        counts = np.bincount(
            owner_grid[owner_grid >= 0].ravel(), minlength=len(normalized)
        )
        for idx, player in enumerate(normalized):
            n_cells = int(counts[idx]) if idx < counts.size else 0
            per_player_cells[player["key"]] = n_cells
            per_player_area[player["key"]] = n_cells * self.cell_area_m2
            per_player_percent[player["key"]] = 100.0 * n_cells / total_cells

        contested_cells = int(np.count_nonzero(contested_mask))

        result: Dict[str, Any] = {
            "valid": True,
            "n_players": len(normalized),
            "grid_resolution": self.grid_resolution,
            "cell_area_m2": self.cell_area_m2,
            "pitch_area_m2": self.pitch_area_m2,
            "pitch_length_m": self.pitch_length_m,
            "pitch_width_m": self.pitch_width_m,
            "owner_grid": owner_grid,
            "team_grid": team_grid,
            "contested_mask": contested_mask,
            "player_keys": [p["key"] for p in normalized],
            "player_teams": [p["team_id"] for p in normalized],
            "player_positions": [(p["x"], p["y"]) for p in normalized],
            "per_player_cells": per_player_cells,
            "per_player_area_m2": per_player_area,
            "per_player_percent": per_player_percent,
            "contested_cells": contested_cells,
            "contested_percent": 100.0 * contested_cells / total_cells,
            "teams_present": sorted(int(t) for t in unique_teams),
            "warnings": warnings,
        }
        self._last_control = result
        return result

    def compute_team_dominance(self, players: List[Dict]) -> Dict:
        """
        Agregar el control por equipo.

        Args:
            players: Lista de jugadores (ver :meth:`compute_control`).

        Returns:
            ``{'team_0_percent', 'team_1_percent', 'contested_percent',
            'per_player_area_m2', ...}``. Los porcentajes de equipo 0, equipo 1,
            'other' (otros equipos o equipo desconocido) y 'contested' suman
            100.0 cuando hay al menos un jugador válido, y 0.0 cuando la lista
            está vacía.
        """
        control = self.compute_control(players)

        base = {
            "valid": control["valid"],
            "team_0_percent": 0.0,
            "team_1_percent": 0.0,
            "contested_percent": 0.0,
            "other_percent": 0.0,
            "team_0_area_m2": 0.0,
            "team_1_area_m2": 0.0,
            "contested_area_m2": 0.0,
            "other_area_m2": 0.0,
            "per_player_area_m2": control["per_player_area_m2"],
            "per_player_percent": control["per_player_percent"],
            "n_players": control["n_players"],
            "pitch_area_m2": self.pitch_area_m2,
            "warnings": control["warnings"],
        }

        if not control["valid"]:
            return base

        team_grid = control["team_grid"]
        contested_mask = control["contested_mask"]
        total_cells = float(self.grid_resolution ** 2)

        cells_0 = int(np.count_nonzero(team_grid == 0))
        cells_1 = int(np.count_nonzero(team_grid == 1))
        cells_contested = int(np.count_nonzero(contested_mask))
        cells_other = int(total_cells) - cells_0 - cells_1 - cells_contested

        base["team_0_percent"] = 100.0 * cells_0 / total_cells
        base["team_1_percent"] = 100.0 * cells_1 / total_cells
        base["contested_percent"] = 100.0 * cells_contested / total_cells
        base["other_percent"] = 100.0 * cells_other / total_cells
        base["team_0_area_m2"] = cells_0 * self.cell_area_m2
        base["team_1_area_m2"] = cells_1 * self.cell_area_m2
        base["contested_area_m2"] = cells_contested * self.cell_area_m2
        base["other_area_m2"] = cells_other * self.cell_area_m2
        return base

    def compute_zone_control(self, players: List[Dict]) -> Dict:
        """
        Control por tercios del campo (defensivo / medio / ofensivo).

        Los tercios se definen sobre el eje x y se etiquetan **desde la
        perspectiva del equipo 0**, que se asume ataca hacia +x:

            - ``defensive``: x en [0, L/3)
            - ``middle``:    x en [L/3, 2L/3)
            - ``attacking``: x en [2L/3, L]

        Para el equipo 1 los papeles están invertidos (su tercio defensivo es el
        etiquetado aquí como ``attacking``).

        Args:
            players: Lista de jugadores (ver :meth:`compute_control`).

        Returns:
            ``{'valid', 'reference_team', 'attacking_direction', 'zones': {...}}``
            donde cada zona contiene ``team_0_percent``, ``team_1_percent``,
            ``contested_percent``, ``other_percent`` (suman 100 dentro de la
            zona), ``x_range_m``, ``zone_area_m2`` y ``n_cells``.
        """
        control = self.compute_control(players)

        third = self.pitch_length_m / 3.0
        bounds = [
            ("defensive", 0.0, third),
            ("middle", third, 2.0 * third),
            ("attacking", 2.0 * third, self.pitch_length_m),
        ]

        zones: Dict[str, Dict[str, Any]] = {}
        team_grid = control["team_grid"]
        contested_mask = control["contested_mask"]

        for name, x_min, x_max in bounds:
            if name == "attacking":
                cols = self._cell_x >= x_min
            else:
                cols = (self._cell_x >= x_min) & (self._cell_x < x_max)
            n_cells = int(np.count_nonzero(cols)) * self.grid_resolution

            zone: Dict[str, Any] = {
                "x_range_m": (round(x_min, 3), round(x_max, 3)),
                "n_cells": n_cells,
                "zone_area_m2": n_cells * self.cell_area_m2,
                "team_0_percent": 0.0,
                "team_1_percent": 0.0,
                "contested_percent": 0.0,
                "other_percent": 0.0,
            }

            if control["valid"] and n_cells > 0:
                sub_team = team_grid[:, cols]
                sub_contested = contested_mask[:, cols]
                total = float(n_cells)
                c0 = int(np.count_nonzero(sub_team == 0))
                c1 = int(np.count_nonzero(sub_team == 1))
                cc = int(np.count_nonzero(sub_contested))
                co = n_cells - c0 - c1 - cc
                zone["team_0_percent"] = 100.0 * c0 / total
                zone["team_1_percent"] = 100.0 * c1 / total
                zone["contested_percent"] = 100.0 * cc / total
                zone["other_percent"] = 100.0 * co / total

            zones[name] = zone

        return {
            "valid": control["valid"],
            "reference_team": 0,
            "attacking_direction": "+x",
            "zones": zones,
            "n_players": control["n_players"],
            "warnings": control["warnings"],
        }

    def compute_voronoi_geometry(self, players: List[Dict]) -> Optional[Dict]:
        """
        Geometría exacta del diagrama de Voronoi vía scipy (opcional).

        Solo para consumidores que necesiten los vértices reales de los
        polígonos. **No se usa para las métricas numéricas**, que se calculan
        siempre por rasterización. Las regiones infinitas de los bordes NO se
        recortan aquí; el consumidor debe recortarlas al campo.

        Args:
            players: Lista de jugadores (ver :meth:`compute_control`).

        Returns:
            Dict con ``points``, ``vertices``, ``regions``, ``point_region`` y
            ``player_keys``; o ``None`` si scipy no está instalado, si hay menos
            de 4 jugadores válidos, o si Qhull falla (p. ej. puntos colineales).
        """
        if not _HAS_SCIPY:
            logger.info("scipy no disponible: compute_voronoi_geometry devuelve None")
            return None

        normalized, _ = self._normalize_players(players)
        if len(normalized) < 4:
            logger.info(
                "Se necesitan >= 4 jugadores para un diagrama de Voronoi 2D (hay %d)",
                len(normalized),
            )
            return None

        points = np.array([[p["x"], p["y"]] for p in normalized], dtype=np.float64)
        try:
            vor = _ScipyVoronoi(points)
        except Exception as exc:  # QhullError y derivados
            logger.warning("scipy.spatial.Voronoi falló (%s): %s", type(exc).__name__, exc)
            return None

        return {
            "points": points,
            "vertices": vor.vertices,
            "regions": vor.regions,
            "point_region": vor.point_region,
            "player_keys": [p["key"] for p in normalized],
        }

    # ------------------------------------------------------------------
    # Render SVG
    # ------------------------------------------------------------------
    def _team_color(self, team_id: int) -> str:
        """Color asociado a un equipo."""
        if team_id == UNKNOWN_TEAM:
            return self.UNKNOWN_TEAM_COLOR
        return self.TEAM_COLORS.get(int(team_id), self.UNKNOWN_TEAM_COLOR)

    def _pitch_lines_svg(self, w: float, h: float) -> str:
        """Líneas del campo, proporciones equivalentes a PitchVisualizer."""
        return (
            f'<g stroke="{self.LINE_COLOR}" fill="none">'
            f'<rect x="0" y="0" width="{w:.2f}" height="{h:.2f}" stroke-width="2"/>'
            f'<line x1="{w / 2:.2f}" y1="0" x2="{w / 2:.2f}" y2="{h:.2f}" stroke-width="2"/>'
            f'<circle cx="{w / 2:.2f}" cy="{h / 2:.2f}" r="{h * 0.175:.2f}" stroke-width="1"/>'
            f'<rect x="0" y="{h * 0.22:.2f}" width="{w * 0.05:.2f}" '
            f'height="{h * 0.56:.2f}" stroke-width="1"/>'
            f'<rect x="0" y="{h * 0.36:.2f}" width="{w * 0.019:.2f}" '
            f'height="{h * 0.28:.2f}" stroke-width="1"/>'
            f'<rect x="{w * 0.95:.2f}" y="{h * 0.22:.2f}" width="{w * 0.05:.2f}" '
            f'height="{h * 0.56:.2f}" stroke-width="1"/>'
            f'<rect x="{w * 0.981:.2f}" y="{h * 0.36:.2f}" width="{w * 0.019:.2f}" '
            f'height="{h * 0.28:.2f}" stroke-width="1"/>'
            f'</g>'
            f'<circle cx="{w / 2:.2f}" cy="{h / 2:.2f}" r="3" fill="{self.LINE_COLOR}"/>'
        )

    def _regions_svg(self, control: Dict, w: float, h: float) -> str:
        """
        Regiones coloreadas por equipo.

        Se agrupan celdas contiguas de la misma fila con el mismo equipo en un
        único ``<rect>`` (codificación por tramos) para no generar un SVG de
        decenas de miles de elementos.
        """
        if not control["valid"]:
            return ""

        team_grid = control["team_grid"]
        contested = control["contested_mask"]
        res = self.grid_resolution
        cell_w = w / res
        cell_h = h / res

        parts: List[str] = ['<g class="voronoi-regions" opacity="0.55">']
        for row in range(res):
            col = 0
            team_row = team_grid[row]
            cont_row = contested[row]
            while col < res:
                team = int(team_row[col])
                is_cont = bool(cont_row[col])
                end = col + 1
                while (
                    end < res
                    and int(team_row[end]) == team
                    and bool(cont_row[end]) == is_cont
                ):
                    end += 1
                color = self.CONTESTED_COLOR if is_cont else self._team_color(team)
                parts.append(
                    f'<rect x="{col * cell_w:.2f}" y="{row * cell_h:.2f}" '
                    f'width="{(end - col) * cell_w:.2f}" height="{cell_h:.2f}" '
                    f'fill="{color}" shape-rendering="crispEdges"/>'
                )
                col = end
        parts.append("</g>")
        return "".join(parts)

    def render_svg(self, players: List[Dict], width_px: int = 800) -> str:
        """
        Renderizar un SVG standalone del campo con las regiones de control.

        El SVG no usa JavaScript ni recursos externos, por lo que puede
        incrustarse directamente en el HTML del dashboard existente
        (``core/interactive_dashboard.py``), cuya paleta y proporciones reutiliza.

        Args:
            players: Lista de jugadores (ver :meth:`compute_control`).
            width_px: Ancho del SVG en píxeles. El alto se deriva de la
                proporción real del campo.

        Returns:
            String SVG bien formado (XML válido). Contiene exactamente un
            elemento ``<circle class="voronoi-player" ...>`` por jugador válido,
            con atributos ``data-player-id`` y ``data-team-id``.
        """
        if width_px <= 0:
            raise ValueError("width_px debe ser positivo")

        w = float(width_px)
        h = w * self.pitch_width_m / self.pitch_length_m
        control = self.compute_control(players)

        parts: List[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
            f'viewBox="0 0 {w:.2f} {h:.2f}" role="img" '
            f'aria-label="Control espacial del campo (Voronoi)">',
            f'<rect x="0" y="0" width="{w:.2f}" height="{h:.2f}" fill="{self.PITCH_COLOR}"/>',
        ]
        parts.append(self._regions_svg(control, w, h))
        parts.append(self._pitch_lines_svg(w, h))

        # Jugadores
        radius = max(4.0, w / 80.0)
        parts.append('<g class="voronoi-players">')
        for key, team_id, (x_m, y_m) in zip(
            control["player_keys"], control["player_teams"], control["player_positions"]
        ):
            cx = min(max(x_m, 0.0), self.pitch_length_m) / self.pitch_length_m * w
            cy = min(max(y_m, 0.0), self.pitch_width_m) / self.pitch_width_m * h
            safe_key = _xml_escape(str(key), {'"': "&quot;"})
            parts.append(
                f'<circle class="voronoi-player" data-player-id="{safe_key}" '
                f'data-team-id="{int(team_id)}" cx="{cx:.2f}" cy="{cy:.2f}" '
                f'r="{radius:.2f}" fill="{self._team_color(int(team_id))}" '
                f'stroke="{self.LINE_COLOR}" stroke-width="2"/>'
            )
        parts.append("</g>")

        # Leyenda con los porcentajes agregados
        if control["valid"]:
            total_cells = float(self.grid_resolution ** 2)
            pct_0 = 100.0 * int(np.count_nonzero(control["team_grid"] == 0)) / total_cells
            pct_1 = 100.0 * int(np.count_nonzero(control["team_grid"] == 1)) / total_cells
            legend = _xml_escape(
                f"Equipo 0: {pct_0:.1f}%  |  Equipo 1: {pct_1:.1f}%"
            )
            parts.append(
                f'<text class="voronoi-legend" x="8" y="{h - 8:.2f}" '
                f'font-family="Segoe UI, Tahoma, sans-serif" font-size="14" '
                f'font-weight="bold" fill="{self.LINE_COLOR}">{legend}</text>'
            )

        parts.append("</svg>")
        return "".join(parts)

    # ------------------------------------------------------------------
    # Estadísticas
    # ------------------------------------------------------------------
    def get_statistics(self) -> Dict:
        """
        Estadísticas acumuladas del analizador.

        Returns:
            Dict con configuración, contadores de uso y el último resumen de
            dominancia por equipo (``last_team_0_percent`` /
            ``last_team_1_percent`` / ``last_contested_percent``), o ``None`` si
            aún no se ha calculado nada.
        """
        last_0 = last_1 = last_c = None
        if self._last_control is not None and self._last_control["valid"]:
            total_cells = float(self.grid_resolution ** 2)
            team_grid = self._last_control["team_grid"]
            last_0 = float(100.0 * int(np.count_nonzero(team_grid == 0)) / total_cells)
            last_1 = float(100.0 * int(np.count_nonzero(team_grid == 1)) / total_cells)
            last_c = float(self._last_control["contested_percent"])

        return {
            "pitch_length_m": self.pitch_length_m,
            "pitch_width_m": self.pitch_width_m,
            "pitch_area_m2": self.pitch_area_m2,
            "grid_resolution": self.grid_resolution,
            "cell_area_m2": self.cell_area_m2,
            "contested_tolerance_m": self.contested_tolerance_m,
            "scipy_available": _HAS_SCIPY,
            "total_computations": self._total_computations,
            "total_players_processed": self._total_players_processed,
            "invalid_players_skipped": self._invalid_players_skipped,
            "out_of_bounds_players": self._out_of_bounds_players,
            "last_team_0_percent": last_0,
            "last_team_1_percent": last_1,
            "last_contested_percent": last_c,
        }

    def reset(self) -> None:
        """Reiniciar los contadores acumulados y el último resultado."""
        self._total_computations = 0
        self._total_players_processed = 0
        self._invalid_players_skipped = 0
        self._out_of_bounds_players = 0
        self._last_control = None
        logger.debug("VoronoiAnalyzer reiniciado")

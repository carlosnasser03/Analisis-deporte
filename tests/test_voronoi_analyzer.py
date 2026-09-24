"""
Tests de core/voronoi_analyzer.py — control espacial (Voronoi).

Todos los tests son sintéticos (posiciones en metros), sin vídeo ni modelos.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.voronoi_analyzer import UNKNOWN_TEAM, VoronoiAnalyzer, _HAS_SCIPY  # noqa: E402


PITCH_L = 105.0
PITCH_W = 68.0
SVG_NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture
def analyzer() -> VoronoiAnalyzer:
    """Analizador con la configuración por defecto."""
    return VoronoiAnalyzer()


def _player(pid, x, y, team=0):
    """Construir un jugador en el formato del contrato."""
    return {"player_id": pid, "position": [x, y], "team_id": team}


# ---------------------------------------------------------------------------
# Construcción y validación
# ---------------------------------------------------------------------------
def test_init_defaults(analyzer):
    """El campo por defecto es 105x68 m y la malla 100x100."""
    assert analyzer.pitch_length_m == PITCH_L
    assert analyzer.pitch_width_m == PITCH_W
    assert analyzer.grid_resolution == 100
    assert analyzer.pitch_area_m2 == pytest.approx(7140.0)
    assert analyzer.cell_area_m2 == pytest.approx(7140.0 / 10000)


def test_init_rejects_invalid_config():
    """Configuraciones imposibles fallan explícitamente."""
    with pytest.raises(ValueError):
        VoronoiAnalyzer(grid_resolution=1)
    with pytest.raises(ValueError):
        VoronoiAnalyzer(pitch_length_m=0)
    with pytest.raises(ValueError):
        VoronoiAnalyzer(pitch_width_m=-10)
    with pytest.raises(ValueError):
        VoronoiAnalyzer(contested_tolerance_m=-1.0)
    with pytest.raises(TypeError):
        VoronoiAnalyzer(grid_resolution=10.5)


# ---------------------------------------------------------------------------
# Casos base de control
# ---------------------------------------------------------------------------
def test_single_player_controls_everything(analyzer):
    """Un solo jugador controla el 100% del campo."""
    result = analyzer.compute_team_dominance([_player("p1", 52.5, 34.0, team=0)])

    assert result["valid"] is True
    assert result["team_0_percent"] == pytest.approx(100.0)
    assert result["team_1_percent"] == pytest.approx(0.0)
    assert result["contested_percent"] == pytest.approx(0.0)
    assert result["per_player_area_m2"]["p1"] == pytest.approx(analyzer.pitch_area_m2)


def test_two_symmetric_players_split_50_50(analyzer):
    """Dos jugadores en espejo respecto al centro dan exactamente 50/50."""
    players = [
        _player("a", 30.0, 34.0, team=0),
        _player("b", 75.0, 34.0, team=1),  # espejo de 30.0 respecto a x=52.5
    ]
    result = analyzer.compute_team_dominance(players)

    assert result["team_0_percent"] == pytest.approx(50.0, abs=1e-9)
    assert result["team_1_percent"] == pytest.approx(50.0, abs=1e-9)
    assert result["contested_percent"] == pytest.approx(0.0)
    assert result["per_player_area_m2"]["a"] == pytest.approx(
        result["per_player_area_m2"]["b"], abs=1e-9
    )


def test_symmetric_players_on_y_axis_split_50_50(analyzer):
    """La simetría también es exacta en el eje ancho (y)."""
    players = [
        _player("a", 52.5, 24.0, team=0),
        _player("b", 52.5, 44.0, team=1),  # espejo respecto a y=34
    ]
    result = analyzer.compute_team_dominance(players)

    assert result["team_0_percent"] == pytest.approx(50.0, abs=1e-9)
    assert result["team_1_percent"] == pytest.approx(50.0, abs=1e-9)


def test_areas_sum_to_100_percent(analyzer):
    """Con un 11 vs 11 realista, todas las áreas suman ~100% y el área del campo."""
    rng = np.random.default_rng(42)
    players = []
    for i in range(11):
        players.append(_player(f"h{i}", rng.uniform(0, 52.5), rng.uniform(0, 68), 0))
    for i in range(11):
        players.append(_player(f"a{i}", rng.uniform(52.5, 105), rng.uniform(0, 68), 1))

    dominance = analyzer.compute_team_dominance(players)
    total_pct = (
        dominance["team_0_percent"]
        + dominance["team_1_percent"]
        + dominance["contested_percent"]
        + dominance["other_percent"]
    )
    assert total_pct == pytest.approx(100.0, abs=1e-9)

    per_player_sum = sum(dominance["per_player_area_m2"].values())
    assert per_player_sum + dominance["contested_area_m2"] == pytest.approx(
        analyzer.pitch_area_m2, abs=1e-6
    )
    assert len(dominance["per_player_area_m2"]) == 22


def test_all_players_same_team(analyzer):
    """Si todos son del mismo equipo, ese equipo domina el 100% y nada es disputado."""
    players = [_player(f"p{i}", 10.0 * (i + 1), 20.0 + 3 * i, team=0) for i in range(6)]
    result = analyzer.compute_team_dominance(players)

    assert result["team_0_percent"] == pytest.approx(100.0)
    assert result["team_1_percent"] == pytest.approx(0.0)
    assert result["contested_percent"] == pytest.approx(0.0)
    assert all(area > 0 for area in result["per_player_area_m2"].values())


def test_empty_player_list(analyzer):
    """Lista vacía: resultado inválido pero sin excepciones ni NaN."""
    control = analyzer.compute_control([])
    dominance = analyzer.compute_team_dominance([])

    assert control["valid"] is False
    assert control["n_players"] == 0
    assert control["per_player_area_m2"] == {}
    assert dominance["valid"] is False
    assert dominance["team_0_percent"] == 0.0
    assert dominance["team_1_percent"] == 0.0
    assert dominance["contested_percent"] == 0.0


def test_players_outside_pitch_bounds(analyzer):
    """Jugadores fuera de los límites: se avisan y su región se recorta al campo."""
    players = [
        _player("fuera", -20.0, 100.0, team=0),   # fuera por ambos ejes
        _player("dentro", 52.5, 34.0, team=1),
    ]
    control = analyzer.compute_control(players)
    dominance = analyzer.compute_team_dominance(players)

    assert control["valid"] is True
    assert any("fuera del campo" in w for w in control["warnings"])
    # El área total sigue sumando el campo completo.
    assert sum(control["per_player_area_m2"].values()) == pytest.approx(
        analyzer.pitch_area_m2, abs=1e-6
    )
    assert dominance["team_0_percent"] + dominance["team_1_percent"] == pytest.approx(
        100.0, abs=1e-9
    )
    # El jugador de fuera controla la esquina más cercana, pero no domina el campo.
    assert 0.0 < dominance["team_0_percent"] < 50.0


def test_invalid_entries_are_skipped(analyzer):
    """Entradas malformadas se ignoran con aviso, sin romper el cálculo."""
    players = [
        _player("ok", 52.5, 34.0, team=0),
        {"player_id": "sin_pos", "team_id": 1},
        {"player_id": "nan", "position": [float("nan"), 10.0], "team_id": 1},
        {"player_id": "texto", "position": ["a", "b"], "team_id": 1},
        "no soy un dict",
    ]
    control = analyzer.compute_control(players)

    assert control["n_players"] == 1
    assert control["per_player_percent"]["ok"] == pytest.approx(100.0)
    assert len(control["warnings"]) == 4


def test_unknown_team_goes_to_other(analyzer):
    """Un jugador sin team_id válido no cuenta como equipo 0 ni 1."""
    players = [
        _player("a", 30.0, 34.0, team=0),
        {"player_id": "b", "position": [75.0, 34.0]},  # sin team_id
    ]
    control = analyzer.compute_control(players)
    dominance = analyzer.compute_team_dominance(players)

    assert UNKNOWN_TEAM in control["teams_present"]
    assert dominance["team_0_percent"] == pytest.approx(50.0, abs=1e-9)
    assert dominance["team_1_percent"] == pytest.approx(0.0)
    assert dominance["other_percent"] == pytest.approx(50.0, abs=1e-9)


def test_closer_player_controls_more_area(analyzer):
    """El jugador más aislado controla más espacio que los apiñados."""
    players = [
        _player("aislado", 90.0, 34.0, team=0),
        _player("junto_1", 20.0, 30.0, team=0),
        _player("junto_2", 22.0, 38.0, team=0),
    ]
    areas = analyzer.compute_control(players)["per_player_area_m2"]

    assert areas["aislado"] > areas["junto_1"]
    assert areas["aislado"] > areas["junto_2"]


def test_contested_tolerance_creates_contested_band():
    """Con tolerancia > 0 aparece una franja disputada entre equipos rivales."""
    strict = VoronoiAnalyzer(contested_tolerance_m=0.0)
    loose = VoronoiAnalyzer(contested_tolerance_m=5.0)
    players = [_player("a", 30.0, 34.0, 0), _player("b", 75.0, 34.0, 1)]

    assert strict.compute_team_dominance(players)["contested_percent"] == 0.0
    loose_result = loose.compute_team_dominance(players)
    assert loose_result["contested_percent"] > 0.0
    total = (
        loose_result["team_0_percent"]
        + loose_result["team_1_percent"]
        + loose_result["contested_percent"]
        + loose_result["other_percent"]
    )
    assert total == pytest.approx(100.0, abs=1e-9)


def test_duplicate_player_ids_are_disambiguated(analyzer):
    """Ids duplicados no se pisan: se renombra el segundo y no se pierde área."""
    players = [_player("x", 30.0, 34.0, 0), _player("x", 75.0, 34.0, 1)]
    control = analyzer.compute_control(players)

    assert len(control["per_player_area_m2"]) == 2
    assert sum(control["per_player_area_m2"].values()) == pytest.approx(
        analyzer.pitch_area_m2, abs=1e-6
    )


# ---------------------------------------------------------------------------
# Control por zonas (tercios)
# ---------------------------------------------------------------------------
def test_zone_control_thirds(analyzer):
    """Cada equipo domina el tercio en el que está solo; el medio se reparte."""
    players = [_player("d", 10.0, 34.0, 0), _player("o", 95.0, 34.0, 1)]
    zones = analyzer.compute_zone_control(players)

    assert zones["valid"] is True
    assert set(zones["zones"]) == {"defensive", "middle", "attacking"}
    assert zones["zones"]["defensive"]["team_0_percent"] == pytest.approx(100.0)
    assert zones["zones"]["attacking"]["team_1_percent"] == pytest.approx(100.0)
    assert zones["zones"]["middle"]["team_0_percent"] == pytest.approx(50.0, abs=1e-9)
    assert zones["zones"]["middle"]["team_1_percent"] == pytest.approx(50.0, abs=1e-9)


def test_zone_control_percentages_sum_100_per_zone(analyzer):
    """Dentro de cada zona los porcentajes suman 100 y los rangos x son correctos."""
    rng = np.random.default_rng(7)
    players = [
        _player(f"p{i}", rng.uniform(0, 105), rng.uniform(0, 68), i % 2)
        for i in range(14)
    ]
    zones = analyzer.compute_zone_control(players)

    for name, zone in zones["zones"].items():
        total = (
            zone["team_0_percent"]
            + zone["team_1_percent"]
            + zone["contested_percent"]
            + zone["other_percent"]
        )
        assert total == pytest.approx(100.0, abs=1e-9), name

    assert zones["zones"]["defensive"]["x_range_m"][0] == 0.0
    assert zones["zones"]["attacking"]["x_range_m"][1] == pytest.approx(PITCH_L)
    total_cells = sum(z["n_cells"] for z in zones["zones"].values())
    assert total_cells == analyzer.grid_resolution ** 2


def test_zone_control_empty_players(analyzer):
    """Sin jugadores, las zonas existen con porcentajes a cero."""
    zones = analyzer.compute_zone_control([])

    assert zones["valid"] is False
    for zone in zones["zones"].values():
        assert zone["team_0_percent"] == 0.0
        assert zone["team_1_percent"] == 0.0


# ---------------------------------------------------------------------------
# Render SVG
# ---------------------------------------------------------------------------
def test_svg_is_well_formed_and_has_one_element_per_player(analyzer):
    """El SVG es XML válido y contiene exactamente un círculo por jugador."""
    players = [_player(f"p{i}", 10.0 + i * 8, 20.0 + (i % 3) * 12, i % 2) for i in range(10)]
    svg = analyzer.render_svg(players)

    root = ET.fromstring(svg)  # lanza ParseError si no es well-formed
    assert root.tag == f"{SVG_NS}svg"

    circles = [
        el for el in root.iter(f"{SVG_NS}circle")
        if el.get("class") == "voronoi-player"
    ]
    assert len(circles) == len(players)
    assert {c.get("data-player-id") for c in circles} == {f"p{i}" for i in range(10)}


def test_svg_is_standalone_and_proportional(analyzer):
    """El SVG no depende de JS ni de recursos externos y respeta la proporción."""
    svg = analyzer.render_svg([_player("a", 30.0, 34.0, 0), _player("b", 75.0, 34.0, 1)],
                              width_px=600)
    root = ET.fromstring(svg)

    assert "<script" not in svg
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in svg
    assert root.get("width") == "600"
    expected_h = round(600 * PITCH_W / PITCH_L)
    assert abs(int(root.get("height")) - expected_h) <= 1
    # Debe haber regiones coloreadas para ambos equipos.
    assert VoronoiAnalyzer.TEAM_COLORS[0] in svg
    assert VoronoiAnalyzer.TEAM_COLORS[1] in svg


def test_svg_escapes_special_characters_in_ids(analyzer):
    """Ids con caracteres XML peligrosos no rompen el documento."""
    players = [_player('<Ramos & "7">', 30.0, 34.0, 0), _player("b", 75.0, 34.0, 1)]
    svg = analyzer.render_svg(players)

    root = ET.fromstring(svg)
    ids = {
        el.get("data-player-id")
        for el in root.iter(f"{SVG_NS}circle")
        if el.get("class") == "voronoi-player"
    }
    assert '<Ramos & "7">' in ids


def test_svg_with_no_players_still_renders_pitch(analyzer):
    """Sin jugadores se dibuja el campo vacío, sin errores."""
    svg = analyzer.render_svg([])
    root = ET.fromstring(svg)

    assert root.tag == f"{SVG_NS}svg"
    players = [el for el in root.iter(f"{SVG_NS}circle") if el.get("class") == "voronoi-player"]
    assert players == []


def test_render_svg_rejects_invalid_width(analyzer):
    """Un ancho no positivo es un error explícito."""
    with pytest.raises(ValueError):
        analyzer.render_svg([_player("a", 10.0, 10.0, 0)], width_px=0)


# ---------------------------------------------------------------------------
# Estadísticas y geometría opcional
# ---------------------------------------------------------------------------
def test_get_statistics_tracks_usage(analyzer):
    """Las estadísticas reflejan el uso real y se reinician con reset()."""
    stats_initial = analyzer.get_statistics()
    assert stats_initial["total_computations"] == 0
    assert stats_initial["last_team_0_percent"] is None

    analyzer.compute_team_dominance([_player("a", 30.0, 34.0, 0), _player("b", 75.0, 34.0, 1)])
    stats = analyzer.get_statistics()

    assert stats["total_computations"] == 1
    assert stats["total_players_processed"] == 2
    assert stats["last_team_0_percent"] == pytest.approx(50.0, abs=1e-9)
    assert stats["grid_resolution"] == 100
    assert stats["scipy_available"] == _HAS_SCIPY

    analyzer.reset()
    assert analyzer.get_statistics()["total_computations"] == 0


def test_scalar_outputs_are_json_serializable(analyzer):
    """Los escalares son tipos Python nativos (necesario para el dashboard HTML)."""
    import json

    players = [_player("a", 30.0, 34.0, 0), _player("b", 75.0, 34.0, 1)]
    dominance = analyzer.compute_team_dominance(players)
    zones = analyzer.compute_zone_control(players)
    stats = analyzer.get_statistics()

    json.dumps(dominance)   # lanza TypeError si hay np.float64/np.int64
    json.dumps(zones)
    json.dumps(stats)
    assert isinstance(stats["last_team_0_percent"], float)


def test_grid_resolution_affects_precision_not_totals():
    """Cambiar la resolución cambia la granularidad, no que las áreas sumen 100%."""
    players = [_player("a", 20.0, 20.0, 0), _player("b", 80.0, 50.0, 1)]

    for res in (10, 50, 200):
        analyzer = VoronoiAnalyzer(grid_resolution=res)
        dominance = analyzer.compute_team_dominance(players)
        assert dominance["team_0_percent"] + dominance["team_1_percent"] == pytest.approx(
            100.0, abs=1e-9
        )
        assert sum(dominance["per_player_area_m2"].values()) == pytest.approx(
            analyzer.pitch_area_m2, abs=1e-6
        )


def test_control_grids_have_expected_shape_and_dtype(analyzer):
    """Las mallas devueltas tienen forma (res, res) y valores coherentes."""
    players = [_player("a", 30.0, 34.0, 0), _player("b", 75.0, 34.0, 1)]
    control = analyzer.compute_control(players)

    assert control["owner_grid"].shape == (100, 100)
    assert control["team_grid"].shape == (100, 100)
    assert control["contested_mask"].shape == (100, 100)
    assert control["contested_mask"].dtype == bool
    assert set(np.unique(control["team_grid"]).tolist()) == {0, 1}
    assert set(np.unique(control["owner_grid"]).tolist()) == {0, 1}


@pytest.mark.skipif(not _HAS_SCIPY, reason="scipy no instalado")
def test_voronoi_geometry_with_scipy(analyzer):
    """Con scipy y >=4 jugadores se expone la geometría exacta de polígonos."""
    players = [
        _player("a", 20.0, 20.0, 0),
        _player("b", 80.0, 20.0, 1),
        _player("c", 20.0, 50.0, 0),
        _player("d", 80.0, 50.0, 1),
    ]
    geometry = analyzer.compute_voronoi_geometry(players)

    assert geometry is not None
    assert geometry["points"].shape == (4, 2)
    assert len(geometry["player_keys"]) == 4
    assert len(geometry["point_region"]) == 4


def test_voronoi_geometry_needs_four_points(analyzer):
    """Con menos de 4 jugadores no hay diagrama 2D: devuelve None sin fallar."""
    assert analyzer.compute_voronoi_geometry([_player("a", 20.0, 20.0, 0)]) is None
    assert analyzer.compute_voronoi_geometry([]) is None

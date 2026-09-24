"""
test_bytetrack_adapter.py - Tests del adaptador ByteTrack (core/bytetrack_adapter.py)

Todos los tests usan detecciones sintéticas generadas con NumPy: no se abre
ningún video ni se carga ningún modelo YOLO.

Los tests de comportamiento se ejecutan contra los dos backends disponibles
(``native`` siempre, ``supervision`` solo si la librería está instalada).
"""

import inspect
from typing import Dict, List, Optional

import numpy as np
import pytest

from core.bytetrack_adapter import (
    HAS_SCIPY,
    HAS_SUPERVISION,
    ByteTrackAdapter,
    ByteTrackState,
)
from core.tracker import PlayerTracker


# --------------------------------------------------------------------------- #
# Utilidades y fixtures
# --------------------------------------------------------------------------- #
BACKENDS = ["native"] + (["supervision"] if HAS_SUPERVISION else [])

BOX_W = 40.0
BOX_H = 80.0


def make_detection(x: float, y: float, confidence: float = 0.9,
                   w: float = BOX_W, h: float = BOX_H, **extra) -> Dict:
    """Crea una detección sintética con la esquina superior izquierda en (x, y)."""
    det = {
        "bbox": [float(x), float(y), float(x + w), float(y + h)],
        "center": [float(x + w / 2), float(y + h / 2)],
        "confidence": float(confidence),
        "class_id": 0,
    }
    det.update(extra)
    return det


def linear_track_detections(n_frames: int, x0: float = 100.0, y0: float = 200.0,
                            vx: float = 8.0, vy: float = 0.0,
                            confidence: float = 0.9) -> List[List[Dict]]:
    """Genera una trayectoria rectilínea de un solo jugador, frame a frame."""
    return [
        [make_detection(x0 + vx * f, y0 + vy * f, confidence)]
        for f in range(n_frames)
    ]


def run_frames(tracker: ByteTrackAdapter, frames: List[List[Dict]],
               start: int = 0) -> List[Dict]:
    """Alimenta el tracker con una secuencia de frames y devuelve los resultados."""
    return [tracker.track(dets, start + i) for i, dets in enumerate(frames)]


@pytest.fixture(params=BACKENDS)
def backend(request) -> str:
    """Backend bajo prueba."""
    return request.param


@pytest.fixture
def tracker(backend) -> ByteTrackAdapter:
    """Adaptador con configuración por defecto sobre el backend parametrizado."""
    return ByteTrackAdapter(backend=backend)


# --------------------------------------------------------------------------- #
# 1. Importación y configuración
# --------------------------------------------------------------------------- #
def test_modulo_importa_sin_supervision(monkeypatch):
    """El módulo funciona aunque supervision no esté disponible."""
    import core.bytetrack_adapter as mod

    monkeypatch.setattr(mod, "_HAS_SUPERVISION", False)
    tracker = ByteTrackAdapter()  # backend="auto"
    assert tracker.backend == "native"

    result = tracker.track([make_detection(10, 10)], 0)
    assert result["backend"] == "native"
    assert result["new_tracks"] == 1

    with pytest.raises(ImportError):
        ByteTrackAdapter(backend="supervision")


def test_constructor_defaults_y_atributos():
    """Los valores por defecto son los del contrato y quedan expuestos."""
    tracker = ByteTrackAdapter()
    assert tracker.max_age == 30
    assert tracker.min_hits == 3
    assert tracker.high_threshold == pytest.approx(0.6)
    assert tracker.low_threshold == pytest.approx(0.1)
    assert tracker.match_threshold == pytest.approx(0.8)
    assert tracker.backend in ("native", "supervision")
    assert tracker.tracks == {}
    assert tracker.next_id == 1
    assert tracker.frame_count == 0


@pytest.mark.parametrize("kwargs", [
    {"max_age": 0},
    {"min_hits": 0},
    {"high_threshold": 1.5},
    {"low_threshold": -0.1},
    {"match_threshold": 2.0},
    {"high_threshold": 0.2, "low_threshold": 0.5},  # low > high
    {"frame_rate": 0},
])
def test_constructor_valida_parametros(kwargs):
    """Parámetros fuera de rango levantan ValueError explícito."""
    with pytest.raises(ValueError):
        ByteTrackAdapter(**kwargs)


def test_backend_invalido_levanta_valueerror():
    """Un nombre de backend desconocido falla en el constructor."""
    with pytest.raises(ValueError):
        ByteTrackAdapter(backend="kalman-magico")


# --------------------------------------------------------------------------- #
# 2. Comportamiento básico del tracking
# --------------------------------------------------------------------------- #
def test_lista_de_detecciones_vacia(tracker):
    """Una lista vacía no rompe nada y no crea tracks."""
    result = tracker.track([], 0)
    assert result["matched"] == 0
    assert result["new_tracks"] == 0
    assert result["active_tracks"] == 0
    assert tracker.get_tracks() == []

    # También tolera None
    assert tracker.track(None, 1)["active_tracks"] == 0
    assert tracker.get_statistics()["total_frames"] == 2


def test_id_estable_en_trayectoria_recta(tracker):
    """Un jugador en línea recta conserva el mismo track_id en todos los frames."""
    frames = linear_track_detections(n_frames=30, vx=8.0)
    observed_ids = set()

    for i, dets in enumerate(frames):
        tracker.track(dets, i)
        tracks = tracker.get_tracks()
        assert len(tracks) == 1, f"frame {i}: se esperaba 1 track, hay {len(tracks)}"
        observed_ids.add(tracks[0]["track_id"])

    assert observed_ids == {1}, f"El ID cambió durante la trayectoria: {observed_ids}"
    assert tracker.get_statistics()["total_tracks_created"] == 1


def test_dos_jugadores_que_se_cruzan_mantienen_sus_ids(tracker):
    """Dos jugadores que se cruzan conservan cada uno su ID original."""
    x_a, x_b = 100.0, 300.0
    v = 10.0
    id_a = id_b = None
    crossed = False

    for f in range(21):
        tracker.track([make_detection(x_a, 200), make_detection(x_b, 200)], f)
        by_x = {round(t["bbox"][0]): t["track_id"] for t in tracker.get_tracks()}

        if f == 0:
            id_a, id_b = by_x[round(x_a)], by_x[round(x_b)]
            assert id_a != id_b
        if abs(x_a - x_b) < BOX_W:
            crossed = True
        if f == 20:
            # Tras el cruce A está a la derecha y B a la izquierda
            assert by_x[round(x_a)] == id_a, "El jugador A perdió su ID tras el cruce"
            assert by_x[round(x_b)] == id_b, "El jugador B perdió su ID tras el cruce"

        x_a += v
        x_b -= v

    assert crossed, "El escenario de prueba no llegó a producir un cruce"
    assert tracker.get_statistics()["total_tracks_created"] == 2


def test_recuperacion_via_deteccion_de_baja_confianza(tracker):
    """La etapa 2 recupera el track usando detecciones de baja confianza."""
    # 5 frames con alta confianza
    for f in range(5):
        tracker.track([make_detection(100 + 5 * f, 200, confidence=0.9)], f)
    track_id = tracker.get_tracks()[0]["track_id"]

    # 4 frames con confianza baja (oclusión parcial): el track debe sobrevivir
    for f in range(5, 9):
        result = tracker.track([make_detection(100 + 5 * f, 200, confidence=0.25)], f)
        assert result["matched_low"] == 1, f"frame {f}: no hubo recuperación en etapa 2"
        assert result["new_tracks"] == 0, f"frame {f}: se creó un track espurio"

    tracks = tracker.get_tracks()
    assert len(tracks) == 1
    assert tracks[0]["track_id"] == track_id, "El ID cambió tras la oclusión"
    assert tracks[0]["recovered_from_low"] is True
    assert tracker.get_statistics()["low_confidence_recoveries"] == 4


def test_deteccion_de_baja_confianza_no_crea_track_nuevo(tracker):
    """Sin track previo, una detección de baja confianza no genera un track."""
    result = tracker.track([make_detection(500, 500, confidence=0.25)], 0)
    assert result["new_tracks"] == 0
    assert result["active_tracks"] == 0
    assert tracker.get_tracks() == []


def test_deteccion_bajo_low_threshold_se_descarta(tracker):
    """Por debajo de low_threshold la detección se ignora por completo."""
    for f in range(4):
        tracker.track([make_detection(100 + 5 * f, 200, confidence=0.9)], f)
    assert len(tracker.get_tracks()) == 1

    # confidence 0.02 < low_threshold (0.1): equivale a no detectar nada
    result = tracker.track([make_detection(120, 200, confidence=0.02)], 4)
    assert result["matched"] == 0
    assert result["new_tracks"] == 0
    assert tracker.get_tracks()[0]["time_since_update"] == 1


def test_track_expira_tras_max_age(backend):
    """Un track sin detecciones se elimina cuando supera max_age."""
    tracker = ByteTrackAdapter(backend=backend, max_age=3)
    for f in range(4):
        tracker.track([make_detection(100, 200, confidence=0.9)], f)
    assert len(tracker.tracks) == 1

    # 3 frames vacíos: sigue vivo (time_since_update = 1, 2, 3)
    for f in range(4, 7):
        tracker.track([], f)
        assert len(tracker.tracks) == 1, f"frame {f}: el track expiró antes de tiempo"

    # 4º frame vacío: time_since_update = 4 > max_age -> se elimina
    result = tracker.track([], 7)
    assert len(tracker.tracks) == 0
    assert result["removed_tracks"] == 1
    assert len(tracker.lost_tracks) == 1
    assert tracker.get_statistics()["lost_tracks"] == 1


def test_track_reaparecido_dentro_de_max_age_conserva_id(backend):
    """Si el jugador reaparece antes de max_age, recupera su mismo ID."""
    tracker = ByteTrackAdapter(backend=backend, max_age=10)
    for f in range(5):
        tracker.track([make_detection(100 + 5 * f, 200)], f)
    original_id = tracker.get_tracks()[0]["track_id"]

    for f in range(5, 8):  # tres frames sin detecciones
        tracker.track([], f)
    assert len(tracker.tracks) == 1

    # Reaparece cerca de donde estaba (la predicción de movimiento lo cubre)
    tracker.track([make_detection(140, 200)], 8)
    tracks = tracker.get_tracks()
    assert len(tracks) == 1
    assert tracks[0]["track_id"] == original_id
    assert tracks[0]["time_since_update"] == 0


def test_min_hits_confirma_el_track(backend):
    """Un track solo se marca 'confirmed' cuando alcanza min_hits asociaciones."""
    tracker = ByteTrackAdapter(backend=backend, min_hits=3)

    tracker.track([make_detection(100, 200)], 0)
    assert tracker.get_tracks()[0]["hits"] == 1
    assert tracker.get_tracks()[0]["confirmed"] is False
    assert tracker.get_confirmed_tracks() == []

    tracker.track([make_detection(105, 200)], 1)
    assert tracker.get_tracks()[0]["confirmed"] is False

    tracker.track([make_detection(110, 200)], 2)
    track = tracker.get_tracks()[0]
    assert track["hits"] == 3
    assert track["confirmed"] is True
    assert len(tracker.get_confirmed_tracks()) == 1
    assert tracker.get_statistics()["confirmed_tracks"] == 1


def test_reset_restaura_estado_inicial(tracker):
    """reset() limpia tracks, histórico, contadores e IDs."""
    for f in range(6):
        tracker.track([make_detection(100 + 5 * f, 200),
                       make_detection(400 - 5 * f, 200)], f)
    assert len(tracker.tracks) == 2
    assert tracker.frame_count == 6

    tracker.reset()

    assert tracker.tracks == {}
    assert tracker.lost_tracks == {}
    assert tracker.next_id == 1
    assert tracker.frame_count == 0
    stats = tracker.get_statistics()
    assert stats["active_tracks"] == 0
    assert stats["total_tracks_created"] == 0
    assert stats["low_confidence_recoveries"] == 0

    # Tras el reset el numerado vuelve a empezar en 1
    tracker.track([make_detection(700, 300)], 0)
    assert tracker.get_tracks()[0]["track_id"] == 1


# --------------------------------------------------------------------------- #
# 3. API de consulta
# --------------------------------------------------------------------------- #
def test_get_tracks_filtra_por_min_confidence(tracker):
    """get_tracks(min_confidence) descarta los tracks por debajo del umbral."""
    for f in range(3):
        tracker.track([make_detection(100 + 5 * f, 200, confidence=0.95),
                       make_detection(400 + 5 * f, 200, confidence=0.65)], f)

    assert len(tracker.get_tracks()) == 2
    assert len(tracker.get_tracks(min_confidence=0.9)) == 1
    assert len(tracker.get_tracks(min_confidence=0.99)) == 0


def test_get_track_by_id(tracker):
    """get_track_by_id devuelve el track o None si no existe."""
    tracker.track([make_detection(100, 200)], 0)
    tracker.track([make_detection(108, 200)], 1)
    track_id = tracker.get_tracks()[0]["track_id"]

    info = tracker.get_track_by_id(track_id)
    assert info is not None
    assert info["track_id"] == track_id
    assert "position_history" in info
    assert len(info["position_history"]) == 2

    assert tracker.get_track_by_id(99999) is None


def test_get_statistics_contiene_claves_esperadas(tracker):
    """get_statistics expone las claves de PlayerTracker más las de ByteTrack."""
    for f in range(4):
        tracker.track([make_detection(100 + 5 * f, 200)], f)

    stats = tracker.get_statistics()
    for key in ("active_tracks", "lost_tracks", "total_frames", "next_id",
                "occluded_tracks", "max_age", "min_hits"):
        assert key in stats, f"falta la clave de PlayerTracker '{key}'"
    for key in ("backend", "confirmed_tracks", "high_threshold",
                "low_threshold", "low_confidence_recoveries"):
        assert key in stats, f"falta la clave de ByteTrack '{key}'"

    assert stats["active_tracks"] == 1
    assert stats["total_frames"] == 4
    assert stats["backend"] == tracker.backend


def test_velocidad_y_posicion_se_actualizan(tracker):
    """El track acumula historial de posiciones y estima velocidad coherente."""
    for f in range(6):
        tracker.track([make_detection(100 + 10.0 * f, 200)], f)

    track = tracker.get_tracks()[0]
    vx, vy = track["velocity"]
    assert vx == pytest.approx(10.0, abs=1e-6)
    assert vy == pytest.approx(0.0, abs=1e-6)

    # 'position' y 'center' apuntan al mismo centroide
    assert tuple(track["center"]) == pytest.approx(tuple(track["position"]))
    expected_cx = 100 + 10.0 * 5 + BOX_W / 2
    assert track["position"][0] == pytest.approx(expected_cx)

    info = tracker.get_track_by_id(track["track_id"])
    assert len(info["position_history"]) == 6


def test_team_id_y_jersey_se_propagan(tracker):
    """Los metadatos opcionales de la detección viajan al track."""
    tracker.track([make_detection(100, 200, team_id=1, jersey_number="10")], 0)
    track = tracker.get_tracks()[0]
    assert track["team_id"] == 1
    assert track["jersey_number"] == "10"

    tracker.track([make_detection(108, 200, team_id=0, jersey_number="7")], 1)
    track = tracker.get_tracks()[0]
    assert track["team_id"] == 0
    assert track["jersey_number"] == "7"


def test_detecciones_malformadas_se_ignoran(tracker, caplog):
    """Entradas inválidas se descartan sin lanzar excepción."""
    bad_detections = [
        {"confidence": 0.9},                                   # sin bbox
        {"bbox": [1, 2, 3], "confidence": 0.9},                # bbox incompleto
        {"bbox": [10, 10, 5, 5], "confidence": 0.9},           # bbox degenerado
        {"bbox": [0, 0, np.nan, 10], "confidence": 0.9},       # no finito
        {"bbox": ["a", "b", "c", "d"], "confidence": 0.9},     # no numérico
        "no soy un dict",                                      # tipo incorrecto
        make_detection(100, 200, 0.9),                         # válida
    ]
    result = tracker.track(bad_detections, 0)
    assert result["new_tracks"] == 1
    assert result["active_tracks"] == 1

    with pytest.raises(TypeError):
        tracker.track("esto no es una lista", 1)


def test_update_housekeeping_y_alias(tracker):
    """update() sin argumentos hace housekeeping; con detecciones delega en track()."""
    assert tracker.update() is None  # sin tracks, no falla

    result = tracker.update([make_detection(100, 200)], 0)
    assert result is not None and result["new_tracks"] == 1
    assert tracker.update() is None
    assert len(tracker.tracks) == 1


def test_frame_id_por_defecto_usa_contador_interno(tracker):
    """Si frame_id es None se usa el contador interno de frames."""
    r0 = tracker.track([make_detection(100, 200)])
    r1 = tracker.track([make_detection(108, 200)])
    assert r0["frame_id"] == 0
    assert r1["frame_id"] == 1
    assert tracker.frame_count == 2


# --------------------------------------------------------------------------- #
# 4. Asociación: húngara vs greedy
# --------------------------------------------------------------------------- #
def test_fallback_greedy_sin_scipy(monkeypatch):
    """Sin SciPy la asociación greedy produce el mismo tracking en un caso simple."""
    import core.bytetrack_adapter as mod

    monkeypatch.setattr(mod, "_HAS_SCIPY", False)
    tracker = ByteTrackAdapter(backend="native")

    x_a, x_b = 100.0, 300.0
    for f in range(15):
        tracker.track([make_detection(x_a, 200), make_detection(x_b, 200)], f)
        x_a += 10
        x_b -= 10

    tracks = tracker.get_tracks()
    assert len(tracks) == 2
    assert {t["track_id"] for t in tracks} == {1, 2}
    assert tracker.get_statistics()["total_tracks_created"] == 2


def test_iou_y_matriz_iou_coinciden():
    """La matriz vectorizada de IoU coincide con el cálculo par a par."""
    tracker = ByteTrackAdapter(backend="native")
    boxes_a = [[0, 0, 10, 10], [20, 20, 40, 40]]
    boxes_b = [[5, 5, 15, 15], [20, 20, 40, 40], [100, 100, 110, 110]]

    matrix = tracker._iou_matrix(boxes_a, boxes_b)
    assert matrix.shape == (2, 3)
    for i, ba in enumerate(boxes_a):
        for j, bb in enumerate(boxes_b):
            assert matrix[i, j] == pytest.approx(tracker._calculate_iou(ba, bb))

    assert matrix[0, 0] == pytest.approx(100 / 300)   # solape parcial
    assert matrix[1, 1] == pytest.approx(1.0)         # cajas idénticas
    assert matrix[0, 2] == pytest.approx(0.0)         # sin solape


# --------------------------------------------------------------------------- #
# 5. Paridad con PlayerTracker (drop-in)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("method", ["track", "get_tracks", "get_track_by_id",
                                    "get_statistics", "reset"])
def test_paridad_de_firmas_con_playertracker(method):
    """Las firmas públicas coinciden exactamente con las de PlayerTracker."""
    sig_ref = inspect.signature(getattr(PlayerTracker, method))
    sig_new = inspect.signature(getattr(ByteTrackAdapter, method))
    ref_params = [(p.name, p.default) for p in sig_ref.parameters.values()]
    new_params = [(p.name, p.default) for p in sig_new.parameters.values()]
    assert new_params[:len(ref_params)] == ref_params, (
        f"{method}: {sig_new} no es compatible con {sig_ref}"
    )


def test_paridad_de_formato_de_salida_con_playertracker():
    """Los dicts devueltos contienen, como mínimo, las claves de PlayerTracker."""
    detections_per_frame = [
        [make_detection(100 + 8 * f, 200, 0.92), make_detection(400 - 8 * f, 220, 0.88)]
        for f in range(8)
    ]

    reference = PlayerTracker(max_age=30, min_hits=3)
    adapter = ByteTrackAdapter(max_age=30, min_hits=3, backend="native")

    for f, dets in enumerate(detections_per_frame):
        ref_result = reference.track([dict(d) for d in dets], f)
        new_result = adapter.track([dict(d) for d in dets], f)

    # --- retorno de track() ---
    assert set(ref_result).issubset(set(new_result)), (
        f"track(): faltan claves {set(ref_result) - set(new_result)}"
    )
    for key in ref_result:
        assert isinstance(new_result[key], type(ref_result[key])), (
            f"track()['{key}']: tipo {type(new_result[key])} != {type(ref_result[key])}"
        )

    # --- get_tracks() ---
    ref_track = reference.get_tracks()[0]
    new_track = adapter.get_tracks()[0]
    assert set(ref_track).issubset(set(new_track)), (
        f"get_tracks(): faltan claves {set(ref_track) - set(new_track)}"
    )
    for key in ref_track:
        assert isinstance(new_track[key], type(ref_track[key])), (
            f"get_tracks()['{key}']: tipo {type(new_track[key])} != {type(ref_track[key])}"
        )

    # --- get_track_by_id() ---
    ref_by_id = reference.get_track_by_id(ref_track["track_id"])
    new_by_id = adapter.get_track_by_id(new_track["track_id"])
    assert set(ref_by_id).issubset(set(new_by_id))

    # --- get_statistics() ---
    ref_stats = reference.get_statistics()
    new_stats = adapter.get_statistics()
    assert set(ref_stats).issubset(set(new_stats)), (
        f"get_statistics(): faltan claves {set(ref_stats) - set(new_stats)}"
    )
    for key in ref_stats:
        assert isinstance(new_stats[key], type(ref_stats[key])), (
            f"get_statistics()['{key}']: tipo {type(new_stats[key])} != {type(ref_stats[key])}"
        )

    # --- formato de bbox/center del contrato ---
    assert len(new_track["bbox"]) == 4
    assert len(new_track["center"]) == 2
    assert all(isinstance(v, float) for v in new_track["bbox"])


def test_intercambiable_en_un_bucle_de_pipeline():
    """Ambos trackers se usan igual desde el mismo bucle (drop-in real)."""
    frames = [
        [make_detection(100 + 6 * f, 200, 0.9), make_detection(300 + 3 * f, 260, 0.8)]
        for f in range(12)
    ]

    def consume(tracker_obj) -> Dict:
        """Bucle genérico que solo usa la API común."""
        tracker_obj.reset()
        ids = set()
        for f, dets in enumerate(frames):
            tracker_obj.track([dict(d) for d in dets], f)
            for t in tracker_obj.get_tracks(min_confidence=0.5):
                ids.add(t["track_id"])
                assert tracker_obj.get_track_by_id(t["track_id"]) is not None
        stats = tracker_obj.get_statistics()
        return {"ids": ids, "active": stats["active_tracks"]}

    ref = consume(PlayerTracker())
    new = consume(ByteTrackAdapter(backend="native"))

    assert new["active"] == ref["active"] == 2
    assert len(new["ids"]) == len(ref["ids"]) == 2


# --------------------------------------------------------------------------- #
# 6. Backend supervision
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAS_SUPERVISION, reason="requiere el paquete 'supervision'")
def test_backend_supervision_se_selecciona_en_auto():
    """Con supervision instalado, backend='auto' resuelve a supervision."""
    tracker = ByteTrackAdapter(backend="auto")
    assert tracker.backend == "supervision"
    assert tracker._sv_tracker is not None


@pytest.mark.skipif(not HAS_SUPERVISION, reason="requiere el paquete 'supervision'")
def test_backends_producen_el_mismo_tracking_en_escenario_simple():
    """Ambos backends coinciden en número de tracks e IDs en un caso limpio."""
    frames = [
        [make_detection(100 + 7 * f, 200, 0.9), make_detection(500 - 7 * f, 200, 0.9)]
        for f in range(15)
    ]

    native = ByteTrackAdapter(backend="native")
    supervision = ByteTrackAdapter(backend="supervision")
    run_frames(native, [[dict(d) for d in fr] for fr in frames])
    run_frames(supervision, [[dict(d) for d in fr] for fr in frames])

    ids_native = sorted(t["track_id"] for t in native.get_tracks())
    ids_sv = sorted(t["track_id"] for t in supervision.get_tracks())
    assert ids_native == ids_sv == [1, 2]
    assert (native.get_statistics()["active_tracks"]
            == supervision.get_statistics()["active_tracks"] == 2)


# --------------------------------------------------------------------------- #
# 7. Estado interno
# --------------------------------------------------------------------------- #
def test_bytetrackstate_defaults():
    """El dataclass de estado arranca con los valores esperados."""
    state = ByteTrackState(track_id=7, bbox=[0.0, 0.0, 10.0, 20.0],
                           confidence=0.8, frame_id=3)
    assert state.age == 1
    assert state.hits == 1
    assert state.time_since_update == 0
    assert state.position_history == []
    assert state.velocity == (0.0, 0.0)
    assert state.recovered_from_low is False
    assert state.low_recoveries == 0


def test_historial_de_posiciones_limitado_a_50(backend):
    """El historial de posiciones no crece sin límite."""
    tracker = ByteTrackAdapter(backend=backend, max_age=60)
    for f in range(70):
        tracker.track([make_detection(100 + 2 * f, 200)], f)

    track_id = tracker.get_tracks()[0]["track_id"]
    history = tracker.get_track_by_id(track_id)["position_history"]
    assert len(history) == 50
    assert tracker.get_tracks()[0]["age"] == 70


def test_lost_tracks_limitado(backend):
    """El histórico de tracks perdidos está acotado."""
    tracker = ByteTrackAdapter(backend=backend, max_age=1)
    tracker.max_lost_tracks = 5

    for f in range(0, 60, 3):
        # cada jugador aparece en una posición distinta y luego desaparece
        tracker.track([make_detection(50 * (f + 1), 200)], f)
        tracker.track([], f + 1)
        tracker.track([], f + 2)

    assert len(tracker.lost_tracks) <= 5
    assert tracker.get_statistics()["lost_tracks"] <= 5


def test_repr_informativo():
    """__repr__ describe la configuración activa."""
    text = repr(ByteTrackAdapter(backend="native", max_age=12, min_hits=2))
    assert "ByteTrackAdapter" in text
    assert "native" in text
    assert "max_age=12" in text


def test_flags_de_dependencias_son_booleanos():
    """Las banderas de dependencias opcionales están expuestas y son bool."""
    assert isinstance(HAS_SUPERVISION, bool)
    assert isinstance(HAS_SCIPY, bool)
    stats = ByteTrackAdapter(backend="native").get_statistics()
    assert stats["has_supervision"] is HAS_SUPERVISION
    assert stats["has_scipy"] is HAS_SCIPY

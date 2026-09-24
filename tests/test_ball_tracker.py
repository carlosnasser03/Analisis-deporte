"""
test_ball_tracker.py - Tests del tracker temporal del balón (core/ball_tracker.py)

Todos los tests usan detecciones sintéticas generadas con numpy/stdlib.
No se abre ningún vídeo ni se carga ningún modelo YOLO.
"""

import math

import numpy as np
import pytest

from core.ball_tracker import BallTracker


# --------------------------------------------------------------------------- #
# Helpers de datos sintéticos
# --------------------------------------------------------------------------- #

def make_candidate(cx, cy, confidence=0.8, size=24.0, with_center=True, with_bbox=True):
    """Construye un candidato con el formato del contrato de integración."""
    candidate = {'confidence': confidence}
    if with_bbox:
        candidate['bbox'] = [cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2]
    if with_center:
        candidate['center'] = [float(cx), float(cy)]
    return candidate


def straight_line(n, x0=100.0, y0=200.0, vx=10.0, vy=0.0):
    """Genera n posiciones en línea recta con velocidad constante."""
    return [(x0 + vx * i, y0 + vy * i) for i in range(n)]


@pytest.fixture
def tracker():
    return BallTracker()


@pytest.fixture
def warm_tracker():
    """Tracker con una trayectoria recta ya establecida (5 detecciones)."""
    t = BallTracker(buffer_size=10, max_displacement_px=150.0, max_missing_frames=15)
    for x, y in straight_line(5):
        t.update([make_candidate(x, y)])
    return t


# --------------------------------------------------------------------------- #
# 1. Estado inicial y configuración
# --------------------------------------------------------------------------- #

def test_estado_inicial(tracker):
    """El tracker arranca vacío y sin predicción."""
    assert len(tracker.buffer) == 0
    assert tracker.predict_next_position() is None
    assert tracker.get_trajectory() == []
    stats = tracker.get_statistics()
    assert stats['frames_processed'] == 0
    assert stats['detection_rate'] == 0.0


@pytest.mark.parametrize("kwargs", [
    {'buffer_size': 0},
    {'buffer_size': -3},
    {'max_displacement_px': 0},
    {'max_displacement_px': -10.0},
    {'max_missing_frames': -1},
])
def test_parametros_invalidos_lanzan_valueerror(kwargs):
    """La configuración fuera de rango falla rápido y con mensaje explícito."""
    with pytest.raises(ValueError):
        BallTracker(**kwargs)


def test_update_devuelve_todas_las_claves_del_contrato(tracker):
    """El dict de salida cumple exactamente el contrato acordado."""
    esperadas = {'detected', 'center', 'bbox', 'confidence',
                 'interpolated', 'frames_missing', 'velocity'}
    resultado = tracker.update([make_candidate(100, 100)])
    assert set(resultado.keys()) == esperadas
    vacio = BallTracker().update([])
    assert set(vacio.keys()) == esperadas


# --------------------------------------------------------------------------- #
# 2. Primer frame / arranque en frío
# --------------------------------------------------------------------------- #

def test_primer_frame_candidato_unico(tracker):
    """Con un solo candidato y sin historia se acepta la detección tal cual."""
    r = tracker.update([make_candidate(300, 400, confidence=0.55)])
    assert r['detected'] is True
    assert r['interpolated'] is False
    assert r['center'] == [300.0, 400.0]
    assert r['bbox'] == [288.0, 388.0, 312.0, 412.0]
    assert r['confidence'] == pytest.approx(0.55)
    assert r['frames_missing'] == 0
    assert r['velocity'] is None  # una sola posición: no hay velocidad


def test_buffer_vacio_elige_mayor_confianza(tracker):
    """Sin buffer no hay criterio espacial: gana la confianza más alta."""
    candidatos = [
        make_candidate(100, 100, confidence=0.31),
        make_candidate(900, 700, confidence=0.92),
        make_candidate(500, 500, confidence=0.60),
    ]
    r = tracker.update(candidatos)
    assert r['detected'] is True
    assert r['center'] == [900.0, 700.0]
    assert r['confidence'] == pytest.approx(0.92)


def test_primer_frame_sin_candidatos_no_interpola(tracker):
    """Sin historia no se puede interpolar: el balón simplemente no está."""
    r = tracker.update([])
    assert r['detected'] is False
    assert r['interpolated'] is False
    assert r['center'] is None
    assert r['bbox'] is None
    assert r['velocity'] is None
    assert r['frames_missing'] == 1
    assert tracker.get_trajectory() == []


# --------------------------------------------------------------------------- #
# 3. Trayectoria recta y predicción
# --------------------------------------------------------------------------- #

def test_trayectoria_recta_prediccion_exacta():
    """Con velocidad constante la extrapolación acierta el siguiente punto."""
    t = BallTracker(buffer_size=10)
    posiciones = straight_line(8, x0=100.0, y0=200.0, vx=10.0, vy=5.0)
    for x, y in posiciones:
        t.update([make_candidate(x, y)])

    pred = t.predict_next_position()
    assert pred is not None
    assert pred[0] == pytest.approx(180.0)  # 100 + 10*8
    assert pred[1] == pytest.approx(240.0)  # 200 + 5*8


def test_velocidad_estimada_coherente(warm_tracker):
    """La velocidad reportada refleja el movimiento real (10 px/frame en x)."""
    r = warm_tracker.update([make_candidate(150, 200)])
    assert r['velocity'] is not None
    assert r['velocity'][0] == pytest.approx(10.0)
    assert r['velocity'][1] == pytest.approx(0.0)


def test_trayectoria_recta_sigue_al_balon():
    """Todas las posiciones de una recta se aceptan como detecciones reales."""
    t = BallTracker()
    for x, y in straight_line(20, vx=12.0, vy=-3.0):
        r = t.update([make_candidate(x, y)])
        assert r['detected'] is True
        assert r['interpolated'] is False
    stats = t.get_statistics()
    assert stats['frames_detected'] == 20
    assert stats['detection_rate'] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# 4. Selección espacial frente a confianza
# --------------------------------------------------------------------------- #

def test_elige_el_mas_cercano_no_el_mas_confiado(warm_tracker):
    """Con historia, la coherencia espacial manda sobre el score de YOLO."""
    pred = warm_tracker.predict_next_position()
    assert pred == pytest.approx((150.0, 200.0))

    candidatos = [
        make_candidate(pred[0] + 2, pred[1] - 1, confidence=0.35),   # el balón
        make_candidate(pred[0] + 90, pred[1] + 60, confidence=0.97),  # cabeza blanca
    ]
    r = warm_tracker.update(candidatos)
    assert r['detected'] is True
    assert r['center'] == [pytest.approx(152.0), pytest.approx(199.0)]
    assert r['confidence'] == pytest.approx(0.35)


def test_falso_positivo_lejano_rechazado(warm_tracker):
    """Un candidato a >max_displacement_px de la predicción se descarta."""
    pred = warm_tracker.predict_next_position()
    lejano = make_candidate(pred[0] + 600, pred[1] + 400, confidence=0.99)

    r = warm_tracker.update([lejano])
    assert r['detected'] is False
    assert r['interpolated'] is True
    assert r['center'] == [pytest.approx(pred[0]), pytest.approx(pred[1])]
    assert warm_tracker.get_statistics()['candidates_rejected_displacement'] == 1


def test_limite_de_desplazamiento_es_inclusivo():
    """Justo en el límite se acepta; un píxel más allá se rechaza."""
    for offset, esperado in [(150.0, True), (150.5, False)]:
        t = BallTracker(max_displacement_px=150.0)
        for x, y in straight_line(4, vx=0.0):  # balón quieto en (100, 200)
            t.update([make_candidate(x, y)])
        pred = t.predict_next_position()
        r = t.update([make_candidate(pred[0] + offset, pred[1], confidence=0.9)])
        assert r['detected'] is esperado


def test_multiples_falsos_positivos_todos_rechazados(warm_tracker):
    """Si ningún candidato es plausible, todos cuentan como rechazados."""
    pred = warm_tracker.predict_next_position()
    candidatos = [
        make_candidate(pred[0] + 500, pred[1], confidence=0.9),
        make_candidate(pred[0], pred[1] + 700, confidence=0.8),
        make_candidate(pred[0] - 400, pred[1] - 400, confidence=0.7),
    ]
    r = warm_tracker.update(candidatos)
    assert r['interpolated'] is True
    assert warm_tracker.get_statistics()['candidates_rejected_displacement'] == 3


# --------------------------------------------------------------------------- #
# 5. Oclusión e interpolación
# --------------------------------------------------------------------------- #

def test_oclusion_temporal_interpola_y_cuenta_frames(warm_tracker):
    """Durante la oclusión se devuelve la posición predicha, marcada como tal."""
    for i in range(1, 6):
        r = warm_tracker.update([])
        assert r['detected'] is False
        assert r['interpolated'] is True
        assert r['center'] is not None
        assert r['frames_missing'] == i
        assert r['bbox'] is not None  # bbox sintético con el último tamaño conocido

    stats = warm_tracker.get_statistics()
    assert stats['frames_interpolated'] == 5
    assert stats['frames_lost'] == 0


def test_interpolacion_avanza_con_la_velocidad(warm_tracker):
    """La posición interpolada sigue la trayectoria, no se congela."""
    r1 = warm_tracker.update([])
    r2 = warm_tracker.update([])
    r3 = warm_tracker.update([])
    assert r2['center'][0] > r1['center'][0]
    assert r3['center'][0] > r2['center'][0]
    # Movimiento uniforme: los pasos interpolados son ~constantes
    paso1 = r2['center'][0] - r1['center'][0]
    paso2 = r3['center'][0] - r2['center'][0]
    assert paso1 == pytest.approx(paso2, abs=1.0)


def test_reenganche_tras_oclusion_corta(warm_tracker):
    """Tras la oclusión, una detección coherente vuelve a confirmarse."""
    for _ in range(3):
        warm_tracker.update([])
    pred = warm_tracker.predict_next_position()
    r = warm_tracker.update([make_candidate(pred[0] + 5, pred[1] + 3, confidence=0.7)])
    assert r['detected'] is True
    assert r['interpolated'] is False
    assert r['frames_missing'] == 0


def test_bbox_interpolado_conserva_tamano():
    """El bbox sintético mantiene el ancho/alto del último bbox real."""
    t = BallTracker()
    for x, y in straight_line(4):
        t.update([make_candidate(x, y, size=30.0)])
    r = t.update([])
    x1, y1, x2, y2 = r['bbox']
    assert (x2 - x1) == pytest.approx(30.0)
    assert (y2 - y1) == pytest.approx(30.0)
    assert ((x1 + x2) / 2) == pytest.approx(r['center'][0])


# --------------------------------------------------------------------------- #
# 6. Pérdida larga y reinicio
# --------------------------------------------------------------------------- #

def test_perdida_larga_declara_balon_perdido():
    """Pasado max_missing_frames el balón se da por perdido y el buffer se limpia."""
    t = BallTracker(max_missing_frames=4)
    for x, y in straight_line(5):
        t.update([make_candidate(x, y)])

    for _ in range(4):
        assert t.update([])['interpolated'] is True

    r = t.update([])
    assert r['detected'] is False
    assert r['interpolated'] is False
    assert r['center'] is None
    assert r['bbox'] is None
    assert r['velocity'] is None
    assert r['frames_missing'] == 5
    assert len(t.buffer) == 0
    assert t.predict_next_position() is None
    assert t.get_statistics()['track_losses'] == 1


def test_reinicio_tras_perdida_acepta_deteccion_lejana():
    """Con el buffer limpio se vuelve al criterio de confianza, sin límite espacial."""
    t = BallTracker(max_missing_frames=2)
    for x, y in straight_line(5):
        t.update([make_candidate(x, y)])
    for _ in range(4):  # 2 interpolados + pérdida
        t.update([])

    lejos = make_candidate(1600, 900, confidence=0.61)
    r = t.update([lejos])
    assert r['detected'] is True
    assert r['center'] == [1600.0, 900.0]
    assert r['frames_missing'] == 0


def test_frames_perdidos_consecutivos_no_generan_trayectoria():
    """Los frames con balón perdido no añaden puntos a la trayectoria."""
    t = BallTracker(max_missing_frames=1)
    t.update([make_candidate(100, 100)])
    t.update([])          # interpolado
    puntos_antes = len(t.get_trajectory())
    for _ in range(5):    # perdidos
        t.update([])
    assert len(t.get_trajectory()) == puntos_antes
    assert t.get_statistics()['frames_lost'] == 5


# --------------------------------------------------------------------------- #
# 7. Robustez ante entradas malformadas
# --------------------------------------------------------------------------- #

def test_candidatos_none_no_rompe(tracker):
    """`None` se trata como 'sin candidatos'."""
    r = tracker.update(None)
    assert r['detected'] is False
    assert r['center'] is None


def test_candidatos_malformados_se_ignoran(tracker):
    """Entradas basura se descartan sin excepción y se contabilizan."""
    basura = [
        None,
        "no soy un dict",
        42,
        {},
        {'bbox': [1, 2, 3]},                       # longitud incorrecta
        {'bbox': [1, 2, 'x', 4]},                  # tipo incorrecto
        {'bbox': [1, 2, float('nan'), 4]},         # NaN
        {'center': [float('inf'), 10]},            # inf
        {'center': [10]},                          # longitud incorrecta
        {'confidence': 0.9},                       # sin posición
    ]
    r = tracker.update(basura)
    assert r['detected'] is False
    assert tracker.get_statistics()['candidates_invalid'] == len(basura)


def test_mezcla_de_validos_e_invalidos(tracker):
    """Un candidato válido entre basura se sigue eligiendo."""
    r = tracker.update([None, {'bbox': [0, 0]}, make_candidate(640, 360, confidence=0.5)])
    assert r['detected'] is True
    assert r['center'] == [640.0, 360.0]


def test_centro_derivado_del_bbox(tracker):
    """Si falta 'center' se calcula desde el bbox."""
    r = tracker.update([{'bbox': [100.0, 200.0, 140.0, 260.0], 'confidence': 0.7}])
    assert r['center'] == [120.0, 230.0]


def test_bbox_con_esquinas_invertidas_se_normaliza(tracker):
    """Un bbox [x2,y2,x1,y1] se reordena en vez de descartarse."""
    r = tracker.update([{'bbox': [140.0, 260.0, 100.0, 200.0], 'confidence': 0.7}])
    assert r['bbox'] == [100.0, 200.0, 140.0, 260.0]
    assert r['center'] == [120.0, 230.0]


def test_confianza_ausente_o_fuera_de_rango(tracker):
    """La confianza se sanea a [0, 1]; si falta, vale 0.0."""
    r = tracker.update([{'center': [50.0, 50.0]}])
    assert r['confidence'] == 0.0
    assert r['bbox'] is None

    t2 = BallTracker()
    r2 = t2.update([make_candidate(10, 10, confidence=5.0)])
    assert r2['confidence'] == 1.0

    t3 = BallTracker()
    r3 = t3.update([make_candidate(10, 10, confidence=-2.0)])
    assert r3['confidence'] == 0.0


def test_acepta_dict_unico_y_arrays_numpy(tracker):
    """Se admite un dict suelto y coordenadas en np.ndarray."""
    r = tracker.update({'center': np.array([320.0, 180.0]), 'confidence': 0.8})
    assert r['detected'] is True
    assert r['center'] == [320.0, 180.0]

    t2 = BallTracker()
    r2 = t2.update([{'bbox': np.array([10.0, 20.0, 30.0, 40.0]), 'confidence': 0.5}])
    assert r2['center'] == [20.0, 30.0]


# --------------------------------------------------------------------------- #
# 8. Buffer, trayectoria, estadísticas y reset
# --------------------------------------------------------------------------- #

def test_buffer_respeta_su_capacidad():
    """El deque nunca supera buffer_size posiciones."""
    t = BallTracker(buffer_size=4)
    for x, y in straight_line(20):
        t.update([make_candidate(x, y)])
    assert len(t.buffer) == 4
    assert t.get_statistics()['buffer_length'] == 4


def test_get_trajectory_estructura_y_frame_ids():
    """La trayectoria registra frame_id, marca interpolados y es una copia."""
    t = BallTracker()
    for i, (x, y) in enumerate(straight_line(3)):
        t.update([make_candidate(x, y)], frame_id=100 + i)
    t.update([], frame_id=103)

    traj = t.get_trajectory()
    assert [p['frame_id'] for p in traj] == [100, 101, 102, 103]
    assert [p['interpolated'] for p in traj] == [False, False, False, True]
    assert all(set(p.keys()) == {'frame_id', 'center', 'bbox', 'confidence',
                                 'interpolated', 'velocity'} for p in traj)

    traj[0]['center'] = None  # mutar la copia no afecta al estado interno
    assert t.get_trajectory()[0]['center'] is not None


def test_frame_id_automatico_cuando_es_none():
    """Sin frame_id explícito se usa un contador interno incremental."""
    t = BallTracker()
    for x, y in straight_line(3):
        t.update([make_candidate(x, y)])
    assert [p['frame_id'] for p in t.get_trajectory()] == [0, 1, 2]
    assert t.frame_count == 3


def test_get_statistics_campos_y_tasas():
    """Las tasas se calculan sobre los frames procesados."""
    t = BallTracker(max_missing_frames=10)
    for x, y in straight_line(6):
        t.update([make_candidate(x, y)])
    for _ in range(2):
        t.update([])

    s = t.get_statistics()
    assert s['frames_processed'] == 8
    assert s['frames_detected'] == 6
    assert s['frames_interpolated'] == 2
    assert s['detection_rate'] == pytest.approx(6 / 8)
    assert s['interpolation_rate'] == pytest.approx(2 / 8)
    assert s['coverage_rate'] == pytest.approx(1.0)
    assert s['max_displacement_px'] == 150.0
    assert s['max_missing_frames'] == 10
    assert s['current_velocity'] is not None


def test_reset_limpia_todo(warm_tracker):
    """reset() devuelve el tracker a su estado inicial."""
    warm_tracker.update([])
    warm_tracker.reset()

    assert len(warm_tracker.buffer) == 0
    assert warm_tracker.get_trajectory() == []
    assert warm_tracker.predict_next_position() is None
    assert warm_tracker.frame_count == 0
    s = warm_tracker.get_statistics()
    assert s['frames_processed'] == 0
    assert s['frames_detected'] == 0
    assert s['frames_interpolated'] == 0
    assert s['track_losses'] == 0


# --------------------------------------------------------------------------- #
# 9. Escenario integrado
# --------------------------------------------------------------------------- #

def test_secuencia_realista_con_ruido_y_huecos():
    """Recta con falsos positivos y huecos: el track sobrevive sin saltos."""
    rng = np.random.default_rng(42)
    t = BallTracker(buffer_size=8, max_displacement_px=120.0, max_missing_frames=10)

    verdaderas = straight_line(40, x0=200.0, y0=300.0, vx=15.0, vy=4.0)
    for i, (x, y) in enumerate(verdaderas):
        candidatos = []
        if i % 5 != 3:  # 1 de cada 5 frames el detector pierde el balón
            ruido = rng.normal(0.0, 1.5, size=2)
            candidatos.append(make_candidate(x + ruido[0], y + ruido[1], confidence=0.45))
        # Falso positivo fijo (línea de banda) muy confiado pero estático.
        # Aparece a partir del frame 3, cuando ya hay trayectoria establecida:
        # en frío el tracker solo dispone del criterio de confianza.
        if i >= 3:
            candidatos.append(make_candidate(50.0, 1000.0, confidence=0.95))

        r = t.update(candidatos, frame_id=i)
        assert r['center'] is not None
        assert math.hypot(r['center'][0] - x, r['center'][1] - y) < 40.0

    s = t.get_statistics()
    assert s['frames_processed'] == 40
    assert s['frames_lost'] == 0
    assert s['track_losses'] == 0
    assert s['coverage_rate'] == pytest.approx(1.0)
    assert s['candidates_rejected_displacement'] >= 1

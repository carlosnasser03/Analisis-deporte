"""
test_inference_slicer.py - Tests de InferenceSlicer y RegionOfInterestSlicer

Cubre los cuatro puntos criticos de la inferencia por tiles:
  1. Traslacion de coordenadas tile -> frame (con casos calculados a mano).
  2. Deduplicacion por NMS de los objetos que caen en zonas de solape.
  3. Recorte correcto de los tiles de borde (sin padding).
  4. Numero de tiles / coste, incluyendo la reduccion que aporta el ROI slicer.

No se carga ningun modelo: `detect_fn` se inyecta como mock o como detector
clasico de OpenCV sobre frames sinteticos de numpy.
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.inference_slicer import (  # noqa: E402
    InferenceSlicer,
    RegionOfInterestSlicer,
    compute_containment_matrix,
    compute_iou,
    compute_iou_matrix,
    non_max_suppression,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_frame(width: int = 1280, height: int = 720, channels: int = 3) -> np.ndarray:
    """Frame sintetico negro."""
    if channels is None:
        return np.zeros((height, width), dtype=np.uint8)
    return np.zeros((height, width, channels), dtype=np.uint8)


def draw_square(frame: np.ndarray, x: int, y: int, size: int = 20) -> None:
    """Dibuja un cuadrado blanco relleno en [x, x+size) x [y, y+size)."""
    frame[y : y + size, x : x + size] = 255


def contour_detect_fn(tile: np.ndarray):
    """
    detect_fn realista sin modelo: encuentra blobs blancos con OpenCV.

    Devuelve bboxes EN COORDENADAS DEL TILE, que es exactamente lo que el slicer
    espera que produzca un detector.
    """
    gray = tile if tile.ndim == 2 else cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detections = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        detections.append(
            {
                "bbox": [float(x), float(y), float(x + w), float(y + h)],
                "confidence": 0.9,
                "class_id": 0,
            }
        )
    return detections


def constant_detect_fn(bbox, confidence: float = 0.9, class_id: int = 0):
    """Fabrica un detect_fn que devuelve siempre el mismo bbox local."""

    def _fn(tile: np.ndarray):
        return [{"bbox": list(bbox), "confidence": confidence, "class_id": class_id}]

    return _fn


def recording_detect_fn(store):
    """detect_fn que registra el shape de cada tile recibido y no detecta nada."""

    def _fn(tile: np.ndarray):
        store.append(tile.shape)
        return []

    return _fn


# ---------------------------------------------------------------------------
# 1. Construccion y validacion
# ---------------------------------------------------------------------------

def test_init_defaults():
    """Los defaults son los del contrato y el paso se deriva del solape."""
    slicer = InferenceSlicer()
    assert slicer.slice_wh == (640, 640)
    assert slicer.overlap_ratio == 0.2
    assert slicer.iou_threshold == 0.5
    assert slicer.max_slices is None
    assert slicer.containment_threshold == 0.8
    # 640 * (1 - 0.2) = 512
    assert slicer.step_wh == (512, 512)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"slice_wh": (0, 640)},
        {"slice_wh": (640, -1)},
        {"overlap_ratio": 1.0},
        {"overlap_ratio": -0.1},
        {"iou_threshold": 1.5},
        {"iou_threshold": -0.2},
        {"max_slices": 0},
        {"containment_threshold": 0.0},
        {"containment_threshold": 1.5},
    ],
)
def test_init_rechaza_parametros_invalidos(kwargs):
    """Cada parametro fuera de rango produce ValueError explicito."""
    with pytest.raises(ValueError):
        InferenceSlicer(**kwargs)


@pytest.mark.parametrize(
    "bad_frame",
    ["no soy un frame", None, np.zeros((10,), dtype=np.uint8), np.zeros((0, 10, 3))],
)
def test_frame_invalido_lanza_valueerror(bad_frame):
    """Un frame que no es ndarray 2D/3D no vacio se rechaza con contexto."""
    slicer = InferenceSlicer()
    with pytest.raises(ValueError):
        slicer.slice_frame(bad_frame)


# ---------------------------------------------------------------------------
# 2. Rejilla de tiles (offsets calculados a mano)
# ---------------------------------------------------------------------------

def test_slice_frame_rejilla_exacta_1280x720():
    """
    Caso calculado a mano.

    Frame 1280x720, tile 640x640, solape 0.2 -> paso 512.
      eje X: 0, 512, 1024        (1024 + 640 = 1664 >= 1280 -> ultimo)
      eje Y: 0, 512              (512 + 640 = 1152 >= 720  -> ultimo)
    Anchos reales: 640, 640, 1280-1024=256. Altos: 640, 720-512=208.
    """
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    slices = slicer.slice_frame(make_frame(1280, 720))

    assert len(slices) == 6
    assert [s["offset"] for s in slices] == [
        (0, 0), (512, 0), (1024, 0),
        (0, 512), (512, 512), (1024, 512),
    ]
    assert [s["size"] for s in slices] == [
        (640, 640), (640, 640), (256, 640),
        (640, 208), (640, 208), (256, 208),
    ]
    assert [s["index"] for s in slices] == [0, 1, 2, 3, 4, 5]
    for tile in slices:
        w, h = tile["size"]
        assert tile["image"].shape[:2] == (h, w)


def test_slice_frame_tiles_contienen_los_pixeles_correctos():
    """El contenido de cada tile es exactamente la region del frame en su offset."""
    frame = np.random.default_rng(0).integers(
        0, 255, size=(500, 800, 3), dtype=np.uint8
    )
    slicer = InferenceSlicer(slice_wh=(300, 300), overlap_ratio=0.25)

    for tile in slicer.slice_frame(frame):
        ox, oy = tile["offset"]
        w, h = tile["size"]
        np.testing.assert_array_equal(tile["image"], frame[oy : oy + h, ox : ox + w])


def test_tiles_de_borde_recortados_sin_padding():
    """
    Ningun tile se sale del frame y los de borde son mas pequenos (no rellenados).

    Frame 1000x600 con tiles de 400x400 y solape 0.25 (paso 300).
    """
    frame = make_frame(1000, 600)
    slicer = InferenceSlicer(slice_wh=(400, 400), overlap_ratio=0.25)
    slices = slicer.slice_frame(frame)

    for tile in slices:
        x1, y1, x2, y2 = tile["bounds"]
        assert 0 <= x1 < x2 <= 1000
        assert 0 <= y1 < y2 <= 600
        assert tile["image"].shape[0] == y2 - y1
        assert tile["image"].shape[1] == x2 - x1

    # El ultimo tile de la fila arranca en 600 y mide 1000-600 = 400 -> no recortado
    # en X, pero en Y el ultimo arranca en 300 y mide 600-300 = 300 < 400.
    alturas = {t["size"][1] for t in slices}
    assert 300 in alturas, "el tile de borde inferior deberia estar recortado a 300 px"
    assert max(t["bounds"][3] for t in slices) == 600


def test_cobertura_completa_del_frame():
    """Cada pixel del frame queda cubierto por al menos un tile."""
    width, height = 1280, 720
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    cobertura = np.zeros((height, width), dtype=np.int32)

    for tile in slicer.slice_frame(make_frame(width, height)):
        x1, y1, x2, y2 = tile["bounds"]
        cobertura[y1:y2, x1:x2] += 1

    assert cobertura.min() >= 1
    assert cobertura.max() >= 2, "con solape debe haber pixeles cubiertos dos veces"


def test_frame_mas_pequeno_que_un_tile():
    """Un frame menor que el tile produce un unico tile completo con offset (0,0)."""
    frame = make_frame(320, 240)
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    slices = slicer.slice_frame(frame)

    assert len(slices) == 1
    assert slices[0]["offset"] == (0, 0)
    assert slices[0]["size"] == (320, 240)
    assert slices[0]["image"].shape == frame.shape


def test_frame_exactamente_del_tamano_del_tile():
    """Sin borde sobrante tampoco se generan tiles extra."""
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    slices = slicer.slice_frame(make_frame(640, 640))
    assert len(slices) == 1
    assert slices[0]["size"] == (640, 640)


def test_overlap_cero_genera_teselado_disjunto():
    """
    Con overlap_ratio=0 los tiles no se solapan y suman exactamente el area del frame.

    Frame 1000x500, tile 300x200 -> X: 0,300,600,900 ; Y: 0,200,400.
    """
    slicer = InferenceSlicer(slice_wh=(300, 200), overlap_ratio=0.0)
    slices = slicer.slice_frame(make_frame(1000, 500))

    assert slicer.step_wh == (300, 200)
    assert len(slices) == 12
    assert [s["offset"] for s in slices][:4] == [(0, 0), (300, 0), (600, 0), (900, 0)]

    cobertura = np.zeros((500, 1000), dtype=np.int32)
    for tile in slices:
        x1, y1, x2, y2 = tile["bounds"]
        cobertura[y1:y2, x1:x2] += 1
    assert cobertura.min() == 1 and cobertura.max() == 1

    area_total = sum(t["size"][0] * t["size"][1] for t in slices)
    assert area_total == 1000 * 500


def test_overlap_alto_genera_muchos_tiles_todos_dentro_del_frame():
    """Solape 0.75 -> paso 25 px con tiles de 100 px: rejilla densa y valida."""
    slicer = InferenceSlicer(slice_wh=(100, 100), overlap_ratio=0.75)
    assert slicer.step_wh == (25, 25)

    slices = slicer.slice_frame(make_frame(400, 400))
    # X: 0,25,...,300 -> 13 posiciones; idem en Y.
    assert len(slices) == 13 * 13
    for tile in slices:
        x1, y1, x2, y2 = tile["bounds"]
        assert 0 <= x1 < x2 <= 400 and 0 <= y1 < y2 <= 400


def test_max_slices_trunca_la_rejilla():
    """max_slices acota el coste y deja constancia en las estadisticas."""
    slicer = InferenceSlicer(slice_wh=(100, 100), overlap_ratio=0.5, max_slices=5)
    slices = slicer.slice_frame(make_frame(800, 800))

    assert len(slices) == 5
    assert slicer.get_statistics()["truncated_frames"] == 1
    assert slicer.count_slices((800, 800, 3)) == 5


def test_count_slices_coincide_con_slice_frame():
    """count_slices permite estimar el coste sin recortar imagenes."""
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    frame = make_frame(1920, 1080)
    assert slicer.count_slices(frame.shape) == len(slicer.slice_frame(frame))


def test_frame_en_escala_de_grises():
    """Un frame 2D (H, W) tambien se puede trocear."""
    frame = make_frame(700, 500, channels=None)
    assert frame.ndim == 2
    slices = InferenceSlicer(slice_wh=(400, 400), overlap_ratio=0.2).slice_frame(frame)
    assert all(t["image"].ndim == 2 for t in slices)
    assert len(slices) > 1


# ---------------------------------------------------------------------------
# 3. Traslacion de coordenadas (el bug clasico)
# ---------------------------------------------------------------------------

def test_traslacion_exacta_calculada_a_mano():
    """
    CASO CALCULADO A MANO.

    Frame 1280x720, tiles 640x640, solape 0.2 -> offsets
      (0,0) (512,0) (1024,0) (0,512) (512,512) (1024,512)
    detect_fn devuelve SIEMPRE el bbox local [10, 20, 30, 40].
    Los bboxes absolutos esperados son offset + bbox, sin excepcion.
    """
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    detecciones = slicer.run(make_frame(1280, 720), constant_detect_fn([10, 20, 30, 40]))

    esperados = [
        [10.0, 20.0, 30.0, 40.0],
        [522.0, 20.0, 542.0, 40.0],
        [1034.0, 20.0, 1054.0, 40.0],
        [10.0, 532.0, 30.0, 552.0],
        [522.0, 532.0, 542.0, 552.0],
        [1034.0, 532.0, 1054.0, 552.0],
    ]
    assert [d["bbox"] for d in detecciones] == esperados

    # El centro se calcula desde el bbox ya trasladado.
    assert [d["center"] for d in detecciones] == [
        [20.0, 30.0],
        [532.0, 30.0],
        [1044.0, 30.0],
        [20.0, 542.0],
        [532.0, 542.0],
        [1044.0, 542.0],
    ]


def test_traslacion_por_tile_individual():
    """Una deteccion emitida solo en el tile 4 aterriza en el offset del tile 4."""
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    slices = slicer.slice_frame(make_frame(1280, 720))
    offset_objetivo = slices[4]["offset"]  # (512, 512)
    assert offset_objetivo == (512, 512)

    llamadas = {"n": 0}

    def detect_fn(tile):
        idx = llamadas["n"]
        llamadas["n"] += 1
        if idx != 4:
            return []
        return [{"bbox": [100.0, 50.0, 140.0, 90.0], "confidence": 0.8}]

    detecciones = slicer.run(make_frame(1280, 720), detect_fn)
    assert len(detecciones) == 1
    assert detecciones[0]["bbox"] == [612.0, 562.0, 652.0, 602.0]
    assert detecciones[0]["slice_offset"] == (512, 512)
    assert detecciones[0]["slice_index"] == 4


def test_center_proporcionado_por_detect_fn_tambien_se_traslada():
    """Si detect_fn ya devuelve 'center', se traslada en vez de recalcularse."""
    slicer = InferenceSlicer(slice_wh=(400, 400), overlap_ratio=0.0)

    def detect_fn(tile):
        return [{"bbox": [0.0, 0.0, 10.0, 10.0], "center": [3.0, 7.0], "confidence": 0.5}]

    detecciones = slicer.run(make_frame(800, 400), detect_fn)
    centros = sorted(tuple(d["center"]) for d in detecciones)
    assert centros == [(3.0, 7.0), (403.0, 7.0)]


def test_detecciones_trasladadas_dentro_de_los_limites_del_frame():
    """Ningun bbox fusionado se sale del frame."""
    width, height = 900, 700
    slicer = InferenceSlicer(slice_wh=(400, 400), overlap_ratio=0.2)
    detecciones = slicer.run(
        make_frame(width, height), constant_detect_fn([5, 5, 395, 395])
    )
    assert detecciones
    for det in detecciones:
        x1, y1, x2, y2 = det["bbox"]
        assert 0 <= x1 <= x2 <= width
        assert 0 <= y1 <= y2 <= height


def test_detect_fn_recibe_tiles_con_el_tamano_de_la_rejilla():
    """Los shapes que ve detect_fn coinciden con los de slice_frame."""
    frame = make_frame(1000, 600)
    slicer = InferenceSlicer(slice_wh=(400, 400), overlap_ratio=0.25)
    esperados = [(t["size"][1], t["size"][0], 3) for t in slicer.slice_frame(frame)]

    vistos = []
    slicer.run(frame, recording_detect_fn(vistos))
    assert vistos == esperados


# ---------------------------------------------------------------------------
# 4. IoU y NMS
# ---------------------------------------------------------------------------

def test_compute_iou_valor_calculado_a_mano():
    """[0,0,10,10] vs [5,5,15,15]: interseccion 25, union 175 -> 1/7."""
    assert compute_iou([0, 0, 10, 10], [5, 5, 15, 15]) == pytest.approx(25.0 / 175.0)


def test_compute_iou_casos_limite():
    """Cajas disjuntas, identicas, contenidas y de area nula."""
    assert compute_iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
    assert compute_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert compute_iou([0, 0, 10, 10], [0, 0, 5, 10]) == pytest.approx(0.5)
    assert compute_iou([0, 0, 0, 0], [0, 0, 0, 0]) == 0.0
    # Contacto por el borde: interseccion de area cero.
    assert compute_iou([0, 0, 10, 10], [10, 0, 20, 10]) == 0.0


def test_compute_iou_matrix_forma_y_vacios():
    """La matriz tiene shape (N, M) y tolera conjuntos vacios."""
    m = compute_iou_matrix([[0, 0, 10, 10], [5, 5, 15, 15]], [[0, 0, 10, 10]])
    assert m.shape == (2, 1)
    assert m[0, 0] == 1.0
    assert compute_iou_matrix([], [[0, 0, 1, 1]]).shape == (0, 1)


def test_nms_elimina_duplicados_y_conserva_la_mayor_confianza():
    """Dos cajas casi identicas colapsan en la de mayor confianza."""
    dets = [
        {"bbox": [100, 100, 140, 140], "confidence": 0.6, "class_id": 0},
        {"bbox": [102, 101, 142, 141], "confidence": 0.95, "class_id": 0},
    ]
    fusionadas = non_max_suppression(dets, iou_threshold=0.5)
    assert len(fusionadas) == 1
    assert fusionadas[0]["confidence"] == 0.95


def test_nms_conserva_objetos_distintos():
    """Objetos separados no se suprimen entre si."""
    dets = [
        {"bbox": [0, 0, 20, 20], "confidence": 0.9, "class_id": 0},
        {"bbox": [500, 500, 520, 520], "confidence": 0.8, "class_id": 0},
        {"bbox": [900, 100, 930, 130], "confidence": 0.7, "class_id": 0},
    ]
    assert len(non_max_suppression(dets, iou_threshold=0.5)) == 3


def test_nms_es_por_clase():
    """Dos cajas identicas de clases distintas se conservan ambas."""
    dets = [
        {"bbox": [10, 10, 50, 50], "confidence": 0.9, "class_id": 0},
        {"bbox": [10, 10, 50, 50], "confidence": 0.8, "class_id": 1},
    ]
    assert len(non_max_suppression(dets, iou_threshold=0.5)) == 2
    # En modo class-agnostic si se suprime una.
    assert len(non_max_suppression(dets, iou_threshold=0.5, class_agnostic=True)) == 1


def test_nms_umbral_estricto():
    """El umbral se aplica como IoU > thr: con thr=1.0 no se suprime nada."""
    dets = [
        {"bbox": [0, 0, 10, 10], "confidence": 0.9, "class_id": 0},
        {"bbox": [0, 0, 10, 10], "confidence": 0.8, "class_id": 0},
    ]
    assert len(non_max_suppression(dets, iou_threshold=1.0)) == 2
    assert len(non_max_suppression(dets, iou_threshold=0.9)) == 1


def test_nms_ordena_por_confianza_descendente():
    """La salida sale ordenada de mayor a menor confianza."""
    dets = [
        {"bbox": [0, 0, 10, 10], "confidence": 0.3, "class_id": 0},
        {"bbox": [100, 100, 110, 110], "confidence": 0.9, "class_id": 0},
        {"bbox": [200, 200, 210, 210], "confidence": 0.6, "class_id": 0},
    ]
    confs = [d["confidence"] for d in non_max_suppression(dets, iou_threshold=0.5)]
    assert confs == [0.9, 0.6, 0.3]


def test_merge_detections_lista_vacia():
    """merge_detections tolera la lista vacia."""
    assert InferenceSlicer().merge_detections([]) == []


def test_merge_detections_formato_invalido():
    """Un dict sin 'bbox' produce ValueError con contexto, no un KeyError pelado."""
    with pytest.raises(ValueError):
        InferenceSlicer().merge_detections([{"confidence": 0.5}])


# ---------------------------------------------------------------------------
# 5. Deduplicacion end-to-end en la zona de solape
# ---------------------------------------------------------------------------

def test_nms_deduplica_objeto_en_zona_de_solape():
    """
    CASO CALCULADO A MANO, end-to-end con un detector real de OpenCV.

    Frame 800x600, tiles 400x400, solape 0.25 -> paso 300.
      X: 0, 300, 600   (anchos 400, 400, 200)
      Y: 0, 300        (altos 400, 300)
    Cuadrado blanco 20x20 en x=[400,420), y=[300,320):
      - tile x=[300,700) y=[0,400)   lo contiene entero -> deteccion local (100,300)
      - tile x=[300,700) y=[300,600) lo contiene entero -> deteccion local (100,0)
      - el resto de tiles no lo tocan
    Las dos detecciones trasladadas son identicas (IoU = 1.0) -> el NMS deja una.
    """
    frame = make_frame(800, 600)
    draw_square(frame, x=400, y=300, size=20)

    slicer = InferenceSlicer(slice_wh=(400, 400), overlap_ratio=0.25, iou_threshold=0.5)
    detecciones = slicer.run(frame, contour_detect_fn)

    assert len(detecciones) == 1, "el duplicado del solape deberia haberse fusionado"
    assert detecciones[0]["bbox"] == [400.0, 300.0, 420.0, 320.0]
    assert detecciones[0]["center"] == [410.0, 310.0]

    stats = slicer.get_statistics()
    assert stats["raw_detections"] == 2
    assert stats["merged_detections"] == 1
    assert stats["suppressed_detections"] == 1


def test_sin_nms_el_duplicado_del_solape_sobrevive():
    """Control del test anterior: sin NMS se ven los dos duplicados del solape."""
    frame = make_frame(800, 600)
    draw_square(frame, x=400, y=300, size=20)

    slicer = InferenceSlicer(
        slice_wh=(400, 400),
        overlap_ratio=0.25,
        iou_threshold=1.0,
        containment_threshold=None,
    )
    detecciones = slicer.run(frame, contour_detect_fn)

    assert len(detecciones) == 2
    assert all(d["bbox"] == [400.0, 300.0, 420.0, 320.0] for d in detecciones)


def test_objeto_cortado_por_el_borde_de_un_tile_se_fusiona_por_contencion():
    """
    CASO CALCULADO A MANO: fragmento de borde.

    Frame 1280x720, tiles 640x640, solape 0.2. El tile 1 abarca x=[512,1152) y el
    tile 2 x=[1024,1280). Un cuadrado en x=[1150,1166) queda CORTADO por el borde
    del tile 1: ese tile solo ve 2 px de ancho.
      - tile 1 -> fragmento absoluto [1150, 620, 1152, 636]
      - tile 2 -> objeto entero      [1150, 620, 1166, 636]
    El IoU entre ambos es 2*16 / (16*16) = 0.125, por debajo del umbral 0.5: un NMS
    de IoU puro los dejaria como dos objetos. La contencion vale 1.0 y los fusiona,
    conservando el entero (desempate por area a igualdad de confianza).
    """
    frame = make_frame(1280, 720)
    draw_square(frame, x=1150, y=620, size=16)

    sin_contencion = InferenceSlicer(
        slice_wh=(640, 640), overlap_ratio=0.2, containment_threshold=None
    ).run(frame, contour_detect_fn)
    assert len(sin_contencion) == 2
    assert compute_iou(
        sin_contencion[0]["bbox"], sin_contencion[1]["bbox"]
    ) == pytest.approx(0.125)

    con_contencion = InferenceSlicer(
        slice_wh=(640, 640), overlap_ratio=0.2, containment_threshold=0.8
    ).run(frame, contour_detect_fn)
    assert len(con_contencion) == 1
    assert con_contencion[0]["bbox"] == [1150.0, 620.0, 1166.0, 636.0]


def test_varios_objetos_pequenos_en_el_frame_completo():
    """Tres objetos separados se recuperan una sola vez cada uno."""
    frame = make_frame(1280, 720)
    posiciones = [(100, 100), (640, 360), (1150, 620)]
    for x, y in posiciones:
        draw_square(frame, x=x, y=y, size=16)

    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2, iou_threshold=0.5)
    detecciones = slicer.run(frame, contour_detect_fn)

    encontrados = sorted((d["bbox"][0], d["bbox"][1]) for d in detecciones)
    assert encontrados == [(100.0, 100.0), (640.0, 360.0), (1150.0, 620.0)]


# ---------------------------------------------------------------------------
# 6. detect_fn degenerado
# ---------------------------------------------------------------------------

def test_detect_fn_sin_detecciones_devuelve_lista_vacia():
    """detect_fn que devuelve [] en todos los tiles."""
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    assert slicer.run(make_frame(1280, 720), lambda tile: []) == []
    assert slicer.get_statistics()["raw_detections"] == 0


def test_detect_fn_devuelve_none():
    """detect_fn que devuelve None se trata como 'sin detecciones'."""
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    assert slicer.run(make_frame(1280, 720), lambda tile: None) == []
    assert slicer.get_statistics()["total_slices"] == 6


def test_detect_fn_que_lanza_excepcion_no_rompe_el_frame():
    """Un fallo del detector en un tile se registra y el resto del frame continua."""
    llamadas = {"n": 0}

    def detect_fn(tile):
        llamadas["n"] += 1
        if llamadas["n"] == 2:
            raise RuntimeError("fallo simulado del modelo")
        return [{"bbox": [0.0, 0.0, 10.0, 10.0], "confidence": 0.5}]

    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    detecciones = slicer.run(make_frame(1280, 720), detect_fn)

    assert len(detecciones) == 5  # 6 tiles - 1 que fallo
    assert slicer.get_statistics()["detect_fn_errors"] == 1


def test_detecciones_con_formato_invalido_se_descartan():
    """bbox de longitud incorrecta, no numerico o ausente: se ignoran con warning."""
    def detect_fn(tile):
        return [
            {"bbox": [1, 2, 3], "confidence": 0.9},
            {"confidence": 0.9},
            {"bbox": "no soy una caja", "confidence": 0.9},
            "ni siquiera soy un dict",
            {"bbox": [0.0, 0.0, 10.0, 10.0], "confidence": 0.9},
        ]

    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.0)
    detecciones = slicer.run(make_frame(640, 640), detect_fn)

    assert len(detecciones) == 1
    assert slicer.get_statistics()["invalid_detections"] == 4


def test_detect_fn_no_callable():
    """run() exige un callable."""
    with pytest.raises(ValueError):
        InferenceSlicer().run(make_frame(640, 640), "no soy callable")


# ---------------------------------------------------------------------------
# 7. Estadisticas
# ---------------------------------------------------------------------------

def test_estadisticas_tras_varios_frames():
    """Los contadores acumulan a lo largo de los frames."""
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    frame = make_frame(1280, 720)
    for _ in range(3):
        slicer.run(frame, constant_detect_fn([10, 20, 30, 40]))

    stats = slicer.get_statistics()
    assert stats["frames_processed"] == 3
    assert stats["full_frame_runs"] == 3
    assert stats["total_slices"] == 18  # 6 tiles x 3 frames
    assert stats["avg_slices_per_frame"] == 6.0
    assert stats["last_slice_count"] == 6
    assert stats["last_grid"] == (3, 2)
    assert stats["raw_detections"] == 18
    assert stats["merged_detections"] == 18


def test_reset_statistics():
    """reset_statistics deja todos los contadores a cero."""
    slicer = InferenceSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    slicer.run(make_frame(1280, 720), constant_detect_fn([1, 1, 5, 5]))
    slicer.reset_statistics()

    stats = slicer.get_statistics()
    assert stats["frames_processed"] == 0
    assert stats["total_slices"] == 0
    assert stats["avg_slices_per_frame"] == 0.0


# ---------------------------------------------------------------------------
# 8. RegionOfInterestSlicer
# ---------------------------------------------------------------------------

def test_roi_centrada_calculada_a_mano():
    """
    CASO CALCULADO A MANO.

    Frame 1280x720, center (640, 360), radius 200 -> ROI (440, 160, 840, 560),
    es decir 400x400, que cabe en un solo tile de 640x640 con offset (440, 160).
    Una deteccion local [10, 10, 30, 30] pasa a [450, 170, 470, 190].
    """
    slicer = RegionOfInterestSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    frame = make_frame(1280, 720)

    assert slicer.compute_roi(frame.shape, (640, 360), 200.0) == (440, 160, 840, 560)

    tiles = slicer.slice_around(frame, (640, 360), radius_px=200.0)
    assert len(tiles) == 1
    assert tiles[0]["offset"] == (440, 160)
    assert tiles[0]["size"] == (400, 400)

    detecciones = slicer.run_around(
        frame, (640, 360), constant_detect_fn([10, 10, 30, 30]), radius_px=200.0
    )
    assert len(detecciones) == 1
    assert detecciones[0]["bbox"] == [450.0, 170.0, 470.0, 190.0]
    assert detecciones[0]["center"] == [460.0, 180.0]


def test_roi_en_esquina_se_recorta_al_frame():
    """Con el centro en las esquinas la ventana se recorta sin offsets negativos."""
    slicer = RegionOfInterestSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    frame = make_frame(1280, 720)

    assert slicer.compute_roi(frame.shape, (0, 0), 200.0) == (0, 0, 200, 200)
    assert slicer.compute_roi(frame.shape, (1280, 720), 200.0) == (1080, 520, 1280, 720)

    tiles = slicer.slice_around(frame, (1280, 720), radius_px=200.0)
    assert len(tiles) == 1
    assert tiles[0]["offset"] == (1080, 520)
    assert tiles[0]["size"] == (200, 200)

    detecciones = slicer.run_around(
        frame, (1280, 720), constant_detect_fn([5, 5, 25, 25]), radius_px=200.0
    )
    assert detecciones[0]["bbox"] == [1085.0, 525.0, 1105.0, 545.0]


def test_roi_esquina_superior_izquierda_traslacion_identidad():
    """En la esquina (0,0) el offset es (0,0): la traslacion es la identidad."""
    slicer = RegionOfInterestSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    detecciones = slicer.run_around(
        make_frame(1280, 720), (10, 10), constant_detect_fn([2, 3, 8, 9]), radius_px=150.0
    )
    assert detecciones[0]["bbox"] == [2.0, 3.0, 8.0, 9.0]


def test_roi_grande_genera_varios_tiles_con_offsets_absolutos():
    """
    CASO CALCULADO A MANO.

    Frame 1280x720, center (640, 360), radius 500 -> ROI recortada a
    (140, 0, 1140, 720), es decir 1000x720. Con tiles 640x640 y paso 512:
      X local: 0, 512  (anchos 640, 488)   -> absolutos 140, 652
      Y local: 0, 512  (altos 640, 208)    -> absolutos 0, 512
    """
    slicer = RegionOfInterestSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    frame = make_frame(1280, 720)

    assert slicer.compute_roi(frame.shape, (640, 360), 500.0) == (140, 0, 1140, 720)

    tiles = slicer.slice_around(frame, (640, 360), radius_px=500.0)
    assert [t["offset"] for t in tiles] == [(140, 0), (652, 0), (140, 512), (652, 512)]
    assert [t["size"] for t in tiles] == [(640, 640), (488, 640), (640, 208), (488, 208)]


def test_roi_reduce_el_numero_de_inferencias():
    """La ventana local cuesta menos llamadas a detect_fn que el barrido completo."""
    frame = make_frame(1920, 1080)
    slicer = RegionOfInterestSlicer(slice_wh=(640, 640), overlap_ratio=0.2)

    vistos_full = []
    slicer.run(frame, recording_detect_fn(vistos_full))
    vistos_roi = []
    slicer.run_around(frame, (960, 540), recording_detect_fn(vistos_roi), radius_px=300.0)

    assert len(vistos_full) == 8   # X: 0,512,1024,1536 ; Y: 0,512
    assert len(vistos_roi) == 1    # ROI de 600x600 cabe en un tile
    assert len(vistos_roi) < len(vistos_full)

    stats = slicer.get_statistics()
    assert stats["full_frame_runs"] == 1
    assert stats["roi_runs"] == 1
    assert stats["frames_processed"] == 2


def test_roi_encuentra_el_objeto_con_detector_real():
    """End-to-end: el objeto dentro de la ventana se recupera en coords del frame."""
    frame = make_frame(1280, 720)
    draw_square(frame, x=700, y=400, size=18)

    slicer = RegionOfInterestSlicer(slice_wh=(320, 320), overlap_ratio=0.2)
    detecciones = slicer.run_around(frame, (709, 409), contour_detect_fn, radius_px=250.0)

    assert len(detecciones) == 1
    assert detecciones[0]["bbox"] == [700.0, 400.0, 718.0, 418.0]


def test_roi_fuera_del_frame_degrada_a_barrido_completo():
    """Un centro completamente fuera del frame vuelve al barrido total."""
    slicer = RegionOfInterestSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    frame = make_frame(1280, 720)

    assert slicer.compute_roi(frame.shape, (5000, 5000), 100.0) is None

    vistos = []
    slicer.run_around(frame, (5000, 5000), recording_detect_fn(vistos), radius_px=100.0)

    assert len(vistos) == 6  # rejilla completa de 1280x720
    stats = slicer.get_statistics()
    assert stats["roi_fallbacks"] == 1
    assert stats["full_frame_runs"] == 1
    assert stats["roi_runs"] == 0


def test_roi_center_none_degrada_a_barrido_completo():
    """Sin posicion previa (primer frame o objeto perdido) se barre todo."""
    slicer = RegionOfInterestSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    vistos = []
    slicer.run_around(make_frame(1280, 720), None, recording_detect_fn(vistos))
    assert len(vistos) == 6
    assert slicer.get_statistics()["roi_fallbacks"] == 1


@pytest.mark.parametrize("radius", [0.0, -10.0, float("nan")])
def test_roi_radio_invalido(radius):
    """radius_px debe ser un numero finito positivo."""
    slicer = RegionOfInterestSlicer()
    with pytest.raises(ValueError):
        slicer.run_around(make_frame(640, 640), (100, 100), lambda t: [], radius_px=radius)


def test_roi_center_invalido():
    """Un center mal formado se rechaza con ValueError."""
    slicer = RegionOfInterestSlicer()
    with pytest.raises(ValueError):
        slicer.compute_roi((720, 1280, 3), ("a", "b"), 100.0)
    with pytest.raises(ValueError):
        slicer.compute_roi((720, 1280, 3), (float("inf"), 10.0), 100.0)


def test_roi_hereda_run_completo():
    """RegionOfInterestSlicer sigue soportando el barrido completo heredado."""
    slicer = RegionOfInterestSlicer(slice_wh=(640, 640), overlap_ratio=0.2)
    assert isinstance(slicer, InferenceSlicer)
    detecciones = slicer.run(make_frame(1280, 720), constant_detect_fn([10, 20, 30, 40]))
    assert [d["bbox"][0] for d in detecciones] == [10.0, 522.0, 1034.0, 10.0, 522.0, 1034.0]


def test_salida_respeta_el_formato_del_contrato():
    """Cada deteccion fusionada tiene bbox, center, confidence y class_id."""
    slicer = InferenceSlicer(slice_wh=(400, 400), overlap_ratio=0.2)
    detecciones = slicer.run(
        make_frame(800, 600), constant_detect_fn([10, 10, 30, 30], 0.77, class_id=32)
    )
    assert detecciones
    for det in detecciones:
        assert isinstance(det["bbox"], list) and len(det["bbox"]) == 4
        assert all(isinstance(v, float) for v in det["bbox"])
        assert isinstance(det["center"], list) and len(det["center"]) == 2
        assert det["confidence"] == pytest.approx(0.77)
        assert det["class_id"] == 32
        assert det["bbox"][0] < det["bbox"][2] and det["bbox"][1] < det["bbox"][3]

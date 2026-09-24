"""
inference_slicer.py - Inferencia por tiles (slicing) para objetos pequenos

PROBLEMA QUE RESUELVE
---------------------
En una toma amplia de camara (por ejemplo 1920x1080 o 4K), el balon puede ocupar
menos de 20x20 pixeles. Los detectores YOLO redimensionan el frame completo a su
resolucion de entrada (tipicamente 640x640); en esa reduccion el balon pasa de
~20 px a ~7 px y practicamente desaparece del mapa de caracteristicas.

La tecnica de "slicing" (tambien conocida como SAHI / tiled inference) divide el
frame en tiles solapados, corre la inferencia sobre cada tile a resolucion nativa
(sin reducir, o reduciendo mucho menos) y fusiona las detecciones de vuelta a las
coordenadas del frame completo.

Tres detalles hacen o rompen la implementacion:

1. Traslacion de coordenadas. Cada bbox detectado dentro de un tile esta en
   coordenadas locales del tile. Hay que sumarle el offset (ox, oy) del tile para
   volver al sistema de coordenadas del frame. Es el bug mas comun de esta tecnica.

2. Deduplicacion. Un objeto situado en la zona de solape se detecta una vez por
   cada tile que lo contiene. Hay que aplicar NMS (Non-Maximum Suppression) sobre
   las detecciones YA trasladadas, nunca antes.
   Ademas del duplicado "completo" existe el duplicado "fragmento": si el objeto
   queda cortado por el borde de un tile, ese tile produce un trozo del objeto y
   el tile vecino el objeto entero. El IoU entre el trozo y el objeto entero es
   bajo, asi que un NMS de IoU puro NO los fusiona. Por eso el NMS de este modulo
   suprime tambien por CONTENCION (interseccion dividida por el area de la caja
   mas pequena), que es 1.0 cuando una caja esta dentro de la otra.

3. Tiles de borde. El ultimo tile de cada fila/columna suele salirse del frame.
   Se recorta (queda mas pequeno) en lugar de rellenarse con padding: el padding
   desplazaria el contenido dentro del tile y por tanto falsearia la traslacion.

COSTE (trade-off real, sin cifras inventadas)
---------------------------------------------
El coste computacional es lineal en el numero de tiles: N tiles => N inferencias
del modelo por frame, mas el coste (pequeno) del recorte y del NMS final. Con la
configuracion por defecto (tiles de 640x640, solape 0.2) un frame de 1920x1080
produce 4x2 = 8 tiles, es decir 8 pasadas del modelo en lugar de 1. Un frame 4K
(3840x2160) produce 8x5 = 40 tiles.

Ese multiplicador es el precio de detectar objetos pequenos. Por eso existe
`RegionOfInterestSlicer`: cuando ya se conoce la posicion del objeto en el frame
anterior (por ejemplo el balon), no hace falta recorrer todo el frame; basta con
concentrar los tiles en una ventana alrededor de esa posicion, lo que reduce el
numero de inferencias por frame. La estrategia habitual es:

    frame 0 (o tras perder el objeto) -> InferenceSlicer.run()        (barrido total)
    frames siguientes                 -> run_around(center_anterior)  (ventana local)

Este modulo NO carga ningun modelo. La funcion de deteccion se inyecta
(`detect_fn`), de modo que puede ser YOLO, un detector clasico de OpenCV o un mock
en los tests.

Dependencias: numpy unicamente (no anade dependencias nuevas al proyecto).
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

__all__ = [
    "compute_iou",
    "compute_iou_matrix",
    "compute_containment_matrix",
    "non_max_suppression",
    "InferenceSlicer",
    "RegionOfInterestSlicer",
]

# Tipo de la funcion de deteccion inyectable:
#   detect_fn(tile: np.ndarray) -> List[Dict]  (formato "Deteccion individual")
DetectFn = Callable[[np.ndarray], Optional[Sequence[Dict]]]


# ---------------------------------------------------------------------------
# Utilidades geometricas (implementadas con numpy, sin torchvision)
# ---------------------------------------------------------------------------

def compute_iou_matrix(boxes_a: Sequence, boxes_b: Sequence) -> np.ndarray:
    """
    Calcula la matriz de IoU (Intersection over Union) entre dos conjuntos de bboxes.

    Args:
        boxes_a: Iterable de bboxes [x1, y1, x2, y2]. Shape (N, 4).
        boxes_b: Iterable de bboxes [x1, y1, x2, y2]. Shape (M, 4).

    Returns:
        np.ndarray: Matriz (N, M) de float64 con el IoU de cada par.
                    Si alguna caja tiene area cero, su IoU es 0.0.
    """
    a = np.asarray(boxes_a, dtype=np.float64).reshape(-1, 4)
    b = np.asarray(boxes_b, dtype=np.float64).reshape(-1, 4)

    if a.shape[0] == 0 or b.shape[0] == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float64)

    inter_x1 = np.maximum(a[:, 0][:, None], b[None, :, 0])
    inter_y1 = np.maximum(a[:, 1][:, None], b[None, :, 1])
    inter_x2 = np.minimum(a[:, 2][:, None], b[None, :, 2])
    inter_y2 = np.minimum(a[:, 3][:, None], b[None, :, 3])

    inter_w = np.clip(inter_x2 - inter_x1, 0.0, None)
    inter_h = np.clip(inter_y2 - inter_y1, 0.0, None)
    intersection = inter_w * inter_h

    area_a = np.clip(a[:, 2] - a[:, 0], 0.0, None) * np.clip(a[:, 3] - a[:, 1], 0.0, None)
    area_b = np.clip(b[:, 2] - b[:, 0], 0.0, None) * np.clip(b[:, 3] - b[:, 1], 0.0, None)

    union = area_a[:, None] + area_b[None, :] - intersection

    with np.errstate(divide="ignore", invalid="ignore"):
        iou = np.where(union > 0.0, intersection / union, 0.0)

    return np.asarray(iou, dtype=np.float64)


def compute_iou(box_a: Sequence[float], box_b: Sequence[float]) -> float:
    """
    Calcula el IoU entre dos bboxes individuales.

    Args:
        box_a: [x1, y1, x2, y2]
        box_b: [x1, y1, x2, y2]

    Returns:
        float: IoU en el rango [0.0, 1.0]. 0.0 si no se solapan o si alguna
               caja tiene area nula.
    """
    return float(compute_iou_matrix([box_a], [box_b])[0, 0])


def compute_containment_matrix(boxes_a: Sequence, boxes_b: Sequence) -> np.ndarray:
    """
    Calcula la matriz de contencion: interseccion / area de la caja mas pequena.

    A diferencia del IoU, esta metrica vale 1.0 cuando una caja esta completamente
    dentro de la otra aunque sus tamanos sean muy distintos. Es lo que permite
    detectar que un fragmento de objeto (producido por el corte de un tile) y el
    objeto entero (detectado en el tile vecino) son la misma cosa.

    Args:
        boxes_a: Iterable de bboxes [x1, y1, x2, y2]. Shape (N, 4).
        boxes_b: Iterable de bboxes [x1, y1, x2, y2]. Shape (M, 4).

    Returns:
        np.ndarray: Matriz (N, M) de float64 en el rango [0.0, 1.0].
    """
    a = np.asarray(boxes_a, dtype=np.float64).reshape(-1, 4)
    b = np.asarray(boxes_b, dtype=np.float64).reshape(-1, 4)

    if a.shape[0] == 0 or b.shape[0] == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float64)

    inter_w = np.clip(
        np.minimum(a[:, 2][:, None], b[None, :, 2])
        - np.maximum(a[:, 0][:, None], b[None, :, 0]),
        0.0,
        None,
    )
    inter_h = np.clip(
        np.minimum(a[:, 3][:, None], b[None, :, 3])
        - np.maximum(a[:, 1][:, None], b[None, :, 1]),
        0.0,
        None,
    )
    intersection = inter_w * inter_h

    area_a = np.clip(a[:, 2] - a[:, 0], 0.0, None) * np.clip(a[:, 3] - a[:, 1], 0.0, None)
    area_b = np.clip(b[:, 2] - b[:, 0], 0.0, None) * np.clip(b[:, 3] - b[:, 1], 0.0, None)
    min_area = np.minimum(area_a[:, None], area_b[None, :])

    with np.errstate(divide="ignore", invalid="ignore"):
        containment = np.where(min_area > 0.0, intersection / min_area, 0.0)

    return np.asarray(containment, dtype=np.float64)


def non_max_suppression(
    detections: Sequence[Dict],
    iou_threshold: float = 0.5,
    class_agnostic: bool = False,
    containment_threshold: Optional[float] = None,
) -> List[Dict]:
    """
    NMS propio sobre detecciones en formato del contrato.

    Algoritmo greedy clasico: se ordena por confianza descendente y, por cada
    deteccion conservada, se suprimen las que tengan IoU ESTRICTAMENTE mayor que
    `iou_threshold` (un umbral de 1.0 por tanto no suprime nada por IoU, ni
    siquiera duplicados exactos).

    Desempate: a igualdad de confianza gana la caja de MAYOR area. Esto importa en
    la inferencia por tiles, donde el fragmento de un objeto cortado por el borde
    de un tile y el objeto entero del tile vecino suelen llegar con la misma
    confianza; sin este desempate podria conservarse el fragmento.

    Args:
        detections: Lista de dicts con al menos 'bbox' y 'confidence'.
        iou_threshold: Umbral de solape para considerar dos cajas el mismo objeto.
        class_agnostic: Si False (por defecto) solo se suprimen entre si las
                        detecciones con el mismo 'class_id' (las que no tienen
                        class_id forman su propio grupo). Si True se ignora la clase.
        containment_threshold: Si no es None, tambien se suprime cuando la
                        contencion (interseccion / area menor) supera el umbral.
                        Sirve para fusionar fragmentos de borde con el objeto
                        entero. None (por defecto en esta funcion) = solo IoU.

    Returns:
        List[Dict]: Detecciones conservadas, ordenadas por confianza descendente.
                    Se devuelven los mismos objetos dict de entrada (no se copian).
    """
    if not detections:
        return []

    n = len(detections)
    boxes = np.zeros((n, 4), dtype=np.float64)
    confidences = np.zeros(n, dtype=np.float64)
    classes: List[object] = []

    for i, det in enumerate(detections):
        boxes[i] = np.asarray(det["bbox"], dtype=np.float64).reshape(4)
        confidences[i] = float(det.get("confidence", 0.0))
        classes.append(None if class_agnostic else det.get("class_id"))

    areas = np.clip(boxes[:, 2] - boxes[:, 0], 0.0, None) * np.clip(
        boxes[:, 3] - boxes[:, 1], 0.0, None
    )

    # Orden estable: confianza desc, area desc, y por ultimo el orden de entrada.
    order = sorted(range(n), key=lambda i: (confidences[i], areas[i]), reverse=True)

    suppressed = np.zeros(n, dtype=bool)
    kept: List[int] = []

    for idx in order:
        if suppressed[idx]:
            continue
        kept.append(idx)

        overlapping = compute_iou_matrix(boxes[idx : idx + 1], boxes)[0] > iou_threshold
        if containment_threshold is not None:
            overlapping |= (
                compute_containment_matrix(boxes[idx : idx + 1], boxes)[0]
                > containment_threshold
            )

        for j in np.nonzero(overlapping)[0]:
            j = int(j)
            if j == idx or suppressed[j]:
                continue
            if class_agnostic or classes[j] == classes[idx]:
                suppressed[j] = True

    return [detections[i] for i in kept]


# ---------------------------------------------------------------------------
# Slicer principal
# ---------------------------------------------------------------------------

class InferenceSlicer:
    """
    Divide un frame en tiles solapados, ejecuta una funcion de deteccion sobre cada
    tile y fusiona los resultados en coordenadas del frame completo.

    El modelo no se carga aqui: la deteccion se inyecta como callable, lo que
    permite testear el slicer sin YOLO y reutilizarlo con cualquier detector.

    Coste: N tiles implican N llamadas a `detect_fn` por frame. Ver el docstring
    del modulo y `count_slices()` para dimensionar ese coste antes de procesar.
    """

    def __init__(
        self,
        slice_wh: Tuple[int, int] = (640, 640),
        overlap_ratio: float = 0.2,
        iou_threshold: float = 0.5,
        max_slices: Optional[int] = None,
        containment_threshold: Optional[float] = 0.8,
    ):
        """
        Args:
            slice_wh: (ancho, alto) de cada tile en pixeles. Debe ser positivo.
                      640x640 coincide con la entrada nativa tipica de YOLO, asi
                      que el tile no sufre reduccion de escala.
            overlap_ratio: Fraccion de solape entre tiles contiguos, en [0.0, 1.0).
                           0.0 = tiles disjuntos (un objeto en la frontera puede
                           partirse); 0.2 es un compromiso razonable.
            iou_threshold: Umbral de IoU del NMS que fusiona los duplicados de las
                           zonas de solape.
            max_slices: Tope opcional de tiles por frame. Si la rejilla lo supera,
                        se conservan los primeros `max_slices` en orden row-major
                        (el resto del frame queda sin analizar) y se registra un
                        warning. Sirve como red de seguridad de latencia.
            containment_threshold: Umbral de contencion (interseccion / area menor)
                        del NMS, en (0.0, 1.0]. Fusiona el fragmento que produce un
                        objeto cortado por el borde de un tile con el objeto entero
                        detectado en el tile vecino, caso que el IoU no cubre.
                        Se aplica dentro de la misma clase, igual que el IoU.
                        None lo desactiva (NMS de IoU puro).

        Raises:
            ValueError: Si algun parametro esta fuera de rango.
        """
        try:
            slice_w, slice_h = int(slice_wh[0]), int(slice_wh[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError(
                f"slice_wh debe ser una tupla (ancho, alto) de enteros, recibido: {slice_wh!r}"
            ) from exc

        if slice_w <= 0 or slice_h <= 0:
            raise ValueError(
                f"slice_wh debe tener ancho y alto positivos, recibido: ({slice_w}, {slice_h})"
            )

        overlap_ratio = float(overlap_ratio)
        if not (0.0 <= overlap_ratio < 1.0):
            raise ValueError(
                f"overlap_ratio debe estar en [0.0, 1.0), recibido: {overlap_ratio}"
            )

        iou_threshold = float(iou_threshold)
        if not (0.0 <= iou_threshold <= 1.0):
            raise ValueError(
                f"iou_threshold debe estar en [0.0, 1.0], recibido: {iou_threshold}"
            )

        if max_slices is not None:
            max_slices = int(max_slices)
            if max_slices < 1:
                raise ValueError(
                    f"max_slices debe ser None o >= 1, recibido: {max_slices}"
                )

        if containment_threshold is not None:
            containment_threshold = float(containment_threshold)
            if not (0.0 < containment_threshold <= 1.0):
                raise ValueError(
                    f"containment_threshold debe ser None o estar en (0.0, 1.0], "
                    f"recibido: {containment_threshold}"
                )

        self.slice_wh: Tuple[int, int] = (slice_w, slice_h)
        self.overlap_ratio: float = overlap_ratio
        self.iou_threshold: float = iou_threshold
        self.max_slices: Optional[int] = max_slices
        self.containment_threshold: Optional[float] = containment_threshold

        # Paso de la rejilla: nunca menor que 1 px, para evitar bucles infinitos
        # con solapes extremos (por ejemplo overlap_ratio=0.999 y tiles pequenos).
        self.step_wh: Tuple[int, int] = (
            max(1, int(round(slice_w * (1.0 - overlap_ratio)))),
            max(1, int(round(slice_h * (1.0 - overlap_ratio)))),
        )

        self._stats: Dict = self._empty_stats()

    # -- estadisticas --------------------------------------------------------

    @staticmethod
    def _empty_stats() -> Dict:
        return {
            "frames_processed": 0,
            "full_frame_runs": 0,
            "roi_runs": 0,
            "roi_fallbacks": 0,
            "total_slices": 0,
            "last_slice_count": 0,
            "last_grid": (0, 0),
            "raw_detections": 0,
            "merged_detections": 0,
            "suppressed_detections": 0,
            "invalid_detections": 0,
            "detect_fn_errors": 0,
            "truncated_frames": 0,
        }

    def get_statistics(self) -> Dict:
        """
        Devuelve un snapshot de las estadisticas acumuladas.

        Returns:
            dict: {
                'frames_processed': frames procesados (run + run_around),
                'full_frame_runs': llamadas a run() con barrido completo,
                'roi_runs': llamadas a run_around() resueltas como ventana local,
                'roi_fallbacks': run_around() que degradaron a barrido completo,
                'total_slices': tiles inferidos acumulados (= llamadas a detect_fn),
                'last_slice_count': tiles del ultimo frame,
                'last_grid': (columnas, filas) de la ultima rejilla,
                'raw_detections': detecciones antes del NMS,
                'merged_detections': detecciones despues del NMS,
                'suppressed_detections': duplicados eliminados por el NMS,
                'invalid_detections': dicts descartados por formato invalido,
                'detect_fn_errors': excepciones capturadas de detect_fn,
                'truncated_frames': frames recortados por max_slices,
                'avg_slices_per_frame': media de tiles por frame,
            }
        """
        stats = dict(self._stats)
        frames = stats["frames_processed"]
        stats["avg_slices_per_frame"] = (
            stats["total_slices"] / frames if frames > 0 else 0.0
        )
        return stats

    def reset_statistics(self) -> None:
        """Reinicia todos los contadores de estadisticas a cero."""
        self._stats = self._empty_stats()

    # -- rejilla de tiles ----------------------------------------------------

    @staticmethod
    def _axis_offsets(length: int, slice_len: int, step: int) -> List[int]:
        """
        Calcula los offsets de inicio de los tiles a lo largo de un eje.

        El ultimo tile se recorta contra el borde (no se desplaza hacia atras ni
        se rellena con padding), de modo que su offset sigue siendo exacto.
        """
        if length <= slice_len:
            return [0]

        offsets: List[int] = []
        pos = 0
        while pos < length:
            offsets.append(pos)
            if pos + slice_len >= length:
                break
            pos += step
        return offsets

    def _grid(self, width: int, height: int) -> List[Tuple[int, int, int, int]]:
        """
        Genera la rejilla de tiles (relativa a una region de tamano width x height).

        Returns:
            List[Tuple[int, int, int, int]]: (x, y, ancho_real, alto_real) por tile,
            en orden row-major. Los anchos/altos reales son menores que slice_wh en
            los tiles de borde.
        """
        slice_w, slice_h = self.slice_wh
        step_x, step_y = self.step_wh

        xs = self._axis_offsets(width, slice_w, step_x)
        ys = self._axis_offsets(height, slice_h, step_y)

        grid: List[Tuple[int, int, int, int]] = []
        for y in ys:
            for x in xs:
                tile_w = min(slice_w, width - x)
                tile_h = min(slice_h, height - y)
                if tile_w <= 0 or tile_h <= 0:
                    continue
                grid.append((x, y, tile_w, tile_h))

        self._stats["last_grid"] = (len(xs), len(ys))
        return grid

    def count_slices(self, frame_shape: Tuple[int, ...]) -> int:
        """
        Numero de tiles (y por tanto de inferencias) que produciria un frame.

        Util para estimar el coste antes de procesar un video entero.

        Args:
            frame_shape: shape de numpy del frame, (alto, ancho[, canales]).

        Returns:
            int: cantidad de tiles, ya aplicando el tope de `max_slices`.
        """
        height, width = int(frame_shape[0]), int(frame_shape[1])
        count = len(self._grid(width, height))
        if self.max_slices is not None:
            count = min(count, self.max_slices)
        return count

    # -- validaciones --------------------------------------------------------

    @staticmethod
    def _validate_frame(frame: np.ndarray) -> Tuple[int, int]:
        """
        Valida el frame y devuelve (ancho, alto).

        Raises:
            ValueError: Si el frame no es un ndarray 2D/3D no vacio.
        """
        if not isinstance(frame, np.ndarray):
            raise ValueError(
                f"frame debe ser un np.ndarray, recibido: {type(frame).__name__}"
            )
        if frame.ndim not in (2, 3):
            raise ValueError(
                f"frame debe tener 2 o 3 dimensiones (H, W[, C]), recibido ndim={frame.ndim}"
            )
        height, width = int(frame.shape[0]), int(frame.shape[1])
        if height <= 0 or width <= 0:
            raise ValueError(
                f"frame vacio: dimensiones ({width}x{height}) no validas"
            )
        return width, height

    # -- slicing -------------------------------------------------------------

    def _build_slices(
        self,
        frame: np.ndarray,
        origin_x: int,
        origin_y: int,
        region_w: int,
        region_h: int,
    ) -> List[Dict]:
        """
        Construye los tiles de una region del frame.

        Los offsets devueltos son ABSOLUTOS respecto al frame completo (incluyen
        `origin_x`/`origin_y`), que es justo lo que necesita la traslacion.
        """
        grid = self._grid(region_w, region_h)

        if self.max_slices is not None and len(grid) > self.max_slices:
            logger.warning(
                "Rejilla de %d tiles supera max_slices=%d; se procesan solo los "
                "primeros %d (parte del frame quedara sin analizar)",
                len(grid),
                self.max_slices,
                self.max_slices,
            )
            grid = grid[: self.max_slices]
            self._stats["truncated_frames"] += 1

        slices: List[Dict] = []
        for index, (x, y, tile_w, tile_h) in enumerate(grid):
            abs_x = origin_x + x
            abs_y = origin_y + y
            try:
                tile = np.ascontiguousarray(
                    frame[abs_y : abs_y + tile_h, abs_x : abs_x + tile_w]
                )
            except Exception as exc:  # pragma: no cover - defensivo
                raise RuntimeError(
                    f"Error recortando el tile {index} en "
                    f"({abs_x}, {abs_y}, {tile_w}, {tile_h}) sobre un frame "
                    f"de shape {frame.shape}: {exc}"
                ) from exc

            slices.append(
                {
                    "image": tile,
                    "offset": (abs_x, abs_y),
                    "index": index,
                    "size": (tile_w, tile_h),
                    "bounds": (abs_x, abs_y, abs_x + tile_w, abs_y + tile_h),
                }
            )
        return slices

    def slice_frame(self, frame: np.ndarray) -> List[Dict]:
        """
        Divide el frame completo en tiles solapados.

        Args:
            frame: Frame de video (H, W, 3) o (H, W).

        Returns:
            List[Dict]: [{'image': ndarray, 'offset': (ox, oy), 'index': int,
                          'size': (w, h), 'bounds': (x1, y1, x2, y2)}, ...]
                        en orden row-major. Los tiles de borde son mas pequenos
                        que `slice_wh` (recortados, nunca rellenados con padding).
                        `image` es una copia contigua, apta para pasar a un modelo.

        Raises:
            ValueError: Si el frame no es valido.
        """
        width, height = self._validate_frame(frame)
        return self._build_slices(frame, 0, 0, width, height)

    # -- traslacion ----------------------------------------------------------

    @staticmethod
    def _translate_detection(
        detection: Dict,
        offset: Tuple[int, int],
        frame_w: int,
        frame_h: int,
    ) -> Optional[Dict]:
        """
        Traslada UNA deteccion de coordenadas del tile a coordenadas del frame.

        Suma el offset del tile a bbox y center, y recorta el resultado a los
        limites del frame. Devuelve None si el dict no respeta el formato del
        contrato (se registra un warning y la deteccion se descarta).
        """
        if not isinstance(detection, dict):
            logger.warning(
                "detect_fn devolvio un elemento que no es dict (%s); se descarta",
                type(detection).__name__,
            )
            return None

        bbox_raw = detection.get("bbox")
        if bbox_raw is None:
            logger.warning("Deteccion sin 'bbox'; se descarta: %r", detection)
            return None

        try:
            bbox = np.asarray(bbox_raw, dtype=np.float64).reshape(-1)
        except (TypeError, ValueError):
            logger.warning("Deteccion con 'bbox' no numerico; se descarta: %r", bbox_raw)
            return None

        if bbox.size != 4 or not np.all(np.isfinite(bbox)):
            logger.warning(
                "Deteccion con 'bbox' invalido (se esperaban 4 valores finitos); "
                "se descarta: %r",
                bbox_raw,
            )
            return None

        ox, oy = float(offset[0]), float(offset[1])

        x1 = float(np.clip(bbox[0] + ox, 0.0, frame_w))
        y1 = float(np.clip(bbox[1] + oy, 0.0, frame_h))
        x2 = float(np.clip(bbox[2] + ox, 0.0, frame_w))
        y2 = float(np.clip(bbox[3] + oy, 0.0, frame_h))

        translated = dict(detection)
        translated["bbox"] = [x1, y1, x2, y2]

        center_raw = detection.get("center")
        if center_raw is not None:
            try:
                center = np.asarray(center_raw, dtype=np.float64).reshape(-1)
            except (TypeError, ValueError):
                center = None
            if center is not None and center.size == 2 and np.all(np.isfinite(center)):
                translated["center"] = [
                    float(np.clip(center[0] + ox, 0.0, frame_w)),
                    float(np.clip(center[1] + oy, 0.0, frame_h)),
                ]
            else:
                translated["center"] = [(x1 + x2) / 2.0, (y1 + y2) / 2.0]
        else:
            translated["center"] = [(x1 + x2) / 2.0, (y1 + y2) / 2.0]

        translated["confidence"] = float(detection.get("confidence", 0.0))
        translated["slice_index"] = detection.get("slice_index", None)
        translated["slice_offset"] = (int(offset[0]), int(offset[1]))
        return translated

    # -- ejecucion -----------------------------------------------------------

    def _detect_on_slices(
        self,
        slices: Sequence[Dict],
        detect_fn: DetectFn,
        frame_w: int,
        frame_h: int,
    ) -> List[Dict]:
        """Ejecuta detect_fn sobre cada tile y devuelve las detecciones trasladadas."""
        translated: List[Dict] = []

        for tile in slices:
            self._stats["total_slices"] += 1
            try:
                raw = detect_fn(tile["image"])
            except Exception as exc:
                self._stats["detect_fn_errors"] += 1
                logger.error(
                    "detect_fn fallo en el tile %d con offset %s (tamano %s): %s",
                    tile["index"],
                    tile["offset"],
                    tile["size"],
                    exc,
                    exc_info=True,
                )
                continue

            if raw is None:
                continue
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, (list, tuple)):
                self._stats["invalid_detections"] += 1
                logger.warning(
                    "detect_fn devolvio %s en el tile %d; se esperaba una lista de dicts",
                    type(raw).__name__,
                    tile["index"],
                )
                continue

            for detection in raw:
                moved = self._translate_detection(
                    detection, tile["offset"], frame_w, frame_h
                )
                if moved is None:
                    self._stats["invalid_detections"] += 1
                    continue
                moved["slice_index"] = tile["index"]
                translated.append(moved)

        return translated

    def merge_detections(self, detections: List[Dict]) -> List[Dict]:
        """
        Fusiona detecciones duplicadas provenientes de las zonas de solape.

        Aplica NMS por clase sobre detecciones que YA estan en coordenadas del
        frame completo. Dos cajas del mismo 'class_id' se consideran el mismo
        objeto si su IoU supera `iou_threshold` (duplicado por solape) o si su
        contencion supera `containment_threshold` (fragmento de borde dentro del
        objeto entero); se conserva la de mayor confianza y, a igualdad, la mayor.

        Args:
            detections: Detecciones en coordenadas absolutas del frame.

        Returns:
            List[Dict]: Detecciones conservadas, ordenadas por confianza descendente.
        """
        if not detections:
            return []

        try:
            merged = non_max_suppression(
                detections,
                iou_threshold=self.iou_threshold,
                class_agnostic=False,
                containment_threshold=self.containment_threshold,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"merge_detections recibio detecciones con formato invalido "
                f"(se espera 'bbox': [x1,y1,x2,y2] y 'confidence'): {exc}"
            ) from exc

        self._stats["suppressed_detections"] += len(detections) - len(merged)
        return merged

    def run(self, frame: np.ndarray, detect_fn: DetectFn) -> List[Dict]:
        """
        Ejecuta la inferencia por tiles sobre el frame completo.

        Args:
            frame: Frame de video (H, W, 3) o (H, W).
            detect_fn: Callable que recibe un tile (np.ndarray) y devuelve una
                       lista de detecciones EN COORDENADAS DEL TILE, en el formato
                       "Deteccion individual" del contrato:
                       {'bbox': [x1,y1,x2,y2], 'center': [cx,cy],
                        'confidence': float, 'class_id': int}.
                       'center' y 'class_id' son opcionales; 'center' se calcula
                       a partir del bbox si falta. Puede devolver None o [].

        Returns:
            List[Dict]: Detecciones fusionadas en coordenadas ABSOLUTAS del frame,
                        ordenadas por confianza descendente. Cada deteccion incluye
                        ademas 'slice_index' y 'slice_offset' para trazabilidad.

        Raises:
            ValueError: Si el frame no es valido o detect_fn no es callable.

        Nota de coste: se realiza una llamada a `detect_fn` por tile. Usa
        `count_slices(frame.shape)` para conocer el multiplicador de antemano.
        """
        width, height = self._validate_frame(frame)
        if not callable(detect_fn):
            raise ValueError(
                f"detect_fn debe ser callable, recibido: {type(detect_fn).__name__}"
            )

        slices = self._build_slices(frame, 0, 0, width, height)
        self._stats["last_slice_count"] = len(slices)
        self._stats["frames_processed"] += 1
        self._stats["full_frame_runs"] += 1

        translated = self._detect_on_slices(slices, detect_fn, width, height)
        self._stats["raw_detections"] += len(translated)

        merged = self.merge_detections(translated)
        self._stats["merged_detections"] += len(merged)
        return merged


class RegionOfInterestSlicer(InferenceSlicer):
    """
    Variante que concentra los tiles alrededor de una posicion conocida.

    Motivacion: el barrido completo cuesta N inferencias por frame. Si el objeto
    (tipicamente el balon) fue localizado en el frame anterior, su posicion en el
    frame actual esta acotada por su velocidad maxima, asi que basta con analizar
    una ventana cuadrada alrededor de la ultima posicion conocida. Eso reduce el
    numero de tiles y, por tanto, el numero de inferencias por frame.

    Uso tipico:
        slicer = RegionOfInterestSlicer()
        if last_center is None:
            dets = slicer.run(frame, detect_fn)            # barrido completo
        else:
            dets = slicer.run_around(frame, last_center, detect_fn, radius_px=400)
        # si run_around no encuentra nada durante varios frames, volver a run()

    Hereda `run()` (barrido completo) sin cambios, de modo que la misma instancia
    sirve para ambos modos y acumula estadisticas conjuntas.
    """

    def compute_roi(
        self,
        frame_shape: Tuple[int, ...],
        center: Tuple[float, float],
        radius_px: float = 400.0,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        Calcula la region de interes cuadrada alrededor de `center`, recortada al frame.

        Args:
            frame_shape: shape de numpy del frame (alto, ancho[, canales]).
            center: (cx, cy) en coordenadas absolutas del frame.
            radius_px: Semilado de la ventana en pixeles (> 0).

        Returns:
            Tuple[int, int, int, int] | None: (x1, y1, x2, y2) enteros con area
            positiva, o None si la ventana queda completamente fuera del frame.

        Raises:
            ValueError: Si `center` no es un par de numeros finitos o radius_px <= 0.
        """
        height, width = int(frame_shape[0]), int(frame_shape[1])

        try:
            cx, cy = float(center[0]), float(center[1])
        except (TypeError, ValueError, IndexError) as exc:
            raise ValueError(
                f"center debe ser un par (cx, cy) de numeros, recibido: {center!r}"
            ) from exc

        if not (np.isfinite(cx) and np.isfinite(cy)):
            raise ValueError(f"center contiene valores no finitos: {center!r}")

        radius_px = float(radius_px)
        if not np.isfinite(radius_px) or radius_px <= 0.0:
            raise ValueError(f"radius_px debe ser > 0, recibido: {radius_px}")

        x1 = int(np.clip(np.floor(cx - radius_px), 0, width))
        y1 = int(np.clip(np.floor(cy - radius_px), 0, height))
        x2 = int(np.clip(np.ceil(cx + radius_px), 0, width))
        y2 = int(np.clip(np.ceil(cy + radius_px), 0, height))

        if x2 - x1 <= 0 or y2 - y1 <= 0:
            return None
        return (x1, y1, x2, y2)

    def slice_around(
        self,
        frame: np.ndarray,
        center: Tuple[float, float],
        radius_px: float = 400.0,
    ) -> List[Dict]:
        """
        Genera los tiles de la ventana alrededor de `center`.

        Los offsets son absolutos respecto al frame completo, igual que en
        `slice_frame`. Si la ventana cae fuera del frame se devuelve la rejilla
        del frame completo (degradacion elegante).

        Args:
            frame: Frame de video.
            center: (cx, cy) posicion previa conocida del objeto.
            radius_px: Semilado de la ventana en pixeles.

        Returns:
            List[Dict]: Tiles en el mismo formato que `slice_frame`.
        """
        width, height = self._validate_frame(frame)
        roi = self.compute_roi(frame.shape, center, radius_px)

        if roi is None:
            logger.warning(
                "ROI centrada en %s con radio %.1f px queda fuera del frame "
                "(%dx%d); se degrada a barrido completo",
                center,
                radius_px,
                width,
                height,
            )
            return self._build_slices(frame, 0, 0, width, height)

        x1, y1, x2, y2 = roi
        return self._build_slices(frame, x1, y1, x2 - x1, y2 - y1)

    def run_around(
        self,
        frame: np.ndarray,
        center: Tuple[float, float],
        detect_fn: DetectFn,
        radius_px: float = 400.0,
    ) -> List[Dict]:
        """
        Ejecuta la inferencia por tiles SOLO alrededor de una posicion conocida.

        Args:
            frame: Frame de video (H, W, 3) o (H, W).
            center: (cx, cy) posicion previa del objeto, en coordenadas absolutas
                    del frame. Si es None se degrada a barrido completo.
            detect_fn: Igual que en `run()`.
            radius_px: Semilado de la ventana de busqueda en pixeles. Debe cubrir
                       el desplazamiento maximo esperado del objeto entre frames.

        Returns:
            List[Dict]: Detecciones fusionadas en coordenadas ABSOLUTAS del frame
                        completo, ordenadas por confianza descendente.

        Raises:
            ValueError: Si el frame no es valido, detect_fn no es callable o
                        radius_px <= 0.
        """
        width, height = self._validate_frame(frame)
        if not callable(detect_fn):
            raise ValueError(
                f"detect_fn debe ser callable, recibido: {type(detect_fn).__name__}"
            )

        if center is None:
            logger.info(
                "run_around sin center conocido; se degrada a barrido completo"
            )
            self._stats["roi_fallbacks"] += 1
            return self.run(frame, detect_fn)

        roi = self.compute_roi(frame.shape, center, radius_px)

        if roi is None:
            logger.warning(
                "ROI centrada en %s con radio %.1f px queda fuera del frame "
                "(%dx%d); se degrada a barrido completo",
                center,
                radius_px,
                width,
                height,
            )
            self._stats["roi_fallbacks"] += 1
            return self.run(frame, detect_fn)

        x1, y1, x2, y2 = roi
        slices = self._build_slices(frame, x1, y1, x2 - x1, y2 - y1)
        self._stats["last_slice_count"] = len(slices)
        self._stats["frames_processed"] += 1
        self._stats["roi_runs"] += 1

        translated = self._detect_on_slices(slices, detect_fn, width, height)
        self._stats["raw_detections"] += len(translated)

        merged = self.merge_detections(translated)
        self._stats["merged_detections"] += len(merged)
        return merged

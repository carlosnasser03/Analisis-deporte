"""
bytetrack_adapter.py - Adaptador ByteTrack drop-in para Scout AI

Propósito
---------
Proporcionar un tracker de jugadores con **asociación en dos etapas** (ByteTrack)
exponiendo exactamente la misma API pública que ``core.tracker.PlayerTracker``,
de forma que pueda intercambiarse sin tocar el resto del pipeline.

Qué hace la asociación en dos etapas
------------------------------------
Un tracker clásico descarta las detecciones de baja confianza antes de asociar.
ByteTrack las conserva y las usa en una segunda pasada:

1. Las detecciones se separan en **alta** confianza (``>= high_threshold``) y
   **baja** confianza (``low_threshold <= conf < high_threshold``).
2. **Etapa 1**: los tracks existentes se asocian con las detecciones de alta
   confianza mediante IoU (asignación húngara si hay SciPy, greedy si no).
3. **Etapa 2**: los tracks que quedaron sin pareja se intentan asociar con las
   detecciones de **baja** confianza. Aquí es donde un jugador parcialmente
   ocluido (cuya detección bajó de confianza) recupera su track en lugar de
   perderlo.
4. Las detecciones de alta confianza sin pareja crean tracks nuevos.
   Las de baja confianza **nunca** crean tracks (evita ruido).
5. Los tracks sin pareja tras ambas etapas envejecen y se eliminan cuando
   ``time_since_update > max_age``.

Backends
--------
- ``supervision``: envuelve ``sv.ByteTrack`` traduciendo formatos de entrada y
  salida a los del contrato de integración.
- ``native``: implementación propia con NumPy + ``scipy.optimize.linear_sum_assignment``
  (con fallback greedy si SciPy no está disponible).

El módulo importa y funciona **sin** ``supervision`` instalado.

Nota: este módulo no mide ni afirma ninguna mejora porcentual respecto a
``PlayerTracker``; describe la técnica, no un beneficio cuantificado.
"""

from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Dependencias opcionales (degradación elegante, REGLA 3 del contrato)
# --------------------------------------------------------------------------- #
try:  # pragma: no cover - depende del entorno
    import supervision as sv

    # En supervision >= 0.28 ByteTrack está deprecado y se elimina en 0.30,
    # por eso comprobamos el atributo y no solo el import del paquete.
    HAS_SUPERVISION = hasattr(sv, "ByteTrack")
except ImportError:  # pragma: no cover - depende del entorno
    sv = None
    HAS_SUPERVISION = False

try:  # pragma: no cover - depende del entorno
    from scipy.optimize import linear_sum_assignment

    HAS_SCIPY = True
except ImportError:  # pragma: no cover - depende del entorno
    linear_sum_assignment = None
    HAS_SCIPY = False


# Alias en minúsculas usados internamente (los tests pueden monkeypatchearlos)
_HAS_SUPERVISION = HAS_SUPERVISION
_HAS_SCIPY = HAS_SCIPY

MAX_LOST_TRACKS = 100
"""Número máximo de tracks perdidos que se conservan en el histórico."""


@dataclass
class ByteTrackState:
    """
    Estado interno de un track gestionado por :class:`ByteTrackAdapter`.

    Replica los campos de ``core.tracker.TrackState`` y añade los propios de
    la asociación en dos etapas.

    Attributes:
        track_id (int): Identificador único y estable del track.
        bbox (List[float]): Última caja conocida ``[x1, y1, x2, y2]``.
        confidence (float): Confianza de la última detección asociada.
        frame_id (int): Frame de la última actualización.
        age (int): Frames transcurridos desde la creación del track.
        hits (int): Número de frames en los que el track fue asociado.
        hit_streak (int): Racha actual de asociaciones consecutivas.
        time_since_update (int): Frames consecutivos sin asociación.
        position_history (List[Tuple[float, float]]): Últimos centroides.
        velocity (Tuple[float, float]): Velocidad estimada en px/frame.
        team_id (Optional[int]): Equipo asignado, si el detector lo aporta.
        jersey_number (Optional[str]): Dorsal, si el OCR lo aporta.
        is_occluded (bool): Evidencia de oclusión en el frame actual.
        occlusion_frames (int): Frames acumulados en estado de oclusión.
        recovered_from_low (bool): La última asociación vino de la etapa 2.
        low_recoveries (int): Veces que el track se recuperó en la etapa 2.
    """

    track_id: int
    bbox: List[float]
    confidence: float
    frame_id: int
    age: int = 1
    hits: int = 1
    hit_streak: int = 1
    time_since_update: int = 0
    position_history: List[Tuple[float, float]] = field(default_factory=list)
    velocity: Tuple[float, float] = (0.0, 0.0)
    team_id: Optional[int] = None
    jersey_number: Optional[str] = None
    is_occluded: bool = False
    occlusion_frames: int = 0
    recovered_from_low: bool = False
    low_recoveries: int = 0


class ByteTrackAdapter:
    """
    Adaptador ByteTrack con la API pública de ``core.tracker.PlayerTracker``.

    Es un reemplazo *drop-in*: mismas firmas y mismos formatos de retorno
    (los diccionarios devueltos son un **superconjunto** de los de
    ``PlayerTracker``: contienen todas sus claves más algunas específicas de
    ByteTrack, por lo que el código existente sigue funcionando).

    Args:
        max_age (int): Frames sin asociación antes de eliminar un track.
        min_hits (int): Asociaciones necesarias para considerar un track
            confirmado (se refleja en la clave ``confirmed``).
        high_threshold (float): Umbral de confianza alta (etapa 1 y creación
            de tracks nuevos).
        low_threshold (float): Confianza mínima para que una detección entre
            en la etapa 2. Por debajo se descarta.
        match_threshold (float): Umbral de *distancia* IoU de la etapa 1, en la
            convención de ByteTrack: se acepta la pareja si
            ``IoU >= 1 - match_threshold`` (0.8 -> IoU >= 0.2).
        second_match_threshold (float): Igual que el anterior para la etapa 2
            (0.5 -> IoU >= 0.5). La etapa 2 es más estricta a propósito.
        backend (str): ``"auto"`` (supervision si está disponible),
            ``"supervision"`` o ``"native"``.
        frame_rate (float): FPS nominal, solo lo usa el backend supervision.
        use_motion_prediction (bool): Extrapola la caja del track con su
            velocidad antes de asociar (backend nativo).

    Raises:
        ValueError: Si algún parámetro está fuera de rango o el backend no existe.
        ImportError: Si se fuerza ``backend="supervision"`` sin la librería.

    Attributes:
        tracks (Dict[int, ByteTrackState]): Tracks activos.
        lost_tracks (Dict[int, ByteTrackState]): Histórico de tracks perdidos.
        next_id (int): ID que se asignará al próximo track.
        backend (str): Backend realmente en uso (``"supervision"`` o ``"native"``).
    """

    def __init__(
        self,
        max_age: int = 30,
        min_hits: int = 3,
        high_threshold: float = 0.6,
        low_threshold: float = 0.1,
        match_threshold: float = 0.8,
        second_match_threshold: float = 0.5,
        backend: str = "auto",
        frame_rate: float = 30.0,
        use_motion_prediction: bool = True,
    ):
        self._validate_params(
            max_age, min_hits, high_threshold, low_threshold,
            match_threshold, second_match_threshold, frame_rate,
        )

        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self.high_threshold = float(high_threshold)
        self.low_threshold = float(low_threshold)
        self.match_threshold = float(match_threshold)
        self.second_match_threshold = float(second_match_threshold)
        self.frame_rate = float(frame_rate)
        self.use_motion_prediction = bool(use_motion_prediction)

        self.backend = self._resolve_backend(backend)

        # Estado (mismos nombres que PlayerTracker para máxima compatibilidad)
        self.tracks: Dict[int, ByteTrackState] = {}
        self.lost_tracks: Dict[int, ByteTrackState] = {}
        self.next_id: int = 1
        self.frame_count: int = 0
        self.max_lost_tracks: int = MAX_LOST_TRACKS

        # Contadores medibles (no son "mejoras", son cuentas reales)
        self._total_tracks_created: int = 0
        self._low_confidence_recoveries: int = 0

        self._sv_tracker = None
        if self.backend == "supervision":
            self._sv_tracker = self._build_supervision_tracker()

        logger.debug(
            "ByteTrackAdapter iniciado (backend=%s, max_age=%d, min_hits=%d, "
            "high=%.2f, low=%.2f, match=%.2f)",
            self.backend, self.max_age, self.min_hits,
            self.high_threshold, self.low_threshold, self.match_threshold,
        )

    # ------------------------------------------------------------------ #
    # Construcción / configuración
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_params(
        max_age: int,
        min_hits: int,
        high_threshold: float,
        low_threshold: float,
        match_threshold: float,
        second_match_threshold: float,
        frame_rate: float,
    ) -> None:
        """Valida los parámetros del constructor.

        Raises:
            ValueError: Si algún parámetro está fuera de rango.
        """
        if max_age < 1:
            raise ValueError(f"max_age debe ser >= 1, recibido {max_age}")
        if min_hits < 1:
            raise ValueError(f"min_hits debe ser >= 1, recibido {min_hits}")
        for name, value in (
            ("high_threshold", high_threshold),
            ("low_threshold", low_threshold),
            ("match_threshold", match_threshold),
            ("second_match_threshold", second_match_threshold),
        ):
            if not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"{name} debe estar en [0, 1], recibido {value}")
        if low_threshold > high_threshold:
            raise ValueError(
                f"low_threshold ({low_threshold}) no puede ser mayor que "
                f"high_threshold ({high_threshold})"
            )
        if frame_rate <= 0:
            raise ValueError(f"frame_rate debe ser > 0, recibido {frame_rate}")

    @staticmethod
    def _resolve_backend(backend: str) -> str:
        """
        Decide qué backend usar.

        Args:
            backend (str): ``"auto"``, ``"supervision"`` o ``"native"``.

        Returns:
            str: Backend efectivo.

        Raises:
            ValueError: Si el nombre no es válido.
            ImportError: Si se exige supervision y no está instalado.
        """
        backend = (backend or "auto").lower()
        if backend not in ("auto", "supervision", "native"):
            raise ValueError(
                f"backend debe ser 'auto', 'supervision' o 'native', recibido '{backend}'"
            )
        if backend == "native":
            return "native"
        if backend == "supervision":
            if not _HAS_SUPERVISION:
                raise ImportError(
                    "backend='supervision' requiere el paquete 'supervision' con "
                    "sv.ByteTrack disponible (pip install supervision)"
                )
            return "supervision"
        return "supervision" if _HAS_SUPERVISION else "native"

    def _build_supervision_tracker(self) -> Any:
        """
        Instancia ``sv.ByteTrack`` mapeando la configuración del adaptador.

        ``minimum_consecutive_frames`` se fija a 1 a propósito: la confirmación
        por ``min_hits`` la gestiona este adaptador, de modo que ambos backends
        se comporten igual.

        Returns:
            Any: Instancia de ``sv.ByteTrack``.

        Raises:
            RuntimeError: Si supervision falla al construir el tracker.
        """
        try:
            with warnings.catch_warnings():
                # sv.ByteTrack emite un FutureWarning de deprecación desde 0.28.
                warnings.simplefilter("ignore")
                return sv.ByteTrack(
                    track_activation_threshold=self.high_threshold,
                    lost_track_buffer=self.max_age,
                    minimum_matching_threshold=self.match_threshold,
                    frame_rate=int(round(self.frame_rate)),
                    minimum_consecutive_frames=1,
                )
        except Exception as exc:  # pragma: no cover - depende de la versión
            raise RuntimeError(
                f"No se pudo construir sv.ByteTrack ({type(exc).__name__}: {exc}). "
                "Usa backend='native'."
            ) from exc

    # ------------------------------------------------------------------ #
    # Utilidades geométricas
    # ------------------------------------------------------------------ #
    def _get_centroid(self, bbox: Sequence[float]) -> Tuple[float, float]:
        """
        Calcula el centroide de un bounding box.

        Args:
            bbox (Sequence[float]): ``[x1, y1, x2, y2]``.

        Returns:
            Tuple[float, float]: ``(cx, cy)``.
        """
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _calculate_iou(self, bbox1: Sequence[float], bbox2: Sequence[float]) -> float:
        """
        Intersection over Union entre dos cajas.

        Args:
            bbox1 (Sequence[float]): ``[x1, y1, x2, y2]``.
            bbox2 (Sequence[float]): ``[x1, y1, x2, y2]``.

        Returns:
            float: IoU en ``[0, 1]``.
        """
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        xi_min = max(x1_min, x2_min)
        yi_min = max(y1_min, y2_min)
        xi_max = min(x1_max, x2_max)
        yi_max = min(y1_max, y2_max)

        if xi_max <= xi_min or yi_max <= yi_min:
            return 0.0

        intersection = (xi_max - xi_min) * (yi_max - yi_min)
        area1 = max(0.0, x1_max - x1_min) * max(0.0, y1_max - y1_min)
        area2 = max(0.0, x2_max - x2_min) * max(0.0, y2_max - y2_min)
        union = area1 + area2 - intersection

        if union <= 0:
            return 0.0
        return float(intersection / union)

    def _iou_matrix(
        self, track_boxes: List[List[float]], det_boxes: List[List[float]]
    ) -> np.ndarray:
        """
        Matriz de IoU vectorizada entre cajas de tracks y de detecciones.

        Usa sv.box_iou_batch de Supervision (optimizado y bien testeado).

        Args:
            track_boxes (List[List[float]]): Cajas de los tracks (N).
            det_boxes (List[List[float]]): Cajas de las detecciones (M).

        Returns:
            np.ndarray: Matriz ``(N, M)`` de IoU.
        """
        if not track_boxes or not det_boxes:
            return np.zeros((len(track_boxes), len(det_boxes)), dtype=float)

        t = np.asarray(track_boxes, dtype=float)  # (N, 4)
        d = np.asarray(det_boxes, dtype=float)    # (M, 4)

        # Usar implementación optimizada de Supervision
        return sv.box_iou_batch(t, d)

    def _associate(
        self,
        track_boxes: List[List[float]],
        det_boxes: List[List[float]],
        min_iou: float,
    ) -> Tuple[List[Tuple[int, int, float]], List[int], List[int]]:
        """
        Asocia cajas de tracks con cajas de detecciones maximizando el IoU.

        Usa asignación húngara (``scipy.optimize.linear_sum_assignment``) y, si
        SciPy no está disponible, un emparejamiento greedy por IoU descendente.

        Args:
            track_boxes (List[List[float]]): Cajas de tracks.
            det_boxes (List[List[float]]): Cajas de detecciones.
            min_iou (float): IoU mínimo aceptable para validar una pareja.

        Returns:
            Tuple: ``(matches, unmatched_tracks, unmatched_dets)`` donde
            ``matches`` es una lista de ``(idx_track, idx_det, iou)``.
        """
        n, m = len(track_boxes), len(det_boxes)
        if n == 0 or m == 0:
            return [], list(range(n)), list(range(m))

        iou = self._iou_matrix(track_boxes, det_boxes)
        matches: List[Tuple[int, int, float]] = []

        if _HAS_SCIPY and linear_sum_assignment is not None:
            try:
                rows, cols = linear_sum_assignment(-iou)
                for r, c in zip(rows, cols):
                    if iou[r, c] >= min_iou:
                        matches.append((int(r), int(c), float(iou[r, c])))
            except Exception as exc:  # pragma: no cover - salvaguarda
                logger.warning(
                    "linear_sum_assignment falló (%s: %s); usando greedy",
                    type(exc).__name__, exc,
                )
                matches = self._greedy_match(iou, min_iou)
        else:
            matches = self._greedy_match(iou, min_iou)

        used_t = {mt[0] for mt in matches}
        used_d = {mt[1] for mt in matches}
        unmatched_tracks = [i for i in range(n) if i not in used_t]
        unmatched_dets = [j for j in range(m) if j not in used_d]
        return matches, unmatched_tracks, unmatched_dets

    @staticmethod
    def _greedy_match(iou: np.ndarray, min_iou: float) -> List[Tuple[int, int, float]]:
        """
        Emparejamiento greedy por IoU descendente (fallback sin SciPy).

        Args:
            iou (np.ndarray): Matriz ``(N, M)`` de IoU.
            min_iou (float): IoU mínimo aceptable.

        Returns:
            List[Tuple[int, int, float]]: Parejas ``(idx_track, idx_det, iou)``.
        """
        matches: List[Tuple[int, int, float]] = []
        used_t: set = set()
        used_d: set = set()

        candidates = [
            (float(iou[i, j]), i, j)
            for i in range(iou.shape[0])
            for j in range(iou.shape[1])
            if iou[i, j] >= min_iou
        ]
        candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

        for value, i, j in candidates:
            if i in used_t or j in used_d:
                continue
            used_t.add(i)
            used_d.add(j)
            matches.append((i, j, value))
        return matches

    def _estimate_velocity(
        self, position_history: List[Tuple[float, float]]
    ) -> Tuple[float, float]:
        """
        Estima la velocidad media (px/frame) con los últimos centroides.

        Args:
            position_history (List[Tuple[float, float]]): Historial de centroides.

        Returns:
            Tuple[float, float]: ``(vx, vy)``.
        """
        if len(position_history) < 2:
            return (0.0, 0.0)
        recent = np.asarray(position_history[-5:], dtype=float)
        if recent.shape[0] < 2:
            return (0.0, 0.0)
        velocities = np.diff(recent, axis=0)
        avg = np.mean(velocities, axis=0)
        return (float(avg[0]), float(avg[1]))

    def _predicted_bbox(self, track: ByteTrackState) -> List[float]:
        """
        Extrapola la caja del track con su velocidad estimada.

        Args:
            track (ByteTrackState): Track a proyectar.

        Returns:
            List[float]: Caja predicha ``[x1, y1, x2, y2]``.
        """
        if not self.use_motion_prediction:
            return list(track.bbox)
        vx, vy = track.velocity
        if vx == 0.0 and vy == 0.0:
            return list(track.bbox)
        steps = float(track.time_since_update + 1)
        x1, y1, x2, y2 = track.bbox
        return [x1 + vx * steps, y1 + vy * steps, x2 + vx * steps, y2 + vy * steps]

    # ------------------------------------------------------------------ #
    # Normalización de entrada
    # ------------------------------------------------------------------ #
    def _normalize_detections(self, detections: Optional[List[Dict]]) -> List[Dict]:
        """
        Valida y normaliza la lista de detecciones de entrada.

        Descarta (con aviso en el log) las detecciones sin ``bbox`` válido y las
        que quedan por debajo de ``low_threshold``. Una detección sin la clave
        ``confidence`` se trata como confianza 1.0.

        Args:
            detections (Optional[List[Dict]]): Detecciones del detector.

        Returns:
            List[Dict]: Detecciones normalizadas, cada una con ``bbox``,
            ``center``, ``confidence`` y el dict original en ``_raw``.
        """
        if not detections:
            return []
        if not isinstance(detections, (list, tuple)):
            raise TypeError(
                f"detections debe ser una lista de dicts, recibido {type(detections).__name__}"
            )

        normalized: List[Dict] = []
        for idx, det in enumerate(detections):
            if not isinstance(det, dict):
                logger.warning("Detección %d ignorada: no es un dict (%s)", idx, type(det).__name__)
                continue

            bbox = det.get("bbox")
            if bbox is None or len(bbox) != 4:
                logger.warning("Detección %d ignorada: 'bbox' ausente o mal formado", idx)
                continue
            try:
                x1, y1, x2, y2 = (float(v) for v in bbox)
            except (TypeError, ValueError):
                logger.warning("Detección %d ignorada: 'bbox' no numérico", idx)
                continue
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                logger.warning("Detección %d ignorada: 'bbox' con valores no finitos", idx)
                continue
            if x2 <= x1 or y2 <= y1:
                logger.warning("Detección %d ignorada: 'bbox' degenerado %s", idx, bbox)
                continue

            raw_conf = det.get("confidence", 1.0)
            try:
                conf = float(raw_conf)
            except (TypeError, ValueError):
                logger.warning("Detección %d ignorada: 'confidence' no numérica", idx)
                continue
            if not math.isfinite(conf):
                logger.warning("Detección %d ignorada: 'confidence' no finita", idx)
                continue
            conf = float(np.clip(conf, 0.0, 1.0))

            if conf < self.low_threshold:
                # Por debajo del umbral bajo ByteTrack descarta la detección.
                continue

            normalized.append({
                "bbox": [x1, y1, x2, y2],
                "center": [(x1 + x2) / 2.0, (y1 + y2) / 2.0],
                "confidence": conf,
                "class_id": int(det.get("class_id", 0) or 0),
                "_raw": det,
            })
        return normalized

    def _split_by_confidence(
        self, detections: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Separa detecciones en alta y baja confianza.

        Args:
            detections (List[Dict]): Detecciones normalizadas.

        Returns:
            Tuple[List[Dict], List[Dict]]: ``(alta, baja)``.
        """
        high = [d for d in detections if d["confidence"] >= self.high_threshold]
        low = [d for d in detections if d["confidence"] < self.high_threshold]
        return high, low

    # ------------------------------------------------------------------ #
    # Ciclo de vida de los tracks
    # ------------------------------------------------------------------ #
    def _create_track(self, detection: Dict, frame_id: int, track_id: Optional[int] = None) -> ByteTrackState:
        """
        Crea un track nuevo a partir de una detección de alta confianza.

        Args:
            detection (Dict): Detección normalizada.
            frame_id (int): Frame actual.
            track_id (Optional[int]): ID forzado (backend supervision).

        Returns:
            ByteTrackState: Track creado y registrado.
        """
        if track_id is None:
            track_id = self.next_id
            self.next_id += 1
        else:
            self.next_id = max(self.next_id, int(track_id) + 1)

        raw = detection.get("_raw", {})
        track = ByteTrackState(
            track_id=int(track_id),
            bbox=list(detection["bbox"]),
            confidence=float(detection["confidence"]),
            frame_id=int(frame_id),
            team_id=raw.get("team_id"),
            jersey_number=raw.get("jersey_number"),
        )
        track.position_history.append(self._get_centroid(track.bbox))
        self.tracks[track.track_id] = track
        self._total_tracks_created += 1
        return track

    def _update_track(
        self,
        track: ByteTrackState,
        detection: Dict,
        frame_id: int,
        from_low: bool,
    ) -> None:
        """
        Actualiza un track con la detección asociada.

        Args:
            track (ByteTrackState): Track a actualizar.
            detection (Dict): Detección normalizada asociada.
            frame_id (int): Frame actual.
            from_low (bool): La asociación viene de la etapa 2 (baja confianza).
        """
        track.bbox = list(detection["bbox"])
        track.confidence = float(detection["confidence"])
        track.hits += 1
        track.hit_streak += 1
        track.time_since_update = 0
        track.frame_id = int(frame_id)
        track.recovered_from_low = bool(from_low)
        if from_low:
            track.low_recoveries += 1
            self._low_confidence_recoveries += 1

        track.position_history.append(self._get_centroid(track.bbox))
        if len(track.position_history) > 50:
            track.position_history.pop(0)
        track.velocity = self._estimate_velocity(track.position_history)

        raw = detection.get("_raw", {})
        if "team_id" in raw:
            track.team_id = raw["team_id"]
        if "jersey_number" in raw:
            track.jersey_number = raw["jersey_number"]

    def _is_occlusion_likely(self, detections: List[Dict], track: ByteTrackState) -> bool:
        """
        Heurística de oclusión: solapamientos parciales o ausencia prolongada.

        Args:
            detections (List[Dict]): Detecciones normalizadas del frame.
            track (ByteTrackState): Track evaluado.

        Returns:
            bool: True si hay evidencia de oclusión.
        """
        overlaps = 0
        for det in detections:
            iou = self._calculate_iou(track.bbox, det["bbox"])
            if 0.1 < iou < 0.9:
                overlaps += 1
        return overlaps > 1 or track.time_since_update > 5

    def _age_and_prune(self, unmatched_track_ids: Sequence[int]) -> int:
        """
        Envejece los tracks sin pareja y elimina los que superan ``max_age``.

        Args:
            unmatched_track_ids (Sequence[int]): IDs sin asociación este frame.

        Returns:
            int: Número de tracks eliminados.
        """
        for track_id in unmatched_track_ids:
            track = self.tracks.get(track_id)
            if track is None:
                continue
            track.time_since_update += 1
            track.hit_streak = 0
            track.recovered_from_low = False

        to_remove = [
            track_id for track_id, track in self.tracks.items()
            if track.time_since_update > self.max_age
        ]
        for track_id in to_remove:
            self.lost_tracks[track_id] = self.tracks.pop(track_id)

        while len(self.lost_tracks) > self.max_lost_tracks:
            oldest = min(self.lost_tracks.keys())
            del self.lost_tracks[oldest]

        return len(to_remove)

    # ------------------------------------------------------------------ #
    # API pública (idéntica a PlayerTracker)
    # ------------------------------------------------------------------ #
    def track(self, detections: List[Dict], frame_id: Optional[int] = None) -> Dict:
        """
        Actualiza los tracks con las detecciones del frame (dos etapas).

        Args:
            detections (List[Dict]): Detecciones ``{'bbox': [x1,y1,x2,y2],
                'confidence': float, 'team_id': int (opcional),
                'jersey_number': str (opcional)}``.
            frame_id (Optional[int]): ID del frame; si es None se usa el contador
                interno.

        Returns:
            dict: ``{'matched', 'new_tracks', 'active_tracks', 'frame_id'}``
            (igual que ``PlayerTracker.track``) más las claves adicionales
            ``'matched_high'``, ``'matched_low'``, ``'removed_tracks'`` y
            ``'backend'``.

        Raises:
            TypeError: Si ``detections`` no es una lista de dicts.
        """
        if frame_id is None:
            frame_id = self.frame_count
        self.frame_count += 1

        normalized = self._normalize_detections(detections)

        # Todos los tracks envejecen un frame (age = vida desde su creación).
        for existing in self.tracks.values():
            existing.age += 1

        if self.backend == "supervision":
            matched_high, matched_low, new_tracks, removed = self._track_supervision(
                normalized, int(frame_id)
            )
        else:
            matched_high, matched_low, new_tracks, removed = self._track_native(
                normalized, int(frame_id)
            )

        # Heurística de oclusión, coherente con PlayerTracker.
        for existing in self.tracks.values():
            existing.is_occluded = self._is_occlusion_likely(normalized, existing)

        return {
            "matched": matched_high + matched_low,
            "new_tracks": new_tracks,
            "active_tracks": len(self.tracks),
            "frame_id": int(frame_id),
            "matched_high": matched_high,
            "matched_low": matched_low,
            "removed_tracks": removed,
            "backend": self.backend,
        }

    def _track_native(
        self, detections: List[Dict], frame_id: int
    ) -> Tuple[int, int, int, int]:
        """
        Implementación nativa de la asociación en dos etapas.

        Args:
            detections (List[Dict]): Detecciones normalizadas.
            frame_id (int): Frame actual.

        Returns:
            Tuple[int, int, int, int]: ``(matched_high, matched_low,
            new_tracks, removed_tracks)``.
        """
        high_dets, low_dets = self._split_by_confidence(detections)

        track_ids = list(self.tracks.keys())
        track_boxes = [self._predicted_bbox(self.tracks[tid]) for tid in track_ids]

        # --- Etapa 1: tracks vs detecciones de ALTA confianza ---------------
        min_iou_stage1 = max(0.0, 1.0 - self.match_threshold)
        matches, unmatched_t_idx, unmatched_d_idx = self._associate(
            track_boxes, [d["bbox"] for d in high_dets], min_iou_stage1
        )
        matched_high = 0
        for t_idx, d_idx, _iou in matches:
            self._update_track(self.tracks[track_ids[t_idx]], high_dets[d_idx], frame_id, from_low=False)
            matched_high += 1

        # --- Etapa 2: tracks sin pareja vs detecciones de BAJA confianza ----
        matched_low = 0
        if unmatched_t_idx and low_dets:
            min_iou_stage2 = max(0.0, 1.0 - self.second_match_threshold)
            rest_ids = [track_ids[i] for i in unmatched_t_idx]
            rest_boxes = [track_boxes[i] for i in unmatched_t_idx]
            matches2, unmatched_t2, _unmatched_low = self._associate(
                rest_boxes, [d["bbox"] for d in low_dets], min_iou_stage2
            )
            for t_idx, d_idx, _iou in matches2:
                self._update_track(self.tracks[rest_ids[t_idx]], low_dets[d_idx], frame_id, from_low=True)
                matched_low += 1
            still_unmatched = [rest_ids[i] for i in unmatched_t2]
        else:
            still_unmatched = [track_ids[i] for i in unmatched_t_idx]

        # --- Nuevos tracks: solo detecciones de ALTA confianza sin pareja ---
        new_tracks = 0
        for d_idx in unmatched_d_idx:
            self._create_track(high_dets[d_idx], frame_id)
            new_tracks += 1

        removed = self._age_and_prune(still_unmatched)
        return matched_high, matched_low, new_tracks, removed

    def _track_supervision(
        self, detections: List[Dict], frame_id: int
    ) -> Tuple[int, int, int, int]:
        """
        Delegación en ``sv.ByteTrack`` traduciendo formatos de entrada y salida.

        Args:
            detections (List[Dict]): Detecciones normalizadas.
            frame_id (int): Frame actual.

        Returns:
            Tuple[int, int, int, int]: ``(matched_high, matched_low,
            new_tracks, removed_tracks)``.

        Raises:
            RuntimeError: Si supervision falla durante la actualización.
        """
        n = len(detections)
        if n:
            sv_dets = sv.Detections(
                xyxy=np.asarray([d["bbox"] for d in detections], dtype=float),
                confidence=np.asarray([d["confidence"] for d in detections], dtype=float),
                class_id=np.asarray([d["class_id"] for d in detections], dtype=int),
                data={"_det_index": np.arange(n)},
            )
        else:
            sv_dets = sv.Detections.empty()

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tracked = self._sv_tracker.update_with_detections(sv_dets)
        except Exception as exc:
            raise RuntimeError(
                f"sv.ByteTrack falló al actualizar el frame {frame_id} "
                f"({type(exc).__name__}: {exc})"
            ) from exc

        matched_high = matched_low = new_tracks = 0
        seen_ids: List[int] = []

        tracker_ids = getattr(tracked, "tracker_id", None)
        if tracker_ids is not None and len(tracked) > 0:
            det_indices = tracked.data.get("_det_index") if tracked.data else None
            for pos in range(len(tracked)):
                raw_tid = tracker_ids[pos]
                if raw_tid is None:
                    continue
                tid = int(raw_tid)
                if det_indices is not None:
                    det = detections[int(det_indices[pos])]
                else:  # pragma: no cover - versiones que no propagan data
                    det = self._match_by_bbox(detections, tracked.xyxy[pos])
                    if det is None:
                        continue

                from_low = det["confidence"] < self.high_threshold
                if tid in self.tracks:
                    self._update_track(self.tracks[tid], det, frame_id, from_low=from_low)
                    if from_low:
                        matched_low += 1
                    else:
                        matched_high += 1
                else:
                    self._create_track(det, frame_id, track_id=tid)
                    new_tracks += 1
                seen_ids.append(tid)

        unmatched = [tid for tid in self.tracks if tid not in set(seen_ids)]
        removed = self._age_and_prune(unmatched)
        return matched_high, matched_low, new_tracks, removed

    @staticmethod
    def _match_by_bbox(detections: List[Dict], bbox: np.ndarray) -> Optional[Dict]:
        """
        Localiza la detección original a partir de su caja (fallback).

        Args:
            detections (List[Dict]): Detecciones normalizadas.
            bbox (np.ndarray): Caja devuelta por supervision.

        Returns:
            Optional[Dict]: Detección coincidente o None.
        """
        for det in detections:
            if np.allclose(np.asarray(det["bbox"], dtype=float), np.asarray(bbox, dtype=float), atol=1e-3):
                return det
        return None

    def _track_to_dict(self, track: ByteTrackState, include_history: bool = False) -> Dict:
        """
        Convierte un track interno al dict público del contrato.

        Args:
            track (ByteTrackState): Track interno.
            include_history (bool): Incluir ``position_history``.

        Returns:
            Dict: Track en formato público (superconjunto del de PlayerTracker).
        """
        center = self._get_centroid(track.bbox) if track.bbox else (0.0, 0.0)
        data = {
            # --- claves idénticas a PlayerTracker ---
            "track_id": track.track_id,
            "bbox": list(track.bbox),
            "confidence": float(track.confidence),
            "age": int(track.age),
            "hits": int(track.hits),
            "team_id": track.team_id,
            "jersey_number": track.jersey_number,
            "is_occluded": bool(track.is_occluded),
            "velocity": tuple(track.velocity),
            "position": center,
            # --- extras del contrato / ByteTrack ---
            "center": [center[0], center[1]],
            "time_since_update": int(track.time_since_update),
            "hit_streak": int(track.hit_streak),
            "confirmed": bool(track.hits >= self.min_hits),
            "recovered_from_low": bool(track.recovered_from_low),
            "low_recoveries": int(track.low_recoveries),
        }
        if include_history:
            data["position_history"] = list(track.position_history)
        return data

    def get_tracks(self, min_confidence: float = 0.0) -> List[Dict]:
        """
        Retorna todos los tracks activos.

        Args:
            min_confidence (float): Confianza mínima para incluir el track.

        Returns:
            List[Dict]: Tracks activos en el formato público.
        """
        return [
            self._track_to_dict(track)
            for track in self.tracks.values()
            if track.confidence >= min_confidence
        ]

    def get_confirmed_tracks(self, min_confidence: float = 0.0) -> List[Dict]:
        """
        Retorna solo los tracks confirmados (``hits >= min_hits``).

        Método adicional (no existe en PlayerTracker); no rompe el drop-in.

        Args:
            min_confidence (float): Confianza mínima para incluir el track.

        Returns:
            List[Dict]: Tracks confirmados.
        """
        return [t for t in self.get_tracks(min_confidence) if t["confirmed"]]

    def get_track_by_id(self, track_id: int) -> Optional[Dict]:
        """
        Obtiene la información de un track concreto.

        Args:
            track_id (int): ID del track.

        Returns:
            Optional[Dict]: Track (incluye ``position_history``) o None si no existe.
        """
        track = self.tracks.get(track_id)
        if track is None:
            return None
        return self._track_to_dict(track, include_history=True)

    def get_statistics(self) -> Dict:
        """
        Estadísticas del tracker.

        Returns:
            dict: Claves de ``PlayerTracker.get_statistics`` más las propias del
            adaptador (``backend``, ``confirmed_tracks``, umbrales y el número
            real de recuperaciones vía detecciones de baja confianza).
        """
        occlusions = sum(1 for t in self.tracks.values() if t.is_occluded)
        confirmed = sum(1 for t in self.tracks.values() if t.hits >= self.min_hits)

        return {
            # --- claves idénticas a PlayerTracker ---
            "active_tracks": len(self.tracks),
            "lost_tracks": len(self.lost_tracks),
            "total_frames": self.frame_count,
            "next_id": self.next_id,
            "occluded_tracks": occlusions,
            "max_age": self.max_age,
            "min_hits": self.min_hits,
            # --- extras de ByteTrack ---
            "confirmed_tracks": confirmed,
            "backend": self.backend,
            "high_threshold": self.high_threshold,
            "low_threshold": self.low_threshold,
            "match_threshold": self.match_threshold,
            "total_tracks_created": self._total_tracks_created,
            "low_confidence_recoveries": self._low_confidence_recoveries,
            "has_supervision": bool(_HAS_SUPERVISION),
            "has_scipy": bool(_HAS_SCIPY),
        }

    def update(self, detections: Optional[List[Dict]] = None,
               frame_id: Optional[int] = None) -> Optional[Dict]:
        """
        Housekeeping (compatible con ``PlayerTracker.update()``).

        Sin argumentos actualiza el contador de frames en oclusión, igual que
        ``PlayerTracker``. Si se le pasan detecciones actúa como alias de
        :meth:`track` por conveniencia.

        Args:
            detections (Optional[List[Dict]]): Detecciones opcionales.
            frame_id (Optional[int]): Frame actual.

        Returns:
            Optional[Dict]: Resultado de :meth:`track` si se pasaron detecciones.
        """
        if detections is not None:
            return self.track(detections, frame_id)

        for track in self.tracks.values():
            if track.is_occluded:
                track.occlusion_frames += 1
            else:
                track.occlusion_frames = 0
        return None

    def reset(self) -> None:
        """Reinicia el tracker (y el backend) a su estado inicial."""
        self.tracks = {}
        self.lost_tracks = {}
        self.next_id = 1
        self.frame_count = 0
        self._total_tracks_created = 0
        self._low_confidence_recoveries = 0

        if self.backend == "supervision" and self._sv_tracker is not None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    self._sv_tracker.reset()
            except Exception as exc:  # pragma: no cover - salvaguarda
                logger.warning(
                    "sv.ByteTrack.reset() falló (%s: %s); se recrea el tracker",
                    type(exc).__name__, exc,
                )
                self._sv_tracker = self._build_supervision_tracker()

    def __repr__(self) -> str:
        return (
            f"ByteTrackAdapter(backend='{self.backend}', max_age={self.max_age}, "
            f"min_hits={self.min_hits}, high_threshold={self.high_threshold}, "
            f"low_threshold={self.low_threshold}, active_tracks={len(self.tracks)})"
        )


__all__ = ["ByteTrackAdapter", "ByteTrackState", "HAS_SUPERVISION", "HAS_SCIPY"]

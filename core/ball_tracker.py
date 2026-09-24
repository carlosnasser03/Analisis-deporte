"""
ball_tracker.py - Tracker temporal avanzado para el balón

Propósito: dar continuidad al seguimiento del balón cuando el detector YOLO falla
intermitentemente o produce falsos positivos (líneas blancas, cabezas, publicidad).

El detector trabaja frame a frame y sin memoria: si en un frame hay tres cajas
candidatas, no tiene forma de saber cuál es realmente el balón. Este módulo añade
la dimensión temporal que falta:

- Mantiene un buffer corto de las últimas posiciones confirmadas.
- Extrapola la siguiente posición esperada (centroide del buffer corregido por la
  velocidad estimada).
- Ante varios candidatos elige el **más cercano a la predicción**, no el de mayor
  confianza: la coherencia espacial es mejor discriminador que el score de YOLO
  para un objeto pequeño y rápido.
- Descarta candidatos cuyo salto respecto a la predicción sea físicamente
  imposible (`max_displacement_px`).
- Si no llega ningún candidato válido, interpola la posición predicha durante un
  número acotado de frames (`max_missing_frames`) antes de declarar el balón
  perdido y reiniciar el buffer.

Inspirado conceptualmente en `sports/common/ball.py` de roboflow-sports, ampliado
con velocidad, rechazo por desplazamiento, interpolación y estadísticas.

Dependencias: solo `numpy` y la librería estándar.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Número máximo de posiciones guardadas en la trayectoria histórica.
# Evita que el consumo de memoria crezca sin límite en vídeos largos.
_MAX_TRAJECTORY_POINTS = 50_000

# Número de saltos usados para estimar la velocidad instantánea.
_VELOCITY_WINDOW = 5


class BallTracker:
    """
    Tracker temporal del balón basado en buffer de posiciones y extrapolación.

    A diferencia de un tracker de jugadores (multi-objeto), aquí solo existe un
    objeto: el balón. Por eso no hay asignación de IDs ni matching húngaro, sino
    una única hipótesis de trayectoria que se confirma, se extrapola o se pierde.

    Attributes:
        buffer_size (int): Capacidad del buffer de posiciones confirmadas.
        max_displacement_px (float): Salto máximo tolerado entre la predicción y
            el candidato aceptado, en píxeles.
        max_missing_frames (int): Frames consecutivos que se interpola antes de
            declarar el balón perdido.
    """

    def __init__(self,
                 buffer_size: int = 10,
                 max_displacement_px: float = 150.0,
                 max_missing_frames: int = 15) -> None:
        """
        Inicializa el tracker del balón.

        Args:
            buffer_size (int): Número de posiciones recientes usadas para
                estimar centroide y velocidad. Debe ser >= 1.
            max_displacement_px (float): Distancia máxima (píxeles) entre la
                posición predicha y un candidato para considerarlo válido.
                Debe ser > 0.
            max_missing_frames (int): Frames consecutivos sin detección válida
                durante los cuales se devuelve la posición interpolada. Pasado
                ese límite el balón se considera perdido y el buffer se limpia.
                Debe ser >= 0.

        Raises:
            ValueError: Si algún parámetro está fuera de rango.
        """
        if not isinstance(buffer_size, int) or buffer_size < 1:
            raise ValueError(f"buffer_size debe ser un entero >= 1, recibido: {buffer_size!r}")
        if not isinstance(max_displacement_px, (int, float)) or max_displacement_px <= 0:
            raise ValueError(
                f"max_displacement_px debe ser un número > 0, recibido: {max_displacement_px!r}"
            )
        if not isinstance(max_missing_frames, int) or max_missing_frames < 0:
            raise ValueError(
                f"max_missing_frames debe ser un entero >= 0, recibido: {max_missing_frames!r}"
            )

        self.buffer_size = int(buffer_size)
        self.max_displacement_px = float(max_displacement_px)
        self.max_missing_frames = int(max_missing_frames)

        # Buffer de posiciones confirmadas (incluye interpoladas, que propagan
        # la trayectoria durante las oclusiones).
        self.buffer: Deque[Tuple[float, float]] = deque(maxlen=self.buffer_size)

        # Trayectoria histórica completa (para dibujar/analizar a posteriori).
        self.trajectory: List[Dict[str, Any]] = []

        self.frame_count: int = 0
        self._frames_missing: int = 0
        self._last_bbox_size: Optional[Tuple[float, float]] = None
        self._last_confidence: Optional[float] = None

        self._stats: Dict[str, int] = {
            'frames_processed': 0,
            'frames_detected': 0,
            'frames_interpolated': 0,
            'frames_lost': 0,
            'candidates_seen': 0,
            'candidates_invalid': 0,
            'candidates_rejected_displacement': 0,
            'track_losses': 0,
        }

    # ------------------------------------------------------------------ #
    # Utilidades internas de validación / geometría
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_finite_number(value: Any) -> bool:
        """
        Indica si un valor es un número real finito (no bool, no NaN, no inf).

        Args:
            value (Any): Valor a comprobar.

        Returns:
            bool: True si es un número finito utilizable como coordenada.
        """
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float, np.integer, np.floating)):
            return math.isfinite(float(value))
        return False

    @classmethod
    def _parse_bbox(cls, raw_bbox: Any) -> Optional[List[float]]:
        """
        Valida y normaliza un bounding box a [x1, y1, x2, y2] con x1<=x2, y1<=y2.

        Args:
            raw_bbox (Any): Valor candidato a bbox.

        Returns:
            Optional[List[float]]: bbox normalizado o None si es inválido.
        """
        if raw_bbox is None:
            return None
        if isinstance(raw_bbox, np.ndarray):
            raw_bbox = raw_bbox.flatten().tolist()
        if not isinstance(raw_bbox, (list, tuple)) or len(raw_bbox) != 4:
            return None
        if not all(cls._is_finite_number(v) for v in raw_bbox):
            return None

        x1, y1, x2, y2 = (float(v) for v in raw_bbox)
        # Normalizar esquinas invertidas en lugar de descartar la detección.
        if x1 > x2:
            x1, x2 = x2, x1
        if y1 > y2:
            y1, y2 = y2, y1
        return [x1, y1, x2, y2]

    @classmethod
    def _parse_center(cls, raw_center: Any) -> Optional[List[float]]:
        """
        Valida un centro y lo normaliza a [cx, cy].

        Args:
            raw_center (Any): Valor candidato a centro.

        Returns:
            Optional[List[float]]: centro válido o None.
        """
        if raw_center is None:
            return None
        if isinstance(raw_center, np.ndarray):
            raw_center = raw_center.flatten().tolist()
        if not isinstance(raw_center, (list, tuple)) or len(raw_center) != 2:
            return None
        if not all(cls._is_finite_number(v) for v in raw_center):
            return None
        return [float(raw_center[0]), float(raw_center[1])]

    @classmethod
    def _parse_confidence(cls, raw_confidence: Any) -> float:
        """
        Normaliza la confianza al rango [0, 1].

        Args:
            raw_confidence (Any): Valor candidato a confianza.

        Returns:
            float: Confianza saneada; 0.0 si el valor es inválido o falta.
        """
        if not cls._is_finite_number(raw_confidence):
            return 0.0
        return float(min(1.0, max(0.0, float(raw_confidence))))

    def _normalize_candidates(self, candidates: Any) -> List[Dict[str, Any]]:
        """
        Convierte la entrada cruda en una lista de candidatos utilizables.

        Acepta listas, tuplas, arrays, un único dict o None. Descarta elementos
        que no aporten una posición válida (ni 'center' ni 'bbox' utilizables).

        Args:
            candidates (Any): Candidatos crudos del detector.

        Returns:
            List[Dict[str, Any]]: Candidatos saneados con claves
                'center', 'bbox' y 'confidence'.
        """
        if candidates is None:
            return []
        if isinstance(candidates, dict):
            candidates = [candidates]
        if isinstance(candidates, np.ndarray):
            candidates = candidates.tolist()
        if not isinstance(candidates, (list, tuple)):
            logger.warning(
                "BallTracker.update: 'candidates' de tipo %s no iterable como lista; "
                "se ignora el frame.", type(candidates).__name__
            )
            return []

        parsed: List[Dict[str, Any]] = []
        for raw in candidates:
            self._stats['candidates_seen'] += 1

            if not isinstance(raw, dict):
                self._stats['candidates_invalid'] += 1
                continue

            bbox = self._parse_bbox(raw.get('bbox'))
            center = self._parse_center(raw.get('center'))

            if center is None and bbox is not None:
                center = [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0]

            if center is None:
                self._stats['candidates_invalid'] += 1
                continue

            parsed.append({
                'center': center,
                'bbox': bbox,
                'confidence': self._parse_confidence(raw.get('confidence')),
            })

        return parsed

    def _estimate_velocity(self) -> Optional[Tuple[float, float]]:
        """
        Estima la velocidad media (px/frame) a partir del buffer.

        Returns:
            Optional[Tuple[float, float]]: (vx, vy) o None si no hay al menos
                dos posiciones en el buffer.
        """
        if len(self.buffer) < 2:
            return None

        recent = np.asarray(list(self.buffer)[-(_VELOCITY_WINDOW + 1):], dtype=float)
        deltas = np.diff(recent, axis=0)
        velocity = deltas.mean(axis=0)
        return (float(velocity[0]), float(velocity[1]))

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #

    def predict_next_position(self) -> Optional[Tuple[float, float]]:
        """
        Predice la posición del balón en el siguiente frame.

        La predicción parte del centroide del buffer (que promedia el ruido de
        detección) y le suma la velocidad estimada multiplicada por el desfase
        temporal del propio centroide: el centroide de N posiciones equiespaciadas
        corresponde al instante (N-1)/2 frames en el pasado, por lo que hay que
        avanzar (N-1)/2 + 1 pasos para situarse en el frame siguiente. Con
        velocidad constante la extrapolación es exacta; con trayectorias curvas
        introduce un pequeño retardo, deseable como suavizado.

        Returns:
            Optional[Tuple[float, float]]: (x, y) predicho, o None si el buffer
                está vacío (no hay historia sobre la que extrapolar).
        """
        if len(self.buffer) == 0:
            return None

        positions = np.asarray(list(self.buffer), dtype=float)
        centroid = positions.mean(axis=0)

        velocity = self._estimate_velocity()
        if velocity is None:
            return (float(centroid[0]), float(centroid[1]))

        lag_steps = (len(self.buffer) - 1) / 2.0 + 1.0
        predicted = centroid + np.asarray(velocity, dtype=float) * lag_steps
        return (float(predicted[0]), float(predicted[1]))

    def update(self,
               candidates: List[Dict],
               frame_id: Optional[int] = None) -> Dict:
        """
        Procesa los candidatos de un frame y actualiza el estado del tracker.

        Estrategia:
            1. Si el buffer está vacío no hay predicción posible: se elige el
               candidato de mayor confianza (arranque en frío).
            2. Con buffer no vacío se elige el candidato más cercano a la
               posición predicha, ignorando la confianza.
            3. Si ese candidato salta más de `max_displacement_px` respecto a la
               predicción se descarta (falso positivo: línea, cabeza, etc.).
            4. Sin candidato válido se devuelve la posición predicha marcada como
               interpolada, hasta `max_missing_frames` frames consecutivos.
            5. Superado ese límite el balón se declara perdido y el buffer se
               limpia, de modo que la siguiente detección reinicia el track.

        Args:
            candidates (List[Dict]): Candidatos del frame. Cada uno con
                'center' [cx, cy] y/o 'bbox' [x1, y1, x2, y2] y opcionalmente
                'confidence'. Se admite lista vacía, None o entradas malformadas.
            frame_id (Optional[int]): ID del frame. Si es None se usa un
                contador interno.

        Returns:
            dict: {
                'detected': bool,
                'center': [x, y] | None,
                'bbox': [x1, y1, x2, y2] | None,
                'confidence': float | None,
                'interpolated': bool,
                'frames_missing': int,
                'velocity': [vx, vy] | None,
            }
        """
        if frame_id is None:
            frame_id = self.frame_count
        self.frame_count += 1
        self._stats['frames_processed'] += 1

        try:
            parsed = self._normalize_candidates(candidates)
        except Exception as exc:  # pragma: no cover - blindaje ante entradas exóticas
            logger.error("BallTracker: error saneando candidatos del frame %s: %s",
                         frame_id, exc)
            parsed = []

        prediction = self.predict_next_position()
        chosen: Optional[Dict[str, Any]] = None

        if parsed:
            if prediction is None:
                # Arranque en frío: sin historia, la confianza es el único criterio.
                chosen = max(parsed, key=lambda c: c['confidence'])
            else:
                pred = np.asarray(prediction, dtype=float)
                centers = np.asarray([c['center'] for c in parsed], dtype=float)
                distances = np.linalg.norm(centers - pred, axis=1)
                best_idx = int(np.argmin(distances))

                if distances[best_idx] <= self.max_displacement_px:
                    chosen = parsed[best_idx]
                else:
                    # Todos los candidatos son incompatibles con la trayectoria.
                    self._stats['candidates_rejected_displacement'] += len(parsed)
                    logger.debug(
                        "Frame %s: %d candidato(s) rechazado(s), salto mínimo %.1f px "
                        "> max_displacement_px=%.1f",
                        frame_id, len(parsed), float(distances[best_idx]),
                        self.max_displacement_px
                    )

        if chosen is not None:
            return self._accept_detection(chosen, frame_id)
        return self._handle_missing(prediction, frame_id)

    def _accept_detection(self, chosen: Dict[str, Any], frame_id: int) -> Dict:
        """
        Confirma un candidato como posición real del balón.

        Args:
            chosen (Dict[str, Any]): Candidato saneado elegido.
            frame_id (int): ID del frame procesado.

        Returns:
            dict: Resultado de `update()` para este frame.
        """
        center = [float(chosen['center'][0]), float(chosen['center'][1])]
        bbox = chosen['bbox']
        confidence = float(chosen['confidence'])

        self.buffer.append((center[0], center[1]))
        self._frames_missing = 0
        self._last_confidence = confidence
        if bbox is not None:
            self._last_bbox_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])
        elif self._last_bbox_size is not None:
            bbox = self._bbox_from_center(center)

        self._stats['frames_detected'] += 1

        velocity = self._estimate_velocity()
        result = {
            'detected': True,
            'center': center,
            'bbox': list(bbox) if bbox is not None else None,
            'confidence': confidence,
            'interpolated': False,
            'frames_missing': 0,
            'velocity': [velocity[0], velocity[1]] if velocity is not None else None,
        }
        self._append_trajectory(result, frame_id)
        return result

    def _handle_missing(self,
                        prediction: Optional[Tuple[float, float]],
                        frame_id: int) -> Dict:
        """
        Gestiona un frame sin candidato válido: interpola o declara pérdida.

        Args:
            prediction (Optional[Tuple[float, float]]): Posición predicha, si la hay.
            frame_id (int): ID del frame procesado.

        Returns:
            dict: Resultado de `update()` para este frame.
        """
        self._frames_missing += 1

        puede_interpolar = (
            prediction is not None
            and self._frames_missing <= self.max_missing_frames
        )

        if puede_interpolar:
            center = [float(prediction[0]), float(prediction[1])]
            # Propagar la predicción al buffer mantiene viva la trayectoria
            # durante la oclusión, en vez de congelar la posición.
            self.buffer.append((center[0], center[1]))
            self._stats['frames_interpolated'] += 1

            velocity = self._estimate_velocity()
            result = {
                'detected': False,
                'center': center,
                'bbox': self._bbox_from_center(center),
                'confidence': self._last_confidence,
                'interpolated': True,
                'frames_missing': self._frames_missing,
                'velocity': [velocity[0], velocity[1]] if velocity is not None else None,
            }
            self._append_trajectory(result, frame_id)
            return result

        # Balón perdido: se limpia la hipótesis para poder reengancharla desde cero.
        if len(self.buffer) > 0:
            self._stats['track_losses'] += 1
            logger.info(
                "Frame %s: balón perdido tras %d frames sin detección válida; "
                "se reinicia el buffer.", frame_id, self._frames_missing
            )
            self.buffer.clear()
            self._last_bbox_size = None
            self._last_confidence = None

        self._stats['frames_lost'] += 1
        return {
            'detected': False,
            'center': None,
            'bbox': None,
            'confidence': None,
            'interpolated': False,
            'frames_missing': self._frames_missing,
            'velocity': None,
        }

    def _bbox_from_center(self, center: Sequence[float]) -> Optional[List[float]]:
        """
        Reconstruye un bbox sintético alrededor de un centro usando el último
        tamaño de caja conocido.

        Args:
            center (Sequence[float]): [cx, cy].

        Returns:
            Optional[List[float]]: bbox estimado o None si nunca hubo un bbox real.
        """
        if self._last_bbox_size is None:
            return None
        w, h = self._last_bbox_size
        cx, cy = float(center[0]), float(center[1])
        return [cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0]

    def _append_trajectory(self, result: Dict[str, Any], frame_id: int) -> None:
        """
        Añade el resultado del frame a la trayectoria histórica.

        Args:
            result (Dict[str, Any]): Resultado devuelto por `update()`.
            frame_id (int): ID del frame.
        """
        self.trajectory.append({
            'frame_id': int(frame_id),
            'center': list(result['center']) if result['center'] is not None else None,
            'bbox': list(result['bbox']) if result['bbox'] is not None else None,
            'confidence': result['confidence'],
            'interpolated': bool(result['interpolated']),
            'velocity': list(result['velocity']) if result['velocity'] is not None else None,
        })
        if len(self.trajectory) > _MAX_TRAJECTORY_POINTS:
            del self.trajectory[0]

    def get_trajectory(self) -> List[Dict]:
        """
        Retorna la trayectoria histórica del balón.

        Solo incluye frames en los que hubo posición (detectada o interpolada);
        los frames con el balón perdido no generan punto.

        Returns:
            List[Dict]: Lista de puntos con 'frame_id', 'center', 'bbox',
                'confidence', 'interpolated' y 'velocity'.
        """
        return [dict(point) for point in self.trajectory]

    def get_statistics(self) -> Dict:
        """
        Retorna estadísticas acumuladas del tracker.

        Returns:
            dict: Contadores absolutos, tasas y configuración vigente.
        """
        procesados = self._stats['frames_processed']
        detectados = self._stats['frames_detected']
        interpolados = self._stats['frames_interpolated']

        def _ratio(numerador: int) -> float:
            return float(numerador) / procesados if procesados > 0 else 0.0

        velocity = self._estimate_velocity()

        return {
            'frames_processed': procesados,
            'frames_detected': detectados,
            'frames_interpolated': interpolados,
            'frames_lost': self._stats['frames_lost'],
            'candidates_seen': self._stats['candidates_seen'],
            'candidates_invalid': self._stats['candidates_invalid'],
            'candidates_rejected_displacement': self._stats['candidates_rejected_displacement'],
            'track_losses': self._stats['track_losses'],
            'detection_rate': _ratio(detectados),
            'interpolation_rate': _ratio(interpolados),
            'coverage_rate': _ratio(detectados + interpolados),
            'frames_missing': self._frames_missing,
            'buffer_length': len(self.buffer),
            'buffer_size': self.buffer_size,
            'trajectory_points': len(self.trajectory),
            'current_velocity': [velocity[0], velocity[1]] if velocity is not None else None,
            'max_displacement_px': self.max_displacement_px,
            'max_missing_frames': self.max_missing_frames,
        }

    def reset(self) -> None:
        """Reinicia el tracker a su estado inicial (buffer, trayectoria y stats)."""
        self.buffer.clear()
        self.trajectory = []
        self.frame_count = 0
        self._frames_missing = 0
        self._last_bbox_size = None
        self._last_confidence = None
        for key in self._stats:
            self._stats[key] = 0

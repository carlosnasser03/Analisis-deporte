"""
team_classifier_embeddings.py - Clasificación de equipos por embeddings visuales

Propósito
---------
Alternativa más robusta a `core/team_classifier.py` (que clusteriza únicamente
por color HSV dominante). En lugar de reducir cada jugador a un color medio,
este módulo describe cada recorte con un **embedding visual** de mayor
dimensionalidad y agrupa esos embeddings con KMeans.

Motivación técnica (sin afirmar métricas no medidas): un color medio colapsa
toda la apariencia del jugador en 3 números, por lo que sombras, uniformes de
tonos parecidos o el portero (que viste distinto a su equipo) desplazan ese
punto y rompen el clustering. Un embedding conserva estructura espacial
(torso vs. piernas), distribución completa de tonos y textura, lo que da al
clustering más información para separar equipos.

Pipeline interno
----------------
1. Recorte de cada bbox del frame (con clipping a los límites del frame).
2. Embedding por recorte:
   - `SiglipVisionModel` (HuggingFace `transformers`) si está disponible.
   - Si no: descriptor clásico OpenCV (histogramas HSV multi-región +
     textura por gradientes Sobel). El módulo funciona sin `transformers`.
3. Reducción de dimensionalidad opcional: `umap-learn` > PCA (scikit-learn o
   implementación numpy interna) > embeddings crudos.
4. KMeans (scikit-learn si está instalado, si no implementación numpy interna).
5. Caché de embeddings por `track_id` para no recalcular en cada frame.

Compatibilidad de API
---------------------
`train(player_boxes, frame)` y `classify(player_boxes, frame)` tienen la misma
firma y el mismo formato de retorno que `core.team_classifier.TeamClassifier`,
por lo que ambas clases son intercambiables. Los parámetros `track_ids` son
opcionales y no rompen la compatibilidad.

Dependencias opcionales: `transformers`, `torch`, `Pillow`, `umap-learn`,
`scikit-learn`. Ninguna es obligatoria.
"""

from __future__ import annotations

import importlib.util
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Generator, Iterable, List, Optional, Sequence, Tuple, TypeVar

import cv2
import numpy as np

logger = logging.getLogger(__name__)

V = TypeVar("V")

# ---------------------------------------------------------------------------
# Detección de dependencias opcionales (sin importarlas: `find_spec` no ejecuta
# el módulo, así que el import de este archivo sigue siendo barato).
# ---------------------------------------------------------------------------


def _module_available(name: str) -> bool:
    """Comprueba si un módulo es importable sin llegar a importarlo."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):  # pragma: no cover - entornos exóticos
        return False


_HAS_TRANSFORMERS = _module_available("transformers")
_HAS_TORCH = _module_available("torch")
_HAS_PIL = _module_available("PIL")
_HAS_UMAP = _module_available("umap")
_HAS_SKLEARN = _module_available("sklearn")

#: Backend basado en SiglipVisionModel (requiere transformers + torch + Pillow).
BACKEND_SIGLIP = "siglip"
#: Backend de respaldo: histogramas HSV multi-región + textura, solo OpenCV.
BACKEND_FALLBACK = "opencv_hsv_texture"

#: Modelo por defecto (mismo que usa roboflow-sports).
DEFAULT_MODEL_NAME = "google/siglip-base-patch16-224"

#: Tamaño mínimo (px) de un recorte para considerarlo utilizable.
_MIN_CROP_PIXELS = 4

#: Tamaño normalizado (ancho, alto) de los recortes en el backend de respaldo.
_FALLBACK_CROP_SIZE = (48, 96)

#: Regiones (y0, y1, x0, x1) en fracciones del recorte, con su peso relativo.
#: El torso pesa más porque es donde vive el color de la camiseta.
_FALLBACK_REGIONS: Tuple[Tuple[float, float, float, float, float], ...] = (
    (0.00, 0.25, 0.00, 1.00, 0.5),   # cabeza / hombros
    (0.20, 0.55, 0.15, 0.85, 1.5),   # torso central (camiseta)
    (0.25, 0.60, 0.00, 1.00, 1.0),   # torso completo
    (0.60, 1.00, 0.00, 1.00, 0.7),   # piernas / pantalón
)

_HIST_BINS_H = 12
_HIST_BINS_S = 8
_HIST_BINS_V = 8
_TEXTURE_BINS = 8


def create_batches(sequence: Iterable[V], batch_size: int) -> Generator[List[V], None, None]:
    """
    Divide una secuencia en lotes de tamaño fijo.

    Args:
        sequence (Iterable[V]): Secuencia de entrada.
        batch_size (int): Tamaño máximo de cada lote (mínimo 1).

    Yields:
        List[V]: Lotes sucesivos de la secuencia.
    """
    batch_size = max(int(batch_size), 1)
    current: List[V] = []
    for element in sequence:
        current.append(element)
        if len(current) == batch_size:
            yield current
            current = []
    if current:
        yield current


# ---------------------------------------------------------------------------
# Implementaciones numpy de respaldo (usadas si scikit-learn no está instalado)
# ---------------------------------------------------------------------------


class _NumpyKMeans:
    """
    KMeans mínimo en numpy puro con inicialización k-means++.

    Existe para que el módulo funcione sin scikit-learn. Expone el subconjunto
    de la API de `sklearn.cluster.KMeans` que este módulo necesita:
    `fit`, `predict`, `cluster_centers_`, `labels_` e `inertia_`.
    """

    def __init__(
        self,
        n_clusters: int = 2,
        n_init: int = 10,
        max_iter: int = 300,
        tol: float = 1e-4,
        random_state: int = 42,
    ):
        self.n_clusters = int(n_clusters)
        self.n_init = int(n_init)
        self.max_iter = int(max_iter)
        self.tol = float(tol)
        self.random_state = int(random_state)
        self.cluster_centers_: Optional[np.ndarray] = None
        self.labels_: Optional[np.ndarray] = None
        self.inertia_: float = float("inf")

    @staticmethod
    def _sq_distances(x: np.ndarray, centers: np.ndarray) -> np.ndarray:
        """Distancias euclídeas al cuadrado entre cada fila de X y cada centro."""
        diff = x[:, None, :] - centers[None, :, :]
        return np.sum(diff * diff, axis=2)

    def _kmeans_plusplus(self, x: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        n_samples = x.shape[0]
        centers = np.empty((self.n_clusters, x.shape[1]), dtype=np.float64)
        first = int(rng.integers(n_samples))
        centers[0] = x[first]
        closest = np.sum((x - centers[0]) ** 2, axis=1)
        for k in range(1, self.n_clusters):
            total = float(closest.sum())
            if total <= 0.0 or not np.isfinite(total):
                centers[k] = x[int(rng.integers(n_samples))]
            else:
                probs = closest / total
                centers[k] = x[int(rng.choice(n_samples, p=probs))]
            closest = np.minimum(closest, np.sum((x - centers[k]) ** 2, axis=1))
        return centers

    def fit(self, x: np.ndarray) -> "_NumpyKMeans":
        """Ajusta los centroides sobre `x` (n_samples, n_features)."""
        x = np.asarray(x, dtype=np.float64)
        if x.ndim != 2:
            raise ValueError("KMeans espera una matriz 2D (n_samples, n_features)")
        if x.shape[0] < self.n_clusters:
            raise ValueError(
                f"Se necesitan al menos {self.n_clusters} muestras, hay {x.shape[0]}"
            )

        rng = np.random.default_rng(self.random_state)
        best_inertia = float("inf")
        best_centers: Optional[np.ndarray] = None
        best_labels: Optional[np.ndarray] = None

        for _ in range(max(1, self.n_init)):
            centers = self._kmeans_plusplus(x, rng)
            labels = np.zeros(x.shape[0], dtype=int)
            for _ in range(self.max_iter):
                distances = self._sq_distances(x, centers)
                labels = np.argmin(distances, axis=1)
                new_centers = centers.copy()
                for k in range(self.n_clusters):
                    members = x[labels == k]
                    if members.shape[0] > 0:
                        new_centers[k] = members.mean(axis=0)
                    else:
                        # Cluster vacío: lo reubicamos en el punto peor cubierto.
                        worst = int(np.argmax(np.min(distances, axis=1)))
                        new_centers[k] = x[worst]
                shift = float(np.linalg.norm(new_centers - centers))
                centers = new_centers
                if shift <= self.tol:
                    break

            distances = self._sq_distances(x, centers)
            labels = np.argmin(distances, axis=1)
            inertia = float(np.sum(np.min(distances, axis=1)))
            if inertia < best_inertia:
                best_inertia = inertia
                best_centers = centers
                best_labels = labels

        self.cluster_centers_ = best_centers
        self.labels_ = best_labels
        self.inertia_ = best_inertia
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Asigna cada fila de `x` al centroide más cercano."""
        if self.cluster_centers_ is None:
            raise RuntimeError("KMeans no ha sido ajustado")
        x = np.asarray(x, dtype=np.float64)
        return np.argmin(self._sq_distances(x, self.cluster_centers_), axis=1)


class _NumpyPCA:
    """
    PCA mínimo por SVD en numpy puro (respaldo si scikit-learn no está).

    Expone `fit`, `transform` y `fit_transform`.
    """

    def __init__(self, n_components: int = 3):
        self.n_components = int(n_components)
        self.mean_: Optional[np.ndarray] = None
        self.components_: Optional[np.ndarray] = None

    def fit(self, x: np.ndarray) -> "_NumpyPCA":
        x = np.asarray(x, dtype=np.float64)
        self.mean_ = x.mean(axis=0)
        centered = x - self.mean_
        n_components = max(1, min(self.n_components, min(centered.shape)))
        try:
            _, _, vt = np.linalg.svd(centered, full_matrices=False)
        except np.linalg.LinAlgError as exc:  # pragma: no cover - numéricamente raro
            raise RuntimeError(f"SVD no convergió en PCA de respaldo: {exc}") from exc
        self.components_ = vt[:n_components]
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.components_ is None or self.mean_ is None:
            raise RuntimeError("PCA no ha sido ajustado")
        x = np.asarray(x, dtype=np.float64)
        return (x - self.mean_) @ self.components_.T

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        return self.fit(x).transform(x)


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------


@dataclass
class EmbeddingTeamProfile:
    """Perfil visual agregado de un equipo tras el entrenamiento."""

    team_id: int
    name: str
    n_samples: int = 0
    share: float = 0.0
    mean_bgr: Tuple[int, int, int] = (0, 0, 0)
    mean_hsv: Tuple[int, int, int] = (0, 0, 0)
    centroid: Optional[np.ndarray] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Clasificador principal
# ---------------------------------------------------------------------------


class EmbeddingTeamClassifier:
    """
    Clasificador de equipos por embeddings visuales.

    Es API-compatible con `core.team_classifier.TeamClassifier`: mismas firmas
    de `train`/`classify` y mismo formato de retorno, de modo que puede
    sustituirlo sin tocar el código llamante.

    Attributes:
        n_clusters (int): Número de equipos a separar.
        device (str): Dispositivo torch para el backend SigLIP ('cpu'/'cuda').
        model_name (str): Identificador HuggingFace del modelo de visión.
        backend (str): Backend efectivo en uso (`BACKEND_SIGLIP` o
            `BACKEND_FALLBACK`). Se resuelve la primera vez que se extraen
            embeddings.
        reduction_method (str): 'umap', 'pca' o 'none' tras entrenar.
        trained (bool): Indica si el clasificador ya fue entrenado.
        n_samples (int): Número de recortes válidos usados en el entrenamiento.
    """

    def __init__(
        self,
        n_clusters: int = 2,
        device: str = "cpu",
        model_name: str = DEFAULT_MODEL_NAME,
        batch_size: int = 32,
        use_transformers: bool = True,
        use_reduction: bool = True,
        n_components: int = 3,
        random_state: int = 42,
        cache_enabled: bool = True,
        max_cache_size: int = 1024,
        min_confidence: float = 0.3,
        umap_min_samples: int = 12,
    ):
        """
        Inicializa el clasificador.

        Args:
            n_clusters (int): Número de equipos/clusters (default: 2).
            device (str): Dispositivo para el modelo de visión ('cpu' o 'cuda').
                Si se pide 'cuda' y no está disponible, se degrada a 'cpu'.
            model_name (str): Modelo HuggingFace usado si `transformers` está
                instalado (default: 'google/siglip-base-patch16-224').
            batch_size (int): Tamaño de lote para la inferencia del modelo.
            use_transformers (bool): Si False, fuerza el backend OpenCV aunque
                `transformers` esté instalado (útil en tests y en CPU lenta).
            use_reduction (bool): Activa la reducción de dimensionalidad.
            n_components (int): Dimensiones objetivo tras la reducción.
            random_state (int): Semilla para KMeans/UMAP (reproducibilidad).
            cache_enabled (bool): Activa el caché de embeddings por track_id.
            max_cache_size (int): Máximo de embeddings cacheados (FIFO).
            min_confidence (float): Umbral de confianza para marcar una
                clasificación como válida.
            umap_min_samples (int): Mínimo de muestras para intentar UMAP;
                por debajo se usa PCA (UMAP es inestable con pocos puntos).

        Raises:
            ValueError: Si `n_clusters` es menor que 1.
        """
        if int(n_clusters) < 1:
            raise ValueError(f"n_clusters debe ser >= 1, se recibió {n_clusters}")

        self.n_clusters = int(n_clusters)
        self.device = str(device)
        self.model_name = str(model_name)
        self.batch_size = max(1, int(batch_size))
        self.use_transformers = bool(use_transformers)
        self.use_reduction = bool(use_reduction)
        self.n_components = max(1, int(n_components))
        self.random_state = int(random_state)
        self.cache_enabled = bool(cache_enabled)
        self.max_cache_size = max(0, int(max_cache_size))
        self.min_confidence = float(min_confidence)
        self.umap_min_samples = max(4, int(umap_min_samples))

        # Estado de entrenamiento
        self.trained: bool = False
        self.n_samples: int = 0
        self.backend: str = BACKEND_FALLBACK
        self.reduction_method: str = "none"
        self.embedding_dim: Optional[int] = None
        self.team_profiles: Dict[int, EmbeddingTeamProfile] = {}
        self.cluster_assignments: Dict[str, List] = {}

        # Modelos internos
        self.kmeans_model: Any = None
        self.reducer: Any = None
        self._model: Any = None
        self._processor: Any = None
        self._torch: Any = None
        self._model_device: str = "cpu"
        self._model_load_attempted: bool = False

        # Caché de embeddings por track_id
        self._cache: "OrderedDict[Any, np.ndarray]" = OrderedDict()
        self._cache_hits: int = 0
        self._cache_misses: int = 0

        # Contadores de clasificación
        self._n_classified: int = 0
        self._n_valid_classified: int = 0

    # ------------------------------------------------------------------
    # Recortes y descriptores
    # ------------------------------------------------------------------

    def _extract_crop(self, frame: np.ndarray, bbox: Sequence[float]) -> Optional[np.ndarray]:
        """
        Recorta la región del jugador, aplicando clipping a los límites del frame.

        Args:
            frame (np.ndarray): Frame BGR (H, W, 3).
            bbox (Sequence[float]): Caja [x1, y1, x2, y2] en píxeles absolutos.

        Returns:
            Optional[np.ndarray]: Recorte BGR, o None si el bbox es inválido,
            está fuera del frame o el recorte resultante es demasiado pequeño.
        """
        if frame is None or not isinstance(frame, np.ndarray):
            return None
        if frame.size == 0 or frame.ndim != 3 or frame.shape[2] < 3:
            return None
        if bbox is None:
            return None

        try:
            coords = list(bbox)
        except TypeError:
            return None
        if len(coords) < 4:
            return None

        try:
            raw = [float(c) for c in coords[:4]]
        except (TypeError, ValueError):
            return None
        if not all(np.isfinite(raw)):
            return None
        x1, y1, x2, y2 = (int(round(c)) for c in raw)

        height, width = frame.shape[:2]
        x1 = max(0, min(x1, width))
        x2 = max(0, min(x2, width))
        y1 = max(0, min(y1, height))
        y2 = max(0, min(y2, height))

        # Recortar solo la mitad superior (45%) para enfocarse en la camiseta y descartar césped
        y2 = y1 + int((y2 - y1) * 0.45)
        if x2 - x1 < _MIN_CROP_PIXELS or y2 - y1 < _MIN_CROP_PIXELS:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None
        return crop

    def _fallback_descriptor(self, crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Descriptor clásico OpenCV: histogramas HSV multi-región + textura.

        Se normaliza el recorte a un tamaño fijo, se divide en regiones
        (cabeza, torso central, torso completo, piernas) y de cada una se
        calculan histogramas de H, S y V. A eso se añade un histograma de
        magnitud de gradiente (Sobel) sobre el recorte completo, que aporta
        información de textura (rayas, números, patrones) independiente del
        tono. El vector final se normaliza en L2.

        Args:
            crop (np.ndarray): Recorte BGR del jugador.

        Returns:
            Optional[np.ndarray]: Vector descriptor float32, o None si falla.
        """
        try:
            resized = cv2.resize(crop, _FALLBACK_CROP_SIZE, interpolation=cv2.INTER_AREA)
            hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        except cv2.error as exc:
            logger.debug("No se pudo preparar el recorte para el descriptor: %s", exc)
            return None

        height, width = hsv.shape[:2]
        parts: List[np.ndarray] = []

        for y0, y1, x0, x1, weight in _FALLBACK_REGIONS:
            ry0, ry1 = int(y0 * height), max(int(y1 * height), int(y0 * height) + 1)
            rx0, rx1 = int(x0 * width), max(int(x1 * width), int(x0 * width) + 1)
            region = hsv[ry0:ry1, rx0:rx1]
            if region.size == 0:
                parts.append(np.zeros(_HIST_BINS_H + _HIST_BINS_S + _HIST_BINS_V, dtype=np.float32))
                continue
            for channel, bins, top in (
                (0, _HIST_BINS_H, 180.0),
                (1, _HIST_BINS_S, 256.0),
                (2, _HIST_BINS_V, 256.0),
            ):
                hist = cv2.calcHist([region], [channel], None, [bins], [0, top]).flatten()
                total = float(hist.sum())
                if total > 0.0:
                    hist = hist / total
                parts.append(hist.astype(np.float32) * float(weight))

        # Textura: histograma de magnitud de gradiente + dispersión global.
        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(grad_x, grad_y)
        magnitude = np.clip(magnitude, 0.0, 255.0)
        texture_hist, _ = np.histogram(magnitude, bins=_TEXTURE_BINS, range=(0.0, 255.0))
        texture_total = float(texture_hist.sum())
        if texture_total > 0.0:
            texture_hist = texture_hist / texture_total
        parts.append(texture_hist.astype(np.float32))
        parts.append(np.array([float(np.std(gray)) / 128.0], dtype=np.float32))

        descriptor = np.concatenate(parts).astype(np.float32)
        norm = float(np.linalg.norm(descriptor))
        if norm > 0.0:
            descriptor = descriptor / norm
        return descriptor

    # ------------------------------------------------------------------
    # Backend SigLIP
    # ------------------------------------------------------------------

    def _ensure_model(self) -> bool:
        """
        Carga perezosamente el modelo SigLIP la primera vez que se necesita.

        Returns:
            bool: True si el backend SigLIP quedó disponible, False si hay que
            usar el descriptor OpenCV de respaldo.
        """
        if self._model_load_attempted:
            return self.backend == BACKEND_SIGLIP

        self._model_load_attempted = True

        if not self.use_transformers:
            logger.debug("use_transformers=False: se usa el descriptor OpenCV.")
            return False
        if not (_HAS_TRANSFORMERS and _HAS_TORCH and _HAS_PIL):
            logger.info(
                "transformers/torch/Pillow no disponibles; se usa el descriptor "
                "OpenCV de respaldo para los embeddings de equipo."
            )
            return False

        try:
            import torch  # type: ignore
            from transformers import SiglipVisionModel  # type: ignore

            try:
                from transformers import AutoImageProcessor as _Processor  # type: ignore
            except ImportError:  # pragma: no cover - versiones antiguas
                from transformers import AutoProcessor as _Processor  # type: ignore

            device = self.device or "cpu"
            if str(device).startswith("cuda") and not torch.cuda.is_available():
                logger.warning("CUDA no disponible; el modelo de equipos usará CPU.")
                device = "cpu"

            model = SiglipVisionModel.from_pretrained(self.model_name)
            model = model.to(device)
            model.eval()
            processor = _Processor.from_pretrained(self.model_name)

            self._torch = torch
            self._model = model
            self._processor = processor
            self._model_device = device
            self.backend = BACKEND_SIGLIP
            logger.info("Backend SigLIP cargado (%s) en %s", self.model_name, device)
            return True
        except Exception as exc:  # noqa: BLE001 - degradación elegante deliberada
            logger.warning(
                "No se pudo cargar el modelo '%s' (%s: %s). Se usa el descriptor "
                "OpenCV de respaldo.",
                self.model_name,
                type(exc).__name__,
                exc,
            )
            self._model = None
            self._processor = None
            return False

    def _siglip_embeddings(self, crops: List[np.ndarray]) -> Optional[np.ndarray]:
        """
        Calcula embeddings SigLIP para una lista de recortes BGR.

        Args:
            crops (List[np.ndarray]): Recortes BGR.

        Returns:
            Optional[np.ndarray]: Matriz (n, d) de embeddings, o None si la
            inferencia falla (en cuyo caso el llamante usa el respaldo).
        """
        if self._model is None or self._processor is None:
            return None
        try:
            from PIL import Image  # type: ignore

            torch = self._torch
            outputs: List[np.ndarray] = []
            pil_crops = [
                Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)) for crop in crops
            ]
            with torch.no_grad():
                for batch in create_batches(pil_crops, self.batch_size):
                    inputs = self._processor(images=batch, return_tensors="pt")
                    inputs = {k: v.to(self._model_device) for k, v in inputs.items()}
                    result = self._model(**inputs)
                    embeddings = torch.mean(result.last_hidden_state, dim=1)
                    outputs.append(embeddings.cpu().numpy())
            if not outputs:
                return None
            return np.concatenate(outputs, axis=0).astype(np.float32)
        except Exception as exc:  # noqa: BLE001 - degradación elegante deliberada
            logger.warning(
                "Fallo en la inferencia SigLIP (%s: %s); se usa el descriptor OpenCV.",
                type(exc).__name__,
                exc,
            )
            return None

    # ------------------------------------------------------------------
    # Caché
    # ------------------------------------------------------------------

    def _cache_get(self, track_id: Any) -> Optional[np.ndarray]:
        """Devuelve el embedding cacheado de un track_id, si existe."""
        if not self.cache_enabled or track_id is None:
            return None
        cached = self._cache.get(track_id)
        if cached is None:
            return None
        self._cache.move_to_end(track_id)
        return cached

    def _cache_put(self, track_id: Any, embedding: np.ndarray) -> None:
        """Guarda un embedding en el caché aplicando desalojo LRU."""
        if not self.cache_enabled or track_id is None or self.max_cache_size <= 0:
            return
        self._cache[track_id] = embedding
        self._cache.move_to_end(track_id)
        while len(self._cache) > self.max_cache_size:
            self._cache.popitem(last=False)

    def clear_cache(self) -> None:
        """Vacía el caché de embeddings y sus contadores."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    # ------------------------------------------------------------------
    # Cálculo de embeddings
    # ------------------------------------------------------------------

    def _compute_embeddings(
        self,
        player_boxes: Sequence[Sequence[float]],
        frame: np.ndarray,
        track_ids: Optional[Sequence[Any]] = None,
    ) -> Tuple[np.ndarray, List[int], Dict[int, np.ndarray]]:
        """
        Calcula el embedding de cada bbox, usando caché por track_id si procede.

        Args:
            player_boxes (Sequence[Sequence[float]]): Cajas [x1, y1, x2, y2].
            frame (np.ndarray): Frame BGR.
            track_ids (Optional[Sequence[Any]]): Identificadores de track
                alineados con `player_boxes`. Si se aportan, los embeddings se
                cachean y reutilizan entre frames.

        Returns:
            Tuple con:
                - np.ndarray (n_valid, d): embeddings de las cajas válidas.
                - List[int]: índices originales de esas cajas válidas.
                - Dict[int, np.ndarray]: color BGR medio del torso por índice.
        """
        n_boxes = len(player_boxes)
        ids: List[Any] = [None] * n_boxes
        if track_ids is not None:
            for i in range(min(n_boxes, len(track_ids))):
                ids[i] = track_ids[i]

        embeddings: Dict[int, np.ndarray] = {}
        mean_colors: Dict[int, np.ndarray] = {}
        pending_indices: List[int] = []
        pending_crops: List[np.ndarray] = []

        for idx, bbox in enumerate(player_boxes):
            cached = self._cache_get(ids[idx])
            if cached is not None:
                self._cache_hits += 1
                embeddings[idx] = cached
                continue

            crop = self._extract_crop(frame, bbox)
            if crop is None:
                continue
            if ids[idx] is not None:
                self._cache_misses += 1

            mean_colors[idx] = self._torso_mean_bgr(crop)
            pending_indices.append(idx)
            pending_crops.append(crop)

        if pending_crops:
            computed: Optional[np.ndarray] = None
            if self._ensure_model():
                computed = self._siglip_embeddings(pending_crops)
                if computed is None:
                    self.backend = BACKEND_FALLBACK
            if computed is None:
                rows = []
                keep: List[int] = []
                for idx, crop in zip(pending_indices, pending_crops):
                    descriptor = self._fallback_descriptor(crop)
                    if descriptor is None:
                        continue
                    rows.append(descriptor)
                    keep.append(idx)
                pending_indices = keep
                computed = np.asarray(rows, dtype=np.float32) if rows else np.empty((0, 0))

            for row, idx in zip(computed, pending_indices):
                vector = np.asarray(row, dtype=np.float32)
                embeddings[idx] = vector
                self._cache_put(ids[idx], vector)

        valid_indices = sorted(embeddings.keys())
        if not valid_indices:
            return np.empty((0, 0), dtype=np.float32), [], mean_colors

        dims = {embeddings[i].shape[0] for i in valid_indices}
        if len(dims) > 1:
            # Puede pasar si el backend cambió a mitad de sesión (p.ej. el modelo
            # falló y se degradó al descriptor OpenCV): descartamos el caché
            # incoherente y nos quedamos con la dimensión mayoritaria.
            logger.warning("Dimensiones de embedding heterogéneas %s; se filtra.", dims)
            counts: Dict[int, int] = {}
            for i in valid_indices:
                counts[embeddings[i].shape[0]] = counts.get(embeddings[i].shape[0], 0) + 1
            target_dim = max(counts, key=lambda d: counts[d])
            valid_indices = [i for i in valid_indices if embeddings[i].shape[0] == target_dim]
            if not valid_indices:
                return np.empty((0, 0), dtype=np.float32), [], mean_colors

        matrix = np.vstack([embeddings[i] for i in valid_indices]).astype(np.float32)
        return matrix, valid_indices, mean_colors

    @staticmethod
    def _torso_mean_bgr(crop: np.ndarray) -> np.ndarray:
        """Color BGR medio de la franja del torso (para `get_team_colors`)."""
        height = crop.shape[0]
        y0 = int(height * 0.20)
        y1 = max(int(height * 0.55), y0 + 1)
        region = crop[y0:y1]
        if region.size == 0:
            region = crop
        return np.mean(region.reshape(-1, region.shape[-1])[:, :3], axis=0)

    # ------------------------------------------------------------------
    # Reducción de dimensionalidad
    # ------------------------------------------------------------------

    def _fit_reducer(self, matrix: np.ndarray) -> np.ndarray:
        """
        Ajusta la reducción de dimensionalidad y proyecta la matriz de entrada.

        Prioridad: UMAP (si está instalado y hay muestras suficientes) > PCA
        (scikit-learn o implementación numpy) > sin reducción.

        Args:
            matrix (np.ndarray): Embeddings crudos (n_samples, n_features).

        Returns:
            np.ndarray: Embeddings proyectados (n_samples, k).
        """
        self.reducer = None
        self.reduction_method = "none"

        n_samples, n_features = matrix.shape
        if not self.use_reduction or n_samples <= self.n_clusters or n_features <= 1:
            return matrix

        target = max(1, min(self.n_components, n_features, n_samples - 1))

        if _HAS_UMAP and n_samples >= self.umap_min_samples:
            try:
                import umap  # type: ignore

                reducer = umap.UMAP(
                    n_components=target,
                    n_neighbors=int(max(2, min(15, n_samples - 1))),
                    random_state=self.random_state,
                )
                projected = np.asarray(reducer.fit_transform(matrix), dtype=np.float64)
                if np.all(np.isfinite(projected)):
                    self.reducer = reducer
                    self.reduction_method = "umap"
                    return projected
                logger.warning("UMAP produjo valores no finitos; se pasa a PCA.")
            except Exception as exc:  # noqa: BLE001 - degradación elegante
                logger.warning(
                    "UMAP falló (%s: %s); se usa PCA.", type(exc).__name__, exc
                )

        if n_features <= target:
            return matrix

        try:
            if _HAS_SKLEARN:
                from sklearn.decomposition import PCA  # type: ignore

                reducer = PCA(n_components=target, random_state=self.random_state)
            else:
                reducer = _NumpyPCA(n_components=target)
            projected = np.asarray(reducer.fit_transform(matrix), dtype=np.float64)
            self.reducer = reducer
            self.reduction_method = "pca"
            return projected
        except Exception as exc:  # noqa: BLE001 - degradación elegante
            logger.warning(
                "PCA falló (%s: %s); se usan los embeddings crudos.",
                type(exc).__name__,
                exc,
            )
            self.reducer = None
            self.reduction_method = "none"
            return matrix

    def _apply_reducer(self, matrix: np.ndarray) -> Optional[np.ndarray]:
        """
        Proyecta embeddings nuevos al espacio aprendido en el entrenamiento.

        Args:
            matrix (np.ndarray): Embeddings crudos (n, d).

        Returns:
            Optional[np.ndarray]: Proyección, o None si la transformación falla.
        """
        if self.reducer is None:
            return matrix
        if self.embedding_dim is not None and matrix.shape[1] != self.embedding_dim:
            logger.warning(
                "Dimensión de embedding %s incompatible con el entrenamiento (%s).",
                matrix.shape[1],
                self.embedding_dim,
            )
            return None
        try:
            projected = np.asarray(self.reducer.transform(matrix), dtype=np.float64)
            if not np.all(np.isfinite(projected)):
                logger.warning("La proyección produjo valores no finitos.")
                return None
            return projected
        except Exception as exc:  # noqa: BLE001 - degradación elegante
            logger.warning(
                "La reducción de dimensionalidad falló al transformar (%s: %s).",
                type(exc).__name__,
                exc,
            )
            return None

    def _make_kmeans(self) -> Any:
        """Instancia KMeans de scikit-learn si está disponible, si no el propio."""
        if _HAS_SKLEARN:
            try:
                from sklearn.cluster import KMeans  # type: ignore

                return KMeans(
                    n_clusters=self.n_clusters,
                    n_init=10,
                    max_iter=300,
                    random_state=self.random_state,
                )
            except Exception as exc:  # noqa: BLE001 - degradación elegante
                logger.warning(
                    "No se pudo crear KMeans de scikit-learn (%s: %s); se usa la "
                    "implementación numpy.",
                    type(exc).__name__,
                    exc,
                )
        return _NumpyKMeans(
            n_clusters=self.n_clusters,
            n_init=10,
            max_iter=300,
            random_state=self.random_state,
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def train(
        self,
        player_boxes: List[List[float]],
        frame: np.ndarray,
        track_ids: Optional[List[Any]] = None,
    ) -> bool:
        """
        Entrena el clasificador con los jugadores presentes en un frame.

        Args:
            player_boxes (List[List[float]]): Cajas [x1, y1, x2, y2] en píxeles.
            frame (np.ndarray): Frame de video BGR.
            track_ids (Optional[List[Any]]): IDs de track alineados con las
                cajas; si se aportan, los embeddings quedan cacheados.

        Returns:
            bool: True si el entrenamiento fue exitoso, False si no hubo
            recortes válidos suficientes o el clustering falló.

        Raises:
            ValueError: Si se aportan menos cajas que clusters (mismo contrato
                que `core.team_classifier.TeamClassifier.train`).
        """
        if player_boxes is None:
            raise ValueError("player_boxes no puede ser None")
        if len(player_boxes) < self.n_clusters:
            raise ValueError(
                f"Se necesitan al menos {self.n_clusters} jugadores para entrenar. "
                f"Se encontraron {len(player_boxes)}"
            )

        matrix, valid_indices, mean_colors = self._compute_embeddings(
            player_boxes, frame, track_ids
        )
        if matrix.shape[0] < self.n_clusters:
            logger.warning(
                "Recortes válidos insuficientes para entrenar: %s < %s",
                matrix.shape[0],
                self.n_clusters,
            )
            return False

        self.embedding_dim = int(matrix.shape[1])
        projected = self._fit_reducer(matrix)

        kmeans = self._make_kmeans()
        try:
            kmeans.fit(projected)
        except Exception as exc:  # noqa: BLE001 - degradación elegante
            logger.error(
                "El clustering KMeans falló (%s: %s).", type(exc).__name__, exc
            )
            return False

        labels = np.asarray(getattr(kmeans, "labels_", None))
        if labels is None or labels.size != projected.shape[0]:
            try:
                labels = np.asarray(kmeans.predict(projected))
            except Exception as exc:  # noqa: BLE001
                logger.error("KMeans no devolvió etiquetas utilizables: %s", exc)
                return False

        self.kmeans_model = kmeans
        self.n_samples = int(matrix.shape[0])
        self.trained = True
        self._build_team_profiles(labels, valid_indices, mean_colors)
        logger.info(
            "EmbeddingTeamClassifier entrenado: %s muestras, backend=%s, "
            "reduccion=%s, dim=%s",
            self.n_samples,
            self.backend,
            self.reduction_method,
            self.embedding_dim,
        )
        return True

    def _build_team_profiles(
        self,
        labels: np.ndarray,
        valid_indices: List[int],
        mean_colors: Dict[int, np.ndarray],
    ) -> None:
        """Construye el perfil visual agregado de cada cluster tras entrenar."""
        self.team_profiles = {}
        centers = getattr(self.kmeans_model, "cluster_centers_", None)
        total = max(1, len(labels))

        for team_id in range(self.n_clusters):
            member_positions = [i for i, lab in enumerate(labels) if int(lab) == team_id]
            colors = [
                mean_colors[valid_indices[pos]]
                for pos in member_positions
                if valid_indices[pos] in mean_colors
            ]
            if colors:
                mean_bgr_arr = np.mean(np.vstack(colors), axis=0)
            else:
                mean_bgr_arr = np.zeros(3, dtype=np.float64)
            bgr_tuple = tuple(int(round(float(c))) for c in mean_bgr_arr[:3])
            hsv_pixel = cv2.cvtColor(
                np.uint8([[list(bgr_tuple)]]), cv2.COLOR_BGR2HSV
            )[0][0]
            self.team_profiles[team_id] = EmbeddingTeamProfile(
                team_id=team_id,
                name=f"Team_{team_id}",
                n_samples=len(member_positions),
                share=float(len(member_positions)) / float(total),
                mean_bgr=bgr_tuple,  # type: ignore[arg-type]
                mean_hsv=tuple(int(v) for v in hsv_pixel),  # type: ignore[arg-type]
                centroid=(
                    np.asarray(centers[team_id], dtype=np.float64)
                    if centers is not None and team_id < len(centers)
                    else None
                ),
            )

    def classify(
        self,
        player_boxes: List[List[float]],
        frame: np.ndarray,
        track_ids: Optional[List[Any]] = None,
    ) -> Dict:
        """
        Asigna cada jugador a un equipo a partir de su embedding visual.

        Args:
            player_boxes (List[List[float]]): Cajas [x1, y1, x2, y2] en píxeles.
            frame (np.ndarray): Frame de video BGR.
            track_ids (Optional[List[Any]]): IDs de track alineados con las
                cajas, para reutilizar embeddings ya calculados.

        Returns:
            dict: {
                'team_assignments': [team_id|None, ...],
                'confidence_scores': [float, ...],
                'valid_classifications': [bool, ...]
            }
            Mismo formato que `core.team_classifier.TeamClassifier.classify`.

        Raises:
            RuntimeError: Si el clasificador no ha sido entrenado.
        """
        if not self.trained or self.kmeans_model is None:
            raise RuntimeError("El clasificador debe entrenarse primero")

        boxes = list(player_boxes) if player_boxes is not None else []
        n_boxes = len(boxes)
        team_assignments: List[Optional[int]] = [None] * n_boxes
        confidence_scores: List[float] = [0.0] * n_boxes
        valid_classifications: List[bool] = [False] * n_boxes

        if n_boxes == 0:
            self.cluster_assignments = {
                "assignments": [],
                "confidence": [],
                "valid": [],
            }
            return {
                "team_assignments": [],
                "confidence_scores": [],
                "valid_classifications": [],
            }

        matrix, valid_indices, _ = self._compute_embeddings(boxes, frame, track_ids)
        if matrix.shape[0] > 0:
            projected = self._apply_reducer(matrix)
            if projected is not None:
                centers = np.asarray(
                    getattr(self.kmeans_model, "cluster_centers_"), dtype=np.float64
                )
                for row, idx in zip(np.asarray(projected, dtype=np.float64), valid_indices):
                    distances = np.linalg.norm(centers - row, axis=1)
                    team_id = int(np.argmin(distances))
                    if self.n_clusters == 1:
                        confidence = 1.0
                    else:
                        ordered = np.sort(distances)
                        confidence = 1.0 - (ordered[0] / (ordered[1] + 1e-6))
                        confidence = float(max(0.0, min(1.0, confidence)))
                    team_assignments[idx] = team_id
                    confidence_scores[idx] = float(confidence)
                    valid_classifications[idx] = bool(confidence > self.min_confidence)

        self._n_classified += n_boxes
        self._n_valid_classified += int(sum(valid_classifications))
        self.cluster_assignments = {
            "assignments": team_assignments,
            "confidence": confidence_scores,
            "valid": valid_classifications,
        }

        return {
            "team_assignments": team_assignments,
            "confidence_scores": confidence_scores,
            "valid_classifications": valid_classifications,
        }

    def get_team_colors(self) -> Dict[int, Dict]:
        """
        Color medio observado por equipo (para dibujar/overlays).

        A diferencia de `TeamClassifier`, aquí el color NO es lo que decide el
        equipo: se calcula a posteriori, promediando el torso de los jugadores
        que el clustering de embeddings asignó a cada cluster.

        Returns:
            dict: {team_id: {'name', 'bgr', 'hsv_range', 'confidence',
                             'player_count'}}
        """
        result: Dict[int, Dict] = {}
        if not self.trained:
            return result

        for team_id, profile in self.team_profiles.items():
            player_count = profile.n_samples
            if self.cluster_assignments:
                player_count = sum(
                    1 for a in self.cluster_assignments.get("assignments", []) if a == team_id
                )
            h, s, v = profile.mean_hsv
            result[team_id] = {
                "name": profile.name,
                "bgr": profile.mean_bgr,
                "hsv_range": (
                    (max(0, int(h) - 10), max(0, int(s) - 30), max(0, int(v) - 40)),
                    (min(180, int(h) + 10), min(255, int(s) + 30), min(255, int(v) + 40)),
                ),
                "confidence": profile.share,
                "player_count": player_count,
            }
        return result

    def get_statistics(self) -> Dict:
        """
        Estadísticas de entrenamiento, backend y caché.

        Returns:
            dict: Estado del modelo. Incluye las claves de
            `TeamClassifier.get_statistics` más información específica de este
            clasificador (backend efectivo, método de reducción, caché).
        """
        return {
            "trained": self.trained,
            "n_samples": self.n_samples,
            "n_clusters": self.n_clusters,
            "team_colors_count": len(self.team_profiles),
            "cluster_assignments_count": len(self.cluster_assignments),
            "backend": self.backend,
            "model_name": self.model_name,
            "device": self.device,
            "reduction_method": self.reduction_method,
            "embedding_dim": self.embedding_dim,
            "n_classified": self._n_classified,
            "n_valid_classified": self._n_valid_classified,
            "cache": {
                "enabled": self.cache_enabled,
                "size": len(self._cache),
                "max_size": self.max_cache_size,
                "hits": self._cache_hits,
                "misses": self._cache_misses,
            },
            "models_available": {
                "kmeans": self.kmeans_model is not None,
                "reducer": self.reducer is not None,
                "transformers": _HAS_TRANSFORMERS,
                "torch": _HAS_TORCH,
                "pillow": _HAS_PIL,
                "umap": _HAS_UMAP,
                "sklearn": _HAS_SKLEARN,
            },
        }

    def reset(self) -> None:
        """
        Reinicia el clasificador a su estado inicial.

        Limpia entrenamiento, perfiles, asignaciones y caché. El modelo de
        visión ya cargado se conserva en memoria para no pagar de nuevo su
        coste de carga.
        """
        self.trained = False
        self.n_samples = 0
        self.kmeans_model = None
        self.reducer = None
        self.reduction_method = "none"
        self.embedding_dim = None
        self.team_profiles = {}
        self.cluster_assignments = {}
        self._n_classified = 0
        self._n_valid_classified = 0
        self.clear_cache()

    def __repr__(self) -> str:  # pragma: no cover - utilidad de depuración
        return (
            f"EmbeddingTeamClassifier(n_clusters={self.n_clusters}, "
            f"backend={self.backend!r}, trained={self.trained}, "
            f"reduction={self.reduction_method!r})"
        )

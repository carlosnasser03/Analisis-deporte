"""
test_team_classifier_embeddings.py - Tests de EmbeddingTeamClassifier

Todos los tests trabajan con frames sintéticos generados proceduralmente con
numpy/OpenCV: un campo verde y "jugadores" rectangulares con camiseta de dos
colores distintos. No se necesita ningún video real ni ningún peso descargado.

Los tests que dependen de dependencias opcionales (`transformers`, `umap-learn`,
`scikit-learn`) usan `pytest.mark.skipif`.
"""

import time
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pytest

from core.team_classifier_embeddings import (
    BACKEND_FALLBACK,
    BACKEND_SIGLIP,
    EmbeddingTeamClassifier,
    _HAS_SKLEARN,
    _HAS_PIL,
    _HAS_TORCH,
    _HAS_TRANSFORMERS,
    _HAS_UMAP,
    _NumpyKMeans,
    _NumpyPCA,
    create_batches,
)

# Colores BGR de los dos "equipos" sintéticos
TEAM_A_BGR = (40, 40, 210)    # rojo
TEAM_B_BGR = (210, 60, 40)    # azul
FIELD_BGR = (45, 120, 45)     # césped
SHORTS_BGR = (235, 235, 235)  # pantalón blanco (igual en ambos equipos)


# ---------------------------------------------------------------------------
# Generadores de datos sintéticos
# ---------------------------------------------------------------------------


def make_field(width: int = 640, height: int = 480, seed: int = 0) -> np.ndarray:
    """Crea un frame BGR de césped con ruido suave."""
    rng = np.random.default_rng(seed)
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = FIELD_BGR
    noise = rng.integers(-12, 13, size=(height, width, 3))
    return np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def draw_player(
    frame: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    jersey_bgr: Tuple[int, int, int],
    rng: np.random.Generator,
    shade: float = 1.0,
) -> List[float]:
    """
    Dibuja un jugador rectangular y devuelve su bbox [x1, y1, x2, y2].

    `shade` simula sombras/iluminación multiplicando la intensidad.
    """
    head_h = int(h * 0.18)
    torso_h = int(h * 0.42)

    head = np.full((head_h, w, 3), (70, 110, 160), dtype=np.int16)
    torso = np.full((torso_h, w, 3), jersey_bgr, dtype=np.int16)
    legs_h = h - head_h - torso_h
    legs = np.full((legs_h, w, 3), SHORTS_BGR, dtype=np.int16)

    body = np.vstack([head, torso, legs]).astype(np.float32) * float(shade)
    body += rng.integers(-10, 11, size=body.shape)
    body = np.clip(body, 0, 255).astype(np.uint8)

    frame[y:y + h, x:x + w] = body
    return [float(x), float(y), float(x + w), float(y + h)]


def synthetic_match(
    n_per_team: int = 5,
    seed: int = 7,
    width: int = 640,
    height: int = 480,
    shadows: bool = False,
) -> Tuple[np.ndarray, List[List[float]], List[int]]:
    """
    Genera un frame con dos equipos.

    Returns:
        (frame, bboxes, etiquetas_verdaderas) donde la etiqueta es 0 o 1.
    """
    rng = np.random.default_rng(seed)
    frame = make_field(width, height, seed=seed)
    boxes: List[List[float]] = []
    truth: List[int] = []

    total = n_per_team * 2
    for i in range(total):
        team = 0 if i < n_per_team else 1
        jersey = TEAM_A_BGR if team == 0 else TEAM_B_BGR
        col = i % 6
        row = i // 6
        w = int(rng.integers(26, 34))
        h = int(rng.integers(70, 90))
        x = 20 + col * 100
        y = 30 + row * 170
        x = min(x, width - w - 1)
        y = min(y, height - h - 1)
        shade = float(rng.uniform(0.55, 1.0)) if shadows else 1.0
        boxes.append(draw_player(frame, x, y, w, h, jersey, rng, shade=shade))
        truth.append(team)

    return frame, boxes, truth


def make_classifier(**kwargs) -> EmbeddingTeamClassifier:
    """Clasificador con el backend OpenCV forzado (rápido y determinista)."""
    params = dict(n_clusters=2, use_transformers=False, umap_min_samples=10_000)
    params.update(kwargs)
    return EmbeddingTeamClassifier(**params)


def teams_separated(assignments: Sequence[Optional[int]], truth: Sequence[int]) -> bool:
    """True si cada equipo real cayó entero en un cluster distinto."""
    if any(a is None for a in assignments):
        return False
    groups = {}
    for assigned, real in zip(assignments, truth):
        groups.setdefault(real, set()).add(assigned)
    if any(len(v) != 1 for v in groups.values()):
        return False
    single = [next(iter(v)) for v in groups.values()]
    return len(set(single)) == len(groups)


# ---------------------------------------------------------------------------
# 1. Construcción e importación
# ---------------------------------------------------------------------------


def test_modulo_importa_sin_dependencias_opcionales():
    """El módulo se importa y expone flags booleanos de disponibilidad."""
    for flag in (_HAS_TRANSFORMERS, _HAS_TORCH, _HAS_PIL, _HAS_UMAP, _HAS_SKLEARN):
        assert isinstance(flag, bool)
    assert BACKEND_FALLBACK != BACKEND_SIGLIP


def test_constructor_valores_por_defecto():
    """El constructor deja el clasificador en estado limpio y sin entrenar."""
    clf = EmbeddingTeamClassifier()
    assert clf.n_clusters == 2
    assert clf.device == "cpu"
    assert clf.model_name == "google/siglip-base-patch16-224"
    assert clf.trained is False
    assert clf.n_samples == 0
    assert clf.kmeans_model is None
    assert clf.reduction_method == "none"


def test_constructor_n_clusters_invalido():
    """n_clusters < 1 es un error de configuración explícito."""
    with pytest.raises(ValueError):
        EmbeddingTeamClassifier(n_clusters=0)


def test_backend_fallback_sin_transformers():
    """Con use_transformers=False nunca se intenta cargar el modelo pesado."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=3)
    assert clf.train(boxes, frame) is True
    assert clf.backend == BACKEND_FALLBACK
    assert clf._model is None


# ---------------------------------------------------------------------------
# 2. Entrenamiento
# ---------------------------------------------------------------------------


def test_train_exitoso():
    """Entrenamiento normal con dos equipos bien diferenciados."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=5)
    assert clf.train(boxes, frame) is True
    assert clf.trained is True
    assert clf.n_samples == len(boxes)
    assert clf.kmeans_model is not None
    assert clf.embedding_dim is not None and clf.embedding_dim > 0


def test_train_menos_jugadores_que_clusters():
    """Menos cajas que clusters lanza ValueError (igual que TeamClassifier)."""
    clf = make_classifier(n_clusters=2)
    frame, boxes, _ = synthetic_match(n_per_team=3)
    with pytest.raises(ValueError):
        clf.train(boxes[:1], frame)


def test_train_lista_de_cajas_vacia():
    """Una lista vacía también incumple el mínimo de muestras."""
    clf = make_classifier()
    frame = make_field()
    with pytest.raises(ValueError):
        clf.train([], frame)


def test_train_frame_vacio_devuelve_false():
    """Un frame sin píxeles no permite entrenar, pero no revienta."""
    clf = make_classifier()
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    boxes = [[0, 0, 30, 80], [40, 0, 70, 80], [80, 0, 110, 80]]
    assert clf.train(boxes, empty) is False
    assert clf.trained is False


def test_train_frame_none_devuelve_false():
    """frame=None se trata como frame inválido, no como excepción."""
    clf = make_classifier()
    boxes = [[0, 0, 30, 80], [40, 0, 70, 80]]
    assert clf.train(boxes, None) is False
    assert clf.trained is False


def test_train_frame_2d_devuelve_false():
    """Un frame en escala de grises (2D) se rechaza limpiamente."""
    clf = make_classifier()
    gray = np.zeros((480, 640), dtype=np.uint8)
    boxes = [[10, 10, 40, 90], [60, 10, 90, 90]]
    assert clf.train(boxes, gray) is False


def test_train_todas_las_cajas_fuera_de_rango():
    """Si ninguna caja cae dentro del frame no hay muestras válidas."""
    clf = make_classifier()
    frame = make_field(320, 240)
    boxes = [[900, 900, 1000, 1100], [-400, -400, -300, -200], [5000, 5000, 5100, 5200]]
    assert clf.train(boxes, frame) is False
    assert clf.trained is False


def test_train_con_tres_clusters():
    """El clasificador no está limitado a 2 equipos."""
    clf = make_classifier(n_clusters=3)
    frame, boxes, _ = synthetic_match(n_per_team=5)
    assert clf.train(boxes, frame) is True
    assert len(clf.team_profiles) == 3


def test_train_frame_uniforme_no_revienta():
    """Frame totalmente negro: entrena o devuelve False, pero nunca lanza."""
    clf = make_classifier()
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    boxes = [[10, 10, 50, 110], [60, 10, 100, 110], [110, 10, 150, 110]]
    result = clf.train(boxes, frame)
    assert result in (True, False)


# ---------------------------------------------------------------------------
# 3. Clasificación
# ---------------------------------------------------------------------------


def test_classify_sin_entrenar_lanza_runtime_error():
    """Contrato idéntico al de TeamClassifier: hay que entrenar primero."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=3)
    with pytest.raises(RuntimeError):
        clf.classify(boxes, frame)


def test_classify_formato_de_salida():
    """Devuelve exactamente las tres claves del contrato, con igual longitud."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)
    result = clf.classify(boxes, frame)

    assert set(result.keys()) == {
        "team_assignments",
        "confidence_scores",
        "valid_classifications",
    }
    assert len(result["team_assignments"]) == len(boxes)
    assert len(result["confidence_scores"]) == len(boxes)
    assert len(result["valid_classifications"]) == len(boxes)
    assert all(isinstance(v, bool) for v in result["valid_classifications"])
    assert all(isinstance(c, float) for c in result["confidence_scores"])


def test_classify_separa_los_dos_equipos():
    """Cada equipo sintético debe caer entero en un cluster distinto."""
    clf = make_classifier()
    frame, boxes, truth = synthetic_match(n_per_team=5, seed=11)
    assert clf.train(boxes, frame) is True
    result = clf.classify(boxes, frame)
    assert teams_separated(result["team_assignments"], truth)


def test_classify_separa_equipos_con_sombras():
    """Con sombras fuertes por jugador la separación debe mantenerse."""
    clf = make_classifier()
    frame, boxes, truth = synthetic_match(n_per_team=5, seed=23, shadows=True)
    assert clf.train(boxes, frame) is True
    result = clf.classify(boxes, frame)
    assert teams_separated(result["team_assignments"], truth)


def test_classify_confianzas_en_rango():
    """Todas las confianzas están acotadas en [0, 1]."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)
    result = clf.classify(boxes, frame)
    assert all(0.0 <= c <= 1.0 for c in result["confidence_scores"])


def test_classify_bbox_fuera_de_rango_marca_invalido():
    """Una caja fuera del frame produce (None, 0.0, False) en su posición."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)

    mixed = list(boxes) + [[5000.0, 5000.0, 5100.0, 5200.0]]
    result = clf.classify(mixed, frame)

    assert result["team_assignments"][-1] is None
    assert result["confidence_scores"][-1] == 0.0
    assert result["valid_classifications"][-1] is False
    assert result["team_assignments"][0] is not None


def test_classify_bbox_degenerado_y_malformado():
    """Cajas degeneradas, cortas, None o con NaN se marcan como inválidas."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)

    malformed = [
        [10.0, 10.0, 10.0, 10.0],        # área cero
        [10.0, 10.0],                    # menos de 4 coordenadas
        None,                            # nada
        [float("nan"), 1.0, 20.0, 40.0],  # NaN
        [50.0, 50.0, 20.0, 20.0],        # invertida (x2 < x1)
    ]
    result = clf.classify(malformed, frame)
    assert result["team_assignments"] == [None] * len(malformed)
    assert all(c == 0.0 for c in result["confidence_scores"])
    assert not any(result["valid_classifications"])


def test_classify_bbox_parcialmente_fuera_se_recorta():
    """Una caja que sale del frame se recorta y sigue siendo clasificable."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)

    height, width = frame.shape[:2]
    partial = [[width - 20.0, height - 40.0, width + 200.0, height + 300.0]]
    result = clf.classify(partial, frame)
    assert result["team_assignments"][0] is not None


def test_classify_lista_vacia():
    """Sin jugadores el resultado son tres listas vacías, no un error."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)
    result = clf.classify([], frame)
    assert result == {
        "team_assignments": [],
        "confidence_scores": [],
        "valid_classifications": [],
    }


def test_classify_frame_vacio_todo_invalido():
    """Clasificar contra un frame vacío no lanza: marca todo como inválido."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)
    result = clf.classify(boxes, np.zeros((0, 0, 3), dtype=np.uint8))
    assert all(a is None for a in result["team_assignments"])
    assert not any(result["valid_classifications"])


def test_classify_es_determinista():
    """Dos llamadas idénticas devuelven exactamente lo mismo."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=5)
    clf.train(boxes, frame)
    first = clf.classify(boxes, frame)
    second = clf.classify(boxes, frame)
    assert first["team_assignments"] == second["team_assignments"]
    assert first["confidence_scores"] == pytest.approx(second["confidence_scores"])


def test_compatibilidad_api_con_team_classifier():
    """Las claves de salida coinciden con las de core.team_classifier."""
    from core.team_classifier import TeamClassifier

    frame, boxes, _ = synthetic_match(n_per_team=5)

    baseline = TeamClassifier(n_clusters=2)
    baseline.train(boxes, frame)
    baseline_result = baseline.classify(boxes, frame)

    clf = make_classifier()
    clf.train(boxes, frame)
    embedding_result = clf.classify(boxes, frame)

    assert set(baseline_result.keys()) == set(embedding_result.keys())
    for key in baseline_result:
        assert len(baseline_result[key]) == len(embedding_result[key])


# ---------------------------------------------------------------------------
# 4. Caché por track_id
# ---------------------------------------------------------------------------


def test_cache_reutiliza_embeddings_entre_frames():
    """Con los mismos track_ids el segundo frame se resuelve desde el caché."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    track_ids = list(range(len(boxes)))

    clf.train(boxes, frame, track_ids=track_ids)
    stats_after_train = clf.get_statistics()["cache"]
    assert stats_after_train["size"] == len(boxes)
    assert stats_after_train["hits"] == 0

    clf.classify(boxes, frame, track_ids=track_ids)
    stats_after_classify = clf.get_statistics()["cache"]
    assert stats_after_classify["hits"] == len(boxes)


def test_cache_ignora_frames_nuevos_para_ids_conocidos():
    """El embedding cacheado se usa aunque el frame cambie por completo."""
    clf = make_classifier()
    frame, boxes, truth = synthetic_match(n_per_team=4, seed=3)
    track_ids = list(range(len(boxes)))
    clf.train(boxes, frame, track_ids=track_ids)
    first = clf.classify(boxes, frame, track_ids=track_ids)

    black = np.zeros_like(frame)
    second = clf.classify(boxes, black, track_ids=track_ids)
    assert first["team_assignments"] == second["team_assignments"]


def test_cache_desactivado_no_acumula():
    """Con cache_enabled=False no se guarda nada ni hay aciertos."""
    clf = make_classifier(cache_enabled=False)
    frame, boxes, _ = synthetic_match(n_per_team=4)
    track_ids = list(range(len(boxes)))
    clf.train(boxes, frame, track_ids=track_ids)
    clf.classify(boxes, frame, track_ids=track_ids)
    cache_stats = clf.get_statistics()["cache"]
    assert cache_stats["size"] == 0
    assert cache_stats["hits"] == 0


def test_cache_respeta_el_limite_lru():
    """El caché nunca crece por encima de max_cache_size."""
    clf = make_classifier(max_cache_size=3)
    frame, boxes, _ = synthetic_match(n_per_team=5)
    track_ids = list(range(len(boxes)))
    clf.train(boxes, frame, track_ids=track_ids)
    assert clf.get_statistics()["cache"]["size"] == 3


def test_clear_cache():
    """clear_cache vacía entradas y contadores sin tocar el entrenamiento."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    track_ids = list(range(len(boxes)))
    clf.train(boxes, frame, track_ids=track_ids)
    clf.clear_cache()
    cache_stats = clf.get_statistics()["cache"]
    assert cache_stats["size"] == 0
    assert cache_stats["hits"] == 0
    assert cache_stats["misses"] == 0
    assert clf.trained is True


def test_sin_track_ids_no_usa_cache():
    """Sin track_ids no hay nada que cachear."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)
    clf.classify(boxes, frame)
    assert clf.get_statistics()["cache"]["size"] == 0


# ---------------------------------------------------------------------------
# 5. Estado, estadísticas y reset
# ---------------------------------------------------------------------------


def test_get_statistics_claves_minimas():
    """get_statistics expone las claves del contrato más las propias."""
    clf = make_classifier()
    stats = clf.get_statistics()
    for key in (
        "trained",
        "n_samples",
        "n_clusters",
        "team_colors_count",
        "cluster_assignments_count",
        "backend",
        "reduction_method",
        "cache",
        "models_available",
    ):
        assert key in stats
    assert stats["trained"] is False


def test_get_statistics_tras_entrenar_y_clasificar():
    """Los contadores reflejan el trabajo realizado."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame)
    clf.classify(boxes, frame)
    stats = clf.get_statistics()
    assert stats["trained"] is True
    assert stats["n_samples"] == len(boxes)
    assert stats["n_classified"] == len(boxes)
    assert stats["backend"] == BACKEND_FALLBACK


def test_get_team_colors_sin_entrenar_esta_vacio():
    """Sin entrenamiento no hay colores que reportar."""
    assert make_classifier().get_team_colors() == {}


def test_get_team_colors_tras_entrenar():
    """Cada equipo reporta color medio, rango HSV y recuento."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=5)
    clf.train(boxes, frame)
    clf.classify(boxes, frame)
    colors = clf.get_team_colors()
    assert len(colors) == 2
    for team_id, info in colors.items():
        assert set(info.keys()) == {
            "name",
            "bgr",
            "hsv_range",
            "confidence",
            "player_count",
        }
        assert len(info["bgr"]) == 3
        assert 0.0 <= info["confidence"] <= 1.0


def test_reset_deja_el_clasificador_como_nuevo():
    """reset limpia entrenamiento, perfiles, asignaciones y caché."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=4)
    clf.train(boxes, frame, track_ids=list(range(len(boxes))))
    clf.classify(boxes, frame)

    clf.reset()

    assert clf.trained is False
    assert clf.n_samples == 0
    assert clf.kmeans_model is None
    assert clf.team_profiles == {}
    assert clf.cluster_assignments == {}
    assert clf.get_statistics()["cache"]["size"] == 0
    with pytest.raises(RuntimeError):
        clf.classify(boxes, frame)


def test_reentrenar_despues_de_reset():
    """Tras reset se puede volver a entrenar sin residuos del estado previo."""
    clf = make_classifier()
    frame, boxes, truth = synthetic_match(n_per_team=5)
    clf.train(boxes, frame)
    clf.reset()
    assert clf.train(boxes, frame) is True
    result = clf.classify(boxes, frame)
    assert teams_separated(result["team_assignments"], truth)


# ---------------------------------------------------------------------------
# 6. Descriptor de respaldo y utilidades internas
# ---------------------------------------------------------------------------


def test_descriptor_fallback_normalizado_y_determinista():
    """El descriptor OpenCV es unitario en L2 y reproducible."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=2)
    crop = clf._extract_crop(frame, boxes[0])
    assert crop is not None
    first = clf._fallback_descriptor(crop)
    second = clf._fallback_descriptor(crop)
    assert first is not None
    assert np.linalg.norm(first) == pytest.approx(1.0, abs=1e-5)
    assert np.allclose(first, second)


def test_descriptor_fallback_distingue_colores_de_camiseta():
    """Dos camisetas distintas están más lejos entre sí que dos iguales."""
    clf = make_classifier()
    frame, boxes, truth = synthetic_match(n_per_team=3)
    crops = [clf._extract_crop(frame, b) for b in boxes]
    descriptors = [clf._fallback_descriptor(c) for c in crops]

    same_team = np.linalg.norm(descriptors[0] - descriptors[1])
    cross_team = np.linalg.norm(descriptors[0] - descriptors[-1])
    assert truth[0] != truth[-1]
    assert cross_team > same_team


def test_extract_crop_recorta_a_los_limites():
    """El recorte se limita al frame aunque la caja lo desborde."""
    clf = make_classifier()
    frame = make_field(100, 80)
    crop = clf._extract_crop(frame, [-50, -50, 60, 60])
    assert crop is not None
    assert crop.shape[0] <= 80 and crop.shape[1] <= 100


def test_create_batches():
    """El generador de lotes respeta el tamaño y no pierde elementos."""
    batches = list(create_batches(list(range(7)), 3))
    assert [len(b) for b in batches] == [3, 3, 1]
    assert [x for b in batches for x in b] == list(range(7))
    assert list(create_batches([], 4)) == []


def test_numpy_kmeans_separa_dos_nubes():
    """El KMeans numpy de respaldo separa dos nubes bien alejadas."""
    rng = np.random.default_rng(0)
    cloud_a = rng.normal(loc=0.0, scale=0.1, size=(20, 4))
    cloud_b = rng.normal(loc=8.0, scale=0.1, size=(20, 4))
    data = np.vstack([cloud_a, cloud_b])

    model = _NumpyKMeans(n_clusters=2, random_state=1).fit(data)
    labels = model.labels_
    assert len(set(labels[:20])) == 1
    assert len(set(labels[20:])) == 1
    assert labels[0] != labels[-1]
    assert model.predict(cloud_a[:3]).tolist() == [labels[0]] * 3


def test_numpy_kmeans_rechaza_menos_muestras_que_clusters():
    """Menos puntos que clusters es un error explícito."""
    with pytest.raises(ValueError):
        _NumpyKMeans(n_clusters=3).fit(np.zeros((2, 3)))


def test_numpy_pca_reduce_dimensionalidad():
    """El PCA numpy de respaldo proyecta al número de componentes pedido."""
    rng = np.random.default_rng(5)
    data = rng.normal(size=(30, 12))
    pca = _NumpyPCA(n_components=3)
    projected = pca.fit_transform(data)
    assert projected.shape == (30, 3)
    assert pca.transform(data[:4]).shape == (4, 3)


def test_reduccion_reporta_metodo_valido():
    """El método de reducción efectivo es uno de los tres contemplados."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=5)
    clf.train(boxes, frame)
    assert clf.reduction_method in ("umap", "pca", "none")


def test_sin_reduccion_usa_embeddings_crudos():
    """Con use_reduction=False el clustering trabaja sobre el vector completo."""
    clf = make_classifier(use_reduction=False)
    frame, boxes, truth = synthetic_match(n_per_team=5)
    assert clf.train(boxes, frame) is True
    assert clf.reduction_method == "none"
    assert clf.reducer is None
    result = clf.classify(boxes, frame)
    assert teams_separated(result["team_assignments"], truth)


def test_rendimiento_camino_fallback():
    """El camino sin transformers debe ser holgadamente apto para vídeo."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=6)
    clf.train(boxes, frame)

    start = time.perf_counter()
    for _ in range(10):
        clf.classify(boxes, frame)
    elapsed = (time.perf_counter() - start) / 10.0
    assert elapsed < 0.5, f"Fallback demasiado lento: {elapsed * 1000:.1f} ms/frame"


# ---------------------------------------------------------------------------
# 7. Dependencias opcionales
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _HAS_SKLEARN, reason="scikit-learn no instalado")
def test_kmeans_usa_sklearn_si_esta_disponible():
    """Con scikit-learn presente se usa su KMeans, no el de respaldo."""
    clf = make_classifier()
    frame, boxes, _ = synthetic_match(n_per_team=5)
    clf.train(boxes, frame)
    assert type(clf.kmeans_model).__name__ == "KMeans"
    assert not isinstance(clf.kmeans_model, _NumpyKMeans)


@pytest.mark.slow
@pytest.mark.skipif(not _HAS_UMAP, reason="umap-learn no instalado")
def test_reduccion_con_umap():
    """Con umap-learn y muestras suficientes la reducción usa UMAP."""
    clf = EmbeddingTeamClassifier(
        n_clusters=2, use_transformers=False, umap_min_samples=10, n_components=2
    )
    frame, boxes, truth = synthetic_match(n_per_team=6, seed=31)
    assert clf.train(boxes, frame) is True
    assert clf.reduction_method in ("umap", "pca")
    result = clf.classify(boxes, frame)
    assert len(result["team_assignments"]) == len(boxes)


@pytest.mark.slow
@pytest.mark.skipif(
    not (_HAS_TRANSFORMERS and _HAS_TORCH and _HAS_PIL),
    reason="transformers/torch/Pillow no instalados",
)
def test_backend_siglip_si_el_modelo_esta_disponible():
    """Camino SigLIP real; se salta si el modelo no se puede cargar (offline)."""
    clf = EmbeddingTeamClassifier(
        n_clusters=2, device="cpu", batch_size=8, umap_min_samples=10_000
    )
    if not clf._ensure_model():
        pytest.skip("El modelo SigLIP no está disponible localmente")

    frame, boxes, truth = synthetic_match(n_per_team=4, seed=41)
    assert clf.train(boxes, frame) is True
    assert clf.backend == BACKEND_SIGLIP
    assert clf.embedding_dim is not None and clf.embedding_dim > 100
    result = clf.classify(boxes, frame)
    assert len(result["team_assignments"]) == len(boxes)


def test_modelo_inexistente_degrada_al_fallback():
    """Un model_name inválido no rompe: se degrada al descriptor OpenCV."""
    clf = EmbeddingTeamClassifier(
        n_clusters=2,
        model_name="modelo/que-no-existe-scout-ai",
        umap_min_samples=10_000,
    )
    frame, boxes, truth = synthetic_match(n_per_team=5, seed=13)
    assert clf.train(boxes, frame) is True
    assert clf.backend == BACKEND_FALLBACK
    result = clf.classify(boxes, frame)
    assert teams_separated(result["team_assignments"], truth)

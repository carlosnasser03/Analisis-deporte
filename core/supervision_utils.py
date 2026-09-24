"""
supervision_utils.py - Utilidades para Supervision v0.29.0

Propósito: Centralizar conversiones, filtros y operaciones comunes con Supervision
para evitar reimplementación y mantener consistencia en toda la codebase.
"""

from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import supervision as sv


def dict_to_detections(
    detections_list: List[Dict],
    class_id_key: str = 'class',
    bbox_key: str = 'bbox',
    confidence_key: str = 'confidence'
) -> sv.Detections:
    """
    Convierte una lista de dicts a sv.Detections.

    Args:
        detections_list: Lista de dicts con format {'bbox': [x1,y1,x2,y2], ...}
        class_id_key: Clave para el class_id en el dict
        bbox_key: Clave para el bbox en el dict
        confidence_key: Clave para la confianza en el dict

    Returns:
        sv.Detections: Objeto de Supervision
    """
    if not detections_list:
        return sv.Detections.empty()

    xyxy_list = []
    confidence_list = []
    class_id_list = []

    for det in detections_list:
        bbox = det.get(bbox_key)
        if bbox is None or len(bbox) != 4:
            continue

        xyxy_list.append(bbox)
        confidence_list.append(float(det.get(confidence_key, 1.0)))
        class_id_list.append(int(det.get(class_id_key, 0)))

    if not xyxy_list:
        return sv.Detections.empty()

    return sv.Detections(
        xyxy=np.array(xyxy_list, dtype=float),
        confidence=np.array(confidence_list, dtype=float),
        class_id=np.array(class_id_list, dtype=int)
    )


def detections_to_dicts(
    detections: sv.Detections,
    class_name_map: Optional[Dict[int, str]] = None
) -> List[Dict]:
    """
    Convierte sv.Detections a lista de dicts (inverso de dict_to_detections).

    Args:
        detections: Objeto Supervision
        class_name_map: Mapeo de class_id a nombre (opcional)

    Returns:
        Lista de dicts con format {'bbox': [...], 'confidence': ..., ...}
    """
    if len(detections) == 0:
        return []

    result = []
    for i, (xyxy, conf, class_id) in enumerate(
        zip(detections.xyxy, detections.confidence, detections.class_id)
    ):
        det_dict = {
            'bbox': list(xyxy.astype(float)),
            'confidence': float(conf),
            'class_id': int(class_id),
        }

        if class_name_map is not None and class_id in class_name_map:
            det_dict['class_name'] = class_name_map[class_id]

        result.append(det_dict)

    return result


def filter_detections_by_confidence(
    detections: sv.Detections,
    min_confidence: float = 0.0,
    max_confidence: float = 1.0
) -> sv.Detections:
    """
    Filtra detecciones por rango de confianza.

    Args:
        detections: Objeto Supervision
        min_confidence: Confianza mínima (inclusiva)
        max_confidence: Confianza máxima (inclusiva)

    Returns:
        sv.Detections filtrado
    """
    mask = (detections.confidence >= min_confidence) & (detections.confidence <= max_confidence)
    return detections[mask]


def filter_detections_by_class(
    detections: sv.Detections,
    class_ids: Union[int, List[int]]
) -> sv.Detections:
    """
    Filtra detecciones por class_id.

    Args:
        detections: Objeto Supervision
        class_ids: ID o lista de IDs de clase a mantener

    Returns:
        sv.Detections filtrado
    """
    if isinstance(class_ids, int):
        class_ids = [class_ids]

    mask = np.isin(detections.class_id, class_ids)
    return detections[mask]


def filter_detections_by_area(
    detections: sv.Detections,
    min_area: float = 0.0,
    max_area: float = float('inf')
) -> sv.Detections:
    """
    Filtra detecciones por área del bounding box.

    Args:
        detections: Objeto Supervision
        min_area: Área mínima en píxeles²
        max_area: Área máxima en píxeles²

    Returns:
        sv.Detections filtrado
    """
    # Calcular área de cada caja: (x2-x1) * (y2-y1)
    xyxy = detections.xyxy
    areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
    mask = (areas >= min_area) & (areas <= max_area)
    return detections[mask]


def get_box_centers(detections: sv.Detections) -> np.ndarray:
    """
    Calcula los centroides de los bounding boxes.

    Args:
        detections: Objeto Supervision

    Returns:
        Array (N, 2) con coordenadas del centro de cada caja
    """
    xyxy = detections.xyxy
    centers = (xyxy[:, :2] + xyxy[:, 2:]) / 2.0
    return centers


def get_box_dimensions(detections: sv.Detections) -> np.ndarray:
    """
    Obtiene ancho y alto de cada bounding box.

    Args:
        detections: Objeto Supervision

    Returns:
        Array (N, 2) con [ancho, alto] de cada caja
    """
    xyxy = detections.xyxy
    widths = xyxy[:, 2] - xyxy[:, 0]
    heights = xyxy[:, 3] - xyxy[:, 1]
    return np.column_stack([widths, heights])


def split_detections_by_class(
    detections: sv.Detections
) -> Dict[int, sv.Detections]:
    """
    Divide las detecciones por class_id.

    Args:
        detections: Objeto Supervision

    Returns:
        Dict {class_id: sv.Detections}
    """
    result = {}
    if len(detections) == 0:
        return result

    for class_id in np.unique(detections.class_id):
        mask = detections.class_id == class_id
        result[int(class_id)] = detections[mask]

    return result


def merge_detections(*detections_list: sv.Detections) -> sv.Detections:
    """
    Fusiona múltiples objetos sv.Detections en uno.

    Args:
        *detections_list: Múltiples objetos sv.Detections

    Returns:
        sv.Detections fusionado
    """
    if not detections_list:
        return sv.Detections.empty()

    # Filtrar vacíos
    non_empty = [d for d in detections_list if len(d) > 0]

    if not non_empty:
        return sv.Detections.empty()

    if len(non_empty) == 1:
        return non_empty[0]

    # Concatenar arrays
    xyxy = np.vstack([d.xyxy for d in non_empty])
    confidence = np.hstack([d.confidence for d in non_empty])
    class_id = np.hstack([d.class_id for d in non_empty])

    return sv.Detections(
        xyxy=xyxy,
        confidence=confidence,
        class_id=class_id
    )


def calculate_iou_matrix(
    boxes1: Union[sv.Detections, np.ndarray],
    boxes2: Union[sv.Detections, np.ndarray]
) -> np.ndarray:
    """
    Calcula matriz de IoU entre dos conjuntos de cajas.

    Args:
        boxes1: sv.Detections o array (N, 4)
        boxes2: sv.Detections o array (M, 4)

    Returns:
        Array (N, M) con IoU entre cada par
    """
    if isinstance(boxes1, sv.Detections):
        boxes1 = boxes1.xyxy
    if isinstance(boxes2, sv.Detections):
        boxes2 = boxes2.xyxy

    return sv.box_iou_batch(boxes1, boxes2)


def get_detections_inside_polygon(
    detections: sv.Detections,
    polygon: np.ndarray
) -> sv.Detections:
    """
    Filtra detecciones cuyos centros están dentro de un polígono.

    Args:
        detections: Objeto Supervision
        polygon: Array (N, 2) con vértices del polígono

    Returns:
        sv.Detections dentro del polígono
    """
    centers = get_box_centers(detections)
    zone = sv.PolygonZone(polygon=polygon)

    # PolygonZone espera detecciones, así que creamos dummy
    dummy = sv.Detections(
        xyxy=np.column_stack([centers - 1, centers + 1]),
        confidence=np.ones(len(centers)),
        class_id=np.zeros(len(centers), dtype=int)
    )

    mask = zone.trigger(detections=dummy)
    return detections[mask]


def annotate_detections(
    frame: np.ndarray,
    detections: sv.Detections,
    class_names: Optional[Dict[int, str]] = None,
    show_confidence: bool = True,
    thickness: int = 2,
    text_scale: float = 0.5
) -> np.ndarray:
    """
    Anota detecciones en un frame.

    Args:
        frame: Imagen BGR
        detections: Objeto Supervision
        class_names: Mapeo de class_id a nombre
        show_confidence: Mostrar score de confianza
        thickness: Grosor de línea
        text_scale: Escala del texto

    Returns:
        Frame anotado
    """
    if len(detections) == 0:
        return frame

    # Box annotator
    box_annotator = sv.BoxAnnotator(thickness=thickness)
    annotated = box_annotator.annotate(scene=frame.copy(), detections=detections)

    # Label annotator
    labels = []
    for conf, class_id in zip(detections.confidence, detections.class_id):
        if class_names and int(class_id) in class_names:
            label = class_names[int(class_id)]
        else:
            label = f"Class {int(class_id)}"

        if show_confidence:
            label += f" {conf:.2f}"

        labels.append(label)

    label_annotator = sv.LabelAnnotator(text_scale=text_scale)
    annotated = label_annotator.annotate(
        scene=annotated,
        detections=detections,
        labels=labels
    )

    return annotated


__all__ = [
    'dict_to_detections',
    'detections_to_dicts',
    'filter_detections_by_confidence',
    'filter_detections_by_class',
    'filter_detections_by_area',
    'get_box_centers',
    'get_box_dimensions',
    'split_detections_by_class',
    'merge_detections',
    'calculate_iou_matrix',
    'get_detections_inside_polygon',
    'annotate_detections',
]

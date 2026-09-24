"""
Ejemplo de uso: Mejoras con Supervision v0.29.0

Demuestra las nuevas funcionalidades y cómo usar supervision_utils
para simplificar el procesamiento de detecciones.
"""

import numpy as np
import cv2
import supervision as sv
from pathlib import Path
from typing import Dict

# Importar utilidades
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.supervision_utils import (
    dict_to_detections,
    detections_to_dicts,
    filter_detections_by_confidence,
    filter_detections_by_class,
    filter_detections_by_area,
    get_box_centers,
    split_detections_by_class,
    annotate_detections,
    calculate_iou_matrix,
)


def example_1_convert_detections():
    """Ejemplo 1: Convertir entre formatos dict y sv.Detections"""
    print("\n=== Ejemplo 1: Conversión de formatos ===")

    # Simular detecciones del detector (formato dict)
    raw_detections = [
        {'bbox': [10, 20, 100, 120], 'confidence': 0.95, 'class': 0},
        {'bbox': [150, 50, 250, 200], 'confidence': 0.87, 'class': 1},
        {'bbox': [300, 300, 380, 400], 'confidence': 0.65, 'class': 0},
    ]

    # Convertir a sv.Detections
    detections = dict_to_detections(raw_detections, class_id_key='class')
    print(f"✓ Convertidas {len(detections)} detecciones a sv.Detections")
    print(f"  Confianzas: {detections.confidence}")
    print(f"  Classes: {detections.class_id}")

    # Convertir de vuelta (para compatibilidad)
    back_to_dicts = detections_to_dicts(detections)
    print(f"✓ Convertidas de vuelta a dicts: {len(back_to_dicts)} elementos")


def example_2_filter_detections():
    """Ejemplo 2: Filtrar detecciones de múltiples formas"""
    print("\n=== Ejemplo 2: Filtrado de detecciones ===")

    raw_detections = [
        {'bbox': [10, 20, 100, 120], 'confidence': 0.95, 'class': 0},  # jugador, alta conf
        {'bbox': [150, 50, 250, 200], 'confidence': 0.45, 'class': 1},  # balón, baja conf
        {'bbox': [300, 300, 380, 400], 'confidence': 0.65, 'class': 0},  # jugador, media conf
    ]

    detections = dict_to_detections(raw_detections, class_id_key='class')
    print(f"Original: {len(detections)} detecciones")

    # Filtrar por confianza
    high_conf = filter_detections_by_confidence(detections, min_confidence=0.7)
    print(f"Confianza >= 0.7: {len(high_conf)} detecciones")

    # Filtrar por clase (solo jugadores)
    players = filter_detections_by_class(detections, class_ids=0)
    print(f"Solo jugadores: {len(players)} detecciones")

    # Filtrar por área (cajas medianas)
    xyxy = detections.xyxy
    areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
    print(f"Áreas: {areas}")

    medium_boxes = filter_detections_by_area(
        detections,
        min_area=2000,
        max_area=15000
    )
    print(f"Área 2000-15000 px²: {len(medium_boxes)} detecciones")


def example_3_analyze_detections():
    """Ejemplo 3: Análisis de detecciones"""
    print("\n=== Ejemplo 3: Análisis de detecciones ===")

    raw_detections = [
        {'bbox': [10, 20, 100, 120], 'confidence': 0.95, 'class': 0},
        {'bbox': [150, 50, 250, 200], 'confidence': 0.87, 'class': 1},
        {'bbox': [300, 300, 380, 400], 'confidence': 0.65, 'class': 0},
    ]

    detections = dict_to_detections(raw_detections, class_id_key='class')

    # Obtener centroides
    centers = get_box_centers(detections)
    print(f"Centroides de cajas:")
    for i, (cx, cy) in enumerate(centers):
        print(f"  Caja {i}: ({cx:.1f}, {cy:.1f})")

    # Dividir por clase
    by_class = split_detections_by_class(detections)
    print(f"Detecciones por clase:")
    for class_id, class_dets in by_class.items():
        print(f"  Clase {class_id}: {len(class_dets)} detecciones")


def example_4_iou_matching():
    """Ejemplo 4: Matching usando IoU (para tracking)"""
    print("\n=== Ejemplo 4: Matching por IoU ===")

    # Simular tracks (posición anterior)
    track_boxes = np.array([
        [10, 20, 100, 120],  # jugador 1
        [150, 50, 250, 200],  # jugador 2
    ])

    # Simular detecciones (posición actual)
    det_boxes = np.array([
        [15, 25, 105, 125],   # cercano a track 1
        [145, 55, 245, 205],  # cercano a track 2
        [300, 300, 380, 400],  # sin track asociado
    ])

    # Calcular matriz de IoU
    iou_matrix = calculate_iou_matrix(track_boxes, det_boxes)

    print("Matriz de IoU (tracks vs detecciones):")
    print(iou_matrix)
    print("\nMatching (mayor IoU):")
    for t_idx in range(len(track_boxes)):
        best_det = np.argmax(iou_matrix[t_idx])
        best_iou = iou_matrix[t_idx, best_det]
        print(f"  Track {t_idx} → Detección {best_det} (IoU={best_iou:.3f})")


def example_5_annotation():
    """Ejemplo 5: Anotar detecciones en un frame"""
    print("\n=== Ejemplo 5: Anotación de detecciones ===")

    # Crear frame de ejemplo
    frame = np.ones((480, 640, 3), dtype=np.uint8) * 255

    raw_detections = [
        {'bbox': [50, 50, 150, 200], 'confidence': 0.95, 'class': 0},
        {'bbox': [200, 100, 300, 250], 'confidence': 0.87, 'class': 1},
    ]

    detections = dict_to_detections(raw_detections, class_id_key='class')

    class_names = {0: 'Jugador', 1: 'Balón'}

    # Anotar
    annotated = annotate_detections(
        frame,
        detections,
        class_names=class_names,
        show_confidence=True,
        thickness=2
    )

    print(f"✓ Frame anotado con {len(detections)} detecciones")

    # Guardar si es necesario (descomentar para probar)
    # cv2.imwrite('annotated_example.jpg', annotated)
    # print("  Guardado como 'annotated_example.jpg'")


def example_6_integration_with_pipeline():
    """Ejemplo 6: Integración con pipeline existente"""
    print("\n=== Ejemplo 6: Integración con pipeline ===")

    # Este es un pseudocódigo de cómo se usaría en el pipeline
    print("""
    En tu pipeline integrado:

    # ANTES
    detections = detector.detect_frame(frame)
    players_list = detections['players']  # lista de dicts
    ball_dict = detections['ball']  # dict especial

    for det in players_list:
        tracker.track([det])  # necesita conversión

    # DESPUÉS (más limpio)
    detections = detector.detect_frame(frame)
    players_sv = detections['players_sv']  # sv.Detections

    # Filtrar en una línea
    high_conf_players = players_sv[players_sv.confidence >= 0.6]

    # Usar directamente con tracking
    tracker.track(high_conf_players)

    # Visualizar debuggeo
    annotated = annotate_detections(frame, players_sv)
    cv2.imshow('Detections', annotated)
    """)


def example_7_performance_comparison():
    """Ejemplo 7: Comparación de performance (IoU calculation)"""
    print("\n=== Ejemplo 7: Performance - IoU Calculation ===")

    import time

    # Crear muchas cajas para benchmark
    np.random.seed(42)
    track_boxes = np.random.rand(100, 4) * 500
    track_boxes[:, 2:] += track_boxes[:, :2]  # asegurar x2>x1, y2>y1

    det_boxes = np.random.rand(150, 4) * 500
    det_boxes[:, 2:] += det_boxes[:, :2]

    # Usar optimización de Supervision
    start = time.perf_counter()
    iou_matrix = sv.box_iou_batch(track_boxes, det_boxes)
    elapsed = time.perf_counter() - start

    print(f"✓ Calculada matriz IoU (100x150) en {elapsed*1000:.2f} ms")
    print(f"  Resultado shape: {iou_matrix.shape}")


if __name__ == "__main__":
    print("=" * 60)
    print("Ejemplos: Mejoras con Supervision v0.29.0")
    print("=" * 60)

    example_1_convert_detections()
    example_2_filter_detections()
    example_3_analyze_detections()
    example_4_iou_matching()
    example_5_annotation()
    example_6_integration_with_pipeline()
    example_7_performance_comparison()

    print("\n" + "=" * 60)
    print("✓ Todos los ejemplos completados")
    print("=" * 60)

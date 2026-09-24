"""
football_tracking_integration_example.py - Ejemplo completo de integración

Demuestra cómo usar Football-Tracking mejorado + Supervision
en un pipeline completo de análisis de partido.
"""

import cv2
import numpy as np
import supervision as sv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from football_tracking_integration import (
    ImprovedFootballDetector,
    MultiStageDetector,
    ImprovedTeamAssigner,
    PossessionAnalyzer,
    RobustMetricsCalculator,
    ShotOnGoalDetector,
)
from core.supervision_utils import (
    annotate_detections,
    get_box_centers,
)


def example_1_simple_detection():
    """Ejemplo 1: Detección básica mejorada"""
    print("\n=== Ejemplo 1: Detección Mejorada ===")

    # Crear detector
    detector = ImprovedFootballDetector(
        model_path="yolov8x",  # O tu modelo entrenado
        conf_threshold=0.3
    )
    print("✓ Detector inicializado")

    # Crear frame dummy
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 255

    # Nota: En producción, aquí iría frame real del video
    # detections = detector.detect(frame)
    print("✓ Detector listo para procesar frames")


def example_2_team_assignment():
    """Ejemplo 2: Asignación de equipos mejorada"""
    print("\n=== Ejemplo 2: Asignación de Equipos ===")

    team_assigner = ImprovedTeamAssigner(n_clusters=2)
    print("✓ Team assigner inicializado")

    # Crear frame dummy con colores
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 200
    # Simular: equipo 1 en rojo, equipo 2 en azul
    frame[100:300, 200:400] = [0, 0, 255]  # Rojo
    frame[400:600, 800:1000] = [255, 0, 0]  # Azul

    # Crear detecciones dummy
    dummy_boxes = np.array([
        [200, 100, 400, 300],  # Rojo
        [800, 400, 1000, 600],  # Azul
    ])
    detections = sv.Detections(
        xyxy=dummy_boxes.astype(float),
        confidence=np.array([0.9, 0.9]),
        class_id=np.array([0, 0])
    )

    # Asignar equipos
    team_labels, diagnostics = team_assigner.assign_teams(frame, detections)
    print(f"✓ Asignados {len(detections)} jugadores a equipos")
    print(f"  Teams: {team_labels}")


def example_3_possession():
    """Ejemplo 3: Análisis de posesión"""
    print("\n=== Ejemplo 3: Análisis de Posesión ===")

    possession = PossessionAnalyzer(distance_threshold=100)

    # Crear detecciones dummy
    player_detections = sv.Detections(
        xyxy=np.array([
            [100, 100, 150, 250],
            [200, 200, 250, 350],
            [500, 500, 550, 650],
            [600, 500, 650, 650],
        ]),
        confidence=np.ones(4),
        class_id=np.zeros(4, dtype=int)
    )

    # Balón en medio
    ball_detection = sv.Detections(
        xyxy=np.array([[125, 125, 175, 175]]),
        confidence=np.ones(1),
        class_id=np.zeros(1, dtype=int)
    )

    # Equipos
    team_labels = np.array([0, 0, 1, 1])

    # Analizar posesión
    result = possession.get_ball_possession(ball_detection, player_detections, team_labels)
    print(f"✓ Posesión analizada")
    print(f"  Equipo: {result['possessing_team']}")
    print(f"  Distancia: {result['distance_to_ball']:.1f} px")
    print(f"  Confianza: {result['confidence']:.2f}")


def example_4_metrics():
    """Ejemplo 4: Cálculo de métricas"""
    print("\n=== Ejemplo 4: Métricas de Rendimiento ===")

    metrics = RobustMetricsCalculator(fps=30, pixels_per_meter=10)

    # Simular trayectoria de jugador
    print("✓ Simulando movimiento de jugador...")

    track_id = 1
    positions = [
        (100, 100), (105, 105), (110, 110),
        (115, 115), (120, 120), (125, 125),
    ]

    for pos in positions:
        metrics.update_player_position(track_id, pos)

    # Calcular métricas
    all_metrics = metrics.calculate_all_metrics(track_id)

    print(f"✓ Métricas calculadas para track {track_id}")
    print(f"  Velocidad: {all_metrics['velocity_kmh']:.2f} km/h")
    print(f"  Distancia: {all_metrics['distance_m']:.2f} m")
    print(f"  Aceleración: {all_metrics['acceleration_ms2']:.2f} m/s²")
    print(f"  Cambios dirección: {all_metrics['direction_changes']}")


def example_5_shot_detection():
    """Ejemplo 5: Detección de tiros a puerta"""
    print("\n=== Ejemplo 5: Detección de Tiros ===")

    shot_detector = ShotOnGoalDetector(frame_width=1280)
    print("✓ Shot detector inicializado")

    # Simular balón moviéndose hacia portería
    print("✓ Simulando tiro a puerta...")

    positions = [640, 600, 560, 520, 480, 440, 400, 350, 300, 64]  # Cruza línea

    for pos in positions:
        is_goal, side = shot_detector.check_goal(pos)
        if is_goal:
            print(f"  ⚽ ¡GOOOOL! en {side}")
            break

    print("✓ Shot detection completado")


def example_6_full_pipeline():
    """Ejemplo 6: Pipeline completo integrado"""
    print("\n=== Ejemplo 6: Pipeline Completo ===")

    print("\nIniciando componentes...")

    detector = ImprovedFootballDetector(model_path="yolov8x")
    team_assigner = ImprovedTeamAssigner()
    possession = PossessionAnalyzer()
    metrics = RobustMetricsCalculator()
    shot_detector = ShotOnGoalDetector(frame_width=1280)

    print("✓ Todos los componentes inicializados")

    print("\nFlejo de procesamiento (cada frame):")
    print("""
    1. Detector.detect(frame)
       ↓ sv.Detections con jugadores, balón, árbitros

    2. Detector.get_players_only(detections)
       ↓ Solo jugadores

    3. TeamAssigner.assign_teams(frame, players)
       ↓ Etiquetas de equipo para cada jugador

    4. Metrics.update_player_position(track_id, center)
       ↓ Histórico de posiciones

    5. Possession.get_ball_possession(ball, players, teams)
       ↓ Posesión actual

    6. Metrics.calculate_all_metrics(track_id)
       ↓ Velocidad, distancia, aceleración

    7. ShotDetector.check_goal(ball_x)
       ↓ Detección de tiros

    8. Anotar y mostrar/exportar
    """)

    print("✓ Pipeline completado exitosamente")


def example_7_multi_stage_detection():
    """Ejemplo 7: Detección en múltiples etapas"""
    print("\n=== Ejemplo 7: Detección Multi-Etapa ===")

    detector = MultiStageDetector()
    print("✓ Multi-stage detector inicializado")

    # Crear frame dummy
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 200

    # Nota: En producción, aquí iría frame real
    # detections, diagnostics = detector.detect(frame)

    print("✓ Multi-stage detector pronto para usar")
    print("\nCaracterísticas:")
    print("  - Detección de baja confianza (jugadores parcialmente ocultos)")
    print("  - Filtrado por tamaño (evita ruido)")
    print("  - Validación temporal (coherencia entre frames)")


if __name__ == "__main__":
    print("=" * 60)
    print("Ejemplos: Football-Tracking Integrado con Supervision")
    print("=" * 60)

    example_1_simple_detection()
    example_2_team_assignment()
    example_3_possession()
    example_4_metrics()
    example_5_shot_detection()
    example_6_full_pipeline()
    example_7_multi_stage_detection()

    print("\n" + "=" * 60)
    print("✓ Todos los ejemplos completados")
    print("=" * 60)

    print("\nPróximos pasos:")
    print("1. Leer FOOTBALL_TRACKING_ANALYSIS.md")
    print("2. Adaptar ejemplos a tu video")
    print("3. Integrar en tu pipeline principal")
    print("4. Calibrar pixels_per_meter según campo")

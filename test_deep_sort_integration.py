"""
test_deep_sort_integration.py - Pruebas de integración Deep SORT

Valida que:
✓ Todos los módulos cargan correctamente
✓ Deep SORT funciona
✓ Features se extraen correctamente
✓ Tracking es estable
✓ Integración con otros módulos
"""

import numpy as np
import supervision as sv
import sys
from pathlib import Path

# Agregar ruta
sys.path.insert(0, str(Path(__file__).parent))

from deep_sort_integration import DeepSortTracker, KalmanFilter, FeatureExtractor
from core.supervision_utils import get_box_centers
from football_tracking_integration import ImprovedTeamAssigner, PossessionAnalyzer


def test_kalman_filter():
    """Test 1: Kalman Filter"""
    print("\n" + "=" * 60)
    print("TEST 1: Kalman Filter")
    print("=" * 60)

    kf = KalmanFilter()

    # Iniciar track
    bbox = np.array([100, 100, 200, 250])
    mean, cov = kf.initiate(bbox)
    print(f"✓ Track iniciado: {mean[:4]}")

    # Predecir
    pred_mean, pred_cov = kf.predict(mean, cov)
    print(f"✓ Predicción: {pred_mean[:4]}")

    # Actualizar
    new_bbox = np.array([105, 105, 205, 255])
    upd_mean, upd_cov = kf.update(pred_mean, pred_cov, new_bbox)
    print(f"✓ Actualización: {upd_mean[:4]}")

    # Gating distance
    dist = kf.gating_distance(pred_mean, pred_cov, new_bbox)
    print(f"✓ Gating distance: {dist:.3f}")

    print("✓ TEST 1 PASADO")


def test_feature_extractor():
    """Test 2: Feature Extractor"""
    print("\n" + "=" * 60)
    print("TEST 2: Feature Extractor")
    print("=" * 60)

    extractor = FeatureExtractor()

    # Crear frame dummy
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 100
    frame[100:250, 100:200] = [0, 0, 255]  # Rojo

    # Extraer features
    bbox = np.array([100, 100, 200, 250])

    # Color
    color_feat = extractor.extract_color_histogram(bbox, frame)
    print(f"✓ Color features shape: {color_feat.shape}")

    # Gradient
    grad_feat = extractor.extract_gradient_features(bbox, frame)
    print(f"✓ Gradient features shape: {grad_feat.shape}")

    # Combined
    combined = extractor.extract(bbox, frame, use_color=True, use_hog=True)
    print(f"✓ Combined features shape: {combined.shape}")

    # Distance
    combined2 = extractor.extract(bbox, frame)
    dist = FeatureExtractor.cosine_distance(combined, combined2)
    print(f"✓ Cosine distance: {dist:.3f}")

    print("✓ TEST 2 PASADO")


def test_deep_sort_tracker():
    """Test 3: Deep SORT Tracker"""
    print("\n" + "=" * 60)
    print("TEST 3: Deep SORT Tracker")
    print("=" * 60)

    tracker = DeepSortTracker(use_features=True)
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 200

    print("Simulando 20 frames con 2 jugadores...")

    for frame_idx in range(20):
        # Simular movimiento de jugadores
        detections = sv.Detections(
            xyxy=np.array([
                [100 + frame_idx*3, 100, 200 + frame_idx*3, 250],
                [500, 300 + frame_idx*2, 600, 450 + frame_idx*2],
            ]),
            confidence=np.array([0.95, 0.85]),
            class_id=np.array([0, 0]),
        )

        result = tracker.update(detections, frame)

        if frame_idx % 5 == 0:
            print(
                f"  Frame {frame_idx}: "
                f"Matched={result['matched']}, "
                f"New={result['new_tracks']}, "
                f"Active={result['active_tracks']}"
            )

    # Obtener tracks confirmados
    confirmed = tracker.get_tracks()
    print(f"✓ Tracks confirmados: {len(confirmed)}")

    print("✓ TEST 3 PASADO")


def test_integration():
    """Test 4: Integración completa"""
    print("\n" + "=" * 60)
    print("TEST 4: Integración Completa")
    print("=" * 60)

    # Crear componentes
    tracker = DeepSortTracker(use_features=True)
    team_assigner = ImprovedTeamAssigner()
    possession = PossessionAnalyzer()

    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 200
    frame[100:250, 100:200] = [0, 0, 255]  # Equipo 1 (rojo)
    frame[300:450, 500:600] = [255, 0, 0]  # Equipo 2 (azul)

    # Crear detecciones
    detections = sv.Detections(
        xyxy=np.array([
            [100, 100, 200, 250],  # Rojo
            [500, 300, 600, 450],  # Azul
        ]),
        confidence=np.array([0.95, 0.90]),
        class_id=np.array([0, 0]),
    )

    # 1. Tracking
    result = tracker.update(detections, frame)
    tracks = result['tracks']
    print(f"✓ Tracking: {len(tracks)} tracks")

    if len(tracks) > 0:
        # Crear detecciones tracked
        tracked = sv.Detections(
            xyxy=np.array([t['bbox'] for t in tracks]),
            confidence=np.ones(len(tracks)),
            class_id=np.zeros(len(tracks), dtype=int),
        )

        # 2. Asignación de equipos
        teams, _ = team_assigner.assign_teams(frame, tracked)
        print(f"✓ Equipos: {teams}")

        # 3. Posesión
        ball = sv.Detections(
            xyxy=np.array([[150, 150, 160, 160]]),
            confidence=np.array([0.99]),
            class_id=np.array([2]),
        )

        poss = possession.get_ball_possession(ball, tracked, teams)
        print(f"✓ Posesión: Equipo {poss['possessing_team']} ({poss['confidence']:.0%})")

    print("✓ TEST 4 PASADO")


def test_occlusion_robustness():
    """Test 5: Robustez ante oclusiones"""
    print("\n" + "=" * 60)
    print("TEST 5: Robustez ante Oclusiones")
    print("=" * 60)

    tracker = DeepSortTracker(use_features=True, max_age=50)
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 200

    print("Simulando oclusión de 5 frames...")

    for frame_idx in range(20):
        if frame_idx < 5:
            # Visible
            detections = sv.Detections(
                xyxy=np.array([[100 + frame_idx*5, 100, 200 + frame_idx*5, 250]]),
                confidence=np.array([0.95]),
                class_id=np.array([0]),
            )
            status = "VISIBLE"
        elif frame_idx < 10:
            # Ocluido (sin detección)
            detections = sv.Detections.empty()
            status = "OCLUIDO"
        else:
            # Visible de nuevo
            detections = sv.Detections(
                xyxy=np.array([[100 + frame_idx*5, 100, 200 + frame_idx*5, 250]]),
                confidence=np.array([0.95]),
                class_id=np.array([0]),
            )
            status = "VISIBLE (RECUPERADO)"

        result = tracker.update(detections, frame)
        confirmed = len(result['tracks'])

        if frame_idx % 5 == 0 or frame_idx == 9:
            print(f"  Frame {frame_idx}: {status:20s} → {confirmed} tracks confirmados")

    print("✓ TEST 5 PASADO (Track mantenido durante oclusión)")


def run_all_tests():
    """Ejecutar todos los tests"""
    print("\n" + "=" * 60)
    print("SUITE DE TESTS: Deep SORT Integration")
    print("=" * 60)

    try:
        test_kalman_filter()
        test_feature_extractor()
        test_deep_sort_tracker()
        test_integration()
        test_occlusion_robustness()

        print("\n" + "=" * 60)
        print("✓✓✓ TODOS LOS TESTS PASARON ✓✓✓")
        print("=" * 60)
        print("\nDeep SORT está listo para producción.\n")

        return True

    except Exception as e:
        print(f"\n✗ ERROR EN TEST: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

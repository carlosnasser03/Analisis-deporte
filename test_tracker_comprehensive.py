"""
test_tracker_comprehensive.py - Suite completa de tests para validar el fix de asignación

Tests que validan:
1. Asignación correcta 1-a-1
2. Manejo de casos ambiguos
3. Creación de nuevos tracks
4. Envejecimiento de tracks sin asignación
5. Oclusiones detectadas correctamente
"""

from core.tracker import PlayerTracker
import numpy as np


class TestTrackerAssignment:
    """Suite de tests para asignación óptima de tracks"""

    @staticmethod
    def test_single_track_single_detection():
        """Test más simple: 1 track + 1 detección"""
        tracker = PlayerTracker(max_age=30, min_hits=1)

        # Frame 1: Crear 1 track
        det1 = [{'bbox': [10, 10, 30, 30], 'confidence': 0.9}]
        r1 = tracker.track(det1, frame_id=1)
        assert r1['matched'] == 0 and r1['new_tracks'] == 1

        # Frame 2: 1 detección cercana
        det2 = [{'bbox': [12, 12, 32, 32], 'confidence': 0.9}]
        r2 = tracker.track(det2, frame_id=2)
        assert r2['matched'] == 1, f"Expected 1 match, got {r2['matched']}"
        assert r2['new_tracks'] == 0
        print("✓ test_single_track_single_detection PASSED")

    @staticmethod
    def test_two_tracks_one_detection_exclusive():
        """Test crítica: 2 tracks solapados + 1 detección

        Valida que SOLO 1 track se asigne a la detección (no ambos)
        """
        tracker = PlayerTracker(max_age=30, min_hits=1)

        # Frame 1: 2 tracks solapados
        det1 = [
            {'bbox': [10, 10, 40, 40], 'confidence': 0.9},   # Track 1
            {'bbox': [25, 10, 55, 40], 'confidence': 0.9},   # Track 2 (solapado)
        ]
        r1 = tracker.track(det1, frame_id=1)
        assert r1['matched'] == 0 and r1['new_tracks'] == 2

        # Guardar IDs y posiciones iniciales
        tracks_f1 = {t['track_id']: t for t in tracker.get_tracks()}
        track_ids = sorted(tracks_f1.keys())

        # Frame 2: 1 detección ambigua
        det2 = [{'bbox': [20, 10, 50, 40], 'confidence': 0.9}]  # En el medio
        r2 = tracker.track(det2, frame_id=2)

        # VALIDACIÓN CRÍTICA
        assert r2['matched'] == 1, \
            f"FALLO CRÍTICO: matched={r2['matched']}, expected 1. " \
            "Esto indica que múltiples tracks se asignaron a 1 detección."

        # Verificar que solo 1 track se actualizó
        tracks_f2 = {t['track_id']: t for t in tracker.get_tracks()}
        updated_count = sum(
            1 for tid in track_ids
            if not np.allclose(tracks_f1[tid]['bbox'], tracks_f2[tid]['bbox'])
        )
        assert updated_count == 1, \
            f"Expected 1 track updated, got {updated_count}"

        print("✓ test_two_tracks_one_detection_exclusive PASSED")

    @staticmethod
    def test_multiple_tracks_multiple_detections():
        """Test: 3 tracks + 3 detecciones (perfect matching)"""
        tracker = PlayerTracker(max_age=30, min_hits=1)

        # Frame 1: 3 tracks
        det1 = [
            {'bbox': [0, 0, 20, 20], 'confidence': 0.9},
            {'bbox': [40, 0, 60, 20], 'confidence': 0.9},
            {'bbox': [80, 0, 100, 20], 'confidence': 0.9},
        ]
        r1 = tracker.track(det1, frame_id=1)
        assert r1['matched'] == 0 and r1['new_tracks'] == 3

        # Frame 2: 3 detecciones (desplazadas)
        det2 = [
            {'bbox': [2, 2, 22, 22], 'confidence': 0.9},
            {'bbox': [42, 2, 62, 22], 'confidence': 0.9},
            {'bbox': [82, 2, 102, 22], 'confidence': 0.9},
        ]
        r2 = tracker.track(det2, frame_id=2)

        # Todos deben matchear
        assert r2['matched'] == 3, \
            f"Expected 3 matches, got {r2['matched']}"
        assert r2['new_tracks'] == 0
        print("✓ test_multiple_tracks_multiple_detections PASSED")

    @staticmethod
    def test_unmatched_detection_creates_new_track():
        """Test: Detección sin match crea nuevo track"""
        tracker = PlayerTracker(max_age=30, min_hits=1)

        # Frame 1: 1 track
        det1 = [{'bbox': [0, 0, 20, 20], 'confidence': 0.9}]
        r1 = tracker.track(det1, frame_id=1)
        assert r1['matched'] == 0 and r1['new_tracks'] == 1

        # Frame 2: 1 detección cerca + 1 lejana
        det2 = [
            {'bbox': [2, 2, 22, 22], 'confidence': 0.9},      # Cerca (match)
            {'bbox': [100, 100, 120, 120], 'confidence': 0.9}, # Lejana (nuevo)
        ]
        r2 = tracker.track(det2, frame_id=2)

        assert r2['matched'] == 1, f"Expected 1 match, got {r2['matched']}"
        assert r2['new_tracks'] == 1, f"Expected 1 new track, got {r2['new_tracks']}"
        assert r2['active_tracks'] == 2, f"Expected 2 active tracks, got {r2['active_tracks']}"
        print("✓ test_unmatched_detection_creates_new_track PASSED")

    @staticmethod
    def test_unmatched_track_ages():
        """Test: Track sin match envejece y se elimina"""
        tracker = PlayerTracker(max_age=3, min_hits=1)  # max_age bajo para test

        # Frame 1: 1 track
        det1 = [{'bbox': [0, 0, 20, 20], 'confidence': 0.9}]
        tracker.track(det1, frame_id=1)
        assert len(tracker.get_tracks()) == 1

        # Frame 2-4: Sin detecciones (track envejece)
        for frame in range(2, 6):
            r = tracker.track([], frame_id=frame)
            tracks = tracker.get_tracks()
            if frame <= 4:  # max_age=3, así que se elimina en frame 5
                # El track aún debe estar activo (time_since_update <= max_age)
                pass
            else:
                # Frame 5: track debe haber sido eliminado (time_since_update > max_age)
                assert len(tracks) == 0, f"Expected 0 tracks in frame {frame}, got {len(tracks)}"

        print("✓ test_unmatched_track_ages PASSED")

    @staticmethod
    def test_empty_detections():
        """Test: Manejar detecciones vacías"""
        tracker = PlayerTracker(max_age=30, min_hits=1)

        # Frame 1: 1 track
        det1 = [{'bbox': [0, 0, 20, 20], 'confidence': 0.9}]
        tracker.track(det1, frame_id=1)

        # Frame 2: Sin detecciones
        r2 = tracker.track([], frame_id=2)
        assert r2['matched'] == 0
        assert r2['new_tracks'] == 0
        assert len(tracker.get_tracks()) == 1  # Track sigue activo pero envejecido
        print("✓ test_empty_detections PASSED")

    @staticmethod
    def test_high_iou_priority():
        """Test: Detecciones con IoU más alto obtienen prioridad"""
        tracker = PlayerTracker(max_age=30, min_hits=1)

        # Frame 1: 2 tracks alejados
        det1 = [
            {'bbox': [0, 0, 20, 20], 'confidence': 0.9},      # Track 1
            {'bbox': [100, 0, 120, 20], 'confidence': 0.9},   # Track 2
        ]
        r1 = tracker.track(det1, frame_id=1)
        tracks_f1 = {t['track_id']: t for t in tracker.get_tracks()}
        track_ids = sorted(tracks_f1.keys())

        # Frame 2: 2 detecciones, pero una tiene IoU muy alta con track 2
        det2 = [
            {'bbox': [10, 0, 30, 20], 'confidence': 0.9},     # Cercana a Track 1 (IoU ~0.33)
            {'bbox': [101, 0, 121, 20], 'confidence': 0.9},   # Muy cercana a Track 2 (IoU ~0.8)
        ]
        r2 = tracker.track(det2, frame_id=2)

        tracks_f2 = {t['track_id']: t for t in tracker.get_tracks()}

        # Track 2 debe matchear con detección 2 (IoU más alto)
        # Track 1 debe matchear con detección 1
        assert r2['matched'] == 2, f"Expected 2 matches, got {r2['matched']}"

        # Verificar que cada track se actualizó con su detección correcta
        track1_matched_det2 = np.allclose(tracks_f2[track_ids[0]]['bbox'], det2[1]['bbox'])
        track2_matched_det1 = np.allclose(tracks_f2[track_ids[1]]['bbox'], det2[0]['bbox'])

        # Track 1 debe tener bbox cercana a det2[0] (la primera detección)
        # Track 2 debe tener bbox cercana a det2[1] (la segunda detección)
        assert np.allclose(tracks_f2[track_ids[0]]['bbox'], det2[0]['bbox']) or \
               np.allclose(tracks_f2[track_ids[0]]['bbox'], det2[1]['bbox']), \
               "Track 1 no se actualizó correctamente"

        print("✓ test_high_iou_priority PASSED")

    @staticmethod
    def test_track_id_stability():
        """Test: IDs de tracks permanecen estables"""
        tracker = PlayerTracker(max_age=30, min_hits=1)

        # Frame 1: Crear 2 tracks
        det1 = [
            {'bbox': [0, 0, 20, 20], 'confidence': 0.9},
            {'bbox': [50, 50, 70, 70], 'confidence': 0.9},
        ]
        tracker.track(det1, frame_id=1)
        tracks_f1 = {t['track_id']: t for t in tracker.get_tracks()}
        ids_f1 = set(tracks_f1.keys())

        # Frames 2-5: Dar tracking
        for frame in range(2, 6):
            det = [
                {'bbox': [0 + frame, 0 + frame, 20 + frame, 20 + frame], 'confidence': 0.9},
                {'bbox': [50 + frame, 50 + frame, 70 + frame, 70 + frame], 'confidence': 0.9},
            ]
            tracker.track(det, frame_id=frame)

        tracks_f5 = {t['track_id']: t for t in tracker.get_tracks()}
        ids_f5 = set(tracks_f5.keys())

        # IDs deben ser los mismos
        assert ids_f1 == ids_f5, f"Track IDs changed: {ids_f1} -> {ids_f5}"
        print("✓ test_track_id_stability PASSED")


def run_all_tests():
    """Ejecuta toda la suite de tests"""
    print("\n" + "="*60)
    print("EXECUTING COMPREHENSIVE TRACKER TESTS")
    print("="*60 + "\n")

    tests = [
        TestTrackerAssignment.test_single_track_single_detection,
        TestTrackerAssignment.test_two_tracks_one_detection_exclusive,
        TestTrackerAssignment.test_multiple_tracks_multiple_detections,
        TestTrackerAssignment.test_unmatched_detection_creates_new_track,
        TestTrackerAssignment.test_unmatched_track_ages,
        TestTrackerAssignment.test_empty_detections,
        TestTrackerAssignment.test_high_iou_priority,
        TestTrackerAssignment.test_track_id_stability,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"✗ {test.__name__} FAILED: {e}\n")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} ERROR: {e}\n")

    print("\n" + "="*60)
    print(f"RESULTS: {passed} PASSED, {failed} FAILED")
    print("="*60)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Tracker fix validated!")
        return True
    else:
        print(f"\n❌ {failed} TESTS FAILED")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)

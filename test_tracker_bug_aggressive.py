"""
test_tracker_bug_aggressive.py - Test más agresivo para exponer el bug

Intenta crear una situación donde:
- 2 tracks existentes
- 1 detección "ambigua" que tiene IoU similar con ambos tracks
- Verificar que ambos no se asignen simultáneamente
"""

from core.tracker import PlayerTracker
import numpy as np


def test_ambiguous_detection_allocation():
    """
    Test más agresivo: detección ambigua entre 2 tracks.

    Setup:
    - Track 1 en [10, 10, 40, 40]  (área 30x30 = 900)
    - Track 2 en [25, 10, 55, 40]  (área 30x30 = 900, overlapping)
    - Nueva detección en [15, 10, 45, 40] (muy solapada con ambas)

    La detección está casi igualmente cerca de ambos tracks.
    Sin fix: ambos podrían asignarse a ella.
    Con fix: solo uno se asigna.
    """
    tracker = PlayerTracker(max_age=30, min_hits=1)

    # Frame 1: Crear 2 tracks que se solapan
    detections_f1 = [
        {'bbox': [10, 10, 40, 40], 'confidence': 0.9},  # Track 1
        {'bbox': [25, 10, 55, 40], 'confidence': 0.9},  # Track 2 (overlapping)
    ]
    result = tracker.track(detections_f1, frame_id=1)

    print("\n=== Frame 1: Crear 2 tracks solapados ===")
    print(f"Track 1: {detections_f1[0]['bbox']}")
    print(f"Track 2: {detections_f1[1]['bbox']}")
    print(f"Result: {result}")

    tracks_f1 = {t['track_id']: t for t in tracker.get_tracks()}
    track_ids = sorted(tracks_f1.keys())
    track1_id, track2_id = track_ids[0], track_ids[1]

    # Frame 2: Una sola detección "ambigua" en el medio
    # Tiene solapamiento significativo con ambos tracks
    detections_f2 = [
        {'bbox': [20, 10, 50, 40], 'confidence': 0.9},  # En el medio, cerca de ambos
    ]

    result = tracker.track(detections_f2, frame_id=2)

    print("\n=== Frame 2: 1 detección ambigua ===")
    print(f"Detección: {detections_f2[0]['bbox']}")
    print(f"Result: {result}")
    print(f"Expected: matched=1, got: matched={result['matched']}")

    tracks_f2 = {t['track_id']: t for t in tracker.get_tracks()}

    # Contar cuántos tracks se actualizaron
    track1_updated = not np.allclose(tracks_f1[track1_id]['bbox'], tracks_f2[track1_id]['bbox'])
    track2_updated = not np.allclose(tracks_f1[track2_id]['bbox'], tracks_f2[track2_id]['bbox'])

    print(f"\nTrack {track1_id} actualizado: {track1_updated}")
    print(f"Track {track2_id} actualizado: {track2_updated}")
    print(f"Total actualizados: {int(track1_updated) + int(track2_updated)}")

    # VALIDACIÓN
    total_updated = int(track1_updated) + int(track2_updated)

    if result['matched'] != total_updated:
        print(f"\nWARNING: matched ({result['matched']}) != tracks_updated ({total_updated})")
        print("Esto indica inconsistencia en la asignación")

    # Solo UN track debe actualizarse
    assert result['matched'] == 1, \
        f"FALLO: Se esperaba 1 match pero se obtuvieron {result['matched']}. " \
        f"Total de tracks actualizados: {total_updated}"

    assert total_updated == 1, \
        f"FALLO: Solo 1 track debería actualizarse pero {total_updated} se actualizaron"

    print("\n=== TEST PASSED ===")


def test_greedy_misallocation():
    """
    Test extreme: 2 tracks, 1 detección, ambos track podrían elegirla greedy.

    Si el algoritmo es "greedy sin exclusión", ambos podrían asignarse.
    """
    tracker = PlayerTracker(max_age=30, min_hits=1)

    # Frame 1: 2 tracks muy lejanos
    detections_f1 = [
        {'bbox': [0, 0, 20, 20], 'confidence': 0.9},
        {'bbox': [100, 100, 120, 120], 'confidence': 0.9},
    ]
    tracker.track(detections_f1, frame_id=1)

    # Frame 2: 1 detección que NO tiene IoU > 0.3 con ninguno
    # Así ambos quedan sin match, y la detección se convierte en nuevo track
    detections_f2 = [
        {'bbox': [50, 50, 70, 70], 'confidence': 0.9},  # Far from both
    ]
    result = tracker.track(detections_f2, frame_id=2)

    print("\n=== Frame 2 (detección lejana): Debería crear nuevo track ===")
    print(f"Result: {result}")
    print(f"Expected: matched=0, new_tracks=1")

    assert result['matched'] == 0, "No debería haber matches"
    assert result['new_tracks'] == 1, "Debería crear 1 nuevo track"
    assert result['active_tracks'] == 3, "Debería haber 3 tracks activos (2 + 1 nuevo)"

    print("✓ Test passed")


if __name__ == '__main__':
    test_ambiguous_detection_allocation()
    test_greedy_misallocation()
    print("\n=== TODOS LOS TESTS PASARON ===")

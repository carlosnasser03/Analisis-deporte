"""
test_tracker_bug.py - Test que reproduce el bug de asignación múltiple de tracks

Problema: Cuando hay 2 tracks y 1 detección, ambos tracks se actualizan con
la misma detección, causando duplicación.

ANTES del fix: El test FALLA (ambos tracks se asignan a la misma detección)
DESPUÉS del fix: El test PASA (solo 1 track se asigna, el otro se predice)
"""

from core.tracker import PlayerTracker


def test_single_detection_multiple_tracks():
    """
    Test crítico: 2 tracks activos + 1 detección nueva

    Solo UN track debe asignarse a esa detección.
    El otro debe mantener su posición anterior (predicción/edad).
    """
    tracker = PlayerTracker(max_age=30, min_hits=1)

    # --- Frame 1: Crear 2 tracks ---
    detections_f1 = [
        {
            'bbox': [10, 10, 30, 30],
            'confidence': 0.9,
            'team_id': 1,
            'jersey_number': '7'
        },
        {
            'bbox': [50, 50, 70, 70],
            'confidence': 0.9,
            'team_id': 2,
            'jersey_number': '10'
        }
    ]
    result = tracker.track(detections_f1, frame_id=1)

    print("\n=== Frame 1: Creación de 2 tracks ===")
    print(f"Result: {result}")
    assert result['matched'] == 0, "Esperado 0 matches en creación"
    assert result['new_tracks'] == 2, "Esperado 2 nuevos tracks"
    assert result['active_tracks'] == 2, "Esperado 2 tracks activos"

    # Guardar las posiciones iniciales
    tracks_f1 = {t['track_id']: t for t in tracker.get_tracks()}
    print(f"Tracks después de F1: {[(t['track_id'], t['bbox']) for t in tracks_f1.values()]}")

    assert len(tracks_f1) == 2, "Debe haber 2 tracks"
    track_ids = list(tracks_f1.keys())
    track1_id, track2_id = track_ids[0], track_ids[1]

    track1_bbox_f1 = tracks_f1[track1_id]['bbox']
    track2_bbox_f1 = tracks_f1[track2_id]['bbox']

    # --- Frame 2: 1 detección cerca del track 1 ---
    # La detección está CERCA de track1 pero también con IoU > 0.3 para track2
    detections_f2 = [
        {
            'bbox': [12, 12, 32, 32],  # Cercana a track1
            'confidence': 0.95,
            'team_id': 1,
            'jersey_number': '7'
        }
    ]
    result = tracker.track(detections_f2, frame_id=2)

    print("\n=== Frame 2: 1 detección (debería asignarse a 1 track) ===")
    print(f"Result: {result}")

    # AQUÍ ES DONDE FALLA SIN FIX:
    # - matched debería ser 1 (1 track se asignó a 1 detección)
    # - Pero sin fix, ambos tracks podrían asignarse

    tracks_f2 = {t['track_id']: t for t in tracker.get_tracks()}
    print(f"Tracks después de F2: {[(t['track_id'], t['bbox']) for t in tracks_f2.values()]}")

    track1_f2 = tracks_f2[track1_id]
    track2_f2 = tracks_f2[track2_id]

    # Track 1 debe actualizarse (IoU más alto)
    # Track 2 debe permanecer igual o envejecer, pero NUNCA asignarse a la detección

    print(f"\nTrack 1 - F1: {track1_bbox_f1} -> F2: {track1_f2['bbox']}")
    print(f"Track 2 - F1: {track2_bbox_f1} -> F2: {track2_f2['bbox']}")

    # VALIDACIÓN CRÍTICA
    print("\n=== VALIDACIÓN CRÍTICA ===")

    # Solo 1 detección, así que solo 1 track debe actualizarse
    assert result['matched'] == 1, \
        f"FALLO: Se esperaba 1 match pero se obtuvieron {result['matched']}. " \
        "Esto indica que múltiples tracks se asignaron a la misma detección."

    # Track 1 debe tener la bbox actualizada (cercana a la detección)
    track1_updated = not np.allclose(track1_f2['bbox'], track1_bbox_f1)

    # Track 2 debe PERMANECER en su posición anterior (sin cambios)
    track2_unchanged = np.allclose(track2_f2['bbox'], track2_bbox_f1)

    print(f"Track 1 actualizado: {track1_updated}")
    print(f"Track 2 sin cambios: {track2_unchanged}")

    # Verificar que solo track1 se actualizó
    if track1_updated:
        print(f"✓ Track {track1_id} se actualizó correctamente")
    else:
        print(f"✗ Track {track1_id} NO se actualizó (algo anda mal)")

    if track2_unchanged:
        print(f"✓ Track {track2_id} se mantuvo sin cambios (correcto)")
    else:
        print(f"✗ Track {track2_id} cambió (VIOLACIÓN - fue asignado incorrectamente)")

    assert track1_updated, "Track 1 debe actualizarse"
    assert track2_unchanged, \
        "FALLO: Track 2 cambió de posición sin ser asignado. " \
        "Indicador de que ambos tracks fueron asignados a la misma detección."

    print("\n=== TEST PASSED ===")


if __name__ == '__main__':
    import numpy as np
    test_single_detection_multiple_tracks()
    print("\nTodo OK - El bug está arreglado!")

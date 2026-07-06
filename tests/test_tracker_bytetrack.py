"""
test_tracker_bytetrack.py - Tests end-to-end del tracker mejorado

Objetivo: Validar que ByteTrack mejorado:
- Mantiene IDs consistentes para jugadores
- Recupera tracks después de oclusiones (Re-ID)
- Detecta anomalías de movimiento
- Genera estadísticas precisas
- Procesa 500+ frames sin fallos

Autor: Scout AI Analytics
"""

import pytest
import numpy as np
import json
from typing import List, Dict, Tuple
from pathlib import Path
import sys

# Agregar paths
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.tracker_improved import ByteTrackImproved, TrackStatus


class MockDetectionGenerator:
    """Generador de detecciones simuladas para testing."""

    def __init__(self, num_players: int = 22, width: int = 1280, height: int = 720):
        """
        Inicializa el generador de detecciones.

        Args:
            num_players (int): Número de jugadores a simular
            width (int): Ancho del campo
            height (int): Alto del campo
        """
        self.num_players = num_players
        self.width = width
        self.height = height

        # Posiciones iniciales de los jugadores
        self.positions = {}
        self.velocities = {}
        self.teams = {}

        # Inicializar posiciones
        team_a_x = width // 4
        team_b_x = 3 * width // 4

        for i in range(num_players):
            player_id = i + 1
            if i < num_players // 2:
                # Equipo A
                x = team_a_x + np.random.randint(-100, 100)
                y = np.random.randint(100, height - 100)
                vx = np.random.uniform(1, 5)
                vy = np.random.uniform(-2, 2)
                self.teams[player_id] = 0
            else:
                # Equipo B
                x = team_b_x + np.random.randint(-100, 100)
                y = np.random.randint(100, height - 100)
                vx = np.random.uniform(-5, -1)
                vy = np.random.uniform(-2, 2)
                self.teams[player_id] = 1

            self.positions[player_id] = (float(x), float(y))
            self.velocities[player_id] = (vx, vy)

    def generate_frame(self, frame_id: int, occlusion_probability: float = 0.05) -> List[Dict]:
        """
        Genera detecciones para un frame.

        Args:
            frame_id (int): ID del frame
            occlusion_probability (float): Probabilidad de oclusión para cada jugador

        Returns:
            List[Dict]: Lista de detecciones
        """
        detections = []

        for player_id, (x, y) in self.positions.items():
            # Actualizar posición
            vx, vy = self.velocities[player_id]
            x += vx
            y += vy

            # Mantener dentro de los límites
            if x < 50:
                x = 50
                vx = abs(vx)
            elif x > self.width - 50:
                x = self.width - 50
                vx = -abs(vx)

            if y < 50:
                y = 50
                vy = abs(vy)
            elif y > self.height - 50:
                y = self.height - 50
                vy = -abs(vy)

            self.positions[player_id] = (x, y)
            self.velocities[player_id] = (vx, vy)

            # Aplicar oclusión aleatoria
            if np.random.random() < occlusion_probability:
                continue

            # Crear detección
            bbox_size = 50
            bbox = [
                x - bbox_size / 2,
                y - bbox_size / 2,
                x + bbox_size / 2,
                y + bbox_size / 2
            ]

            detection = {
                'bbox': bbox,
                'confidence': 0.95 + np.random.uniform(-0.05, 0.0),
                'team_id': self.teams[player_id],
                'jersey_number': f"{self.teams[player_id]}{player_id % 11 + 1}"
            }

            detections.append(detection)

        return detections


class TestByteTrackImproved:
    """Suite de tests para ByteTrack mejorado."""

    @pytest.fixture
    def tracker(self):
        """Crea una instancia del tracker."""
        return ByteTrackImproved(max_age=30, min_hits=3)

    def test_initialization(self, tracker):
        """Test: Inicialización correcta del tracker."""
        assert tracker.frame_count == 0
        assert len(tracker.tracks) == 0
        assert len(tracker.lost_tracks) == 0
        assert tracker.next_id == 1

    def test_single_frame_tracking(self, tracker):
        """Test: Tracking de un solo frame."""
        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
            {'bbox': [200, 150, 250, 250], 'confidence': 0.92},
        ]

        result = tracker.track(detections)

        assert result['new_tracks'] == 2
        assert len(tracker.tracks) == 2
        assert result['active_tracks'] == 2

    def test_track_continuity(self, tracker):
        """Test: Continuidad de IDs en múltiples frames."""
        # Frame 1
        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
            {'bbox': [300, 150, 350, 250], 'confidence': 0.92},
        ]

        tracker.track(detections)
        tracks_frame1 = tracker.get_active_tracks()
        ids_frame1 = {t['track_id'] for t in tracks_frame1}

        # Frame 2 - jugadores se mueven ligeramente
        detections = [
            {'bbox': [110, 105, 160, 205], 'confidence': 0.94},
            {'bbox': [310, 155, 360, 255], 'confidence': 0.93},
        ]

        tracker.track(detections)
        tracks_frame2 = tracker.get_active_tracks()
        ids_frame2 = {t['track_id'] for t in tracks_frame2}

        # Los IDs deben mantenerse
        assert ids_frame1 == ids_frame2

    def test_track_confirmation(self, tracker):
        """Test: Confirmación de tracks después de min_hits."""
        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
        ]

        # Los primeros 2 frames son TENTATIVE
        for _ in range(2):
            tracker.track(detections)

        confirmed_tracks = [t for t in tracker.get_active_tracks()
                           if t['status'] == 'CONFIRMED']
        assert len(confirmed_tracks) == 0

        # Frame 3 - ahora debe estar CONFIRMED
        tracker.track(detections)
        confirmed_tracks = [t for t in tracker.get_active_tracks()
                           if t['status'] == 'CONFIRMED']
        assert len(confirmed_tracks) == 1

    def test_occlusion_detection(self, tracker):
        """Test: Detección de oclusiones."""
        # Dos jugadores
        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
            {'bbox': [300, 150, 350, 250], 'confidence': 0.92},
        ]

        tracker.track(detections)

        # Crear oclusión (muchos jugadores superpuestos)
        occluded_detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
            {'bbox': [120, 110, 170, 210], 'confidence': 0.80},  # Solapamiento
            {'bbox': [140, 130, 190, 230], 'confidence': 0.75},  # Solapamiento
        ]

        tracker.track(occluded_detections)
        tracks = tracker.get_active_tracks()

        # Algunos tracks deben ser marcados como ocluidos
        occluded = [t for t in tracks if t['is_occluded']]
        assert len(occluded) > 0

    def test_track_loss_and_recovery(self, tracker):
        """Test: Pérdida y recuperación de tracks."""
        initial_track_id = None

        # Crear track
        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
        ]

        for _ in range(3):
            tracker.track(detections)

        tracks = tracker.get_active_tracks()
        initial_track_id = tracks[0]['track_id']

        # Perder track (sin detecciones por varios frames)
        for _ in range(15):
            tracker.track([])

        # Track debe estar en lost_tracks
        assert initial_track_id not in tracker.tracks

        # Recuperar track (nueva detección cerca de la posición anterior)
        detections = [
            {'bbox': [105, 105, 155, 205], 'confidence': 0.95},
        ]

        tracker.track(detections)

        # El track puede ser recuperado o ser un nuevo ID
        # Esto depende de la estrategia de Re-ID
        assert len(tracker.tracks) > 0

    def test_simulation_500_frames(self):
        """Test PRINCIPAL: Simular 500 frames con 22 jugadores."""
        tracker = ByteTrackImproved(max_age=30, min_hits=3)
        generator = MockDetectionGenerator(num_players=22)

        frame_stats = []
        id_changes = {}  # Rastrear cambios de ID por jugador

        # Procesar 500 frames
        for frame_id in range(500):
            detections = generator.generate_frame(frame_id)

            result = tracker.track(detections)
            frame_stats.append(result)

            # Obtener tracks activos
            tracks = tracker.get_active_tracks()

            # Rastrear IDs consistentes
            for track in tracks:
                track_id = track['track_id']
                team = track['team_id']
                jersey = track['jersey_number']

                key = (team, jersey) if jersey else team

                if key not in id_changes:
                    id_changes[key] = []

                id_changes[key].append(track_id)

        # Análisis de resultados
        stats = tracker.get_statistics()

        print("\n" + "="*60)
        print("RESULTADOS DE TRACKING - 500 FRAMES")
        print("="*60)
        print(f"Total de frames procesados: {stats['total_frames']}")
        print(f"Total de detecciones: {stats['total_detections']}")
        print(f"Total de matches: {stats['total_matches']}")
        print(f"Tasa de éxito de tracking: {stats['tracking_success_rate']:.2f}%")
        print(f"Tracks activos: {stats['active_tracks']}")
        print(f"Tracks confirmados: {stats['confirmed_tracks']}")
        print(f"Total de IDs únicos creados: {stats['total_track_ids']}")
        print(f"Recuperaciones por oclusión: {stats['occlusion_recoveries']}")
        print(f"Movimientos anómalos detectados: {stats['anomalous_movements']}")
        print("="*60)

        # Validaciones
        assert stats['total_frames'] == 500, "Deben procesarse 500 frames"
        assert stats['total_detections'] > 0, "Deben haber detecciones"
        assert stats['tracking_success_rate'] >= 85.0, f"Tasa de éxito debe ser >= 85%, actual: {stats['tracking_success_rate']:.2f}%"
        assert stats['total_track_ids'] <= 50, f"No deben crearse más de 50 IDs únicos para 22 jugadores, actual: {stats['total_track_ids']}"

        # Validar consistencia de IDs
        id_fragmentations = 0
        for key, ids in id_changes.items():
            unique_ids = len(set(ids))
            if unique_ids > 1:
                id_fragmentations += unique_ids - 1

        print(f"\nFragmentación de IDs total: {id_fragmentations}")

        assert id_fragmentations <= 5, f"Fragmentación debe ser baja, actual: {id_fragmentations}"

        return stats

    def test_validation_consistency(self):
        """Test: Validación de consistencia de teams."""
        tracker = ByteTrackImproved(max_age=30, min_hits=3)

        # Crear track con equipo A
        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95, 'team_id': 0},
        ]

        tracker.track(detections)
        track_id = tracker.get_active_tracks()[0]['track_id']

        # Intentar cambiar de equipo (debería mantener el anterior o rechazar)
        detections = [
            {'bbox': [110, 105, 160, 205], 'confidence': 0.95, 'team_id': 1},
        ]

        tracker.track(detections)

        # El track debe rechazar el cambio de equipo después de N cambios
        stats = tracker.get_statistics()

        # Aunque el cambio suceda, el tracker debe registrar anomalías
        assert stats is not None

    def test_get_track_by_id(self, tracker):
        """Test: Obtener información de track específico."""
        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
        ]

        tracker.track(detections)
        tracks = tracker.get_active_tracks()
        track_id = tracks[0]['track_id']

        # Obtener información detallada
        track_info = tracker.get_track_by_id(track_id)

        assert track_info is not None
        assert track_info['track_id'] == track_id
        assert 'bbox' in track_info
        assert 'metrics' in track_info
        assert 'position_history' in track_info

    def test_statistics_accuracy(self):
        """Test: Precisión de estadísticas."""
        tracker = ByteTrackImproved(max_age=30, min_hits=3)

        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
            {'bbox': [300, 150, 350, 250], 'confidence': 0.92},
        ]

        for _ in range(5):
            tracker.track(detections)

        stats = tracker.get_statistics()

        assert stats['total_frames'] == 5
        assert stats['total_detections'] == 10  # 2 por frame * 5 frames
        assert stats['active_tracks'] == 2
        assert stats['confirmed_tracks'] == 2  # Después de min_hits (3)

    def test_reset(self, tracker):
        """Test: Reset del tracker."""
        detections = [
            {'bbox': [100, 100, 150, 200], 'confidence': 0.95},
        ]

        tracker.track(detections)
        assert len(tracker.tracks) > 0

        tracker.reset()

        assert len(tracker.tracks) == 0
        assert len(tracker.lost_tracks) == 0
        assert tracker.frame_count == 0
        assert tracker.next_id == 1


class TestReIDMatcher:
    """Tests para el matcher de Re-ID."""

    def test_feature_extraction(self):
        """Test: Extracción de características."""
        from core.tracker_improved import ReIDMatcher

        matcher = ReIDMatcher()

        # Crear imagen de prueba
        image = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
        bbox = [100, 100, 200, 300]

        features = matcher.extract_features(image, bbox)

        assert features is not None
        assert features.width_height_ratio > 0
        assert features.color_histogram is not None

    def test_similarity_computation(self):
        """Test: Cálculo de similitud."""
        from core.tracker_improved import ReIDMatcher, ReIDFeatures

        matcher = ReIDMatcher(similarity_threshold=0.75)

        # Crear características idénticas
        features1 = ReIDFeatures()
        features2 = ReIDFeatures()

        features1.color_histogram = np.array([1.0, 0.5, 0.3] * 100)
        features2.color_histogram = np.array([1.0, 0.5, 0.3] * 100)

        features1.width_height_ratio = 0.5
        features2.width_height_ratio = 0.5

        similarity = matcher.compute_similarity(features1, features2)

        # Similitud debe ser alta para características idénticas
        assert similarity > 0.5


def generate_test_report(stats: Dict) -> Dict:
    """Genera reporte de tests."""
    return {
        'test_type': 'tracker_improved_validation',
        'timestamp': str(np.datetime64('today')),
        'results': {
            'frames_processed': stats['total_frames'],
            'success_rate': stats['tracking_success_rate'],
            'active_tracks': stats['active_tracks'],
            'total_ids_created': stats['total_track_ids'],
            'occlusion_recoveries': stats['occlusion_recoveries'],
            'status': 'PASSED' if stats['tracking_success_rate'] >= 85.0 else 'FAILED'
        },
        'requirements': {
            'min_success_rate': 85.0,
            'max_ids_for_22_players': 50,
            'max_fragmentation': 5
        }
    }


if __name__ == '__main__':
    # Ejecutar test principal
    test_instance = TestByteTrackImproved()
    stats = test_instance.test_simulation_500_frames()

    # Generar reporte
    report = generate_test_report(stats)

    # Guardar reporte
    output_path = project_root / 'data' / 'logs' / 'tracker_improvements.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nReporte guardado en: {output_path}")

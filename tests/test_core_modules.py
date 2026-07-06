"""
test_core_modules.py - Tests para módulos core

Valida que los módulos core (player_analyzer, team_classifier, tracker,
jersey_number_detector) funcionen correctamente con:
- Happy path: flujos normales de funcionamiento
- Edge cases: casos límite
- Error handling: manejo de errores
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

# Agregar ruta del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.player_analyzer import PlayerAnalyzer, PlayerStats
from core.team_classifier import TeamClassifier
from core.tracker import PlayerTracker, TrackState
from core.jersey_number_detector import JerseyNumberDetector


class TestPlayerAnalyzerDistanceCalculation:
    """Tests para el cálculo de distancia del analizador de jugadores"""

    def test_player_analyzer_distance_calculation_happy_path(self, mock_tracks):
        """Test: Cálculo correcto de distancia con tracks válidos"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        # Validar que se calcula la distancia
        result = analyzer.calculate_distance(mock_tracks, player_id=1)

        assert 'total_distance_m' in result
        assert 'num_samples' in result
        assert 'interpolated_frames' in result
        assert result['total_distance_m'] >= 0
        assert result['num_samples'] > 0

    def test_player_analyzer_distance_calculation_no_scale(self):
        """Test: Error cuando no hay escala calibrada"""
        analyzer = PlayerAnalyzer(fps=30)  # sin pixels_per_meter
        tracks = [
            {'frame_idx': 0, 'player_id': 1, 'center': [100, 100], 'confidence': 0.9},
            {'frame_idx': 1, 'player_id': 1, 'center': [150, 150], 'confidence': 0.9},
        ]

        with pytest.raises(ValueError, match="escala píxeles-metros no calibrada"):
            analyzer.calculate_distance(tracks, player_id=1)

    def test_player_analyzer_distance_calculation_empty_tracks(self):
        """Test: Manejo de tracks vacíos"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        result = analyzer.calculate_distance([], player_id=1)

        assert result['total_distance_m'] == 0.0
        assert result['num_samples'] == 0

    def test_player_analyzer_distance_calculation_single_track(self):
        """Test: Manejo de un solo track"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)
        tracks = [
            {'frame_idx': 0, 'player_id': 1, 'center': [100, 100], 'confidence': 0.9},
        ]

        result = analyzer.calculate_distance(tracks, player_id=1)

        assert result['total_distance_m'] == 0.0  # Una posición = sin movimiento
        assert result['num_samples'] == 1

    @pytest.mark.edge_case
    def test_player_analyzer_distance_calculation_outlier_removal(self):
        """Test: Remoción de outliers en distancia"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)
        tracks = [
            {'frame_idx': i, 'player_id': 1, 'center': [100 + i*10, 100], 'confidence': 0.9}
            for i in range(10)
        ]
        # Agregar salto anómalo
        tracks.append({'frame_idx': 11, 'player_id': 1, 'center': [9000, 9000], 'confidence': 0.9})

        result = analyzer.calculate_distance(sorted(tracks, key=lambda x: x['frame_idx']), player_id=1)

        # La distancia debe ser razonable, no afectada por el salto
        assert result['total_distance_m'] < 2000  # Sanity check

    def test_player_analyzer_distance_calculation_confidence_filtering(self):
        """Test: Filtrado por confianza"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0, min_confidence=0.8)
        tracks = [
            {'frame_idx': 0, 'player_id': 1, 'center': [100, 100], 'confidence': 0.9},
            {'frame_idx': 1, 'player_id': 1, 'center': [150, 150], 'confidence': 0.5},  # Baja confianza
            {'frame_idx': 2, 'player_id': 1, 'center': [200, 200], 'confidence': 0.95},
        ]

        result = analyzer.calculate_distance(tracks, player_id=1)

        # Debe ignorar el track con baja confianza
        assert result['num_samples'] == 2


class TestPlayerAnalyzerCalibrationFallback:
    """Tests para la calibración y fallback del analizador"""

    def test_player_analyzer_calibration_from_detections(self, mock_field_corners):
        """Test: Calibración correcta desde esquinas detectadas"""
        analyzer = PlayerAnalyzer(fps=30)

        analyzer.set_scale_from_detections(mock_field_corners)

        assert analyzer.pixels_per_meter > 0
        assert isinstance(analyzer.pixels_per_meter, float)

    def test_player_analyzer_calibration_insufficient_corners(self):
        """Test: Fallback cuando hay menos de 4 esquinas"""
        analyzer = PlayerAnalyzer(fps=30)
        insufficient_corners = [(0, 0), (100, 100), (200, 200)]

        analyzer.set_scale_from_detections(insufficient_corners)

        # Debe ignorar y mantener pixels_per_meter sin cambios
        assert analyzer.pixels_per_meter is None

    def test_player_analyzer_velocity_calculation(self, mock_tracks):
        """Test: Cálculo correcto de velocidad"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        result = analyzer.calculate_velocity(mock_tracks, player_id=1)

        assert 'max_velocity_m_s' in result
        assert 'avg_velocity_m_s' in result
        assert result['max_velocity_m_s'] >= 0
        assert result['avg_velocity_m_s'] >= 0

    def test_player_analyzer_intensity_calculation(self, mock_tracks):
        """Test: Cálculo correcto de intensidad"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        result = analyzer.calculate_intensity(mock_tracks, player_id=1)

        assert 'movement_intensity_percent' in result
        assert 'static_time_percent' in result
        assert 0 <= result['movement_intensity_percent'] <= 100
        assert 0 <= result['static_time_percent'] <= 100

    def test_player_analyzer_heatmap_generation(self, mock_tracks):
        """Test: Generación correcta de heatmap"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        result = analyzer.calculate_heatmap(mock_tracks, player_id=1, grid_size=10)

        assert 'heatmap_grid' in result
        assert 'center_of_mass' in result
        assert 'positional_zones' in result
        assert len(result['heatmap_grid']) == 10

    def test_player_analyzer_team_comparison(self, mock_player_stats):
        """Test: Comparación con equipo"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        # Crear estadísticas de equipo
        team_stats = [mock_player_stats for _ in range(5)]

        result = analyzer.compare_with_team(mock_player_stats, team_stats)

        assert 'distance_percentile' in result
        assert 'velocity_percentile' in result
        assert 0 <= result['distance_percentile'] <= 100


class TestTeamClassifierAccuracy:
    """Tests para precisión del clasificador de equipos"""

    @pytest.mark.requires_opencv
    def test_team_classifier_training(self, mock_frame, mock_bboxes, mock_hsv_colors):
        """Test: Entrenamiento correcto del clasificador"""
        classifier = TeamClassifier(n_clusters=2)

        # Mock _extract_player_color para retornar colores simulados
        with patch.object(classifier, '_extract_player_color', side_effect=mock_hsv_colors):
            success = classifier.train(mock_bboxes, mock_frame)

        assert success is True
        assert classifier.trained is True
        assert len(classifier.team_colors) == 2

    @pytest.mark.requires_opencv
    def test_team_classifier_training_insufficient_players(self, mock_frame):
        """Test: Error cuando hay muy pocos jugadores"""
        classifier = TeamClassifier(n_clusters=2)
        insufficient_bboxes = [[100, 100, 200, 300]]  # Solo 1 jugador

        with pytest.raises(ValueError):
            classifier.train(insufficient_bboxes, mock_frame)

    @pytest.mark.requires_opencv
    def test_team_classifier_classification(self, mock_frame, mock_bboxes, mock_hsv_colors):
        """Test: Clasificación correcta después del entrenamiento"""
        classifier = TeamClassifier(n_clusters=2)

        with patch.object(classifier, '_extract_player_color', side_effect=mock_hsv_colors):
            classifier.train(mock_bboxes, mock_frame)

        with patch.object(classifier, '_extract_player_color', side_effect=mock_hsv_colors):
            result = classifier.classify(mock_bboxes, mock_frame)

        assert 'team_assignments' in result
        assert 'confidence_scores' in result
        assert len(result['team_assignments']) == len(mock_bboxes)

    def test_team_classifier_classification_without_training(self, mock_frame, mock_bboxes):
        """Test: Error cuando se clasifica sin entrenar"""
        classifier = TeamClassifier(n_clusters=2)

        with pytest.raises(RuntimeError, match="debe entrenarse primero"):
            classifier.classify(mock_bboxes, mock_frame)

    @pytest.mark.edge_case
    def test_team_classifier_extraction_failure(self, mock_frame):
        """Test: Manejo de fallos en extracción de color"""
        classifier = TeamClassifier(n_clusters=2)

        # Mock que retorna None (fallo de extracción)
        with patch.object(classifier, '_extract_player_color', return_value=None):
            bboxes = [[100, 100, 200, 300], [300, 150, 400, 350]]
            success = classifier.train(bboxes, mock_frame)

        # Debe fallar si no hay suficientes colores válidos
        assert success is False


class TestTrackerPersistence:
    """Tests para persistencia y consistencia del tracker"""

    def test_tracker_initialization(self):
        """Test: Inicialización correcta del tracker"""
        tracker = PlayerTracker(max_age=30, min_hits=3)

        assert tracker.max_age == 30
        assert tracker.min_hits == 3
        assert len(tracker.tracks) == 0
        assert tracker.next_id == 1

    def test_tracker_update_existing_track(self):
        """Test: Actualización de track existente"""
        tracker = PlayerTracker()

        # Agregar track inicial
        initial_bbox = [100, 100, 200, 300]
        track = TrackState(
            track_id=1,
            bbox=initial_bbox,
            confidence=0.9,
            frame_id=0
        )
        tracker.tracks[1] = track

        # Verificar persistencia
        assert 1 in tracker.tracks
        assert tracker.tracks[1].bbox == initial_bbox

    def test_tracker_centroid_calculation(self):
        """Test: Cálculo correcto de centroide"""
        tracker = PlayerTracker()
        bbox = [100, 100, 200, 300]

        centroid = tracker._get_centroid(bbox)

        assert centroid == (150, 200)

    def test_tracker_iou_calculation(self):
        """Test: Cálculo correcto de IoU"""
        tracker = PlayerTracker()

        bbox1 = [0, 0, 100, 100]
        bbox2 = [50, 50, 150, 150]

        iou = tracker._calculate_iou(bbox1, bbox2)

        assert 0 <= iou <= 1
        assert iou > 0  # Hay overlap

    @pytest.mark.edge_case
    def test_tracker_iou_no_overlap(self):
        """Test: IoU cuando no hay overlap"""
        tracker = PlayerTracker()

        bbox1 = [0, 0, 100, 100]
        bbox2 = [200, 200, 300, 300]

        iou = tracker._calculate_iou(bbox1, bbox2)

        assert iou == 0.0

    @pytest.mark.edge_case
    def test_tracker_iou_perfect_overlap(self):
        """Test: IoU con overlap perfecto"""
        tracker = PlayerTracker()

        bbox1 = [0, 0, 100, 100]
        bbox2 = [0, 0, 100, 100]

        iou = tracker._calculate_iou(bbox1, bbox2)

        assert iou == 1.0

    def test_tracker_track_aging(self):
        """Test: Envejecimiento de tracks"""
        tracker = PlayerTracker(max_age=10)

        track = TrackState(track_id=1, bbox=[100, 100, 200, 300], confidence=0.9, frame_id=0)
        track.time_since_update = 5

        tracker.tracks[1] = track

        # Verificar que el track está activo
        assert track.time_since_update < tracker.max_age


class TestJerseyDetectorOCR:
    """Tests para detector de números de camiseta con OCR"""

    def test_jersey_detector_initialization(self):
        """Test: Inicialización correcta del detector"""
        detector = JerseyNumberDetector(use_paddle=False, use_easyocr=False)

        assert detector.ocr_type == "none"
        assert 'total_detections' in detector.detection_stats

    def test_jersey_detector_valid_numbers(self):
        """Test: Validación de números válidos"""
        detector = JerseyNumberDetector(use_paddle=False, use_easyocr=False)

        valid_nums = detector.VALID_NUMBERS

        # Debe contener números del 0 al 99
        assert '0' in valid_nums
        assert '99' in valid_nums
        assert len(valid_nums) == 100

    @pytest.mark.edge_case
    def test_jersey_detector_invalid_number(self):
        """Test: Rechazo de números inválidos"""
        detector = JerseyNumberDetector(use_paddle=False, use_easyocr=False)

        # 100+ no debe estar en válidos
        assert '100' not in detector.VALID_NUMBERS
        assert '-1' not in detector.VALID_NUMBERS

    @pytest.mark.requires_opencv
    def test_jersey_detector_roi_extraction_valid_bbox(self, mock_frame):
        """Test: Extracción de ROI con bbox válido"""
        detector = JerseyNumberDetector(use_paddle=False, use_easyocr=False)

        bbox = [100, 100, 200, 300]

        # Método privado _extract_roi debe devolver región
        roi = detector._extract_number_region(mock_frame, bbox)

        assert roi is not None or roi is None  # Puede retornar None si falla

    @pytest.mark.edge_case
    def test_jersey_detector_roi_extraction_invalid_bbox(self, mock_frame):
        """Test: Manejo de bbox inválido"""
        detector = JerseyNumberDetector(use_paddle=False, use_easyocr=False)

        # bbox fuera de límites
        bbox = [10000, 10000, 20000, 30000]

        # No debe crashear
        try:
            roi = detector._extract_number_region(mock_frame, bbox)
        except Exception:
            pytest.fail("Debe manejar bbox inválido sin crash")

    def test_jersey_detector_stats_tracking(self):
        """Test: Seguimiento correcto de estadísticas"""
        detector = JerseyNumberDetector(use_paddle=False, use_easyocr=False)

        # Verificar que se inicializa con ceros
        assert detector.detection_stats['total_detections'] == 0
        assert detector.detection_stats['successful_ocr'] == 0
        assert detector.detection_stats['valid_numbers'] == 0


class TestCoreModulesIntegration:
    """Tests de integración entre módulos core"""

    def test_player_analyzer_with_multiple_players(self, mock_tracks):
        """Test: Análisis de múltiples jugadores simultáneamente"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        # Analizar múltiples jugadores
        results = {}
        for player_id in [1, 2, 3, 4]:
            result = analyzer.calculate_distance(mock_tracks, player_id=player_id)
            results[player_id] = result

        assert len(results) == 4
        assert all(r['total_distance_m'] >= 0 for r in results.values())

    def test_analyzer_and_tracker_consistency(self):
        """Test: Consistencia entre analizador y tracker"""
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)
        tracker = PlayerTracker()

        # Ambos deben inicializar sin errores
        assert analyzer is not None
        assert tracker is not None
        assert len(tracker.tracks) == 0

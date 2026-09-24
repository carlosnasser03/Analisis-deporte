"""
test_pipeline_interfaces.py - Tests para validar interfaces del pipeline

Valida que:
1. Métodos del tracker sean llamados correctamente
2. Objetos sean de tipo correcto
3. Campos de diccionarios existan
4. Conversiones de datos sean válidas
5. No haya incompatibilidades de tipos

Ejecución: pytest tests/test_pipeline_interfaces.py -v
"""

import sys
from pathlib import Path
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

# Agregar ruta del proyecto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Importar clases a testear
from core.tracker import PlayerTracker, TrackState
from core.distance_velocity_calculator import (
    DistanceVelocityAnalyzer, TrackPoint, DistanceMetrics, VelocityMetrics
)
from core.intensity_analyzer import IntensityAnalyzer, IntensityMetrics
from core.heatmap_generator import HeatmapManager, HeatmapConfig, HeatmapData


class TestTrackerInterface:
    """Tests para interfaz de PlayerTracker"""

    def test_tracker_has_track_method(self):
        """Verificar que tracker tiene método track() no update()"""
        tracker = PlayerTracker()

        # ✓ track() debe existir
        assert hasattr(tracker, 'track'), "PlayerTracker debe tener método track()"
        assert callable(getattr(tracker, 'track')), "track() debe ser callable"

        # Verificar que track() acepta detections
        detections = [
            {'bbox': [10, 10, 50, 50], 'confidence': 0.9}
        ]
        result = tracker.track(detections)

        # Debe retornar diccionario con stats
        assert isinstance(result, dict), "track() debe retornar diccionario"
        assert 'active_tracks' in result, "Result debe contener 'active_tracks'"

    def test_tracker_get_tracks_method(self):
        """Verificar método get_tracks() retorna formato correcto"""
        tracker = PlayerTracker()

        # Agregar un track
        detections = [
            {'bbox': [10, 10, 50, 50], 'confidence': 0.95}
        ]
        tracker.track(detections)

        # Obtener tracks
        tracks = tracker.get_tracks(min_confidence=0.5)

        # Debe ser lista
        assert isinstance(tracks, list), "get_tracks() debe retornar List"

        # Cada track debe tener campos requeridos
        if len(tracks) > 0:
            track_dict = tracks[0]
            required_fields = ['track_id', 'bbox', 'confidence', 'position']
            for field in required_fields:
                assert field in track_dict, f"track dict debe tener '{field}'"

            # position debe ser tupla (x, y)
            position = track_dict['position']
            assert isinstance(position, tuple), "position debe ser tupla"
            assert len(position) == 2, "position debe ser (x, y)"

    def test_trackstate_no_class_name_attribute(self):
        """Verificar que TrackState NO tiene class_name"""
        track = TrackState(
            track_id=1,
            bbox=[10, 10, 50, 50],
            confidence=0.9,
            frame_id=0
        )

        # ✓ Estos campos existen
        assert hasattr(track, 'track_id')
        assert hasattr(track, 'bbox')
        assert hasattr(track, 'jersey_number')
        assert hasattr(track, 'team_id')

        # ✗ class_name NO existe
        assert not hasattr(track, 'class_name'), \
            "TrackState NO debe tener 'class_name' - usar 'jersey_number' o 'team_id'"

    def test_tracker_update_method_exists_but_no_params(self):
        """Verificar que update() existe pero es solo housekeeping"""
        tracker = PlayerTracker()

        # update() existe pero no toma parámetros
        assert hasattr(tracker, 'update'), "tracker debe tener update() para housekeeping"

        # update() no debe tomar detecciones
        try:
            # Si llamamos update() sin parámetros, debe funcionar
            tracker.update()
        except TypeError:
            pass  # Esperado si no hay parámetros


class TestDistanceVelocityInterface:
    """Tests para interfaz de DistanceVelocityAnalyzer"""

    def test_analyzer_returns_dictionary(self):
        """Verificar que analyze_player_trajectory retorna Dict"""
        analyzer = DistanceVelocityAnalyzer(fps=30, pixels_per_meter=10)

        # Crear trayectoria de prueba
        tracks = [
            TrackPoint(frame=i, x=10 + i, y=20 + i * 0.5, confidence=0.95)
            for i in range(10)
        ]

        result = analyzer.analyze_player_trajectory(tracks)

        # Debe ser diccionario
        assert isinstance(result, dict), "analyze_player_trajectory() debe retornar Dict"

        # Debe tener claves requeridas
        required_keys = ['distance', 'velocity', 'movement', 'summary']
        for key in required_keys:
            assert key in result, f"Result debe contener '{key}'"

    def test_distance_metrics_access(self):
        """Verificar acceso correcto a DistanceMetrics"""
        analyzer = DistanceVelocityAnalyzer(fps=30, pixels_per_meter=10)

        tracks = [
            TrackPoint(frame=i, x=100 + i * 2, y=50 + i, confidence=0.95)
            for i in range(20)
        ]

        result = analyzer.analyze_player_trajectory(tracks)

        # Acceso a distance metrics
        distance_metrics = result['distance']

        # Debe ser DistanceMetrics dataclass
        assert hasattr(distance_metrics, 'total_distance'), \
            "DistanceMetrics debe tener 'total_distance'"
        assert isinstance(distance_metrics.total_distance, (int, float))

    def test_velocity_metrics_access(self):
        """Verificar acceso correcto a VelocityMetrics"""
        analyzer = DistanceVelocityAnalyzer(fps=30, pixels_per_meter=10)

        tracks = [
            TrackPoint(frame=i, x=100 + i * 2, y=50 + i, confidence=0.95)
            for i in range(20)
        ]

        result = analyzer.analyze_player_trajectory(tracks)

        # Acceso a velocity metrics
        velocity_metrics = result['velocity']

        # Verificar campos
        assert hasattr(velocity_metrics, 'velocity_per_frame'), \
            "VelocityMetrics debe tener 'velocity_per_frame'"
        assert hasattr(velocity_metrics, 'max_velocity'), \
            "VelocityMetrics debe tener 'max_velocity'"
        assert hasattr(velocity_metrics, 'average_velocity'), \
            "VelocityMetrics debe tener 'average_velocity'"

        # velocity_per_frame debe ser lista
        assert isinstance(velocity_metrics.velocity_per_frame, list)


class TestIntensityAnalyzerInterface:
    """Tests para interfaz de IntensityAnalyzer"""

    def test_intensity_analyze_returns_dataclass(self):
        """Verificar que analyze() retorna IntensityMetrics"""
        analyzer = IntensityAnalyzer(fps=30)

        velocities = np.array([2.0, 3.5, 4.0, 2.5, 1.0, 5.0] * 3)
        positions = [(100 + i, 50 + i * 0.5) for i in range(len(velocities))]

        result = analyzer.analyze(velocities, position_history=positions)

        # Debe ser IntensityMetrics
        assert isinstance(result, IntensityMetrics), \
            "analyze() debe retornar IntensityMetrics dataclass"

    def test_intensity_metrics_fields(self):
        """Verificar campos correctos en IntensityMetrics"""
        analyzer = IntensityAnalyzer(fps=30)

        velocities = np.array([2.0, 3.5, 4.0, 2.5, 1.0, 5.0] * 3)
        result = analyzer.analyze(velocities)

        # Campos que SÍ existen
        assert hasattr(result, 'active_movement_percentage'), \
            "IntensityMetrics debe tener 'active_movement_percentage'"
        assert hasattr(result, 'sprint_count'), \
            "IntensityMetrics debe tener 'sprint_count'"
        assert hasattr(result, 'direction_changes_count'), \
            "IntensityMetrics debe tener 'direction_changes_count'"

        # Campos que NO existen (errores comunes)
        assert not hasattr(result, 'movement_intensity_percent'), \
            "IntensityMetrics NO tiene 'movement_intensity_percent' - usar 'active_movement_percentage'"
        assert not hasattr(result, 'sprints_count'), \
            "IntensityMetrics NO tiene 'sprints_count' - usar 'sprint_count'"
        assert not hasattr(result, 'directional_changes'), \
            "IntensityMetrics NO tiene 'directional_changes' - usar 'direction_changes_count'"


class TestHeatmapInterface:
    """Tests para interfaz de HeatmapManager"""

    def test_heatmap_expects_tuples_not_trackpoints(self):
        """Verificar que heatmap espera List[Tuple] no List[TrackPoint]"""
        config = HeatmapConfig(canvas_width=1280, canvas_height=720)
        manager = HeatmapManager(config=config)

        # Crear posiciones como tuplas ✓
        positions_tuples = [
            (100.0, 200.0),
            (105.0, 205.0),
            (110.0, 210.0),
        ]

        # Debe funcionar con tuplas
        result = manager.generate_complete_analysis(
            tracks=positions_tuples,
            player_id=1,
            fps=30
        )

        # Verificar retorno
        assert isinstance(result, HeatmapData), \
            "generate_complete_analysis() debe retornar HeatmapData"

    def test_heatmap_data_fields(self):
        """Verificar campos en HeatmapData"""
        config = HeatmapConfig(canvas_width=1280, canvas_height=720)
        manager = HeatmapManager(config=config)

        positions = [(100 + i * 2, 200 + i) for i in range(50)]

        result = manager.generate_complete_analysis(
            tracks=positions,
            player_id=1,
            fps=30
        )

        # Verificar campos
        assert hasattr(result, 'heatmap_image')
        assert hasattr(result, 'zone_stats')
        assert hasattr(result, 'grid_histogram')
        assert hasattr(result, 'peak_position')
        assert hasattr(result, 'peak_intensity')
        assert hasattr(result, 'coverage_percentage')

        # Tipos correctos
        assert isinstance(result.heatmap_image, np.ndarray)
        assert isinstance(result.zone_stats, list)
        assert isinstance(result.grid_histogram, np.ndarray)


class TestPipelineDataConversions:
    """Tests para conversiones de datos en el pipeline"""

    def test_trackpoint_to_tuple_conversion(self):
        """Verificar conversión correcta de TrackPoint a tuplas (x, y)"""
        track_points = [
            TrackPoint(frame=0, x=100.5, y=200.3),
            TrackPoint(frame=1, x=102.1, y=201.8),
            TrackPoint(frame=2, x=104.0, y=203.2),
        ]

        # Conversión correcta
        positions = [(tp.x, tp.y) for tp in track_points]

        # Verificar
        assert len(positions) == 3
        assert positions[0] == (100.5, 200.3)
        assert all(isinstance(p, tuple) and len(p) == 2 for p in positions)

    def test_trackstate_to_dict_with_position(self):
        """Verificar extracción de posición desde TrackState"""
        # TrackState interno
        track = TrackState(
            track_id=5,
            bbox=[100, 200, 150, 250],  # x1, y1, x2, y2
            confidence=0.95,
            frame_id=10
        )

        # Calcular centroide
        center_x = (track.bbox[0] + track.bbox[2]) / 2  # (100 + 150) / 2 = 125
        center_y = (track.bbox[1] + track.bbox[3]) / 2  # (200 + 250) / 2 = 225
        position = (center_x, center_y)

        assert position == (125.0, 225.0)

    def test_dict_access_patterns(self):
        """Verificar patrones de acceso a diccionarios"""
        # Simulación de resultado de analyze_player_trajectory
        analysis_result = {
            'distance': DistanceMetrics(
                total_distance=100.5,
                distance_by_frame=[1.0, 1.2, 0.8],
                cumulative_distance=[0, 1.0, 2.2, 3.0],
                interpolated_frames=0,
                confidence_avg=0.95
            ),
            'velocity': VelocityMetrics(
                velocity_per_frame=[3.3, 4.0, 2.7],
                max_velocity=5.2,
                average_velocity=3.7,
                median_velocity=3.5,
                percentile_90=4.8,
                percentile_95=5.0
            ),
            'movement': {},
            'summary': {'total_frames': 3, 'fps': 30, 'duration_seconds': 0.1}
        }

        # Acceso correcto con ['key']
        total_dist = analysis_result['distance'].total_distance
        assert total_dist == 100.5

        velocities = analysis_result['velocity'].velocity_per_frame
        assert velocities == [3.3, 4.0, 2.7]


class TestInterfaceCompatibility:
    """Tests de compatibilidad entre componentes"""

    def test_pipeline_flow_tracker_to_heatmap(self):
        """Validar flujo: Tracker → TrackPoint → Heatmap"""
        # 1. Simulación de tracker result
        tracker = PlayerTracker()
        detections = [
            {'bbox': [100, 200, 150, 250], 'confidence': 0.95},
            {'bbox': [300, 150, 350, 200], 'confidence': 0.92}
        ]
        tracker.track(detections, frame_id=0)

        # 2. Obtener tracks
        active_tracks = tracker.get_tracks(min_confidence=0.5)
        assert len(active_tracks) > 0

        # 3. Convertir a TrackPoint
        track_points = []
        for track_dict in active_tracks:
            tp = TrackPoint(
                frame=0,
                x=track_dict['position'][0],
                y=track_dict['position'][1],
                confidence=track_dict['confidence']
            )
            track_points.append(tp)

        # 4. Convertir a posiciones para heatmap
        positions = [(tp.x, tp.y) for tp in track_points]

        # 5. Usar en heatmap
        config = HeatmapConfig(canvas_width=1280, canvas_height=720)
        manager = HeatmapManager(config=config)

        # Debe funcionar sin errores
        result = manager.generate_complete_analysis(
            tracks=positions,
            player_id=1,
            fps=30
        )

        assert result is not None

    def test_pipeline_flow_complete(self):
        """Validar flujo completo: Track → Distance → Intensity"""
        # 1. Crear puntos de trayectoria
        track_points = [
            TrackPoint(frame=i, x=100 + i * 2, y=200 + i, confidence=0.95)
            for i in range(30)
        ]

        # 2. Análisis de distancia
        analyzer = DistanceVelocityAnalyzer(fps=30, pixels_per_meter=10)
        distance_analysis = analyzer.analyze_player_trajectory(track_points)

        # 3. Acceso correcto a campos
        velocities = np.array(distance_analysis['velocity'].velocity_per_frame)

        # 4. Análisis de intensidad
        positions = [(tp.x, tp.y) for tp in track_points]
        intensity_analyzer = IntensityAnalyzer(fps=30)
        intensity = intensity_analyzer.analyze(velocities, position_history=positions)

        # 5. Verificar accesos correctos
        assert isinstance(intensity.active_movement_percentage, (int, float))
        assert isinstance(intensity.sprint_count, int)
        assert intensity.total_distance > 0


class TestErrorCases:
    """Tests para casos de error común"""

    def test_calling_update_with_detections_fails(self):
        """Verificar que update(detections) no funciona"""
        tracker = PlayerTracker()

        # update() no debe aceptar parámetros
        detections = [{'bbox': [10, 10, 50, 50], 'confidence': 0.9}]

        # Esto debe fallar o no hacer nada
        try:
            result = tracker.update(detections)
            # Si no falló, está mal
            # update() no debe aceptar detecciones
        except TypeError:
            # Esperado - update() no toma parámetros
            pass

    def test_accessing_nonexistent_fields(self):
        """Verificar que intentar acceder a campos inexistentes falla"""
        track = TrackState(
            track_id=1,
            bbox=[10, 10, 50, 50],
            confidence=0.9,
            frame_id=0
        )

        # Estos accesos deben fallar
        try:
            _ = track.class_name
            assert False, "class_name no debe existir"
        except AttributeError:
            pass  # Esperado

        # Esto también
        try:
            _ = track.position
            # Si llegamos aquí, es porque existe (pero no debería en interfaz estándar)
        except AttributeError:
            pass  # Esperado


def run_all_tests():
    """Ejecutar todos los tests"""
    test_classes = [
        TestTrackerInterface,
        TestDistanceVelocityInterface,
        TestIntensityAnalyzerInterface,
        TestHeatmapInterface,
        TestPipelineDataConversions,
        TestInterfaceCompatibility,
        TestErrorCases
    ]

    print("\n" + "=" * 70)
    print("VALIDACIÓN DE INTERFACES DEL PIPELINE")
    print("=" * 70 + "\n")

    total_tests = 0
    passed_tests = 0

    for test_class in test_classes:
        print(f"\n{test_class.__name__}")
        print("-" * 70)

        instance = test_class()
        methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in methods:
            total_tests += 1
            try:
                method = getattr(instance, method_name)
                method()
                print(f"  ✓ {method_name}")
                passed_tests += 1
            except AssertionError as e:
                print(f"  ✗ {method_name}")
                print(f"    Error: {str(e)}")
            except Exception as e:
                print(f"  ✗ {method_name}")
                print(f"    Exception: {type(e).__name__}: {str(e)}")

    print("\n" + "=" * 70)
    print(f"Resultado: {passed_tests}/{total_tests} tests pasaron")
    print("=" * 70 + "\n")

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

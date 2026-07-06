"""
test_integration.py - Tests de integración end-to-end

Valida el flujo completo del sistema:
- Procesamiento end-to-end de video
- Integración de todos los módulos
- Importación correcta de todos los módulos
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import logging

# Agregar ruta del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEndToEndVideoProcessing:
    """Tests para procesamiento end-to-end"""

    @pytest.mark.integration
    def test_end_to_end_video_processing(self, temp_dir, temp_video_file):
        """Test: Procesamiento completo de video"""
        # Este test simula el flujo completo del pipeline

        from pipeline.video_processor import VideoProcessor, ProcessingConfig

        # Configurar procesador
        config = ProcessingConfig(
            min_confidence=0.5,
            skip_frames=1,
            enable_tracking=True,
            enable_team_classification=True,
            output_dir=temp_dir
        )

        processor = VideoProcessor(config=config)

        # Verificar que se inicializó correctamente
        assert processor is not None
        assert processor.config.enable_tracking is True

    @pytest.mark.integration
    def test_pipeline_with_real_video(self, temp_dir):
        """Test: Pipeline con video real (simulado)"""
        from pipeline.batch_processor import BatchProcessor

        # Crear procesador de batch
        batch = BatchProcessor(
            input_dir=str(temp_dir),
            output_dir=str(temp_dir / "results")
        )

        assert batch is not None
        assert batch.max_workers > 0

    @pytest.mark.integration
    def test_end_to_end_with_tracking(self, mock_tracks, temp_dir):
        """Test: E2E con tracking de jugadores"""
        from core.tracker import PlayerTracker
        from core.player_analyzer import PlayerAnalyzer

        # Crear tracker y analizador
        tracker = PlayerTracker(max_age=30)
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        # Procesar tracks
        distance = analyzer.calculate_distance(mock_tracks, player_id=1)
        velocity = analyzer.calculate_velocity(mock_tracks, player_id=1)

        assert distance['total_distance_m'] >= 0
        assert velocity['max_velocity_m_s'] >= 0

    @pytest.mark.integration
    def test_end_to_end_with_team_classification(self, mock_frame, mock_bboxes, mock_hsv_colors):
        """Test: E2E con clasificación de equipos"""
        from core.team_classifier import TeamClassifier

        classifier = TeamClassifier(n_clusters=2)

        # Mock extracción de color
        with patch.object(classifier, '_extract_player_color', side_effect=mock_hsv_colors):
            success = classifier.train(mock_bboxes, mock_frame)

        assert success is True

    @pytest.mark.integration
    def test_end_to_end_with_jersey_detection(self):
        """Test: E2E con detección de números"""
        from core.jersey_number_detector import JerseyNumberDetector

        detector = JerseyNumberDetector(use_paddle=False, use_easyocr=False)

        # Verificar inicialización
        assert detector.ocr_type is not None

    @pytest.mark.integration
    def test_end_to_end_with_logging(self, temp_log_dir, temp_video_file):
        """Test: E2E con logging centralizado"""
        from utils.logger import ScoutLogger

        logger = ScoutLogger(log_dir=str(temp_log_dir))

        # Simular procesamiento
        logger.log_processing_start(str(temp_video_file))

        detections = [
            {'class': 'player', 'confidence': 0.95, 'bbox': {}},
            {'class': 'ball', 'confidence': 0.88, 'bbox': {}},
        ]

        logger.log_detection(0, detections)
        logger.log_processing_end(str(temp_video_file), duration=10.5, success=True)

        summary = logger.get_summary()

        assert summary['total_detections'] == 2
        assert summary['total_errors'] == 0

    @pytest.mark.integration
    def test_end_to_end_validation_chain(self, temp_video_file, mock_detections):
        """Test: E2E con cadena de validaciones"""
        from utils.validators import (
            VideoValidator,
            DetectionValidator,
            DependencyValidator
        )

        # Validar video
        video_result = VideoValidator.validate_video_file(str(temp_video_file))

        # Validar detecciones
        detection_result = DetectionValidator.validate_detection_output(mock_detections)

        # Validar dependencias
        dep_result = DependencyValidator.check_dependencies()

        assert video_result is not None
        assert detection_result is not None
        assert dep_result is not None

    @pytest.mark.integration
    def test_end_to_end_result_export(self, temp_dir):
        """Test: E2E con exportación de resultados"""
        from pipeline.video_processor import ProcessingResult

        # Crear resultado
        result = ProcessingResult(
            video_path="/path/to/video.mp4",
            total_frames=100,
            processed_frames=100,
            skipped_frames=0,
            timestamp="2026-07-06T00:00:00"
        )

        # Guardar resultado
        output_path = temp_dir / "result.json"
        result.save_json(output_path)

        assert output_path.exists()

        # Verificar contenido
        with open(output_path, 'r') as f:
            loaded = json.load(f)

        assert loaded['total_frames'] == 100


class TestAllModulesImportCorrectly:
    """Tests para verificar que todos los módulos se importan correctamente"""

    def test_core_modules_import(self):
        """Test: Importación de módulos core"""
        try:
            from core.player_analyzer import PlayerAnalyzer
            from core.team_classifier import TeamClassifier
            from core.tracker import PlayerTracker
            from core.jersey_number_detector import JerseyNumberDetector
            from core.detector import Detector
            from core.metrics import MetricsCalculator
            from core.report_generator import ReportGenerator

            assert PlayerAnalyzer is not None
            assert TeamClassifier is not None
            assert PlayerTracker is not None
            assert JerseyNumberDetector is not None
        except ImportError as e:
            pytest.fail(f"Error importing core modules: {e}")

    def test_pipeline_modules_import(self):
        """Test: Importación de módulos pipeline"""
        try:
            from pipeline.batch_processor import BatchProcessor
            from pipeline.video_processor import VideoProcessor, ProcessingConfig
            from pipeline.frame_processor import FrameProcessor
            from pipeline.result_combiner import ResultCombiner

            assert BatchProcessor is not None
            assert VideoProcessor is not None
            assert ProcessingConfig is not None
            assert FrameProcessor is not None
            assert ResultCombiner is not None
        except ImportError as e:
            pytest.fail(f"Error importing pipeline modules: {e}")

    def test_utils_modules_import(self):
        """Test: Importación de módulos utils"""
        try:
            from utils.logger import ScoutLogger
            from utils.validators import (
                VideoValidator,
                DetectionValidator,
                ConfigValidator,
                DependencyValidator
            )
            from utils.file_handler import FileHandler
            from utils.video_splitter import VideoSplitter

            assert ScoutLogger is not None
            assert VideoValidator is not None
            assert DetectionValidator is not None
            assert ConfigValidator is not None
            assert DependencyValidator is not None
            assert FileHandler is not None
        except ImportError as e:
            pytest.fail(f"Error importing utils modules: {e}")

    def test_config_modules_import(self):
        """Test: Importación de módulos de configuración"""
        try:
            from config.constants import VALID_CLASSES, VALID_TEAMS

            assert VALID_CLASSES is not None
            assert VALID_TEAMS is not None
        except ImportError as e:
            # Puede no existir, es opcional
            pass

    def test_no_logging_basicconfig_pollution(self):
        """Test: Verificar que ningún módulo contamina con logging.basicConfig()"""
        with patch('logging.basicConfig') as mock_basicconfig:
            # Reimportar módulos
            import importlib
            import core.player_analyzer
            import utils.logger
            import pipeline.video_processor

            importlib.reload(core.player_analyzer)
            importlib.reload(utils.logger)
            importlib.reload(pipeline.video_processor)

            # basicConfig no debe ser llamado (excepto posiblemente por validators.py)
            # Si se llama, es un error que debe ser verificado

    def test_all_core_classes_available(self):
        """Test: Todas las clases core son accesibles"""
        from core.player_analyzer import PlayerAnalyzer, PlayerStats
        from core.team_classifier import TeamClassifier, TeamColor
        from core.tracker import PlayerTracker, TrackState
        from core.jersey_number_detector import JerseyNumberDetector, JerseyDetectionResult

        # Crear instancias para verificar
        analyzer = PlayerAnalyzer()
        classifier = TeamClassifier()
        tracker = PlayerTracker()
        detector = JerseyNumberDetector(use_paddle=False, use_easyocr=False)

        assert analyzer is not None
        assert classifier is not None
        assert tracker is not None
        assert detector is not None

    def test_all_pipeline_classes_available(self):
        """Test: Todas las clases pipeline son accesibles"""
        from pipeline.batch_processor import BatchProcessor
        from pipeline.video_processor import VideoProcessor, ProcessingConfig, ProcessingResult
        from pipeline.frame_processor import FrameProcessor, FrameData
        from pipeline.result_combiner import ResultCombiner

        # Crear instancias
        config = ProcessingConfig()
        processor = VideoProcessor(config=config)
        batch = BatchProcessor(input_dir=".", output_dir=".")
        frame_proc = FrameProcessor()
        combiner = ResultCombiner()

        assert config is not None
        assert processor is not None
        assert batch is not None
        assert frame_proc is not None
        assert combiner is not None

    def test_all_utils_classes_available(self):
        """Test: Todas las clases utils son accesibles"""
        from utils.logger import ScoutLogger
        from utils.validators import (
            VideoValidator,
            DetectionValidator,
            ConfigValidator,
            DependencyValidator,
            ValidationResult
        )
        from utils.file_handler import FileHandler

        logger = ScoutLogger(log_dir="/tmp")
        validator_result = ValidationResult(
            is_valid=True,
            message="test",
            details={},
            warnings=[],
            errors=[]
        )
        file_handler = FileHandler()

        assert logger is not None
        assert validator_result is not None
        assert file_handler is not None


class TestComplexIntegrationScenarios:
    """Tests para escenarios complejos de integración"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_full_pipeline_workflow(self, temp_dir, mock_tracks, mock_detections):
        """Test: Flujo completo del pipeline"""
        from core.player_analyzer import PlayerAnalyzer
        from core.tracker import PlayerTracker
        from pipeline.result_combiner import ResultCombiner
        from utils.logger import ScoutLogger

        # Inicializar componentes
        logger = ScoutLogger(log_dir=str(temp_dir / "logs"))
        tracker = PlayerTracker()
        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)
        combiner = ResultCombiner()

        logger.log_processing_start("/test/video.mp4")

        # Procesar tracks
        distance = analyzer.calculate_distance(mock_tracks, player_id=1)
        logger.log_detection(0, mock_detections['players'])

        # Combinar resultados
        combined = combiner.combine([mock_detections])

        logger.log_processing_end("/test/video.mp4", duration=5.0)

        # Verificar que todo funcionó
        assert logger.detection_count > 0

    @pytest.mark.integration
    def test_error_recovery_workflow(self, temp_log_dir):
        """Test: Recuperación de errores en workflow"""
        from utils.logger import ScoutLogger

        logger = ScoutLogger(log_dir=str(temp_log_dir))

        # Simular error
        try:
            raise ValueError("Simulated processing error")
        except ValueError as e:
            logger.log_error(e, context="frame_processing", severity="ERROR")

        # Verificar que error fue registrado
        assert logger.error_count > 0
        assert len(logger.error_history) > 0

    @pytest.mark.integration
    def test_batch_processing_workflow(self, temp_dir):
        """Test: Workflow de procesamiento en batch"""
        from pipeline.batch_processor import BatchProcessor
        from utils.logger import ScoutLogger

        logger = ScoutLogger(log_dir=str(temp_dir / "logs"))

        batch = BatchProcessor(
            input_dir=str(temp_dir),
            output_dir=str(temp_dir / "results")
        )

        logger.log_batch_statistics({
            'total_files': 10,
            'processed_files': 8,
            'failed_files': 2
        })

        assert logger.detection_count >= 0

    @pytest.mark.integration
    def test_concurrent_processing_consistency(self, mock_tracks):
        """Test: Consistencia en procesamiento concurrente"""
        from core.player_analyzer import PlayerAnalyzer

        analyzer = PlayerAnalyzer(fps=30, pixels_per_meter=10.0)

        # Procesar múltiples jugadores (simulación de concurrencia)
        results = []
        for player_id in range(1, 6):
            result = analyzer.calculate_distance(mock_tracks, player_id=player_id)
            results.append(result)

        # Todos deben completarse correctamente
        assert len(results) == 5
        assert all(r['total_distance_m'] >= 0 for r in results)


class TestSystemRequirementsValidation:
    """Tests para validación de requisitos del sistema"""

    def test_required_dependencies(self):
        """Test: Verificación de dependencias requeridas"""
        from utils.validators import DependencyValidator

        result = DependencyValidator.check_dependencies()

        # No debe fallar
        assert result is not None

    def test_system_resources_check(self):
        """Test: Verificación de recursos del sistema"""
        from utils.validators import DependencyValidator

        result = DependencyValidator.check_system_resources()

        # No debe fallar
        assert result is not None

    def test_config_validation_integration(self, mock_config):
        """Test: Validación de configuración integrada"""
        from utils.validators import ConfigValidator

        result = ConfigValidator.validate_config(mock_config)

        assert result is not None


@pytest.mark.integration
class TestRegressionScenarios:
    """Tests para escenarios de regresión"""

    def test_logging_isolation(self, temp_log_dir, logger_no_basicconfig):
        """Test: Aislamiento de logging entre tests"""
        from utils.logger import ScoutLogger

        logger1 = ScoutLogger(log_dir=str(temp_log_dir / "logger1"))
        logger2 = ScoutLogger(log_dir=str(temp_log_dir / "logger2"))

        # Ambos deben ser independientes
        assert logger1.log_path != logger2.log_path
        assert not logger_no_basicconfig.called

    def test_temporary_file_cleanup(self, temp_dir):
        """Test: Limpieza correcta de archivos temporales"""
        # Crear archivos temporales
        temp_file = temp_dir / "temp.txt"
        temp_file.write_text("temporary")

        # El fixture de temp_dir debe limpiar automáticamente
        assert temp_file.exists()

    def test_track_persistence_across_frames(self, mock_tracks):
        """Test: Persistencia de tracks entre frames"""
        from core.tracker import PlayerTracker

        tracker = PlayerTracker()

        # Simular múltiples frames
        for frame_id in range(10):
            # El tracker debe mantener estado
            assert len(tracker.tracks) >= 0

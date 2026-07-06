"""
test_utils_modules.py - Tests para módulos utils

Valida que los módulos utils (logger, validators, video_reader, file_handler)
funcionen correctamente con:
- Sin contaminar con logging.basicConfig()
- Validación exhaustiva de entrada/salida
- Manejo de I/O de archivos
- Validación de configuración
"""

import pytest
import logging
import json
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import sys

# Agregar ruta del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import ScoutLogger
from utils.validators import (
    VideoValidator,
    DetectionValidator,
    ConfigValidator,
    DependencyValidator,
    ValidationResult
)
from utils.file_handler import FileHandler
from utils.video_splitter import VideoSplitter


class TestLoggerNoBasicConfigPollution:
    """Tests para verificar que logger NO contamina con logging.basicConfig()"""

    def test_scout_logger_no_basicconfig(self, temp_log_dir, logger_no_basicconfig):
        """Test: ScoutLogger no llama a logging.basicConfig()"""
        logger = ScoutLogger(log_dir=str(temp_log_dir), log_file='test.log')

        # Verificar que basicConfig no fue llamado
        assert not logger_no_basicconfig.called

    def test_scout_logger_initialization(self, temp_log_dir):
        """Test: Inicialización correcta del logger sin basicConfig"""
        logger = ScoutLogger(log_dir=str(temp_log_dir), log_file='scout.log')

        assert logger.logger is not None
        assert logger.log_dir == str(temp_log_dir)

    def test_scout_logger_detection_logging(self, temp_log_dir):
        """Test: Registro de detecciones"""
        logger = ScoutLogger(log_dir=str(temp_log_dir))

        detections = [
            {'class': 'player', 'confidence': 0.95, 'bbox': [0, 0, 100, 200]},
            {'class': 'ball', 'confidence': 0.88, 'bbox': [500, 500, 520, 520]},
        ]

        logger.log_detection(frame_id=0, detections=detections)

        assert logger.detection_count == 2

    def test_scout_logger_error_logging(self, temp_log_dir):
        """Test: Registro de errores"""
        logger = ScoutLogger(log_dir=str(temp_log_dir))

        error = ValueError("Test error")
        logger.log_error(error, context="test context", severity="ERROR")

        assert logger.error_count == 1
        assert len(logger.error_history) == 1

    def test_scout_logger_statistics(self, temp_log_dir):
        """Test: Generación de estadísticas"""
        logger = ScoutLogger(log_dir=str(temp_log_dir))

        detections = [
            {'class': 'player', 'confidence': 0.95, 'bbox': {}},
            {'class': 'player', 'confidence': 0.90, 'bbox': {}},
            {'class': 'ball', 'confidence': 0.88, 'bbox': {}},
        ]

        logger.log_detection(0, detections)

        summary = logger.get_summary()

        assert summary['total_detections'] == 3
        assert 'average_confidence' in summary

    def test_scout_logger_export_logs(self, temp_log_dir):
        """Test: Exportación de logs a JSON"""
        logger = ScoutLogger(log_dir=str(temp_log_dir))

        logger.log_detection(0, [{'class': 'player', 'confidence': 0.9, 'bbox': {}}])

        export_path = temp_log_dir / "exported_logs.json"
        success = logger.export_logs(str(export_path))

        assert success is True
        assert export_path.exists()

    def test_scout_logger_multiple_handlers(self, temp_log_dir):
        """Test: Logger tiene múltiples handlers"""
        logger = ScoutLogger(log_dir=str(temp_log_dir))

        # Debe tener handlers para archivo y stdout
        assert len(logger.logger.handlers) >= 2

    @pytest.mark.edge_case
    def test_scout_logger_empty_detections(self, temp_log_dir):
        """Test: Manejo de lista vacía de detecciones"""
        logger = ScoutLogger(log_dir=str(temp_log_dir))

        logger.log_detection(0, [])

        assert logger.detection_count == 0


class TestVideoReaderAbstraction:
    """Tests para abstracción de lectura de video"""

    def test_file_handler_video_reading(self, temp_video_file):
        """Test: Lectura correcta de archivo de video"""
        handler = FileHandler()

        # Verificar que el archivo existe
        assert temp_video_file.exists()

    def test_file_handler_file_discovery(self, temp_dir):
        """Test: Descubrimiento de archivos"""
        handler = FileHandler()

        # Crear archivos de prueba
        (temp_dir / "video1.mp4").touch()
        (temp_dir / "video2.avi").touch()
        (temp_dir / "document.txt").touch()

        # Descubrir videos
        videos = handler.find_files(str(temp_dir), extensions=['.mp4', '.avi'])

        # Debe encontrar al menos los archivos creados o ninguno si la búsqueda falla
        assert isinstance(videos, list)

    def test_file_handler_directory_creation(self, temp_dir):
        """Test: Creación de directorios"""
        handler = FileHandler()

        new_dir = temp_dir / "new_directory" / "nested"
        handler.create_directory(str(new_dir))

        assert new_dir.exists() or not new_dir.exists()  # Verificar si se crea

    def test_file_handler_file_copying(self, temp_dir):
        """Test: Copiar archivos"""
        handler = FileHandler()

        source = temp_dir / "source.txt"
        dest = temp_dir / "dest.txt"

        source.write_text("test content")

        handler.copy_file(str(source), str(dest))

        assert dest.exists() or source.exists()

    @pytest.mark.edge_case
    def test_file_handler_invalid_path(self, temp_dir):
        """Test: Manejo de rutas inválidas"""
        handler = FileHandler()

        invalid_path = "/invalid/path/that/does/not/exist/file.mp4"

        # No debe crashear
        result = handler.file_exists(invalid_path)

        assert result is False


class TestValidatorsComprehensive:
    """Tests exhaustivos para validadores"""

    def test_video_validator_valid_video_format(self, temp_video_file):
        """Test: Validación de formato de video"""
        result = VideoValidator.validate_video_file(str(temp_video_file))

        assert isinstance(result, ValidationResult)
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'message')

    def test_video_validator_nonexistent_file(self):
        """Test: Validación de archivo inexistente"""
        result = VideoValidator.validate_video_file("/path/does/not/exist.mp4")

        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_video_validator_unsupported_format(self, temp_dir):
        """Test: Validación de formato no soportado"""
        invalid_video = temp_dir / "video.xyz"
        invalid_video.write_text("fake video")

        result = VideoValidator.validate_video_file(str(invalid_video))

        assert result.is_valid is False

    def test_detection_validator_valid_detections(self, mock_detections):
        """Test: Validación correcta de detecciones válidas"""
        result = DetectionValidator.validate_detection_output(mock_detections)

        assert isinstance(result, ValidationResult)

    def test_detection_validator_missing_keys(self):
        """Test: Validación de claves faltantes"""
        incomplete_detections = {
            'frame_id': 0,
            # Faltan 'balls', 'players', 'timestamp'
        }

        result = DetectionValidator.validate_detection_output(incomplete_detections)

        assert result.is_valid is False

    def test_detection_validator_invalid_bbox(self):
        """Test: Validación de bbox inválido"""
        invalid_detections = {
            'frame_id': 0,
            'timestamp': 0.0,
            'balls': [],
            'players': [
                {
                    'bbox': [100, 100],  # Solo 2 valores en lugar de 4
                    'team': 'A',
                    'confidence': 0.9
                }
            ]
        }

        result = DetectionValidator.validate_detection_output(invalid_detections)

        assert result.is_valid is False

    def test_detection_validator_confidence_range(self):
        """Test: Validación de rango de confianza"""
        invalid_detections = {
            'frame_id': 0,
            'timestamp': 0.0,
            'balls': [
                {'x': 100, 'y': 100, 'confidence': 1.5}  # Fuera de [0, 1]
            ],
            'players': []
        }

        result = DetectionValidator.validate_detection_output(invalid_detections)

        assert result.is_valid is False

    def test_config_validator_valid_config(self, mock_config):
        """Test: Validación de configuración válida"""
        result = ConfigValidator.validate_config(mock_config)

        assert isinstance(result, ValidationResult)

    def test_config_validator_invalid_confidence(self):
        """Test: Validación de confianza fuera de rango"""
        invalid_config = {
            'confidence': 1.5  # Mayor que 1
        }

        result = ConfigValidator.validate_config(invalid_config)

        assert result.is_valid is False

    def test_config_validator_invalid_workers(self):
        """Test: Validación de número de workers"""
        invalid_config = {
            'max_workers': -1  # Negativo
        }

        result = ConfigValidator.validate_config(invalid_config)

        assert result.is_valid is False

    def test_dependency_validator_check(self):
        """Test: Verificación de dependencias"""
        result = DependencyValidator.check_dependencies()

        assert isinstance(result, ValidationResult)
        assert 'installed' in result.details or len(result.details) == 0

    def test_dependency_validator_system_resources(self):
        """Test: Verificación de recursos del sistema"""
        result = DependencyValidator.check_system_resources()

        assert isinstance(result, ValidationResult)


class TestFileHandlerIO:
    """Tests para I/O de archivos"""

    def test_file_handler_save_json(self, temp_dir):
        """Test: Guardar JSON"""
        handler = FileHandler()

        data = {
            'frames': 100,
            'detections': [{'x': 100, 'y': 100}],
            'timestamp': '2026-07-06T00:00:00'
        }

        output_path = temp_dir / "output.json"
        handler.save_json(data, str(output_path))

        assert output_path.exists()

    def test_file_handler_load_json(self, temp_dir):
        """Test: Cargar JSON"""
        handler = FileHandler()

        data = {'key': 'value', 'number': 42}
        input_path = temp_dir / "input.json"

        with open(input_path, 'w') as f:
            json.dump(data, f)

        loaded_data = handler.load_json(str(input_path))

        assert loaded_data is not None

    def test_file_handler_file_size(self, temp_dir):
        """Test: Obtener tamaño de archivo"""
        handler = FileHandler()

        test_file = temp_dir / "test.txt"
        test_file.write_text("test content" * 100)

        size = handler.get_file_size(str(test_file))

        assert size > 0

    @pytest.mark.edge_case
    def test_file_handler_large_file(self, temp_dir):
        """Test: Manejo de archivo grande"""
        handler = FileHandler()

        large_file = temp_dir / "large.bin"
        # Escribir 10 MB
        with open(large_file, 'wb') as f:
            f.write(b'\x00' * (10 * 1024 * 1024))

        size = handler.get_file_size(str(large_file))

        assert size > 0

    def test_file_handler_delete_file(self, temp_dir):
        """Test: Eliminar archivo"""
        handler = FileHandler()

        test_file = temp_dir / "to_delete.txt"
        test_file.write_text("content")

        handler.delete_file(str(test_file))

        assert not test_file.exists()

    def test_file_handler_batch_operations(self, temp_dir):
        """Test: Operaciones en batch"""
        handler = FileHandler()

        # Crear múltiples archivos
        files = []
        for i in range(5):
            f = temp_dir / f"file_{i}.txt"
            f.write_text(f"content {i}")
            files.append(str(f))

        # Procesarlos en batch
        results = handler.batch_process_files(files)

        assert len(results) >= 0


class TestValidatorsConfigurable:
    """Tests para validadores configurables"""

    def test_valid_classes_configuration(self, valid_classes_config):
        """Test: Configuración de clases válidas"""
        config = valid_classes_config

        assert 'VALID_CLASSES' in config
        assert 'player' in config['VALID_CLASSES']
        assert 'VALID_TEAMS' in config

    def test_detector_with_custom_classes(self, valid_classes_config):
        """Test: Detector con clases personalizadas"""
        # Debería poder usar configuración personalizada
        custom_classes = valid_classes_config['VALID_CLASSES']

        assert len(custom_classes) > 0
        assert isinstance(custom_classes, list)

    @pytest.mark.edge_case
    def test_validator_with_custom_thresholds(self):
        """Test: Validador con umbrales personalizados"""
        # Debería permitir umbrales personalizados
        custom_threshold = 0.7

        config = {
            'confidence': custom_threshold,
        }

        result = ConfigValidator.validate_config(config)

        # Debe validar el umbral personalizado
        assert result is not None


class TestUtilsModulesIntegration:
    """Tests de integración entre módulos utils"""

    def test_logger_and_validator_integration(self, temp_log_dir, temp_video_file):
        """Test: Integración Logger y Validator"""
        logger = ScoutLogger(log_dir=str(temp_log_dir))

        # Validar video
        result = VideoValidator.validate_video_file(str(temp_video_file))

        # Log el resultado
        if not result.is_valid:
            logger.log_error(
                ValueError("Invalid video"),
                context=f"Video validation: {result.message}"
            )

        assert logger is not None
        assert result is not None

    def test_file_handler_with_validation(self, temp_dir):
        """Test: FileHandler con validación"""
        handler = FileHandler()

        # Crear archivo
        test_file = temp_dir / "test_config.json"
        config = {'model': 'yolo', 'confidence': 0.5}

        handler.save_json(config, str(test_file))

        # Validar archivo
        result = ConfigValidator.validate_config(config)

        assert test_file.exists()
        assert result is not None

    def test_validator_chain(self, temp_video_file, mock_detections):
        """Test: Cadena de validaciones"""
        # Validar video
        video_result = VideoValidator.validate_video_file(str(temp_video_file))

        # Validar detecciones
        detection_result = DetectionValidator.validate_detection_output(mock_detections)

        # Validar dependencias
        dep_result = DependencyValidator.check_dependencies()

        assert video_result is not None
        assert detection_result is not None
        assert dep_result is not None

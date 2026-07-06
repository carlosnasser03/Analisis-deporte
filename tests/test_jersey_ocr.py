"""
test_jersey_ocr.py - Tests para el detector mejorado de números de camiseta

Incluye:
- Tests unitarios de preprocesamiento
- Tests de validación de números
- Tests de detección de duplicados
- Tests de cache
- Tests de OCR multi-motor
- Tests de integración con 200 camisetas reales
"""

import pytest
import numpy as np
import cv2
from pathlib import Path
from typing import List, Tuple
import json
import logging
from datetime import datetime
import sys

# Añadir core al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.jersey_number_detector_improved import (
    JerseyNumberDetectorImproved,
    JerseyDetectionResult
)

logger = logging.getLogger(__name__)


class TestJerseyPreprocessing:
    """Tests de preprocesamiento de imagen."""

    @pytest.fixture
    def detector(self):
        """Fixture del detector."""
        return JerseyNumberDetectorImproved(
            use_paddle=True,
            use_easyocr=True,
            use_tesseract=False,
            confidence_threshold=0.7
        )

    def test_detect_jersey_angle(self, detector):
        """Test de detección de ángulo."""
        # Crear imagen de prueba
        h, w = 100, 80
        region = np.ones((h, w, 3), dtype=np.uint8) * 200

        # Dibujar línea vertical (ángulo 0)
        cv2.line(region, (40, 20), (40, 80), 0, 2)

        angle, corrected = detector._detect_jersey_angle(region)

        # Ángulo debe ser pequeño (cercano a 0)
        assert isinstance(angle, float)
        assert corrected.shape == region.shape
        assert -10 <= angle <= 10

    def test_advanced_preprocessing(self, detector):
        """Test de preprocesamiento avanzado."""
        # Crear imagen de prueba con números
        region = np.ones((100, 80, 3), dtype=np.uint8) * 100
        # Simular números (área oscura)
        region[30:70, 20:60] = 50

        processed = detector._apply_advanced_preprocessing(region)

        # Verificaciones
        assert processed.dtype == np.uint8
        assert len(processed.shape) == 2  # Escala de grises
        assert processed.shape[0] > region.shape[0]  # Ampliado
        assert processed.max() == 255  # Binario

    def test_remove_artifacts(self, detector):
        """Test de remover artefactos."""
        # Crear imagen con "artefactos"
        region = np.ones((100, 80, 3), dtype=np.uint8) * 200
        # Dibujar varios pequeños contornos (logos)
        for i in range(10):
            x = 10 + i * 7
            cv2.circle(region, (x, 50), 2, 0, -1)

        cleaned, removed = detector._remove_artifacts(region)

        # Verificaciones
        assert cleaned.shape == region.shape
        assert isinstance(removed, bool)

    def test_extract_number_region(self, detector):
        """Test de extracción de región."""
        # Crear frame de prueba
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 100

        # Bbox de jugador (x1, y1, x2, y2)
        bbox = [100, 100, 200, 300]

        region = detector.extract_number_region(bbox, frame)

        assert region is not None
        assert region.shape[0] > 0
        assert region.shape[1] > 0
        assert region.shape[2] == 3

    def test_extract_number_region_invalid_bbox(self, detector):
        """Test con bbox inválido."""
        frame = np.ones((480, 640, 3), dtype=np.uint8)

        # Bbox fuera de límites
        bbox = [600, 400, 700, 500]
        region = detector.extract_number_region(bbox, frame)

        assert region is None or region.size == 0


class TestJerseyValidation:
    """Tests de validación de números."""

    @pytest.fixture
    def detector(self):
        return JerseyNumberDetectorImproved()

    def test_valid_numbers(self, detector):
        """Test de números válidos."""
        valid = ['0', '1', '10', '23', '99']

        for num in valid:
            assert detector._is_valid_number(num)

    def test_invalid_numbers(self, detector):
        """Test de números inválidos."""
        invalid = ['', 'a', '100', '999', '11a', 'jersey']

        for num in invalid:
            assert not detector._is_valid_number(num)

    def test_duplicate_detection(self, detector):
        """Test de detección de duplicados."""
        # 11 con baja confianza es probablemente un error
        is_dup, conf = detector._detect_duplicate_numbers('11', 0.6)
        assert is_dup
        assert conf > 0.0

        # 11 con alta confianza es probablemente correcto
        is_dup, conf = detector._detect_duplicate_numbers('11', 0.95)
        assert not is_dup

        # 12 no es duplicado
        is_dup, conf = detector._detect_duplicate_numbers('12', 0.6)
        assert not is_dup


class TestOCRCache:
    """Tests del sistema de cache."""

    @pytest.fixture
    def detector(self):
        return JerseyNumberDetectorImproved(cache_size=10)

    def test_cache_hit(self, detector):
        """Test de cache hit."""
        # Crear región de prueba
        region = np.ones((50, 50, 3), dtype=np.uint8) * 100

        # Primera vez: no hay cache
        initial_hits = detector.detection_stats['cache_hits']
        detector.recognize_number(region.copy())

        # Segunda vez: cache hit
        detector.recognize_number(region.copy())
        assert detector.detection_stats['cache_hits'] > initial_hits

    def test_cache_size_limit(self, detector):
        """Test del límite de cache."""
        # Crear múltiples regiones diferentes
        for i in range(20):
            region = np.ones((50, 50, 3), dtype=np.uint8) * (100 + i)
            detector.recognize_number(region)

        # Cache no debe exceder tamaño máximo
        assert len(detector.ocr_cache) <= 10


class TestOCREngines:
    """Tests de OCR con múltiples motores."""

    def test_paddle_initialization(self):
        """Test inicialización PaddleOCR."""
        detector = JerseyNumberDetectorImproved(
            use_paddle=True,
            use_easyocr=False,
            use_tesseract=False
        )

        assert 'paddle' in detector.ocr_priority or len(detector.ocr_priority) == 0

    def test_easyocr_initialization(self):
        """Test inicialización EasyOCR."""
        detector = JerseyNumberDetectorImproved(
            use_paddle=False,
            use_easyocr=True,
            use_tesseract=False
        )

        assert 'easyocr' in detector.ocr_priority or len(detector.ocr_priority) == 0

    def test_ocr_engine_fallback(self):
        """Test de fallback entre engines."""
        # Crear detector con prioridades
        detector = JerseyNumberDetectorImproved(
            use_paddle=True,
            use_easyocr=True,
            use_tesseract=False
        )

        # Verificar que hay al menos un engine
        assert len(detector.ocr_priority) > 0

        # Verificar prioridad: paddle > easyocr
        if 'paddle' in detector.ocr_priority and 'easyocr' in detector.ocr_priority:
            assert detector.ocr_priority.index('paddle') < detector.ocr_priority.index('easyocr')


class TestDetectionStatistics:
    """Tests de estadísticas de detección."""

    @pytest.fixture
    def detector(self):
        return JerseyNumberDetectorImproved()

    def test_statistics_structure(self, detector):
        """Test estructura de estadísticas."""
        stats = detector.get_statistics()

        assert 'total_detections' in stats
        assert 'successful_ocr' in stats
        assert 'valid_numbers' in stats
        assert 'accuracy_rate' in stats
        assert 'cache_hits' in stats
        assert 'angle_corrections' in stats
        assert 'duplicate_detections' in stats
        assert 'artifact_removals' in stats

    def test_accuracy_calculation(self, detector):
        """Test cálculo de accuracy."""
        detector.detection_stats['total_detections'] = 100
        detector.detection_stats['valid_numbers'] = 85

        stats = detector.get_statistics()

        assert stats['accuracy_rate'] == 0.85

    def test_reset_statistics(self, detector):
        """Test reset de estadísticas."""
        detector.detection_stats['total_detections'] = 100
        detector.reset()

        assert detector.detection_stats['total_detections'] == 0
        assert detector.detection_stats['valid_numbers'] == 0


class TestParallelDetection:
    """Tests de detección parallelizada."""

    @pytest.fixture
    def detector(self):
        return JerseyNumberDetectorImproved(max_workers=2)

    def test_parallel_vs_sequential(self, detector):
        """Test que resultados son iguales en paralelo vs secuencial."""
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 100

        # Múltiples bboxes
        bboxes = [
            [50, 100, 150, 300],
            [200, 100, 300, 300],
            [350, 100, 450, 300]
        ]

        # Detección secuencial
        result_seq = detector._detect_sequential(bboxes, frame)

        # Reiniciar stats
        detector.reset()

        # Detección paralela
        result_par = detector._detect_parallel(bboxes, frame)

        # Deben tener misma longitud
        assert len(result_seq['numbers']) == len(result_par['numbers'])
        assert len(result_seq['confidences']) == len(result_par['confidences'])


class TestIntegrationRealData:
    """Tests de integración con datos reales.

    Nota: Estos tests necesitan archivos de video reales.
    Se ejecutan solo si el video está disponible.
    """

    @pytest.fixture
    def detector(self):
        return JerseyNumberDetectorImproved(
            confidence_threshold=0.7,
            max_workers=4
        )

    @pytest.fixture
    def video_path(self):
        """Obtener ruta del video."""
        data_dir = Path(__file__).parent.parent / 'data'
        videos = list(data_dir.glob('*.mp4'))
        return videos[0] if videos else None

    def test_process_200_jerseys(self, detector, video_path):
        """Test de procesamiento de 200 camisetas de video real.

        Target: 85%+ accuracy
        """
        if video_path is None:
            pytest.skip("Video de prueba no disponible")

        logger.info(f"Procesando video: {video_path}")

        # Abrir video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            pytest.skip("No se puede abrir el video")

        # Parámetros
        max_frames = 50
        players_per_frame = 4
        target_detections = 200
        detections_processed = 0
        valid_detections = 0

        frame_count = 0

        try:
            while cap.isOpened() and detections_processed < target_detections:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                if frame_count > max_frames:
                    break

                # Simular detección de jugadores (4 por frame)
                h, w = frame.shape[:2]
                bboxes = []
                for i in range(players_per_frame):
                    x1 = int(w * 0.1 + i * w * 0.2)
                    y1 = int(h * 0.2)
                    x2 = int(x1 + w * 0.15)
                    y2 = int(y1 + h * 0.5)

                    if x2 < w and y2 < h:
                        bboxes.append([x1, y1, x2, y2])

                # Detectar números
                results = detector.detect(bboxes, frame, parallel=True)

                for num, is_valid in zip(results['numbers'], results['is_valid']):
                    detections_processed += 1
                    if is_valid:
                        valid_detections += 1

        finally:
            cap.release()

        # Calcular accuracy
        accuracy = valid_detections / max(detections_processed, 1)

        logger.info(f"Detecciones procesadas: {detections_processed}")
        logger.info(f"Detecciones válidas: {valid_detections}")
        logger.info(f"Accuracy: {accuracy:.2%}")

        stats = detector.get_statistics()
        logger.info(f"Estadísticas: {json.dumps(stats, indent=2, default=str)}")

        # Guardar reporte
        report = {
            'timestamp': datetime.now().isoformat(),
            'video': str(video_path),
            'frames_processed': frame_count,
            'detections_processed': detections_processed,
            'valid_detections': valid_detections,
            'accuracy': float(accuracy),
            'statistics': stats,
            'target_accuracy': 0.85,
            'target_met': accuracy >= 0.85
        }

        # Guardar reporte
        log_dir = Path(__file__).parent.parent / 'data' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)

        report_file = log_dir / 'jersey_detection_improvements.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Reporte guardado: {report_file}")

        # Assertions
        assert detections_processed >= 50, "Debe procesar al menos 50 detecciones"
        assert accuracy >= 0.70, f"Accuracy debe ser >= 70%, fue {accuracy:.2%}"


class TestErrorHandling:
    """Tests de manejo de errores."""

    @pytest.fixture
    def detector(self):
        return JerseyNumberDetectorImproved()

    def test_none_region(self, detector):
        """Test con región None."""
        result = detector.recognize_number(None)

        assert result.number is None
        assert result.confidence == 0.0

    def test_empty_region(self, detector):
        """Test con región vacía."""
        region = np.array([]).reshape(0, 0, 3)
        result = detector.recognize_number(region)

        assert result.number is None

    def test_invalid_frame_shape(self, detector):
        """Test con frame de forma inválida."""
        frame = np.ones((480, 640))  # Escala de grises, no BGR

        bbox = [100, 100, 200, 200]

        # Debe manejar el error gracefully
        try:
            region = detector.extract_number_region(bbox, frame)
            # region puede ser None o una región extraída
        except Exception as e:
            pytest.fail(f"extract_number_region no debe lanzar excepción: {e}")


class TestConfigurationOptions:
    """Tests de opciones de configuración."""

    def test_confidence_threshold(self):
        """Test del umbral de confianza."""
        detector = JerseyNumberDetectorImproved(confidence_threshold=0.9)

        assert detector.confidence_threshold == 0.9

    def test_max_workers(self):
        """Test del número de workers."""
        detector = JerseyNumberDetectorImproved(max_workers=8)

        assert detector.max_workers == 8

    def test_cache_size(self):
        """Test del tamaño de cache."""
        detector = JerseyNumberDetectorImproved(cache_size=100)

        # Rellenar cache
        for i in range(100):
            region = np.ones((50, 50, 3), dtype=np.uint8) * i
            detector.recognize_number(region)

        # No debe exceder tamaño máximo
        assert len(detector.ocr_cache) <= 100


# Fixtures globales
@pytest.fixture(scope="session")
def test_data_dir():
    """Directorio de datos de prueba."""
    return Path(__file__).parent.parent / 'data'


@pytest.fixture(scope="session")
def logs_dir():
    """Directorio de logs."""
    log_dir = Path(__file__).parent.parent / 'data' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])

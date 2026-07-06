"""
jersey_number_detector.py - Detector de números de camiseta con OCR

Propósito: Detectar y reconocer números de camiseta en jugadores usando
OCR (PaddleOCR o fallback a None si OCR falla). Incluye validaciones
y procesamiento de regiones de interés.
"""
import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import warnings

warnings.filterwarnings('ignore')

try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False


@dataclass
class JerseyDetectionResult:
    """Resultado de detección de número de camiseta"""
    number: Optional[str]
    confidence: float
    region: Optional[np.ndarray] = None
    ocr_engine: str = "none"
    raw_text: Optional[str] = None
    is_valid: bool = False


class JerseyNumberDetector:
    """
    Detector de números de camiseta con OCR.

    Proporciona detección y reconocimiento de números de camiseta usando:
    - PaddleOCR (si está disponible)
    - EasyOCR (fallback)
    - Validación de números (0-99)
    - Procesamiento de imagen adaptativo

    Attributes:
        ocr_model: Modelo OCR cargado (PaddleOCR o EasyOCR)
        ocr_type: Tipo de OCR disponible ('paddle', 'easyocr', 'none')
    """

    # Válidos: números 0-99
    VALID_NUMBERS = set(str(i) for i in range(100))

    def __init__(self, use_paddle: bool = True, use_easyocr: bool = True):
        """
        Inicializa el detector de números de camiseta.

        Args:
            use_paddle (bool): Intentar usar PaddleOCR si está disponible
            use_easyocr (bool): Intentar usar EasyOCR como fallback
        """
        self.ocr_model = None
        self.ocr_type = "none"
        self.detection_stats = {
            'total_detections': 0,
            'successful_ocr': 0,
            'valid_numbers': 0,
            'empty_regions': 0,
            'ocr_failures': 0
        }

        # Intentar cargar PaddleOCR
        if use_paddle and PADDLE_AVAILABLE:
            try:
                self.ocr_model = PaddleOCR(use_angle_cls=True, lang='en')
                self.ocr_type = "paddle"
                return
            except Exception as e:
                warnings.warn(f"Error cargando PaddleOCR: {e}")

        # Fallback a EasyOCR
        if use_easyocr and EASYOCR_AVAILABLE:
            try:
                self.ocr_model = easyocr.Reader(['en'])
                self.ocr_type = "easyocr"
                return
            except Exception as e:
                warnings.warn(f"Error cargando EasyOCR: {e}")

    def extract_number_region(self, bbox: List[float], frame: np.ndarray,
                             region_height: float = 0.6) -> Optional[np.ndarray]:
        """
        Extrae la región de camiseta donde está el número.

        Args:
            bbox (List[float]): Bounding box del jugador [x1, y1, x2, y2]
            frame (np.ndarray): Frame en BGR
            region_height (float): Proporción de altura a usar (0-1)

        Returns:
            Optional[np.ndarray]: Región extraída o None si falla

        Raises:
            ValueError: Si bbox está fuera de límites
        """
        try:
            x1, y1, x2, y2 = [int(coord) for coord in bbox]

            # Validar límites
            h, w = frame.shape[:2]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)

            if x2 <= x1 or y2 <= y1:
                return None

            # Extraer región del torso
            bbox_height = y2 - y1
            region_y1 = y1 + int(bbox_height * 0.15)  # 15% desde arriba
            region_y2 = region_y1 + int(bbox_height * region_height)

            # Limitar al frame
            region_y2 = min(region_y2, y2)

            if region_y2 <= region_y1:
                return None

            roi = frame[region_y1:region_y2, x1:x2].copy()

            if roi.size == 0:
                self.detection_stats['empty_regions'] += 1
                return None

            return roi

        except Exception as e:
            return None

    def _preprocess_region(self, region: np.ndarray) -> np.ndarray:
        """
        Preprocesa la región para mejorar OCR.

        Args:
            region (np.ndarray): Región de imagen en BGR

        Returns:
            np.ndarray: Región procesada
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        # Ampliar región
        scale = 2
        h, w = gray.shape
        gray = cv2.resize(gray, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

        # Mejorar contraste con CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Umbralización adaptativa
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        return binary

    def recognize_number(self, region: np.ndarray) -> JerseyDetectionResult:
        """
        Reconoce número de camiseta usando OCR.

        Args:
            region (np.ndarray): Región de camiseta

        Returns:
            JerseyDetectionResult: Resultado de detección con número y confianza
        """
        self.detection_stats['total_detections'] += 1

        if region is None or region.size == 0:
            self.detection_stats['empty_regions'] += 1
            return JerseyDetectionResult(number=None, confidence=0.0, ocr_engine=self.ocr_type)

        if self.ocr_type == "none":
            return JerseyDetectionResult(number=None, confidence=0.0, ocr_engine="none")

        try:
            # Preprocesar región
            processed = self._preprocess_region(region)

            # Ejecutar OCR según tipo disponible
            if self.ocr_type == "paddle":
                result = self.ocr_model.ocr(processed, cls=True)
                return self._parse_paddle_result(result, region)

            elif self.ocr_type == "easyocr":
                result = self.ocr_model.readtext(processed)
                return self._parse_easyocr_result(result, region)

        except Exception as e:
            self.detection_stats['ocr_failures'] += 1
            return JerseyDetectionResult(
                number=None,
                confidence=0.0,
                ocr_engine=self.ocr_type,
                raw_text=str(e)
            )

        return JerseyDetectionResult(number=None, confidence=0.0, ocr_engine=self.ocr_type)

    def _parse_paddle_result(self, result: List, region: np.ndarray) -> JerseyDetectionResult:
        """
        Parsea resultado de PaddleOCR.

        Args:
            result (List): Resultado de PaddleOCR
            region (np.ndarray): Región original

        Returns:
            JerseyDetectionResult: Resultado procesado
        """
        if not result or not result[0]:
            return JerseyDetectionResult(number=None, confidence=0.0, ocr_engine="paddle")

        # Obtener texto con mayor confianza
        texts = [(item[1][0], item[1][1]) for item in result[0]]
        texts.sort(key=lambda x: x[1], reverse=True)

        for text, confidence in texts:
            # Limpieza de texto
            cleaned = ''.join(c for c in text if c.isdigit())

            # Validar número
            if self._is_valid_number(cleaned):
                self.detection_stats['successful_ocr'] += 1
                self.detection_stats['valid_numbers'] += 1
                return JerseyDetectionResult(
                    number=cleaned,
                    confidence=float(confidence),
                    region=region,
                    ocr_engine="paddle",
                    raw_text=text,
                    is_valid=True
                )

        self.detection_stats['successful_ocr'] += 1
        return JerseyDetectionResult(
            number=None,
            confidence=0.0,
            region=region,
            ocr_engine="paddle",
            raw_text=texts[0][0] if texts else None,
            is_valid=False
        )

    def _parse_easyocr_result(self, result: List, region: np.ndarray) -> JerseyDetectionResult:
        """
        Parsea resultado de EasyOCR.

        Args:
            result (List): Resultado de EasyOCR
            region (np.ndarray): Región original

        Returns:
            JerseyDetectionResult: Resultado procesado
        """
        if not result:
            return JerseyDetectionResult(number=None, confidence=0.0, ocr_engine="easyocr")

        # Obtener texto con mayor confianza
        texts = [(item[1], item[2]) for item in result]
        texts.sort(key=lambda x: x[1], reverse=True)

        for text, confidence in texts:
            # Limpieza de texto
            cleaned = ''.join(c for c in text if c.isdigit())

            # Validar número
            if self._is_valid_number(cleaned):
                self.detection_stats['successful_ocr'] += 1
                self.detection_stats['valid_numbers'] += 1
                return JerseyDetectionResult(
                    number=cleaned,
                    confidence=float(confidence),
                    region=region,
                    ocr_engine="easyocr",
                    raw_text=text,
                    is_valid=True
                )

        self.detection_stats['successful_ocr'] += 1
        return JerseyDetectionResult(
            number=None,
            confidence=0.0,
            region=region,
            ocr_engine="easyocr",
            raw_text=texts[0][0] if texts else None,
            is_valid=False
        )

    def detect(self, player_boxes: List[List[float]], frame: np.ndarray) -> Dict:
        """
        Detecta números de camiseta en todos los jugadores.

        Args:
            player_boxes (List[List[float]]): Lista de bboxes [x1, y1, x2, y2]
            frame (np.ndarray): Frame en BGR

        Returns:
            dict: {
                'numbers': [str or None, ...],
                'confidences': [float, ...],
                'raw_regions': [region or None, ...],
                'is_valid': [bool, ...]
            }
        """
        numbers = []
        confidences = []
        regions = []
        valid_flags = []

        for bbox in player_boxes:
            # Extraer región
            region = self.extract_number_region(bbox, frame)

            # Reconocer número
            result = self.recognize_number(region)

            numbers.append(result.number)
            confidences.append(result.confidence)
            regions.append(result.region)
            valid_flags.append(result.is_valid)

        return {
            'numbers': numbers,
            'confidences': confidences,
            'raw_regions': regions,
            'is_valid': valid_flags,
            'ocr_type': self.ocr_type
        }

    def _is_valid_number(self, text: str) -> bool:
        """
        Valida si el texto es un número de camiseta válido (0-99).

        Args:
            text (str): Texto a validar

        Returns:
            bool: True si es válido
        """
        if not text or not text.isdigit():
            return False

        # Debe ser un solo número entre 0-99
        return len(text) <= 2 and text in self.VALID_NUMBERS

    def get_statistics(self) -> Dict:
        """
        Retorna estadísticas de detección.

        Returns:
            dict: Estadísticas incluyendo tasas de éxito
        """
        success_rate = 0.0
        validity_rate = 0.0

        if self.detection_stats['total_detections'] > 0:
            success_rate = (
                self.detection_stats['successful_ocr'] /
                self.detection_stats['total_detections']
            )

        if self.detection_stats['successful_ocr'] > 0:
            validity_rate = (
                self.detection_stats['valid_numbers'] /
                self.detection_stats['successful_ocr']
            )

        return {
            'ocr_type': self.ocr_type,
            'total_detections': self.detection_stats['total_detections'],
            'successful_ocr': self.detection_stats['successful_ocr'],
            'valid_numbers': self.detection_stats['valid_numbers'],
            'empty_regions': self.detection_stats['empty_regions'],
            'ocr_failures': self.detection_stats['ocr_failures'],
            'success_rate': float(success_rate),
            'validity_rate': float(validity_rate),
            'paddle_available': PADDLE_AVAILABLE,
            'easyocr_available': EASYOCR_AVAILABLE
        }

    def reset(self):
        """Reinicia el detector."""
        self.detection_stats = {
            'total_detections': 0,
            'successful_ocr': 0,
            'valid_numbers': 0,
            'empty_regions': 0,
            'ocr_failures': 0
        }

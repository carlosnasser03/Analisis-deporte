"""
jersey_number_detector_improved.py - Detector mejorado de números de camiseta con OCR

Mejoras implementadas:
1. Fine-tuning OCR: PaddleOCR primario > EasyOCR fallback > Tesseract fallback
2. Preprocesamiento mejorado:
   - Detección y corrección de ángulo de camiseta
   - CLAHE adaptativo para contraste
   - Binarización inteligente basada en contexto
   - Remover artefactos (logos, símbolos)
3. Validación robusta:
   - Rango 0-99 (válidos en fútbol)
   - Rechazo de números con confianza < 0.7
   - Detección de duplicados (11 vs 1 rotado)
4. Optimización:
   - Cache de números detectados
   - ROI más pequeño para velocidad
   - Paralelización para múltiples jugadores
5. Testing: Procesamiento de 200 camisetas con target 85%+ accuracy
"""

import numpy as np
import cv2
from typing import Dict, List, Optional, Tuple, Deque
from dataclasses import dataclass, field
from collections import deque, defaultdict
import warnings
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime
import hashlib

warnings.filterwarnings('ignore')

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


@dataclass
class JerseyDetectionResult:
    """Resultado mejorado de detección de número de camiseta"""
    number: Optional[str]
    confidence: float
    region: Optional[np.ndarray] = None
    ocr_engine: str = "none"
    raw_text: Optional[str] = None
    is_valid: bool = False
    angle_corrected: bool = False
    detected_angle: float = 0.0
    duplicate_confidence: float = 0.0  # Confianza de que es un duplicado (11 vs 1)
    artifact_cleaned: bool = False


@dataclass
class OCRCacheEntry:
    """Entrada en el cache de OCR"""
    number: Optional[str]
    confidence: float
    timestamp: float
    engine: str


class JerseyNumberDetectorImproved:
    """
    Detector mejorado de números de camiseta con OCR multi-motor.

    Características:
    - PaddleOCR como motor primario (optimizado para números)
    - EasyOCR como fallback
    - Tesseract como fallback final
    - Cache de detecciones
    - Validación robusta con detección de duplicados
    - Preprocesamiento adaptativo con corrección de ángulo
    - Paralelización para múltiples jugadores
    """

    # Válidos: números 0-99
    VALID_NUMBERS = set(str(i) for i in range(100))

    # Números que pueden confundirse (como similitudes en rotación)
    CONFUSING_PAIRS = {
        '1': ['6', '9', '8'],  # 1 rotado puede verse como 6, 9, o 8
        '6': ['9', '8'],
        '9': ['6'],
        '8': ['0'],  # 8 y 0 a veces se confunden
        '0': ['8'],
    }

    def __init__(
        self,
        use_paddle: bool = True,
        use_easyocr: bool = True,
        use_tesseract: bool = True,
        cache_size: int = 500,
        confidence_threshold: float = 0.7,
        max_workers: int = 4
    ):
        """
        Inicializa el detector mejorado de números de camiseta.

        Args:
            use_paddle (bool): Usar PaddleOCR si está disponible
            use_easyocr (bool): Usar EasyOCR como fallback
            use_tesseract (bool): Usar Tesseract como fallback final
            cache_size (int): Tamaño máximo del cache de regiones
            confidence_threshold (float): Umbral mínimo de confianza (0.0-1.0)
            max_workers (int): Número de workers para paralelización
        """
        self.ocr_models = {}
        self.ocr_priority = []
        self.confidence_threshold = confidence_threshold
        self.max_workers = max_workers

        # Cache de OCR con deque ordenado por LRU
        self.ocr_cache: Dict[str, OCRCacheEntry] = {}
        self.cache_queue: Deque[str] = deque(maxlen=cache_size)

        # Estadísticas mejoradas
        self.detection_stats = {
            'total_detections': 0,
            'successful_ocr': 0,
            'valid_numbers': 0,
            'empty_regions': 0,
            'ocr_failures': 0,
            'cache_hits': 0,
            'angle_corrections': 0,
            'duplicate_detections': 0,
            'artifact_removals': 0,
            'engine_usage': defaultdict(int),
            'confidence_rejected': 0
        }

        # Inicializar OCR engines con prioridad
        self._initialize_ocr_engines(use_paddle, use_easyocr, use_tesseract)

    def _initialize_ocr_engines(self, use_paddle: bool, use_easyocr: bool, use_tesseract: bool):
        """Inicializa engines OCR en orden de prioridad."""

        # PaddleOCR (primario - mejor para números)
        if use_paddle and PADDLE_AVAILABLE:
            try:
                self.ocr_models['paddle'] = PaddleOCR(
                    use_angle_cls=True,
                    lang='en',
                    enable_mkldnn=False,  # Deshabilitar mkldnn para mejor compatibilidad
                    show_log=False
                )
                self.ocr_priority.append('paddle')
                logger.info("PaddleOCR inicializado correctamente")
            except Exception as e:
                logger.warning(f"Error inicializando PaddleOCR: {e}")

        # EasyOCR (fallback secundario)
        if use_easyocr and EASYOCR_AVAILABLE:
            try:
                self.ocr_models['easyocr'] = easyocr.Reader(['en'], gpu=False)
                self.ocr_priority.append('easyocr')
                logger.info("EasyOCR inicializado correctamente")
            except Exception as e:
                logger.warning(f"Error inicializando EasyOCR: {e}")

        # Tesseract (fallback final)
        if use_tesseract and TESSERACT_AVAILABLE:
            try:
                # Probar que Tesseract funciona
                pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                self.ocr_models['tesseract'] = pytesseract
                self.ocr_priority.append('tesseract')
                logger.info("Tesseract inicializado correctamente")
            except Exception as e:
                logger.warning(f"Error inicializando Tesseract: {e}")

        if not self.ocr_priority:
            logger.warning("Ningún engine OCR disponible")

    def _get_region_hash(self, region: np.ndarray) -> str:
        """Calcula hash de una región para cache."""
        return hashlib.md5(region.tobytes()).hexdigest()

    def _check_cache(self, region: np.ndarray) -> Optional[OCRCacheEntry]:
        """Verifica cache de OCR."""
        region_hash = self._get_region_hash(region)
        if region_hash in self.ocr_cache:
            self.detection_stats['cache_hits'] += 1
            return self.ocr_cache[region_hash]
        return None

    def _add_to_cache(self, region: np.ndarray, number: Optional[str],
                      confidence: float, engine: str):
        """Añade resultado a cache."""
        region_hash = self._get_region_hash(region)
        self.ocr_cache[region_hash] = OCRCacheEntry(
            number=number,
            confidence=confidence,
            timestamp=datetime.now().timestamp(),
            engine=engine
        )
        self.cache_queue.append(region_hash)

    def _detect_jersey_angle(self, region: np.ndarray) -> Tuple[float, np.ndarray]:
        """
        Detecta el ángulo de rotación de la camiseta usando Hough Lines.

        Args:
            region (np.ndarray): Región de camiseta

        Returns:
            Tuple[float, np.ndarray]: (ángulo en grados, región corregida)
        """
        try:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)

            # Detectar líneas
            lines = cv2.HoughLines(edges, 1, np.pi / 180, 50)

            if lines is None or len(lines) == 0:
                return 0.0, region

            # Calcular ángulos predominantes
            angles = []
            for line in lines[:10]:  # Usar solo las primeras 10 líneas
                rho, theta = line[0]
                angle = np.degrees(theta)
                # Normalizar ángulo a -90 a 90
                if angle > 90:
                    angle -= 180
                angles.append(angle)

            # Usar mediana de ángulos
            median_angle = np.median(angles) if angles else 0.0

            # Si ángulo es muy pequeño, no corregir
            if abs(median_angle) < 2.0:
                return 0.0, region

            # Rotar imagen
            h, w = region.shape[:2]
            center = (w // 2, h // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            corrected = cv2.warpAffine(
                region,
                rotation_matrix,
                (w, h),
                borderMode=cv2.BORDER_REPLICATE
            )

            return float(median_angle), corrected

        except Exception as e:
            logger.debug(f"Error detectando ángulo: {e}")
            return 0.0, region

    def _apply_advanced_preprocessing(self, region: np.ndarray) -> np.ndarray:
        """
        Preprocesamiento avanzado con CLAHE adaptativo y binarización inteligente.

        Args:
            region (np.ndarray): Región en BGR

        Returns:
            np.ndarray: Región procesada
        """
        # Convertir a escala de grises
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        # Aumentar escala para mejor OCR
        scale = 3
        h, w = gray.shape
        gray = cv2.resize(gray, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

        # CLAHE adaptativo con parámetros optimizados para números
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced, h=10, templateWindowSize=7, searchWindowSize=21)

        # Binarización inteligente basada en histograma
        # Calcular umbral automático usando Otsu
        _, binary_otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # También intentar binarización adaptativa como alternativa
        binary_adaptive = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Usar la que tenga mejor contraste (varianza)
        var_otsu = cv2.Laplacian(binary_otsu, cv2.CV_64F).var()
        var_adaptive = cv2.Laplacian(binary_adaptive, cv2.CV_64F).var()

        binary = binary_otsu if var_otsu > var_adaptive else binary_adaptive

        return binary

    def _remove_artifacts(self, region: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        Intenta remover artefactos como logos y símbolos.

        Args:
            region (np.ndarray): Región en BGR

        Returns:
            Tuple[np.ndarray, bool]: (región limpia, si se removieron artefactos)
        """
        try:
            # Convertir a escala de grises
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

            # Detectar contornos grandes (logos, símbolos)
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Si hay muchos contornos pequeños, es probable que haya artefactos
            small_contours = [c for c in contours if cv2.contourArea(c) < 100]

            if len(small_contours) > 5:
                # Aplicar morphological operations para limpiar
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
                cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)

                # Convertir de vuelta a BGR
                cleaned_bgr = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)
                return cleaned_bgr, True

            return region, False

        except Exception as e:
            logger.debug(f"Error removiendo artefactos: {e}")
            return region, False

    def _detect_duplicate_numbers(self, detected_number: str, confidence: float) -> Tuple[bool, float]:
        """
        Detecta si el número detectado es un duplicado (ej: 11 vs 1 rotado).

        Args:
            detected_number (str): Número detectado
            confidence (float): Confianza de la detección

        Returns:
            Tuple[bool, float]: (es_duplicado, confianza_de_duplicado)
        """
        # Detectar patrones sospechosos
        if not detected_number:
            return False, 0.0

        # Si es un número de un dígito repetido (11, 22, 33, etc.)
        if len(detected_number) == 2 and detected_number[0] == detected_number[1]:
            digit = detected_number[0]

            # Verificar si este dígito es confundible cuando se rota
            if digit in self.CONFUSING_PAIRS:
                # Si confianza es baja, es más probable que sea un error
                if confidence < 0.75:
                    # Calcular confianza de duplicado: número repetido + baja confianza = probable error
                    duplicate_confidence = 1.0 - confidence
                    return True, duplicate_confidence

        return False, 0.0

    def extract_number_region(
        self,
        bbox: List[float],
        frame: np.ndarray,
        region_height: float = 0.5
    ) -> Optional[np.ndarray]:
        """
        Extrae región optimizada de números (ROI más pequeño).

        Args:
            bbox (List[float]): Bounding box [x1, y1, x2, y2]
            frame (np.ndarray): Frame en BGR
            region_height (float): Proporción de altura a usar

        Returns:
            Optional[np.ndarray]: Región extraída o None
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

            # ROI más pequeño y centrado en el número
            bbox_height = y2 - y1
            bbox_width = x2 - x1

            # Número típicamente está en el centro vertical (35%-70% de la camiseta)
            region_y1 = y1 + int(bbox_height * 0.30)
            region_y2 = region_y1 + int(bbox_height * region_height)

            # Centrar horizontalmente
            region_x1 = x1 + int(bbox_width * 0.15)
            region_x2 = region_x1 + int(bbox_width * 0.70)

            # Limitar al frame
            region_x2 = min(region_x2, x2)
            region_y2 = min(region_y2, y2)

            if region_x2 <= region_x1 or region_y2 <= region_y1:
                return None

            roi = frame[region_y1:region_y2, region_x1:region_x2].copy()

            if roi.size == 0:
                self.detection_stats['empty_regions'] += 1
                return None

            return roi

        except Exception as e:
            logger.debug(f"Error extrayendo región: {e}")
            return None

    def recognize_number(self, region: np.ndarray) -> JerseyDetectionResult:
        """
        Reconoce número usando OCR multi-motor con fallback.

        Args:
            region (np.ndarray): Región de camiseta

        Returns:
            JerseyDetectionResult: Resultado de detección
        """
        self.detection_stats['total_detections'] += 1

        if region is None or region.size == 0:
            self.detection_stats['empty_regions'] += 1
            return JerseyDetectionResult(number=None, confidence=0.0)

        # Verificar cache
        cached = self._check_cache(region)
        if cached is not None:
            return JerseyDetectionResult(
                number=cached.number,
                confidence=cached.confidence,
                ocr_engine=cached.engine,
                is_valid=cached.number in self.VALID_NUMBERS if cached.number else False
            )

        # Remover artefactos
        cleaned_region, artifacts_removed = self._remove_artifacts(region)
        if artifacts_removed:
            self.detection_stats['artifact_removals'] += 1
            region = cleaned_region

        # Detectar y corregir ángulo
        angle, corrected_region = self._detect_jersey_angle(region)
        angle_corrected = angle != 0.0
        if angle_corrected:
            self.detection_stats['angle_corrections'] += 1
            region = corrected_region

        # Preprocesar
        processed = self._apply_advanced_preprocessing(region)

        # Intentar con cada motor OCR en orden de prioridad
        for engine in self.ocr_priority:
            try:
                result = self._recognize_with_engine(processed, engine)

                if result and result.number:
                    # Validar confianza
                    if result.confidence < self.confidence_threshold:
                        self.detection_stats['confidence_rejected'] += 1
                        continue

                    # Detectar duplicados
                    is_duplicate, duplicate_conf = self._detect_duplicate_numbers(
                        result.number,
                        result.confidence
                    )
                    if is_duplicate:
                        self.detection_stats['duplicate_detections'] += 1
                        result.duplicate_confidence = duplicate_conf
                        # No rechazar, pero marcar como sospechoso
                        logger.debug(f"Número sospechoso detectado: {result.number}")

                    # Validar número
                    if self._is_valid_number(result.number):
                        self.detection_stats['successful_ocr'] += 1
                        self.detection_stats['valid_numbers'] += 1
                        self.detection_stats['engine_usage'][engine] += 1
                        result.angle_corrected = angle_corrected
                        result.detected_angle = angle
                        result.artifact_cleaned = artifacts_removed
                        result.is_valid = True
                        result.ocr_engine = engine

                        # Añadir a cache
                        self._add_to_cache(region, result.number, result.confidence, engine)

                        return result

                # Si no es válido pero tenemos algo, continuar con siguiente engine
                if result and result.number:
                    logger.debug(f"Número inválido con {engine}: {result.number}")
                    continue

            except Exception as e:
                logger.debug(f"Error con {engine}: {e}")
                self.detection_stats['ocr_failures'] += 1
                continue

        self.detection_stats['successful_ocr'] += 1
        return JerseyDetectionResult(
            number=None,
            confidence=0.0,
            angle_corrected=angle_corrected,
            detected_angle=angle,
            artifact_cleaned=artifacts_removed
        )

    def _recognize_with_engine(self, processed: np.ndarray, engine: str) -> Optional[JerseyDetectionResult]:
        """Reconoce número con un engine específico."""

        if engine == 'paddle':
            return self._recognize_paddle(processed)
        elif engine == 'easyocr':
            return self._recognize_easyocr(processed)
        elif engine == 'tesseract':
            return self._recognize_tesseract(processed)

        return None

    def _recognize_paddle(self, processed: np.ndarray) -> Optional[JerseyDetectionResult]:
        """Reconoce con PaddleOCR."""
        if 'paddle' not in self.ocr_models:
            return None

        try:
            result = self.ocr_models['paddle'].ocr(processed, cls=True)

            if not result or not result[0]:
                return None

            # Obtener mejor detección
            detections = [(item[1][0], item[1][1]) for item in result[0]]
            detections.sort(key=lambda x: x[1], reverse=True)

            for text, confidence in detections:
                cleaned = ''.join(c for c in text if c.isdigit())
                if cleaned:
                    return JerseyDetectionResult(
                        number=cleaned,
                        confidence=float(confidence),
                        ocr_engine="paddle",
                        raw_text=text
                    )

            return None

        except Exception as e:
            logger.debug(f"Error con PaddleOCR: {e}")
            return None

    def _recognize_easyocr(self, processed: np.ndarray) -> Optional[JerseyDetectionResult]:
        """Reconoce con EasyOCR."""
        if 'easyocr' not in self.ocr_models:
            return None

        try:
            result = self.ocr_models['easyocr'].readtext(processed)

            if not result:
                return None

            # Obtener mejor detección
            detections = [(item[1], item[2]) for item in result]
            detections.sort(key=lambda x: x[1], reverse=True)

            for text, confidence in detections:
                cleaned = ''.join(c for c in text if c.isdigit())
                if cleaned:
                    return JerseyDetectionResult(
                        number=cleaned,
                        confidence=float(confidence),
                        ocr_engine="easyocr",
                        raw_text=text
                    )

            return None

        except Exception as e:
            logger.debug(f"Error con EasyOCR: {e}")
            return None

    def _recognize_tesseract(self, processed: np.ndarray) -> Optional[JerseyDetectionResult]:
        """Reconoce con Tesseract."""
        if 'tesseract' not in self.ocr_models:
            return None

        try:
            # Convertir a RGB para Tesseract
            rgb = cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB)

            # Usar Tesseract con configuración optimizada para números
            data = pytesseract.image_to_data(
                rgb,
                output_type=pytesseract.Output.DICT,
                config='--psm 6 -c tessedit_char_whitelist=0123456789'
            )

            if not data or not data['text']:
                return None

            # Procesar resultados
            for text, conf in zip(data['text'], data['confidence']):
                if text and int(conf) > 0:
                    cleaned = ''.join(c for c in text if c.isdigit())
                    if cleaned:
                        return JerseyDetectionResult(
                            number=cleaned,
                            confidence=float(conf) / 100.0,
                            ocr_engine="tesseract",
                            raw_text=text
                        )

            return None

        except Exception as e:
            logger.debug(f"Error con Tesseract: {e}")
            return None

    def detect(self, player_boxes: List[List[float]], frame: np.ndarray, parallel: bool = True) -> Dict:
        """
        Detecta números en todos los jugadores (con opción de paralelización).

        Args:
            player_boxes (List[List[float]]): Lista de bboxes
            frame (np.ndarray): Frame en BGR
            parallel (bool): Usar paralelización

        Returns:
            dict: Resultados de detección
        """
        if parallel and len(player_boxes) > 1:
            return self._detect_parallel(player_boxes, frame)
        else:
            return self._detect_sequential(player_boxes, frame)

    def _detect_sequential(self, player_boxes: List[List[float]], frame: np.ndarray) -> Dict:
        """Detección secuencial."""
        numbers = []
        confidences = []
        regions = []
        valid_flags = []
        details = []

        for bbox in player_boxes:
            region = self.extract_number_region(bbox, frame)
            result = self.recognize_number(region)

            numbers.append(result.number)
            confidences.append(result.confidence)
            regions.append(result.region)
            valid_flags.append(result.is_valid)
            details.append({
                'angle_corrected': result.angle_corrected,
                'detected_angle': result.detected_angle,
                'artifact_cleaned': result.artifact_cleaned,
                'duplicate_confidence': result.duplicate_confidence,
                'ocr_engine': result.ocr_engine
            })

        return {
            'numbers': numbers,
            'confidences': confidences,
            'raw_regions': regions,
            'is_valid': valid_flags,
            'details': details,
            'ocr_engines': self.ocr_priority
        }

    def _detect_parallel(self, player_boxes: List[List[float]], frame: np.ndarray) -> Dict:
        """Detección parallelizada."""
        numbers = [None] * len(player_boxes)
        confidences = [0.0] * len(player_boxes)
        regions = [None] * len(player_boxes)
        valid_flags = [False] * len(player_boxes)
        details = [{}] * len(player_boxes)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for idx, bbox in enumerate(player_boxes):
                region = self.extract_number_region(bbox, frame)
                future = executor.submit(self.recognize_number, region)
                futures[future] = (idx, region)

            for future in as_completed(futures):
                idx, region = futures[future]
                try:
                    result = future.result()
                    numbers[idx] = result.number
                    confidences[idx] = result.confidence
                    regions[idx] = result.region
                    valid_flags[idx] = result.is_valid
                    details[idx] = {
                        'angle_corrected': result.angle_corrected,
                        'detected_angle': result.detected_angle,
                        'artifact_cleaned': result.artifact_cleaned,
                        'duplicate_confidence': result.duplicate_confidence,
                        'ocr_engine': result.ocr_engine
                    }
                except Exception as e:
                    logger.error(f"Error en worker para índice {idx}: {e}")

        return {
            'numbers': numbers,
            'confidences': confidences,
            'raw_regions': regions,
            'is_valid': valid_flags,
            'details': details,
            'ocr_engines': self.ocr_priority
        }

    def _is_valid_number(self, text: str) -> bool:
        """Valida número (0-99)."""
        if not text or not text.isdigit():
            return False
        return len(text) <= 2 and text in self.VALID_NUMBERS

    def get_statistics(self) -> Dict:
        """Retorna estadísticas mejoradas."""
        total = self.detection_stats['total_detections']
        successful = self.detection_stats['successful_ocr']
        valid = self.detection_stats['valid_numbers']

        success_rate = (successful / total) if total > 0 else 0.0
        validity_rate = (valid / successful) if successful > 0 else 0.0
        accuracy = (valid / total) if total > 0 else 0.0

        return {
            'ocr_engines': self.ocr_priority,
            'total_detections': total,
            'successful_ocr': successful,
            'valid_numbers': valid,
            'accuracy_rate': float(accuracy),
            'success_rate': float(success_rate),
            'validity_rate': float(validity_rate),
            'cache_hits': self.detection_stats['cache_hits'],
            'angle_corrections': self.detection_stats['angle_corrections'],
            'duplicate_detections': self.detection_stats['duplicate_detections'],
            'artifact_removals': self.detection_stats['artifact_removals'],
            'confidence_rejected': self.detection_stats['confidence_rejected'],
            'empty_regions': self.detection_stats['empty_regions'],
            'ocr_failures': self.detection_stats['ocr_failures'],
            'engine_usage': dict(self.detection_stats['engine_usage']),
            'confidence_threshold': self.confidence_threshold
        }

    def reset(self):
        """Reinicia detector."""
        self.detection_stats = {
            'total_detections': 0,
            'successful_ocr': 0,
            'valid_numbers': 0,
            'empty_regions': 0,
            'ocr_failures': 0,
            'cache_hits': 0,
            'angle_corrections': 0,
            'duplicate_detections': 0,
            'artifact_removals': 0,
            'engine_usage': defaultdict(int),
            'confidence_rejected': 0
        }
        self.ocr_cache.clear()
        self.cache_queue.clear()

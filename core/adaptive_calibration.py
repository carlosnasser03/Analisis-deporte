"""
adaptive_calibration.py - Análisis adaptativo de video y ajuste automático de parámetros

Propósito: Analizar calidad de video (brillo, blur, oclusión, clima) y ajustar
parámetros de detección automáticamente sin necesidad de SLM. 100% offline.

Uso:
    analyzer = VideoQualityAnalyzer(sample_frames=10)
    metrics = analyzer.analyze_video('path/to/video.mp4')

    calibrator = AdaptiveCalibration()
    config = calibrator.get_optimal_config(metrics)
"""

import logging
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum


# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(name)s: %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


# ============================================================================
# ENUMS Y TIPOS DE DATOS
# ============================================================================

class LightingCondition(Enum):
    """Condiciones de iluminación detectadas"""
    NORMAL = "NORMAL"
    DARK = "DARK"
    BRIGHT = "BRIGHT"
    VARIABLE = "VARIABLE"


class WeatherCondition(Enum):
    """Condiciones climáticas detectadas"""
    CLEAR = "CLEAR"
    RAIN = "RAIN"
    FOG = "FOG"


class VideoQuality(Enum):
    """Calidad general del video"""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"


@dataclass
class VideoQualityMetrics:
    """Métricas de calidad de video"""
    brightness: float  # 0-255
    brightness_std: float  # Desviación estándar
    blur_level: float  # 0-1 (0=nítido, 1=muy borroso)
    motion_blur: float  # 0-1
    occlusion_rate: float  # 0-1 (porcentaje de píxeles oscuros)
    lighting_condition: LightingCondition
    weather_condition: WeatherCondition
    crowd_density: float  # 0-1
    video_quality: VideoQuality
    analysis_frames: int
    frame_rate: float

    def to_dict(self) -> Dict:
        """Convierte a diccionario para almacenamiento"""
        data = asdict(self)
        data['lighting_condition'] = self.lighting_condition.value
        data['weather_condition'] = self.weather_condition.value
        data['video_quality'] = self.video_quality.value
        return data


@dataclass
class ProcessingConfig:
    """Configuración de procesamiento adaptada"""
    confidence_threshold: float  # 0.45-0.75
    gk_sensitivity: float  # 0.8-1.3
    tracker_max_distance: float  # 50-150 píxeles
    skip_frames: int  # 1-5
    use_motion_blur: bool
    quality_report: str  # Resumen de ajustes realizados

    def to_dict(self) -> Dict:
        """Convierte a diccionario"""
        return asdict(self)


# ============================================================================
# ANALIZADOR DE CALIDAD DE VIDEO
# ============================================================================

class VideoQualityAnalyzer:
    """
    Analiza frames de video para determinar calidad y condiciones.
    Utiliza técnicas de visión por computadora sin modelos entrenados.
    """

    # Constantes de análisis
    MIN_BRIGHTNESS = 20  # Muy oscuro
    MAX_BRIGHTNESS = 235  # Muy claro
    BLUR_THRESHOLD = 100  # Laplacian variance threshold
    OCCLUSION_THRESHOLD = 0.4  # 40% de píxeles oscuros

    def __init__(self, sample_frames: int = 10):
        """
        Args:
            sample_frames (int): Número de frames para muestrear del video
        """
        self.sample_frames = sample_frames
        logger.info(f"Inicializando VideoQualityAnalyzer (sample_frames={sample_frames})")

    def analyze_video(self, video_path: str) -> Optional[VideoQualityMetrics]:
        """
        Analiza un video completo para obtener métricas de calidad.

        Args:
            video_path (str): Ruta al archivo de video

        Returns:
            VideoQualityMetrics: Métricas de calidad o None si falla

        Raises:
            FileNotFoundError: Si el video no existe
            ValueError: Si el video no se puede leer
        """
        video_path = Path(video_path)

        if not video_path.exists():
            logger.error(f"Video no encontrado: {video_path}")
            raise FileNotFoundError(f"Video no encontrado: {video_path}")

        logger.info(f"Analizando video: {video_path.name}")

        # Abrir video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"No se pudo abrir el video: {video_path}")
            raise ValueError(f"No se pudo abrir el video: {video_path}")

        try:
            # Obtener información del video
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            frame_rate = cap.get(cv2.CAP_PROP_FPS)

            if total_frames == 0:
                logger.warning("El video no tiene frames o no se pudo leer el total")
                total_frames = 1

            logger.debug(f"Video: {total_frames} frames, {frame_rate:.1f} fps")

            # Determinar frames a muestrear
            frame_indices = self._get_sample_frame_indices(total_frames)
            logger.debug(f"Muestreando frames: {frame_indices}")

            # Analizar cada frame
            brightness_values = []
            blur_values = []
            motion_blur_values = []
            occlusion_values = []
            crowd_density_values = []

            prev_frame = None

            for idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()

                if not ret or frame is None:
                    logger.warning(f"No se pudo leer frame {idx}")
                    continue

                # Análisis de este frame
                brightness = self._calculate_brightness(frame)
                brightness_values.append(brightness)

                blur = self._detect_blur(frame)
                blur_values.append(blur)

                if prev_frame is not None:
                    motion_blur = self._detect_motion_blur(prev_frame, frame)
                    motion_blur_values.append(motion_blur)

                occlusion = self._estimate_occlusion(frame)
                occlusion_values.append(occlusion)

                crowd = self._estimate_crowd_density(frame)
                crowd_density_values.append(crowd)

                prev_frame = frame.copy()

                logger.debug(
                    f"Frame {idx}: brightness={brightness:.1f}, "
                    f"blur={blur:.3f}, occlusion={occlusion:.2f}"
                )

            # Agregación de métricas
            if not brightness_values:
                logger.warning("No se pudieron analizar frames. Retornando None")
                return None

            brightness_mean = float(np.mean(brightness_values))
            brightness_std = float(np.std(brightness_values))
            blur_level = float(np.mean(blur_values))
            motion_blur = float(np.mean(motion_blur_values)) if motion_blur_values else 0.0
            occlusion_rate = float(np.mean(occlusion_values))
            crowd_density = float(np.mean(crowd_density_values))

            # Clasificación de condiciones
            lighting = self._classify_lighting(brightness_mean, brightness_std)
            weather = self._detect_weather(blur_values, occlusion_values)
            quality = self._classify_quality(
                brightness_mean, blur_level, occlusion_rate, crowd_density
            )

            logger.info(
                f"Análisis completado - "
                f"Brillo: {brightness_mean:.1f}, "
                f"Blur: {blur_level:.3f}, "
                f"Calidad: {quality.value}"
            )

            return VideoQualityMetrics(
                brightness=brightness_mean,
                brightness_std=brightness_std,
                blur_level=blur_level,
                motion_blur=motion_blur,
                occlusion_rate=occlusion_rate,
                lighting_condition=lighting,
                weather_condition=weather,
                crowd_density=crowd_density,
                video_quality=quality,
                analysis_frames=len(brightness_values),
                frame_rate=frame_rate
            )

        finally:
            cap.release()
            logger.debug("Video liberado")

    # ========================================================================
    # MÉTODOS HELPER - ANÁLISIS INDIVIDUAL
    # ========================================================================

    def _calculate_brightness(self, frame: np.ndarray) -> float:
        """
        Calcula el brillo promedio de un frame usando histograma.

        Args:
            frame: Imagen BGR de OpenCV

        Returns:
            Brillo promedio (0-255)
        """
        try:
            # Convertir a escala de grises
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Calcular promedio (equivalente a calcular el brillo medio)
            brightness = float(np.mean(gray))

            return brightness
        except Exception as e:
            logger.warning(f"Error calculando brillo: {e}")
            return 127.0  # Valor por defecto

    def _detect_blur(self, frame: np.ndarray) -> float:
        """
        Detecta blur usando Laplacian variance method.

        Args:
            frame: Imagen BGR

        Returns:
            Nivel de blur (0-1, donde 0 es nítido y 1 es muy borroso)
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Calcular varianza de Laplacian
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

            # Normalizar a rango 0-1
            # Asumir que valores < 100 = blur, valores > 500 = nítido
            blur_level = max(0.0, min(1.0, 1.0 - (laplacian_var / 500.0)))

            return float(blur_level)
        except Exception as e:
            logger.warning(f"Error detectando blur: {e}")
            return 0.5  # Valor por defecto

    def _detect_motion_blur(
        self, frame1: np.ndarray, frame2: np.ndarray
    ) -> float:
        """
        Detecta motion blur comparando dos frames consecutivos.

        Args:
            frame1: Frame anterior
            frame2: Frame actual

        Returns:
            Nivel de motion blur (0-1)
        """
        try:
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

            # Calcular diferencia entre frames
            diff = cv2.absdiff(gray1, gray2)

            # Calcular porcentaje de píxeles que cambiaron
            threshold = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)[1]
            changed_pixels = np.sum(threshold) / threshold.size

            # Motion blur es proporcional al cambio entre frames
            motion_blur = float(min(1.0, changed_pixels * 2.0))

            return motion_blur
        except Exception as e:
            logger.warning(f"Error detectando motion blur: {e}")
            return 0.0

    def _estimate_occlusion(self, frame: np.ndarray) -> float:
        """
        Estima oclusión detectando áreas muy oscuras.

        Args:
            frame: Imagen BGR

        Returns:
            Tasa de oclusión (0-1)
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Contar píxeles oscuros (< 50)
            dark_pixels = np.sum(gray < 50)
            total_pixels = gray.size

            occlusion_rate = float(dark_pixels / total_pixels)

            return occlusion_rate
        except Exception as e:
            logger.warning(f"Error estimando oclusión: {e}")
            return 0.0

    def _detect_weather(
        self, blur_values: List[float], occlusion_values: List[float]
    ) -> WeatherCondition:
        """
        Detecta condiciones climáticas basándose en blur y oclusión.

        Args:
            blur_values: Lista de valores de blur
            occlusion_values: Lista de valores de oclusión

        Returns:
            Condición climática detectada
        """
        try:
            if not blur_values or not occlusion_values:
                return WeatherCondition.CLEAR

            avg_blur = np.mean(blur_values)
            avg_occlusion = np.mean(occlusion_values)

            # Heurística: FOG si hay alto blur y oclusión
            if avg_blur > 0.6 and avg_occlusion > 0.3:
                logger.debug("Detectada niebla (alto blur + oclusión)")
                return WeatherCondition.FOG

            # Heurística: RAIN si hay alto blur pero oclusión moderada
            if avg_blur > 0.5 and 0.15 < avg_occlusion < 0.4:
                logger.debug("Detectada lluvia (blur moderado-alto)")
                return WeatherCondition.RAIN

            logger.debug("Condición climática: CLEAR")
            return WeatherCondition.CLEAR
        except Exception as e:
            logger.warning(f"Error detectando clima: {e}")
            return WeatherCondition.CLEAR

    def _classify_lighting(
        self, brightness: float, brightness_std: float
    ) -> LightingCondition:
        """
        Clasifica la condición de iluminación.

        Args:
            brightness: Brillo promedio
            brightness_std: Desviación estándar de brillo

        Returns:
            Condición de iluminación
        """
        try:
            # DARK: brillo muy bajo
            if brightness < 60:
                logger.debug(f"Iluminación: DARK (brightness={brightness:.1f})")
                return LightingCondition.DARK

            # BRIGHT: brillo muy alto
            if brightness > 180:
                logger.debug(f"Iluminación: BRIGHT (brightness={brightness:.1f})")
                return LightingCondition.BRIGHT

            # VARIABLE: alta desviación estándar (iluminación inconsistente)
            if brightness_std > 60:
                logger.debug(
                    f"Iluminación: VARIABLE (std={brightness_std:.1f})"
                )
                return LightingCondition.VARIABLE

            logger.debug("Iluminación: NORMAL")
            return LightingCondition.NORMAL
        except Exception as e:
            logger.warning(f"Error clasificando iluminación: {e}")
            return LightingCondition.NORMAL

    def _classify_quality(
        self,
        brightness: float,
        blur_level: float,
        occlusion_rate: float,
        crowd_density: float,
    ) -> VideoQuality:
        """
        Clasifica la calidad general del video.

        Args:
            brightness: Brillo promedio
            blur_level: Nivel de blur (0-1)
            occlusion_rate: Tasa de oclusión
            crowd_density: Densidad de multitud

        Returns:
            Clasificación de calidad
        """
        try:
            # Contar problemas
            problems = 0

            # Brillo
            if brightness < 40 or brightness > 200:
                problems += 1

            # Blur
            if blur_level > 0.6:
                problems += 2

            # Oclusión
            if occlusion_rate > 0.4:
                problems += 1

            # Densidad de multitud muy alta
            if crowd_density > 0.8:
                problems += 1

            # Clasificar según problemas
            if problems == 0:
                quality = VideoQuality.EXCELLENT
            elif problems == 1:
                quality = VideoQuality.GOOD
            elif problems <= 2:
                quality = VideoQuality.FAIR
            else:
                quality = VideoQuality.POOR

            logger.debug(
                f"Calidad: {quality.value} (problems={problems}, "
                f"brightness={brightness:.1f}, blur={blur_level:.3f})"
            )

            return quality
        except Exception as e:
            logger.warning(f"Error clasificando calidad: {e}")
            return VideoQuality.FAIR

    def _estimate_crowd_density(self, frame: np.ndarray) -> float:
        """
        Estima la densidad de multitud/píxeles en movimiento.

        Args:
            frame: Imagen BGR

        Returns:
            Densidad (0-1)
        """
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Aplicar blur para encontrar regiones densas
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Detectar bordes (áreas con actividad)
            edges = cv2.Canny(blurred, 50, 150)

            # Densidad = porcentaje de píxeles con bordes
            density = float(np.sum(edges > 0) / edges.size)

            return density
        except Exception as e:
            logger.warning(f"Error estimando densidad de multitud: {e}")
            return 0.5

    def _get_sample_frame_indices(self, total_frames: int) -> List[int]:
        """
        Determina qué frames muestrear del video.

        Args:
            total_frames: Total de frames en el video

        Returns:
            Lista de índices de frames a muestrear
        """
        if total_frames <= self.sample_frames:
            # Si hay pocos frames, tomar todos
            return list(range(total_frames))

        # Distribuir uniformemente
        indices = np.linspace(0, total_frames - 1, self.sample_frames, dtype=int)
        return list(indices)


# ============================================================================
# CALIBRACIÓN ADAPTATIVA
# ============================================================================

class AdaptiveCalibration:
    """
    Ajusta parámetros de procesamiento basándose en métricas de calidad de video.
    """

    # Valores por defecto (baseline)
    DEFAULT_CONFIDENCE_THRESHOLD = 0.55
    DEFAULT_GK_SENSITIVITY = 1.0
    DEFAULT_TRACKER_MAX_DISTANCE = 100
    DEFAULT_SKIP_FRAMES = 1
    DEFAULT_USE_MOTION_BLUR = False

    def __init__(self):
        """Inicializa el calibrador"""
        logger.info("Inicializando AdaptiveCalibration")

    def get_optimal_config(
        self, quality_metrics: VideoQualityMetrics
    ) -> ProcessingConfig:
        """
        Genera configuración óptima basada en métricas de calidad.

        Args:
            quality_metrics: Métricas del video (VideoQualityMetrics o dict)

        Returns:
            Configuración de procesamiento ajustada
        """
        # Convertir dict a dataclass si es necesario
        if isinstance(quality_metrics, dict):
            quality_metrics = self._dict_to_metrics(quality_metrics)

        logger.info(
            f"Calibrando parámetros - "
            f"Calidad: {quality_metrics.video_quality.value}, "
            f"Brillo: {quality_metrics.brightness:.1f}"
        )

        # Inicializar con valores por defecto
        config = ProcessingConfig(
            confidence_threshold=self.DEFAULT_CONFIDENCE_THRESHOLD,
            gk_sensitivity=self.DEFAULT_GK_SENSITIVITY,
            tracker_max_distance=self.DEFAULT_TRACKER_MAX_DISTANCE,
            skip_frames=self.DEFAULT_SKIP_FRAMES,
            use_motion_blur=self.DEFAULT_USE_MOTION_BLUR,
            quality_report="",
        )

        # Aplicar ajustes basados en condiciones
        adjustments = []

        # =====================================================================
        # AJUSTE 1: Brillo muy bajo (< 50)
        # =====================================================================
        if quality_metrics.brightness < 50:
            config.confidence_threshold -= 0.15
            config.gk_sensitivity += 0.2
            adjustments.append(
                f"Brillo bajo ({quality_metrics.brightness:.1f}): "
                f"↓ conf_threshold, ↑ gk_sensitivity"
            )
            logger.debug("Ajuste: Brillo bajo")

        # =====================================================================
        # AJUSTE 2: Blur alto (> 0.5)
        # =====================================================================
        if quality_metrics.blur_level > 0.5:
            config.tracker_max_distance += 30
            config.skip_frames = max(config.skip_frames, 2)
            adjustments.append(
                f"Blur alto ({quality_metrics.blur_level:.3f}): "
                f"↑ tracker_max_distance, ↑ skip_frames"
            )
            logger.debug("Ajuste: Blur alto")

        # =====================================================================
        # AJUSTE 3: Oclusión alta (> 0.4)
        # =====================================================================
        if quality_metrics.occlusion_rate > 0.4:
            config.gk_sensitivity += 0.15
            config.confidence_threshold -= 0.10
            adjustments.append(
                f"Oclusión alta ({quality_metrics.occlusion_rate:.2f}): "
                f"↑ gk_sensitivity, ↓ conf_threshold"
            )
            logger.debug("Ajuste: Oclusión alta")

        # =====================================================================
        # AJUSTE 4: Iluminación variable
        # =====================================================================
        if quality_metrics.lighting_condition == LightingCondition.VARIABLE:
            config.use_motion_blur = True
            config.skip_frames = max(config.skip_frames, 2)
            adjustments.append(
                "Iluminación variable: "
                "✓ motion_blur, ↑ skip_frames"
            )
            logger.debug("Ajuste: Iluminación variable")

        # =====================================================================
        # AJUSTE 5: Clima adverso (lluvia/niebla)
        # =====================================================================
        if quality_metrics.weather_condition in [
            WeatherCondition.RAIN, WeatherCondition.FOG
        ]:
            config.gk_sensitivity += 0.1
            config.tracker_max_distance += 20
            adjustments.append(
                f"Clima adverso ({quality_metrics.weather_condition.value}): "
                f"↑ gk_sensitivity, ↑ tracker_max_distance"
            )
            logger.debug(f"Ajuste: Clima adverso ({quality_metrics.weather_condition.value})")

        # =====================================================================
        # AJUSTE 6: Motion blur alto
        # =====================================================================
        if quality_metrics.motion_blur > 0.5:
            config.skip_frames = max(config.skip_frames, 3)
            config.tracker_max_distance += 20
            adjustments.append(
                f"Motion blur alto ({quality_metrics.motion_blur:.3f}): "
                f"↑↑ skip_frames, ↑ tracker_max_distance"
            )
            logger.debug("Ajuste: Motion blur alto")

        # =====================================================================
        # AJUSTE 7: Calidad POOR
        # =====================================================================
        if quality_metrics.video_quality == VideoQuality.POOR:
            config.skip_frames = max(config.skip_frames, 3)
            config.confidence_threshold -= 0.25
            config.gk_sensitivity += 0.15
            adjustments.append(
                "Calidad POOR: "
                "↑↑ skip_frames, ↓↓ conf_threshold, ↑ gk_sensitivity"
            )
            logger.debug("Ajuste: Calidad POOR")

        # =====================================================================
        # AJUSTE 8: Densidad de multitud muy alta (oclusión por multitud)
        # =====================================================================
        if quality_metrics.crowd_density > 0.7:
            config.gk_sensitivity += 0.1
            config.confidence_threshold -= 0.05
            adjustments.append(
                f"Multitud densa ({quality_metrics.crowd_density:.2f}): "
                f"↑ gk_sensitivity, ↓ conf_threshold"
            )
            logger.debug("Ajuste: Multitud densa")

        # =====================================================================
        # CLAMPEAR VALORES AL RANGO VÁLIDO
        # =====================================================================
        config.confidence_threshold = self._clamp(
            config.confidence_threshold, 0.45, 0.75
        )
        config.gk_sensitivity = self._clamp(
            config.gk_sensitivity, 0.8, 1.3
        )
        config.tracker_max_distance = self._clamp(
            config.tracker_max_distance, 50, 150
        )
        config.skip_frames = self._clamp(
            config.skip_frames, 1, 5
        )

        # =====================================================================
        # GENERAR REPORTE
        # =====================================================================
        report = self._generate_report(quality_metrics, config, adjustments)
        config.quality_report = report

        logger.info(
            f"Configuración generada: "
            f"conf_threshold={config.confidence_threshold:.3f}, "
            f"gk_sensitivity={config.gk_sensitivity:.3f}, "
            f"skip_frames={config.skip_frames}"
        )

        return config

    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Limita un valor a un rango [min, max]"""
        return max(min_val, min(max_val, value))

    def _generate_report(
        self,
        metrics: VideoQualityMetrics,
        config: ProcessingConfig,
        adjustments: List[str],
    ) -> str:
        """
        Genera un reporte de ajustes realizados.

        Args:
            metrics: Métricas de entrada
            config: Configuración generada
            adjustments: Lista de ajustes aplicados

        Returns:
            Reporte en formato texto
        """
        lines = [
            "=" * 70,
            "REPORTE DE CALIBRACIÓN ADAPTATIVA",
            "=" * 70,
            "",
            "MÉTRICAS DE ENTRADA:",
            f"  - Calidad general: {metrics.video_quality.value}",
            f"  - Brillo: {metrics.brightness:.1f} (±{metrics.brightness_std:.1f})",
            f"  - Blur: {metrics.blur_level:.3f}",
            f"  - Motion blur: {metrics.motion_blur:.3f}",
            f"  - Oclusión: {metrics.occlusion_rate:.2f}",
            f"  - Iluminación: {metrics.lighting_condition.value}",
            f"  - Clima: {metrics.weather_condition.value}",
            f"  - Densidad de multitud: {metrics.crowd_density:.2f}",
            f"  - Frames analizados: {metrics.analysis_frames}",
            f"  - Frame rate: {metrics.frame_rate:.1f} fps",
            "",
            "AJUSTES APLICADOS:",
        ]

        if adjustments:
            for adj in adjustments:
                lines.append(f"  ✓ {adj}")
        else:
            lines.append("  - Sin ajustes necesarios (video de buena calidad)")

        lines.extend([
            "",
            "CONFIGURACIÓN RESULTANTE:",
            f"  - confidence_threshold: {config.confidence_threshold:.3f}",
            f"  - gk_sensitivity: {config.gk_sensitivity:.3f}",
            f"  - tracker_max_distance: {config.tracker_max_distance:.1f}px",
            f"  - skip_frames: {config.skip_frames}",
            f"  - use_motion_blur: {config.use_motion_blur}",
            "=" * 70,
        ])

        return "\n".join(lines)

    def _dict_to_metrics(self, data: Dict) -> VideoQualityMetrics:
        """
        Convierte diccionario a VideoQualityMetrics.
        Útil para deserialización.

        Args:
            data: Diccionario con métricas

        Returns:
            VideoQualityMetrics
        """
        # Convertir valores de enum si son strings
        lighting = data.get('lighting_condition', 'NORMAL')
        if isinstance(lighting, str):
            lighting = LightingCondition[lighting]

        weather = data.get('weather_condition', 'CLEAR')
        if isinstance(weather, str):
            weather = WeatherCondition[weather]

        quality = data.get('video_quality', 'FAIR')
        if isinstance(quality, str):
            quality = VideoQuality[quality]

        return VideoQualityMetrics(
            brightness=float(data.get('brightness', 127.0)),
            brightness_std=float(data.get('brightness_std', 30.0)),
            blur_level=float(data.get('blur_level', 0.3)),
            motion_blur=float(data.get('motion_blur', 0.1)),
            occlusion_rate=float(data.get('occlusion_rate', 0.1)),
            lighting_condition=lighting,
            weather_condition=weather,
            crowd_density=float(data.get('crowd_density', 0.3)),
            video_quality=quality,
            analysis_frames=int(data.get('analysis_frames', 10)),
            frame_rate=float(data.get('frame_rate', 25.0)),
        )


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def analyze_and_calibrate(video_path: str) -> Tuple[VideoQualityMetrics, ProcessingConfig]:
    """
    Analiza un video y retorna configuración calibrada en un paso.

    Función de conveniencia que combina análisis y calibración.

    Args:
        video_path: Ruta al video

    Returns:
        Tupla (VideoQualityMetrics, ProcessingConfig)

    Ejemplo:
        metrics, config = analyze_and_calibrate('video.mp4')
        print(config.quality_report)
    """
    logger.info(f"Iniciando análisis y calibración de: {video_path}")

    # Analizar
    analyzer = VideoQualityAnalyzer(sample_frames=10)
    metrics = analyzer.analyze_video(video_path)

    if metrics is None:
        logger.error("No se pudieron obtener métricas. Retornando config por defecto")
        default_metrics = VideoQualityMetrics(
            brightness=127.0,
            brightness_std=30.0,
            blur_level=0.3,
            motion_blur=0.1,
            occlusion_rate=0.1,
            lighting_condition=LightingCondition.NORMAL,
            weather_condition=WeatherCondition.CLEAR,
            crowd_density=0.3,
            video_quality=VideoQuality.FAIR,
            analysis_frames=0,
            frame_rate=25.0,
        )
        metrics = default_metrics

    # Calibrar
    calibrator = AdaptiveCalibration()
    config = calibrator.get_optimal_config(metrics)

    logger.info("Análisis y calibración completados")

    return metrics, config

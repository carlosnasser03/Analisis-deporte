"""
validators.py - Funciones de validación para el pipeline

Propósito: Proporciona validación exhaustiva de archivos de entrada,
configuración, salida de detecciones y dependencias del sistema.

Características:
- Validación de archivos de video
- Validación de salida de detecciones
- Validación de configuración
- Verificación de dependencias
- Reportes detallados de validación
"""

import os
import cv2
import json
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass


# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de una validación"""
    is_valid: bool
    message: str
    details: Dict[str, Any]
    warnings: List[str]
    errors: List[str]


class VideoValidator:
    """Valida archivos de video"""

    # Formatos soportados
    SUPPORTED_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}

    # Rangos permitidos
    MIN_DURATION_SECONDS = 1
    MAX_DURATION_SECONDS = 3600  # 1 hora
    MIN_WIDTH = 320
    MIN_HEIGHT = 240
    MAX_WIDTH = 8192
    MAX_HEIGHT = 8192
    MIN_FPS = 15
    MAX_FPS = 120

    @staticmethod
    def validate_video_file(video_path: str) -> ValidationResult:
        """
        Valida un archivo de video.

        Args:
            video_path (str): Ruta al archivo de video

        Returns:
            ValidationResult: Resultado de validación detallado

        Example:
            >>> result = VideoValidator.validate_video_file("video.mp4")
            >>> if result.is_valid:
            ...     print("Video válido")
            ... else:
            ...     print(result.message)
        """
        errors = []
        warnings = []
        details = {}

        # 1. Verificar existencia del archivo
        if not os.path.exists(video_path):
            return ValidationResult(
                is_valid=False,
                message=f"Archivo no encontrado: {video_path}",
                details={},
                warnings=[],
                errors=[f"Archivo no encontrado: {video_path}"]
            )

        # 2. Verificar extensión
        file_ext = Path(video_path).suffix.lower()
        if file_ext not in VideoValidator.SUPPORTED_FORMATS:
            errors.append(
                f"Formato no soportado: {file_ext}. "
                f"Formatos permitidos: {VideoValidator.SUPPORTED_FORMATS}"
            )

        # 3. Verificar permisos de lectura
        if not os.access(video_path, os.R_OK):
            errors.append(f"No hay permisos de lectura: {video_path}")

        # 4. Verificar tamaño del archivo
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        details['file_size_mb'] = file_size_mb

        if file_size_mb < 1:
            warnings.append("El archivo es muy pequeño (< 1 MB)")
        if file_size_mb > 5000:  # 5 GB
            warnings.append("El archivo es muy grande (> 5 GB)")

        # 5. Validar contenido del video
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            errors.append(f"No se puede abrir el video con OpenCV")
            return ValidationResult(
                is_valid=False,
                message="Video inválido o corrupto",
                details=details,
                warnings=warnings,
                errors=errors
            )

        # 6. Extraer propiedades del video
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_seconds = total_frames / fps if fps > 0 else 0

        details.update({
            'total_frames': total_frames,
            'fps': fps,
            'width': width,
            'height': height,
            'duration_seconds': duration_seconds,
        })

        # 7. Validar rango de frames
        if total_frames < 30:
            warnings.append(f"Video muy corto: {total_frames} frames")

        # 8. Validar duración
        if duration_seconds < VideoValidator.MIN_DURATION_SECONDS:
            errors.append(f"Duración muy corta: {duration_seconds}s")
        if duration_seconds > VideoValidator.MAX_DURATION_SECONDS:
            errors.append(f"Duración muy larga: {duration_seconds}s")

        # 9. Validar FPS
        if fps < VideoValidator.MIN_FPS or fps > VideoValidator.MAX_FPS:
            warnings.append(f"FPS inusual: {fps} (normal: 15-120)")

        # 10. Validar resolución
        if width < VideoValidator.MIN_WIDTH or height < VideoValidator.MIN_HEIGHT:
            warnings.append(
                f"Resolución baja: {width}x{height} "
                f"(mínimo recomendado: {VideoValidator.MIN_WIDTH}x"
                f"{VideoValidator.MIN_HEIGHT})"
            )
        if width > VideoValidator.MAX_WIDTH or height > VideoValidator.MAX_HEIGHT:
            errors.append(f"Resolución muy alta: {width}x{height}")

        # 11. Intentar leer algunos frames
        frame_read_errors = 0
        for i in range(min(10, total_frames)):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i * (total_frames // 10))
            ret, frame = cap.read()
            if not ret or frame is None:
                frame_read_errors += 1

        if frame_read_errors > 3:
            errors.append(f"Errores al leer frames: {frame_read_errors}/10")

        cap.release()

        # Resultado final
        is_valid = len(errors) == 0

        message = "Video válido" if is_valid else f"Video inválido: {'; '.join(errors)}"

        return ValidationResult(
            is_valid=is_valid,
            message=message,
            details=details,
            warnings=warnings,
            errors=errors
        )


class DetectionValidator:
    """Valida salida de detecciones"""

    @staticmethod
    def validate_detection_output(detections: Dict) -> ValidationResult:
        """
        Valida formato y contenido de salida de detecciones.

        Args:
            detections (Dict): Diccionario de detecciones

        Returns:
            ValidationResult: Resultado de validación

        Example:
            >>> detections = {
            ...     'balls': [{'x': 100, 'y': 100, 'confidence': 0.9}],
            ...     'players': [{'team': 'A', 'bbox': [0, 0, 50, 100]}]
            ... }
            >>> result = DetectionValidator.validate_detection_output(detections)
        """
        errors = []
        warnings = []
        details = {}

        # 1. Verificar estructura básica
        if not isinstance(detections, dict):
            return ValidationResult(
                is_valid=False,
                message="Las detecciones deben ser un diccionario",
                details={},
                warnings=[],
                errors=["Tipo incorrecto"]
            )

        required_keys = {'balls', 'players', 'frame_id', 'timestamp'}
        missing_keys = required_keys - set(detections.keys())
        if missing_keys:
            errors.append(f"Claves requeridas faltantes: {missing_keys}")

        # 2. Validar información del frame
        if 'frame_id' in detections:
            if not isinstance(detections['frame_id'], int):
                errors.append("frame_id debe ser un entero")

        if 'timestamp' in detections:
            if not isinstance(detections['timestamp'], (int, float)):
                errors.append("timestamp debe ser numérico")

        # 3. Validar balones detectados
        balls = detections.get('balls', [])
        if not isinstance(balls, list):
            errors.append("balls debe ser una lista")
        else:
            details['total_balls'] = len(balls)
            for i, ball in enumerate(balls):
                if not isinstance(ball, dict):
                    errors.append(f"Ball {i} debe ser un diccionario")
                    continue

                # Validar campos del balón
                required_ball_keys = {'x', 'y', 'confidence'}
                missing_ball_keys = required_ball_keys - set(ball.keys())
                if missing_ball_keys:
                    errors.append(f"Ball {i} faltan campos: {missing_ball_keys}")

                # Validar rango de confianza
                if 'confidence' in ball:
                    conf = ball['confidence']
                    if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
                        errors.append(f"Ball {i} confidence inválida: {conf}")

        # 4. Validar jugadores detectados
        players = detections.get('players', [])
        if not isinstance(players, list):
            errors.append("players debe ser una lista")
        else:
            details['total_players'] = len(players)
            for i, player in enumerate(players):
                if not isinstance(player, dict):
                    errors.append(f"Player {i} debe ser un diccionario")
                    continue

                # Validar campos del jugador
                required_player_keys = {'bbox', 'team', 'confidence'}
                missing_player_keys = required_player_keys - set(player.keys())
                if missing_player_keys:
                    errors.append(
                        f"Player {i} faltan campos: {missing_player_keys}"
                    )

                # Validar bbox
                if 'bbox' in player:
                    bbox = player['bbox']
                    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                        errors.append(f"Player {i} bbox inválido: {bbox}")

                # Validar team
                if 'team' in player:
                    if player['team'] not in ['A', 'B', 'referee']:
                        warnings.append(f"Player {i} team desconocido: {player['team']}")

        # Resultado final
        is_valid = len(errors) == 0

        message = "Detecciones válidas" if is_valid else \
                 f"Detecciones inválidas: {'; '.join(errors)}"

        return ValidationResult(
            is_valid=is_valid,
            message=message,
            details=details,
            warnings=warnings,
            errors=errors
        )


class ConfigValidator:
    """Valida archivos de configuración"""

    @staticmethod
    def validate_config(config: Dict) -> ValidationResult:
        """
        Valida estructura y valores de configuración.

        Args:
            config (Dict): Diccionario de configuración

        Returns:
            ValidationResult: Resultado de validación

        Example:
            >>> config = {'model_path': 'models/yolo.pt', 'confidence': 0.5}
            >>> result = ConfigValidator.validate_config(config)
        """
        errors = []
        warnings = []
        details = {}

        # Validaciones mínimas
        if 'model_path' in config:
            if not os.path.exists(config['model_path']):
                errors.append(f"Modelo no encontrado: {config['model_path']}")

        if 'confidence' in config:
            conf = config['confidence']
            if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
                errors.append(f"confidence debe estar entre 0 y 1: {conf}")

        if 'max_workers' in config:
            workers = config['max_workers']
            if not isinstance(workers, int) or workers < 1:
                errors.append(f"max_workers debe ser >= 1: {workers}")

        details['validated_keys'] = list(config.keys())

        is_valid = len(errors) == 0

        message = "Configuración válida" if is_valid else \
                 f"Configuración inválida: {'; '.join(errors)}"

        return ValidationResult(
            is_valid=is_valid,
            message=message,
            details=details,
            warnings=warnings,
            errors=errors
        )

    @staticmethod
    def validate_config_file(config_path: str) -> ValidationResult:
        """
        Valida un archivo de configuración YAML.

        Args:
            config_path (str): Ruta al archivo YAML

        Returns:
            ValidationResult: Resultado de validación
        """
        errors = []
        warnings = []

        # Verificar existencia
        if not os.path.exists(config_path):
            return ValidationResult(
                is_valid=False,
                message=f"Archivo de config no encontrado: {config_path}",
                details={},
                warnings=[],
                errors=[f"Archivo no encontrado: {config_path}"]
            )

        # Intentar parsear YAML
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return ValidationResult(
                is_valid=False,
                message=f"Error al parsear YAML: {e}",
                details={},
                warnings=[],
                errors=[f"YAML inválido: {e}"]
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                message=f"Error al leer config: {e}",
                details={},
                warnings=[],
                errors=[f"Error de lectura: {e}"]
            )

        # Validar contenido
        return ConfigValidator.validate_config(config)


class DependencyValidator:
    """Verifica dependencias del sistema"""

    REQUIRED_PACKAGES = {
        'numpy': 'NumPy',
        'cv2': 'OpenCV',
        'ultralytics': 'YOLOv8',
        'sklearn': 'Scikit-learn',
        'yaml': 'PyYAML',
    }

    OPTIONAL_PACKAGES = {
        'torch': 'PyTorch',
        'tensorflow': 'TensorFlow',
    }

    @staticmethod
    def check_dependencies() -> ValidationResult:
        """
        Verifica si están instaladas todas las dependencias requeridas.

        Returns:
            ValidationResult: Resultado de validación de dependencias

        Example:
            >>> result = DependencyValidator.check_dependencies()
            >>> if result.is_valid:
            ...     print("Todas las dependencias están instaladas")
        """
        errors = []
        warnings = []
        details = {'installed': {}, 'missing': {}}

        # Verificar paquetes requeridos
        for package_name, display_name in DependencyValidator.REQUIRED_PACKAGES.items():
            try:
                __import__(package_name)
                details['installed'][display_name] = True
                logger.info(f"✓ {display_name} instalado")
            except ImportError:
                errors.append(f"{display_name} no está instalado")
                details['missing'][display_name] = True
                logger.warning(f"✗ {display_name} no está instalado")

        # Verificar paquetes opcionales
        for package_name, display_name in DependencyValidator.OPTIONAL_PACKAGES.items():
            try:
                __import__(package_name)
                details['installed'][display_name] = True
                logger.info(f"✓ {display_name} instalado")
            except ImportError:
                warnings.append(f"{display_name} no está instalado (opcional)")
                logger.info(f"~ {display_name} no está instalado (opcional)")

        is_valid = len(errors) == 0

        message = "Todas las dependencias están instaladas" if is_valid else \
                 f"Faltan dependencias: {'; '.join(errors)}"

        return ValidationResult(
            is_valid=is_valid,
            message=message,
            details=details,
            warnings=warnings,
            errors=errors
        )

    @staticmethod
    def check_system_resources() -> ValidationResult:
        """
        Verifica recursos disponibles del sistema.

        Returns:
            ValidationResult: Resultado de validación
        """
        errors = []
        warnings = []
        details = {}

        try:
            import psutil

            # CPU
            cpu_count = psutil.cpu_count()
            details['cpu_count'] = cpu_count
            if cpu_count < 2:
                warnings.append(f"Pocas CPUs disponibles: {cpu_count}")

            # Memoria RAM
            memory = psutil.virtual_memory()
            details['memory_gb'] = memory.total / (1024 ** 3)
            if memory.total / (1024 ** 3) < 4:
                warnings.append("Poca memoria RAM disponible (< 4 GB)")

            # Espacio en disco
            disk = psutil.disk_usage('/')
            details['disk_free_gb'] = disk.free / (1024 ** 3)
            if disk.free / (1024 ** 3) < 10:
                warnings.append("Poco espacio en disco (< 10 GB)")

            is_valid = len(errors) == 0

        except ImportError:
            warnings.append("psutil no está instalado (no se puede verificar recursos)")
            is_valid = True  # No es error fatal

        message = "Recursos del sistema suficientes" if is_valid else \
                 f"Problemas de recursos: {'; '.join(errors)}"

        return ValidationResult(
            is_valid=is_valid,
            message=message,
            details=details,
            warnings=warnings,
            errors=errors
        )


def validate_all(video_path: str, config_path: str) -> Dict[str, ValidationResult]:
    """
    Ejecuta todas las validaciones.

    Args:
        video_path (str): Ruta al video
        config_path (str): Ruta a configuración

    Returns:
        Dict: Resultados de todas las validaciones
    """
    results = {
        'video': VideoValidator.validate_video_file(video_path),
        'config': ConfigValidator.validate_config_file(config_path),
        'dependencies': DependencyValidator.check_dependencies(),
        'system': DependencyValidator.check_system_resources(),
    }

    return results

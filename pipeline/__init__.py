"""
pipeline - Módulo principal del pipeline Scout AI

Contiene los componentes core del pipeline de procesamiento de video:
- VideoProcessor: Orquestador principal
- FrameProcessor: Procesador de frames individuales
- Estructuras de datos para resultados y configuración

Version: 1.0
Author: Scout AI
"""

from .video_processor import VideoProcessor, ProcessingConfig, ProcessingResult
from .frame_processor import FrameProcessor, FrameData, Detection, DetectionQuality

__all__ = [
    'VideoProcessor',
    'FrameProcessor',
    'ProcessingConfig',
    'ProcessingResult',
    'FrameData',
    'Detection',
    'DetectionQuality',
]

__version__ = '1.0.0'

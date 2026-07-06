"""
pipeline - Módulo principal del pipeline Scout AI

Contiene los componentes core del pipeline de procesamiento de video:
- VideoProcessor: Orquestador principal
- VideoProcessorFase3: Pipeline end-to-end integrado FASE 3
- FrameProcessor: Procesador de frames individuales
- Estructuras de datos para resultados y configuración

Version: 2.0 (FASE 3)
Author: Scout AI
"""

from .video_processor import VideoProcessor, ProcessingConfig, ProcessingResult
from .video_processor_fase3 import (
    VideoProcessorFase3,
    ProcessingConfigFase3,
    ProcessingResultFase3,
    PerformanceBenchmark
)
from .frame_processor import FrameProcessor, FrameData, Detection, DetectionQuality

__all__ = [
    # FASE 1-2
    'VideoProcessor',
    'FrameProcessor',
    'ProcessingConfig',
    'ProcessingResult',
    'FrameData',
    'Detection',
    'DetectionQuality',
    # FASE 3
    'VideoProcessorFase3',
    'ProcessingConfigFase3',
    'ProcessingResultFase3',
    'PerformanceBenchmark',
]

__version__ = '2.0.0'
__phase__ = 'FASE 3 - Pipeline End-to-End Integrado'

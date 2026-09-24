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

import logging

logger = logging.getLogger(__name__)

# FASE 1-2 imports
try:
    from .video_processor import VideoProcessor, ProcessingConfig, ProcessingResult
except ImportError as e:
    logger.error(f"Failed to import VideoProcessor from pipeline.video_processor: {e}")
    VideoProcessor = None
    ProcessingConfig = None
    ProcessingResult = None

try:
    from .video_processor_fase3 import (
        VideoProcessorFase3,
        ProcessingConfigFase3,
        ProcessingResultFase3,
        PerformanceBenchmark
    )
except ImportError as e:
    logger.error(f"Failed to import VideoProcessorFase3: {e}")
    VideoProcessorFase3 = None
    ProcessingConfigFase3 = None
    ProcessingResultFase3 = None
    PerformanceBenchmark = None

try:
    from .frame_processor import FrameProcessor, FrameData, Detection, DetectionQuality
except ImportError as e:
    logger.error(f"Failed to import FrameProcessor: {e}")
    FrameProcessor = None
    FrameData = None
    Detection = None
    DetectionQuality = None

# FASE 5 imports
try:
    from .integrated_pipeline import (
        IntegratedAnalysisPipeline,
        ProcessingConfig,
        FrameResult,
        PipelineResult,
        process_video_simple
    )
except ImportError as e:
    logger.error(f"Failed to import IntegratedAnalysisPipeline: {e}")
    IntegratedAnalysisPipeline = None
    FrameResult = None
    PipelineResult = None
    process_video_simple = None

__all__ = [
    # FASE 1-2
    'VideoProcessor',
    'FrameProcessor',
    'ProcessingResult',
    'FrameData',
    'Detection',
    'DetectionQuality',
    # FASE 3
    'VideoProcessorFase3',
    'ProcessingConfigFase3',
    'ProcessingResultFase3',
    'PerformanceBenchmark',
    # FASE 5
    'IntegratedAnalysisPipeline',
    'FrameResult',
    'PipelineResult',
    'process_video_simple',
]

__version__ = '2.0.0'
__phase__ = 'FASE 3 - Pipeline End-to-End Integrado'

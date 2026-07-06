"""
tests package - Suite de tests para Scout AI

Contiene todos los tests para validar la FASE 2 del proyecto.
Incluye tests para:
- Módulos core (player_analyzer, team_classifier, tracker, jersey_detector)
- Módulos pipeline (batch_processor, video_processor, frame_processor, result_combiner)
- Módulos utils (logger, validators, file_handler, video_splitter)
- Tests de integración end-to-end

Para ejecutar los tests:
    pytest tests/ -v
    pytest tests/test_core_modules.py -v
    pytest tests/test_pipeline_modules.py -v
    pytest tests/test_utils_modules.py -v
    pytest tests/test_integration.py -v

Para ejecutar con cobertura:
    pytest tests/ --cov=. --cov-report=html
"""

__version__ = "1.0.0"
__all__ = [
    "conftest",
    "test_core_modules",
    "test_pipeline_modules",
    "test_utils_modules",
    "test_integration",
]

# Core module - utilidades para detección, análisis y reportes
# Versión: 2.1 (FASE 2 - Arquitectura + Análisis Final)

from .metrics import DetectionMetrics
from .homography_validator import HomographyValidator
from .detector import BallDetector, CornerDetector, UnifiedDetector
from .team_classifier import TeamClassifier, TeamColor
from .tracker import PlayerTracker
from .jersey_number_detector import JerseyNumberDetector
from .player_analyzer import PlayerAnalyzer, PlayerStats
from .report_generator import ReportGenerator

__version__ = "2.1"

__all__ = [
    'DetectionMetrics',
    'HomographyValidator',
    'BallDetector',
    'CornerDetector',
    'UnifiedDetector',
    'TeamClassifier',
    'TeamColor',
    'PlayerTracker',
    'JerseyNumberDetector',
    'PlayerAnalyzer',
    'PlayerStats',
    'ReportGenerator',
]

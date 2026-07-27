# Core module - utilidades para detección, análisis y reportes
# Versión: 2.2 (FASE 4 - Consolidador de Estadísticas)

# Core statistics modules (no dependencies)
from .player_stats_aggregator import (
    PlayerStatsAggregator,
    StatsExporter,
    IntensityCategory,
    MovementProfile,
    ZoneStats,
    VelocityMetrics,
    IntensityMetrics,
    DistanceMetrics,
)

# Optional modules (may require external dependencies)
try:
    from .metrics import DetectionMetrics
except ImportError:
    DetectionMetrics = None

try:
    from .homography_validator import HomographyValidator
except ImportError:
    HomographyValidator = None

try:
    from .detector import BallDetector, CornerDetector, UnifiedDetector
except ImportError:
    BallDetector = CornerDetector = UnifiedDetector = None

try:
    from .team_classifier import TeamClassifier, TeamColor
except ImportError:
    TeamClassifier = TeamColor = None

try:
    from .tracker import PlayerTracker
except ImportError:
    PlayerTracker = None

try:
    from .jersey_number_detector import JerseyNumberDetector
except ImportError:
    JerseyNumberDetector = None

try:
    from .player_analyzer import PlayerAnalyzer, PlayerStats as PlayerAnalyzerStats
    PlayerStats = PlayerAnalyzerStats
except ImportError:
    PlayerAnalyzer = PlayerStats = None

try:
    from .report_generator import ReportGenerator
except ImportError:
    ReportGenerator = None

__version__ = "2.2"

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
    'PlayerStatsAggregator',
    'StatsExporter',
    'IntensityCategory',
    'MovementProfile',
    'ZoneStats',
    'VelocityMetrics',
    'IntensityMetrics',
    'DistanceMetrics',
]

"""
football_tracking_integration - Integración de Football-Tracking con Supervision

Módulos:
- improved_detector: Detección con sv.Detections
- improved_team_assigner: Asignación de equipos + análisis de posesión
- improved_metrics: Cálculo de métricas de rendimiento
"""

from .improved_detector import ImprovedFootballDetector, MultiStageDetector
from .improved_team_assigner import ImprovedTeamAssigner, PossessionAnalyzer
from .improved_metrics import RobustMetricsCalculator, ShotOnGoalDetector

__all__ = [
    'ImprovedFootballDetector',
    'MultiStageDetector',
    'ImprovedTeamAssigner',
    'PossessionAnalyzer',
    'RobustMetricsCalculator',
    'ShotOnGoalDetector',
]

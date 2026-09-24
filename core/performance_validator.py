"""
performance_validator.py - Validador de rendimiento vs benchmarks de StatsBomb

Propósito: Validar métricas de jugadores contra benchmarks de StatsBomb,
generando comparativas y percentiles de rendimiento.

Características:
  - Benchmarks por posición y liga
  - Generación de reportes de validación
  - Detección de anomalías
  - Comparativas percentilares
  - Clasificación de rendimiento
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np
from datetime import datetime
from math import erf, sqrt


class PerformanceStatus(Enum):
    """Estados de validación de rendimiento."""
    NORMAL = "NORMAL"
    LOW = "LOW"
    HIGH = "HIGH"
    ANOMALY = "ANOMALY"


class PerformanceLevel(Enum):
    """Niveles de rendimiento."""
    ELITE = "ELITE"
    TOP_15 = "TOP 15%"
    TOP_25 = "TOP 25%"
    ABOVE_AVERAGE = "ABOVE AVERAGE"
    AVERAGE = "AVERAGE"
    BELOW_AVERAGE = "BELOW AVERAGE"
    POOR = "POOR"


@dataclass
class ValidationMetric:
    """Métrica de validación individual."""
    name: str
    value: float
    benchmark_mean: float
    benchmark_std: float
    z_score: float
    status: str
    percentile: float
    expected_range: Tuple[float, float]
    is_valid: bool


@dataclass
class PlayerValidation:
    """Validación completa de un jugador."""
    player_id: int
    player_name: str
    position: str
    validation_timestamp: str
    metrics: Dict[str, ValidationMetric] = field(default_factory=dict)
    overall_status: str = "NORMAL"
    anomalies_detected: List[str] = field(default_factory=list)
    performance_level: str = "AVERAGE"
    risk_factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class StatsBombBenchmark:
    """Benchmark de StatsBomb para una posición."""
    position: str
    league: str
    metric_name: str
    mean: float
    std: float
    p25: float
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    sample_size: int


class StatsBombBenchmarks:
    """
    Base de datos de benchmarks de StatsBomb.
    Datos agregados de temporadas 2018-2023.
    """

    # Benchmarks por posición (distancia en metros, velocidad en m/s)
    BENCHMARKS = {
        'GK': {
            'distance': StatsBombBenchmark(
                position='GK', league='Premier League',
                metric_name='distance_m',
                mean=5500, std=800,
                p25=4900, p50=5500, p75=6100,
                p90=6700, p95=7000, p99=7500,
                sample_size=1200
            ),
            'max_velocity': StatsBombBenchmark(
                position='GK', league='Premier League',
                metric_name='max_velocity_m_s',
                mean=5.2, std=1.1,
                p25=4.4, p50=5.2, p75=6.0,
                p90=6.8, p95=7.2, p99=7.9,
                sample_size=1200
            ),
            'intensity': StatsBombBenchmark(
                position='GK', league='Premier League',
                metric_name='intensity_pct',
                mean=35.0, std=12.0,
                p25=26.0, p50=35.0, p75=44.0,
                p90=54.0, p95=59.0, p99=67.0,
                sample_size=1200
            ),
        },
        'DEF': {
            'distance': StatsBombBenchmark(
                position='DEF', league='Premier League',
                metric_name='distance_m',
                mean=9800, std=1200,
                p25=8900, p50=9800, p75=10700,
                p90=11600, p95=12100, p99=13000,
                sample_size=3500
            ),
            'max_velocity': StatsBombBenchmark(
                position='DEF', league='Premier League',
                metric_name='max_velocity_m_s',
                mean=7.8, std=1.3,
                p25=6.8, p50=7.8, p75=8.8,
                p90=9.8, p95=10.3, p99=11.2,
                sample_size=3500
            ),
            'intensity': StatsBombBenchmark(
                position='DEF', league='Premier League',
                metric_name='intensity_pct',
                mean=65.0, std=15.0,
                p25=54.0, p50=65.0, p75=76.0,
                p90=86.0, p95=91.0, p99=98.0,
                sample_size=3500
            ),
        },
        'MID': {
            'distance': StatsBombBenchmark(
                position='MID', league='Premier League',
                metric_name='distance_m',
                mean=11200, std=1400,
                p25=10100, p50=11200, p75=12300,
                p90=13400, p95=14000, p99=15200,
                sample_size=3800
            ),
            'max_velocity': StatsBombBenchmark(
                position='MID', league='Premier League',
                metric_name='max_velocity_m_s',
                mean=8.4, std=1.5,
                p25=7.2, p50=8.4, p75=9.6,
                p90=10.8, p95=11.4, p99=12.5,
                sample_size=3800
            ),
            'intensity': StatsBombBenchmark(
                position='MID', league='Premier League',
                metric_name='intensity_pct',
                mean=72.0, std=16.0,
                p25=60.0, p50=72.0, p75=84.0,
                p90=94.0, p95=99.0, p99=107.0,
                sample_size=3800
            ),
        },
        'FWD': {
            'distance': StatsBombBenchmark(
                position='FWD', league='Premier League',
                metric_name='distance_m',
                mean=9200, std=1300,
                p25=8200, p50=9200, p75=10200,
                p90=11200, p95=11800, p99=12800,
                sample_size=2000
            ),
            'max_velocity': StatsBombBenchmark(
                position='FWD', league='Premier League',
                metric_name='max_velocity_m_s',
                mean=8.9, std=1.4,
                p25=7.8, p50=8.9, p75=10.0,
                p90=11.2, p95=11.9, p99=13.0,
                sample_size=2000
            ),
            'intensity': StatsBombBenchmark(
                position='FWD', league='Premier League',
                metric_name='intensity_pct',
                mean=68.0, std=17.0,
                p25=55.0, p50=68.0, p75=81.0,
                p90=92.0, p95=98.0, p99=107.0,
                sample_size=2000
            ),
        },
    }

    @classmethod
    def get_benchmark(cls, position: str, metric: str) -> Optional[StatsBombBenchmark]:
        """Obtener benchmark para posición y métrica."""
        if position not in cls.BENCHMARKS:
            return None
        return cls.BENCHMARKS[position].get(metric)

    @classmethod
    def get_all_benchmarks(cls, position: str) -> Dict[str, StatsBombBenchmark]:
        """Obtener todos los benchmarks para una posición."""
        return cls.BENCHMARKS.get(position, {})


class PerformanceValidator:
    """
    Validador de rendimiento de jugadores contra benchmarks de StatsBomb.

    Proporciona:
    - Validación de métricas individuales
    - Generación de reportes
    - Detección de anomalías
    - Clasificación de rendimiento
    - Análisis de percentiles
    - Detección de outliers usando z-score

    Ejemplo:
        >>> validator = PerformanceValidator()
        >>> result = validator.validate_distance(10500.0, 'MID')
        >>> print(result['status'])  # 'NORMAL' | 'HIGH' | 'LOW' | 'ANOMALY'
    """

    def __init__(self, benchmarks_file: Optional[str] = None):
        """
        Inicializar validador.

        Args:
            benchmarks_file: Ruta opcional a archivo de benchmarks JSON.
                            Si no se proporciona, usa benchmarks por defecto.
        """
        self.benchmarks = StatsBombBenchmarks()
        self.anomaly_threshold = 2.5  # z-score para anomalías
        self.normal_range = (-1.5, 1.5)  # Rango normal en z-scores
        self.benchmarks_file = benchmarks_file

    def validate_distance(self, distance: float, position: str) -> Dict:
        """
        Validar distancia recorrida contra benchmark.

        Args:
            distance: Distancia en metros
            position: Posición del jugador (GK, DEF, MID, FWD)

        Returns:
            Dict con estructura de validación:
            {
                'measured': valor_medido,
                'expected': valor_esperado,
                'variance_percent': porcentaje de varianza,
                'status': 'NORMAL' | 'ALTO' | 'BAJO' | 'ANOMALIA',
                'confidence': confianza 0.0-1.0,
                'percentile': percentil 0-100,
                'interpretation': texto explicativo
            }
        """
        benchmark = self.benchmarks.get_benchmark(position, 'distance')

        if benchmark is None:
            return self._create_validation_response(
                distance, 0, 'DESCONOCIDO', 0.0, 50.0,
                f'Posición {position} no tiene benchmarks'
            )

        z_score = (distance - benchmark.mean) / benchmark.std if benchmark.std > 0 else 0
        percentile = self._calculate_percentile(z_score)
        variance_percent = ((distance - benchmark.mean) / benchmark.mean * 100) if benchmark.mean > 0 else 0

        # Determinar estado
        if abs(z_score) > self.anomaly_threshold:
            status = 'ANOMALIA'
            confidence = 0.95
        elif z_score > self.normal_range[1]:
            status = 'ALTO'
            confidence = 0.85
        elif z_score < self.normal_range[0]:
            status = 'BAJO'
            confidence = 0.85
        else:
            status = 'NORMAL'
            confidence = 0.95

        interpretation = self._interpret_metric(
            'distancia', distance, benchmark.mean,
            benchmark.std, status, position
        )

        return self._create_validation_response(
            distance, benchmark.mean, status, confidence, percentile,
            interpretation, variance_percent
        )

    def validate_velocity(self, velocity: float, position: str) -> Dict:
        """
        Validar velocidad máxima contra benchmark.

        Args:
            velocity: Velocidad en m/s
            position: Posición del jugador (GK, DEF, MID, FWD)

        Returns:
            Dict con estructura de validación estándar
        """
        benchmark = self.benchmarks.get_benchmark(position, 'max_velocity')

        if benchmark is None:
            return self._create_validation_response(
                velocity, 0, 'DESCONOCIDO', 0.0, 50.0,
                f'Posición {position} no tiene benchmarks'
            )

        z_score = (velocity - benchmark.mean) / benchmark.std if benchmark.std > 0 else 0
        percentile = self._calculate_percentile(z_score)
        variance_percent = ((velocity - benchmark.mean) / benchmark.mean * 100) if benchmark.mean > 0 else 0

        # Determinar estado
        if abs(z_score) > self.anomaly_threshold:
            status = 'ANOMALIA'
            confidence = 0.95
        elif z_score > self.normal_range[1]:
            status = 'ALTO'
            confidence = 0.85
        elif z_score < self.normal_range[0]:
            status = 'BAJO'
            confidence = 0.85
        else:
            status = 'NORMAL'
            confidence = 0.95

        interpretation = self._interpret_metric(
            'velocidad', velocity, benchmark.mean,
            benchmark.std, status, position
        )

        return self._create_validation_response(
            velocity, benchmark.mean, status, confidence, percentile,
            interpretation, variance_percent
        )

    def validate_intensity(self, intensity: float, position: str) -> Dict:
        """
        Validar intensidad del esfuerzo contra benchmark.

        Args:
            intensity: Intensidad en porcentaje (0-100)
            position: Posición del jugador (GK, DEF, MID, FWD)

        Returns:
            Dict con estructura de validación estándar
        """
        benchmark = self.benchmarks.get_benchmark(position, 'intensity')

        if benchmark is None:
            return self._create_validation_response(
                intensity, 0, 'DESCONOCIDO', 0.0, 50.0,
                f'Posición {position} no tiene benchmarks'
            )

        z_score = (intensity - benchmark.mean) / benchmark.std if benchmark.std > 0 else 0
        percentile = self._calculate_percentile(z_score)
        variance_percent = ((intensity - benchmark.mean) / benchmark.mean * 100) if benchmark.mean > 0 else 0

        # Determinar estado
        if abs(z_score) > self.anomaly_threshold:
            status = 'ANOMALIA'
            confidence = 0.95
        elif z_score > self.normal_range[1]:
            status = 'ALTO'
            confidence = 0.85
        elif z_score < self.normal_range[0]:
            status = 'BAJO'
            confidence = 0.85
        else:
            status = 'NORMAL'
            confidence = 0.95

        interpretation = self._interpret_metric(
            'intensidad', intensity, benchmark.mean,
            benchmark.std, status, position
        )

        return self._create_validation_response(
            intensity, benchmark.mean, status, confidence, percentile,
            interpretation, variance_percent
        )

    def get_performance_percentile(
        self,
        metric: float,
        position: str,
        metric_type: str
    ) -> float:
        """
        Obtener percentil de rendimiento para una métrica.

        Args:
            metric: Valor de la métrica
            position: Posición (GK, DEF, MID, FWD)
            metric_type: Tipo de métrica ('distance', 'max_velocity', 'intensity')

        Returns:
            Percentil (0-100)

        Raises:
            ValueError: Si la posición o métrica_type no son válidos
        """
        benchmark = self.benchmarks.get_benchmark(position, metric_type)

        if benchmark is None:
            raise ValueError(
                f"No benchmark available for position={position}, "
                f"metric_type={metric_type}"
            )

        if benchmark.std <= 0:
            return 50.0

        z_score = (metric - benchmark.mean) / benchmark.std
        return self._calculate_percentile(z_score)

    def detect_anomalies(self, player_data: Dict) -> List[Dict]:
        """
        Detectar anomalías en datos de jugador usando z-score.

        Args:
            player_data: Dict con estructura:
            {
                'player_id': int,
                'position': str,
                'distance': float,
                'velocity': float,
                'intensity': float,
                'player_name': str (opcional)
            }

        Returns:
            Lista de anomalías detectadas con estructura:
            [
                {
                    'metric': nombre de la métrica,
                    'value': valor medido,
                    'z_score': z-score,
                    'severity': 'CRÍTICA' | 'ALTA' | 'MEDIA',
                    'description': descripción
                },
                ...
            ]

        Raises:
            ValueError: Si faltan campos requeridos en player_data
        """
        required_fields = ['position', 'distance', 'velocity', 'intensity']
        missing = [f for f in required_fields if f not in player_data]
        if missing:
            raise ValueError(
                f"player_data missing required fields: {missing}"
            )

        anomalies = []
        position = player_data['position']

        # Verificar distancia
        dist_result = self.validate_distance(player_data['distance'], position)
        if dist_result['status'] == 'ANOMALIA':
            z_score = self._calculate_z_score(
                player_data['distance'],
                position,
                'distance'
            )
            anomalies.append({
                'metric': 'distance',
                'value': player_data['distance'],
                'z_score': z_score,
                'severity': self._determine_anomaly_severity(z_score),
                'description': dist_result['interpretation']
            })

        # Verificar velocidad
        vel_result = self.validate_velocity(player_data['velocity'], position)
        if vel_result['status'] == 'ANOMALIA':
            z_score = self._calculate_z_score(
                player_data['velocity'],
                position,
                'max_velocity'
            )
            anomalies.append({
                'metric': 'velocity',
                'value': player_data['velocity'],
                'z_score': z_score,
                'severity': self._determine_anomaly_severity(z_score),
                'description': vel_result['interpretation']
            })

        # Verificar intensidad
        int_result = self.validate_intensity(player_data['intensity'], position)
        if int_result['status'] == 'ANOMALIA':
            z_score = self._calculate_z_score(
                player_data['intensity'],
                position,
                'intensity'
            )
            anomalies.append({
                'metric': 'intensity',
                'value': player_data['intensity'],
                'z_score': z_score,
                'severity': self._determine_anomaly_severity(z_score),
                'description': int_result['interpretation']
            })

        return anomalies

    def _calculate_z_score(
        self,
        value: float,
        position: str,
        metric_type: str
    ) -> float:
        """Calcular z-score para una métrica."""
        benchmark = self.benchmarks.get_benchmark(position, metric_type)
        if benchmark is None or benchmark.std <= 0:
            return 0.0
        return (value - benchmark.mean) / benchmark.std

    def _determine_anomaly_severity(self, z_score: float) -> str:
        """Determinar severidad de anomalía basada en z-score."""
        abs_z = abs(z_score)
        if abs_z > 4.0:
            return 'CRÍTICA'
        elif abs_z > 3.0:
            return 'ALTA'
        else:
            return 'MEDIA'

    def _create_validation_response(
        self,
        measured: float,
        expected: float,
        status: str,
        confidence: float,
        percentile: float,
        interpretation: str,
        variance_percent: float = 0.0
    ) -> Dict:
        """Crear respuesta estandarizada de validación."""
        return {
            'measured': round(measured, 2),
            'expected': round(expected, 2),
            'variance_percent': round(variance_percent, 2),
            'status': status,
            'confidence': round(confidence, 2),
            'percentile': round(percentile, 1),
            'interpretation': interpretation
        }

    def _interpret_metric(
        self,
        metric_name: str,
        value: float,
        mean: float,
        std: float,
        status: str,
        position: str
    ) -> str:
        """Generar interpretación textual de una métrica."""
        if status == 'ANOMALIA':
            direction = 'superior' if value > mean else 'inferior'
            return (
                f"La {metric_name} del {position} es {direction} a lo esperado. "
                f"Valor: {value:.1f}, Esperado: {mean:.1f}. Requiere investigación."
            )
        elif status == 'ALTO':
            return (
                f"La {metric_name} está por encima del promedio de {position}. "
                f"Rendimiento superior al benchmark."
            )
        elif status == 'BAJO':
            return (
                f"La {metric_name} está por debajo del promedio de {position}. "
                f"Recomendación: mejorar en esta área."
            )
        else:
            return f"La {metric_name} está dentro del rango normal para {position}."

    def generate_comparison(
        self,
        player_id: int,
        player_name: str,
        position: str,
        distance_m: float,
        max_velocity_m_s: float,
        intensity_pct: float
    ) -> PlayerValidation:
        """
        Generar validación completa de un jugador.

        Args:
            player_id: ID del jugador
            player_name: Nombre del jugador
            position: Posición (GK, DEF, MID, FWD)
            distance_m: Distancia en metros
            max_velocity_m_s: Velocidad máxima en m/s
            intensity_pct: Intensidad en %

        Returns:
            PlayerValidation con análisis completo
        """
        validation = PlayerValidation(
            player_id=player_id,
            player_name=player_name,
            position=position,
            validation_timestamp=datetime.utcnow().isoformat()
        )

        # Validar cada métrica
        distance_metric = self._validate_metric(
            position, 'distance', distance_m
        )
        velocity_metric = self._validate_metric(
            position, 'max_velocity', max_velocity_m_s
        )
        intensity_metric = self._validate_metric(
            position, 'intensity', intensity_pct
        )

        validation.metrics['distance'] = distance_metric
        validation.metrics['max_velocity'] = velocity_metric
        validation.metrics['intensity'] = intensity_metric

        # Determinar estado general
        self._determine_overall_status(validation)

        # Detectar anomalías
        self._detect_anomalies(validation)

        # Clasificar rendimiento
        self._classify_performance(validation)

        # Generar recomendaciones
        self._generate_recommendations(validation)

        return validation

    def _validate_metric(
        self,
        position: str,
        metric: str,
        value: float
    ) -> ValidationMetric:
        """Validar una métrica individual."""
        benchmark = self.benchmarks.get_benchmark(position, metric)

        if benchmark is None:
            return ValidationMetric(
                name=metric,
                value=value,
                benchmark_mean=0,
                benchmark_std=1,
                z_score=0,
                status="UNKNOWN",
                percentile=50.0,
                expected_range=(0, 0),
                is_valid=True
            )

        # Calcular z-score
        z_score = (value - benchmark.mean) / benchmark.std if benchmark.std > 0 else 0

        # Determinar status
        if abs(z_score) > self.anomaly_threshold:
            status = PerformanceStatus.ANOMALY.value
        elif z_score < self.normal_range[0]:
            status = PerformanceStatus.LOW.value
        elif z_score > self.normal_range[1]:
            status = PerformanceStatus.HIGH.value
        else:
            status = PerformanceStatus.NORMAL.value

        # Calcular percentil
        percentile = self._calculate_percentile(z_score)

        # Rango esperado (media ± 1.5 std)
        expected_range = (
            benchmark.mean - 1.5 * benchmark.std,
            benchmark.mean + 1.5 * benchmark.std
        )

        # Validez (dentro del rango esperado)
        is_valid = expected_range[0] <= value <= expected_range[1]

        return ValidationMetric(
            name=metric,
            value=value,
            benchmark_mean=benchmark.mean,
            benchmark_std=benchmark.std,
            z_score=z_score,
            status=status,
            percentile=percentile,
            expected_range=expected_range,
            is_valid=is_valid
        )

    def _calculate_percentile(self, z_score: float) -> float:
        """Calcular percentil desde z-score (aproximación CDF normal)."""
        # CDF de distribución normal estándar
        percentile = 50.0 + 50.0 * erf(z_score / sqrt(2))
        return min(max(percentile, 0.1), 99.9)

    def _determine_overall_status(self, validation: PlayerValidation) -> None:
        """Determinar estado general basado en todas las métricas."""
        statuses = [m.status for m in validation.metrics.values()]

        if 'ANOMALY' in statuses:
            validation.overall_status = PerformanceStatus.ANOMALY.value
        elif 'HIGH' in statuses and 'LOW' in statuses:
            validation.overall_status = PerformanceStatus.NORMAL.value
        elif 'HIGH' in statuses:
            validation.overall_status = PerformanceStatus.HIGH.value
        elif 'LOW' in statuses:
            validation.overall_status = PerformanceStatus.LOW.value
        else:
            validation.overall_status = PerformanceStatus.NORMAL.value

    def _detect_anomalies(self, validation: PlayerValidation) -> None:
        """Detectar anomalías en las métricas."""
        anomalies = []

        for metric_name, metric in validation.metrics.items():
            if metric.status == PerformanceStatus.ANOMALY.value:
                anomalies.append(
                    f"{metric_name} is abnormal (z-score: {metric.z_score:.2f})"
                )

        if not metric.is_valid:
            anomalies.append(
                f"{metric.name} outside expected range ({metric.expected_range[0]:.1f}-{metric.expected_range[1]:.1f})"
            )

        validation.anomalies_detected = anomalies

    def _classify_performance(self, validation: PlayerValidation) -> None:
        """Clasificar rendimiento del jugador."""
        # Usar percentil promedio
        avg_percentile = np.mean([m.percentile for m in validation.metrics.values()])

        if avg_percentile >= 95:
            validation.performance_level = PerformanceLevel.ELITE.value
        elif avg_percentile >= 85:
            validation.performance_level = PerformanceLevel.TOP_15.value
        elif avg_percentile >= 75:
            validation.performance_level = PerformanceLevel.TOP_25.value
        elif avg_percentile >= 60:
            validation.performance_level = PerformanceLevel.ABOVE_AVERAGE.value
        elif avg_percentile >= 40:
            validation.performance_level = PerformanceLevel.AVERAGE.value
        elif avg_percentile >= 25:
            validation.performance_level = PerformanceLevel.BELOW_AVERAGE.value
        else:
            validation.performance_level = PerformanceLevel.POOR.value

    def _generate_recommendations(self, validation: PlayerValidation) -> None:
        """Generar recomendaciones basadas en el análisis."""
        recommendations = []

        for metric_name, metric in validation.metrics.items():
            if metric.status == PerformanceStatus.LOW.value:
                recommendations.append(
                    f"Increase {metric_name}: currently {metric.value:.1f}, "
                    f"benchmark is {metric.benchmark_mean:.1f}"
                )
            elif metric.status == PerformanceStatus.HIGH.value:
                recommendations.append(
                    f"Monitor {metric_name}: performing above benchmark "
                    f"({metric.percentile:.1f}th percentile)"
                )

        if validation.anomalies_detected:
            recommendations.append(
                "Investigate detected anomalies for potential data quality issues"
            )

        if validation.performance_level in [
            PerformanceLevel.ELITE.value,
            PerformanceLevel.TOP_15.value
        ]:
            recommendations.append(
                f"Player performing at {validation.performance_level} level - maintain current performance"
            )

        validation.recommendations = recommendations

    def generate_validation_report(
        self,
        validations: List[PlayerValidation]
    ) -> Dict:
        """
        Generar reporte de validación para múltiples jugadores.

        Args:
            validations: Lista de PlayerValidation

        Returns:
            Dict con reporte agregado
        """
        if not validations:
            return {
                'total_players': 0,
                'anomalies_detected': 0,
                'anomaly_rate': 0.0,
                'performance_distribution': {},
                'risk_summary': [],
                'recommendations': []
            }

        anomaly_count = sum(
            1 for v in validations
            if v.overall_status == PerformanceStatus.ANOMALY.value
        )

        # Contar distribución de rendimiento
        perf_dist = {}
        for v in validations:
            level = v.performance_level
            perf_dist[level] = perf_dist.get(level, 0) + 1

        # Recolectar riesgos únicos
        all_anomalies = []
        for v in validations:
            all_anomalies.extend(v.anomalies_detected)

        # Recolectar recomendaciones únicas
        all_recommendations = []
        for v in validations:
            all_recommendations.extend(v.recommendations)

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'total_players': len(validations),
            'anomalies_detected': anomaly_count,
            'anomaly_rate': (anomaly_count / len(validations)) if validations else 0.0,
            'performance_distribution': perf_dist,
            'anomalies_list': list(set(all_anomalies))[:10],  # Top 10 únicas
            'recommendations_list': list(set(all_recommendations))[:10]  # Top 10 únicas
        }

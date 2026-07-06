"""
performance_optimizer.py - Performance Optimization and Benchmarking for Scout AI Pipeline

Este módulo proporciona herramientas para optimizar y benchmarkear los componentes
del pipeline, incluyendo vectorización de NumPy, caché de modelos, memory pooling,
y medición detallada de rendimiento.

Classes:
    PerformanceOptimizer: Orquestador de optimizaciones
    BenchmarkRunner: Ejecutor de benchmarks
    PerformanceMetrics: Métricas de rendimiento

Author: Scout AI Performance Team
Date: 2026-07-06
"""

import numpy as np
import time
import logging
import psutil
import os
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
from pathlib import Path
from functools import wraps


@dataclass
class PerformanceMetrics:
    """Métricas de rendimiento para operaciones"""
    operation_name: str
    execution_time_ms: float
    memory_used_mb: float
    cpu_percent: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convertir a diccionario"""
        return asdict(self)


class MemoryPool:
    """
    Pool de memoria preasignada para frames de video.

    Reduce fragmentación de memoria y mejora performance al reutilizar
    buffers en lugar de asignar nuevos para cada frame.
    """

    def __init__(self, frame_shape: Tuple[int, int, int] = (1080, 1920, 3),
                 pool_size: int = 10, dtype=np.uint8):
        """
        Inicializa el pool de memoria.

        Args:
            frame_shape: Forma del frame (H, W, C)
            pool_size: Cantidad de buffers a preasignar
            dtype: Tipo de dato NumPy
        """
        self.frame_shape = frame_shape
        self.pool_size = pool_size
        self.dtype = dtype
        self.available_buffers = []
        self.in_use_buffers = set()
        self.logger = logging.getLogger(__name__)

        # Preasignar buffers
        for _ in range(pool_size):
            buffer = np.zeros(frame_shape, dtype=dtype)
            self.available_buffers.append(buffer)

        self.logger.info(f"MemoryPool inicializado: {pool_size} buffers de {frame_shape}")

    def acquire(self) -> np.ndarray:
        """
        Obtiene un buffer del pool.

        Returns:
            np.ndarray: Buffer disponible
        """
        if self.available_buffers:
            buffer = self.available_buffers.pop()
            buffer_id = id(buffer)
            self.in_use_buffers.add(buffer_id)
            return buffer
        else:
            # Si no hay disponibles, crear uno nuevo
            self.logger.warning("MemoryPool exhausted, allocating new buffer")
            return np.zeros(self.frame_shape, dtype=self.dtype)

    def release(self, buffer: np.ndarray):
        """
        Devuelve un buffer al pool.

        Args:
            buffer: Buffer a devolver
        """
        buffer_id = id(buffer)
        if buffer_id in self.in_use_buffers:
            self.in_use_buffers.remove(buffer_id)
            # Limpiar el buffer
            buffer.fill(0)
            self.available_buffers.append(buffer)

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del pool"""
        return {
            'total_buffers': self.pool_size,
            'available': len(self.available_buffers),
            'in_use': len(self.in_use_buffers),
            'utilization_percent': (len(self.in_use_buffers) / self.pool_size * 100)
                                   if self.pool_size > 0 else 0
        }


class ModelCache:
    """
    Caché para modelos YOLO y otros componentes.

    Evita recargar modelos innecesariamente, mejorando
    significativamente el rendimiento en batch processing.
    """

    def __init__(self, max_size: int = 5):
        """
        Inicializa el caché de modelos.

        Args:
            max_size: Máximo número de modelos en caché
        """
        self.cache = {}
        self.max_size = max_size
        self.access_times = {}
        self.logger = logging.getLogger(__name__)
        self.hit_count = 0
        self.miss_count = 0

    def put(self, key: str, model: Any):
        """
        Añade un modelo al caché.

        Args:
            key: Identificador del modelo
            model: Modelo a cachear
        """
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Evictar el modelo menos usado recientemente (LRU)
            oldest_key = min(self.access_times, key=self.access_times.get)
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
            self.logger.debug(f"Evicted model from cache: {oldest_key}")

        self.cache[key] = model
        self.access_times[key] = time.time()
        self.logger.debug(f"Model cached: {key}")

    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un modelo del caché.

        Args:
            key: Identificador del modelo

        Returns:
            Modelo si existe, None en caso contrario
        """
        if key in self.cache:
            self.access_times[key] = time.time()
            self.hit_count += 1
            return self.cache[key]
        else:
            self.miss_count += 1
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché"""
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'hits': self.hit_count,
            'misses': self.miss_count,
            'hit_rate_percent': hit_rate,
            'cached_models': list(self.cache.keys())
        }


class VectorizationOptimizer:
    """
    Optimizaciones de operaciones NumPy para máximo rendimiento.

    Proporciona versiones vectorizadas de operaciones comunes en lugar
    de loops, aprovechando la eficiencia de NumPy/BLAS.
    """

    @staticmethod
    def vectorized_bbox_overlap(boxes1: np.ndarray, boxes2: np.ndarray) -> np.ndarray:
        """
        Calcula IoU (Intersection over Union) de forma vectorizada.

        Args:
            boxes1: Array de forma (N, 4) con [x1, y1, x2, y2]
            boxes2: Array de forma (M, 4) con [x1, y1, x2, y2]

        Returns:
            Array de forma (N, M) con valores IoU
        """
        # Expandir dimensiones para broadcasting
        boxes1 = np.expand_dims(boxes1, axis=1)  # (N, 1, 4)
        boxes2 = np.expand_dims(boxes2, axis=0)  # (1, M, 4)

        # Calcular intersección
        x1_inter = np.maximum(boxes1[..., 0], boxes2[..., 0])
        y1_inter = np.maximum(boxes1[..., 1], boxes2[..., 1])
        x2_inter = np.minimum(boxes1[..., 2], boxes2[..., 2])
        y2_inter = np.minimum(boxes1[..., 3], boxes2[..., 3])

        inter_area = np.maximum(0, x2_inter - x1_inter) * np.maximum(0, y2_inter - y1_inter)

        # Calcular unión
        box1_area = (boxes1[..., 2] - boxes1[..., 0]) * (boxes1[..., 3] - boxes1[..., 1])
        box2_area = (boxes2[..., 2] - boxes2[..., 0]) * (boxes2[..., 3] - boxes2[..., 1])

        union_area = box1_area + box2_area - inter_area

        # Calcular IoU
        iou = inter_area / (union_area + 1e-6)
        return iou

    @staticmethod
    def vectorized_distance_matrix(points1: np.ndarray, points2: np.ndarray) -> np.ndarray:
        """
        Calcula matriz de distancias de forma vectorizada (Euclidiana).

        Args:
            points1: Array de forma (N, 2) con [x, y]
            points2: Array de forma (M, 2) con [x, y]

        Returns:
            Array de forma (N, M) con distancias
        """
        # Expandir para broadcasting
        p1 = np.expand_dims(points1, axis=1)  # (N, 1, 2)
        p2 = np.expand_dims(points2, axis=0)  # (1, M, 2)

        # Calcular diferencias al cuadrado
        diff = p1 - p2  # (N, M, 2)
        dist_sq = np.sum(diff ** 2, axis=2)  # (N, M)

        # Raíz cuadrada
        distances = np.sqrt(np.maximum(dist_sq, 0))
        return distances

    @staticmethod
    def vectorized_color_distance(colors1: np.ndarray, colors2: np.ndarray,
                                 space: str = 'bgr') -> np.ndarray:
        """
        Calcula distancia entre colores de forma vectorizada.

        Args:
            colors1: Array de forma (N, 3) con valores BGR/RGB
            colors2: Array de forma (M, 3) con valores BGR/RGB
            space: Espacio de color ('bgr', 'hsv', 'lab')

        Returns:
            Array de forma (N, M) con distancias
        """
        if space == 'bgr' or space == 'rgb':
            # Distancia Euclidiana en espacio RGB
            c1 = np.expand_dims(colors1, axis=1)  # (N, 1, 3)
            c2 = np.expand_dims(colors2, axis=0)  # (1, M, 3)

            diff = c1 - c2
            dist = np.sqrt(np.sum(diff ** 2, axis=2))
            return dist
        else:
            # Para otros espacios, usar como Euclidiana
            return VectorizationOptimizer.vectorized_color_distance(colors1, colors2, 'bgr')


class BenchmarkRunner:
    """Ejecutor de benchmarks para componentes del pipeline"""

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Inicializa el runner de benchmarks.

        Args:
            output_dir: Directorio para guardar resultados
        """
        self.output_dir = Path(output_dir) if output_dir else Path("data/logs")
        self.results = []
        self.logger = logging.getLogger(__name__)

    def benchmark_function(self, func: Callable, *args,
                          iterations: int = 1,
                          func_name: Optional[str] = None,
                          metadata: Optional[Dict] = None) -> PerformanceMetrics:
        """
        Ejecuta un benchmark de una función.

        Args:
            func: Función a benchmarkear
            *args: Argumentos para la función
            iterations: Número de iteraciones
            func_name: Nombre de la función
            metadata: Metadatos adicionales

        Returns:
            PerformanceMetrics con resultados
        """
        func_name = func_name or func.__name__
        process = psutil.Process(os.getpid())

        try:
            # Warmup
            func(*args)

            # Medir
            mem_before = process.memory_info().rss / (1024 ** 2)
            cpu_before = process.cpu_percent()

            start_time = time.perf_counter()

            for _ in range(iterations):
                func(*args)

            end_time = time.perf_counter()

            mem_after = process.memory_info().rss / (1024 ** 2)
            cpu_after = process.cpu_percent()

            execution_time_ms = (end_time - start_time) / iterations * 1000
            memory_used_mb = mem_after - mem_before
            cpu_percent = (cpu_before + cpu_after) / 2

            metrics = PerformanceMetrics(
                operation_name=func_name,
                execution_time_ms=execution_time_ms,
                memory_used_mb=memory_used_mb,
                cpu_percent=cpu_percent,
                metadata=metadata or {}
            )

            self.results.append(metrics)
            self.logger.info(
                f"Benchmark {func_name}: {execution_time_ms:.2f}ms, "
                f"{memory_used_mb:.2f}MB, {cpu_percent:.1f}% CPU"
            )

            return metrics

        except Exception as e:
            self.logger.error(f"Error benchmarking {func_name}: {str(e)}")
            return PerformanceMetrics(
                operation_name=func_name,
                execution_time_ms=0,
                memory_used_mb=0,
                cpu_percent=0,
                success=False,
                error=str(e)
            )

    def save_results(self, filename: str = "benchmark_results.json"):
        """Guarda resultados de benchmarks"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / filename

        data = {
            'timestamp': datetime.now().isoformat(),
            'results': [r.to_dict() for r in self.results],
            'summary': {
                'total_benchmarks': len(self.results),
                'successful': sum(1 for r in self.results if r.success),
                'failed': sum(1 for r in self.results if not r.success),
                'avg_execution_time_ms': np.mean([r.execution_time_ms for r in self.results if r.success]),
                'total_memory_used_mb': sum(r.memory_used_mb for r in self.results if r.success)
            }
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        self.logger.info(f"Benchmark results saved to {output_path}")


class PerformanceOptimizer:
    """Orquestador principal de optimizaciones"""

    def __init__(self):
        """Inicializa el optimizador"""
        self.logger = logging.getLogger(__name__)
        self.memory_pool = None
        self.model_cache = ModelCache()
        self.vectorizer = VectorizationOptimizer()
        self.benchmarks = []

    def initialize_memory_pool(self, frame_shape: Tuple = (1080, 1920, 3),
                              pool_size: int = 10):
        """Inicializa el pool de memoria"""
        self.memory_pool = MemoryPool(frame_shape, pool_size)
        return self.memory_pool

    def get_optimization_report(self) -> Dict[str, Any]:
        """Genera reporte de optimizaciones disponibles"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'optimizations': {
                'memory_pool': {
                    'enabled': self.memory_pool is not None,
                    'stats': self.memory_pool.get_stats() if self.memory_pool else None
                },
                'model_cache': {
                    'enabled': True,
                    'stats': self.model_cache.get_stats()
                },
                'vectorization': {
                    'enabled': True,
                    'methods': [
                        'vectorized_bbox_overlap',
                        'vectorized_distance_matrix',
                        'vectorized_color_distance'
                    ]
                }
            }
        }
        return report

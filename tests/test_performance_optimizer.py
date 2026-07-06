"""
test_performance_optimizer.py - Tests for performance optimization modules

Tests para las optimizaciones de performance: vectorización, caché de modelos,
memory pooling, y benchmarking.
"""

import pytest
import numpy as np
import logging
from pathlib import Path
from unittest.mock import Mock, patch

# Setup path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.performance_optimizer import (
    PerformanceOptimizer,
    VectorizationOptimizer,
    MemoryPool,
    ModelCache,
    BenchmarkRunner,
    PerformanceMetrics
)


class TestVectorizationOptimizer:
    """Tests para optimizaciones de vectorización"""

    def test_vectorized_bbox_overlap(self):
        """Test cálculo vectorizado de IoU"""
        boxes1 = np.array([[10, 10, 100, 100], [50, 50, 150, 150]], dtype=np.float32)
        boxes2 = np.array([[20, 20, 110, 110], [60, 60, 160, 160]], dtype=np.float32)

        iou = VectorizationOptimizer.vectorized_bbox_overlap(boxes1, boxes2)

        # Verificar forma
        assert iou.shape == (2, 2)

        # Verificar rangos (IoU debe estar entre 0 y 1)
        assert np.all(iou >= 0) and np.all(iou <= 1)

        # Verificar que boxes iguales tienen IoU = 1
        same_box_iou = VectorizationOptimizer.vectorized_bbox_overlap(boxes1, boxes1)
        np.testing.assert_array_almost_equal(np.diag(same_box_iou), np.ones(2), decimal=5)

    def test_vectorized_distance_matrix(self):
        """Test cálculo vectorizado de matriz de distancias"""
        points1 = np.array([[0, 0], [10, 10], [20, 20]], dtype=np.float32)
        points2 = np.array([[0, 0], [5, 5]], dtype=np.float32)

        distances = VectorizationOptimizer.vectorized_distance_matrix(points1, points2)

        # Verificar forma
        assert distances.shape == (3, 2)

        # Verificar distancia conocida
        expected_dist = np.sqrt(2 * (10 ** 2))  # distancia de (10,10) a (5,5)
        np.testing.assert_almost_equal(distances[1, 1], expected_dist, decimal=5)

        # Verificar que distancia a sí mismo es 0
        same_points_dist = VectorizationOptimizer.vectorized_distance_matrix(points1, points1)
        np.testing.assert_array_almost_equal(np.diag(same_points_dist), np.zeros(3), decimal=5)

    def test_vectorized_color_distance(self):
        """Test cálculo vectorizado de distancia de colores"""
        colors1 = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)
        colors2 = np.array([[0, 0, 255], [255, 255, 255]], dtype=np.uint8)

        distances = VectorizationOptimizer.vectorized_color_distance(colors1, colors2)

        # Verificar forma
        assert distances.shape == (2, 2)

        # Verificar rangos (distancia debe ser positiva)
        assert np.all(distances >= 0)

        # Verificar que colores iguales tienen distancia = 0
        same_colors = np.array([[100, 100, 100], [50, 50, 50]], dtype=np.uint8)
        same_dist = VectorizationOptimizer.vectorized_color_distance(same_colors, same_colors)
        np.testing.assert_array_almost_equal(np.diag(same_dist), np.zeros(2), decimal=5)


class TestMemoryPool:
    """Tests para memory pooling"""

    def test_memory_pool_initialization(self):
        """Test inicialización del pool de memoria"""
        frame_shape = (480, 640, 3)
        pool = MemoryPool(frame_shape=frame_shape, pool_size=5)

        stats = pool.get_stats()
        assert stats['total_buffers'] == 5
        assert stats['available'] == 5
        assert stats['in_use'] == 0
        assert stats['utilization_percent'] == 0

    def test_acquire_release_cycle(self):
        """Test ciclo de adquisición y liberación de buffers"""
        pool = MemoryPool(frame_shape=(100, 100, 3), pool_size=3)

        # Adquirir buffers
        buf1 = pool.acquire()
        buf2 = pool.acquire()

        stats = pool.get_stats()
        assert stats['available'] == 1
        assert stats['in_use'] == 2

        # Liberar un buffer
        pool.release(buf1)
        stats = pool.get_stats()
        assert stats['available'] == 2
        assert stats['in_use'] == 1

        # Liberar otro
        pool.release(buf2)
        stats = pool.get_stats()
        assert stats['available'] == 3
        assert stats['in_use'] == 0

    def test_pool_exhaustion(self):
        """Test comportamiento cuando pool se agota"""
        pool = MemoryPool(frame_shape=(100, 100, 3), pool_size=1)

        buf1 = pool.acquire()
        buf2 = pool.acquire()  # Pool exhausted, crea nuevo

        # Verificar que se pueden usar ambos
        assert buf1 is not None
        assert buf2 is not None
        assert buf1 is not buf2

    def test_buffer_cleanup_on_release(self):
        """Test que buffers se limpian al liberar"""
        pool = MemoryPool(frame_shape=(10, 10, 3), pool_size=2)

        buf = pool.acquire()
        buf[0, 0] = [255, 255, 255]  # Llenar con datos

        pool.release(buf)

        # Verificar que se limpió
        assert np.all(buf == 0)


class TestModelCache:
    """Tests para caché de modelos"""

    def test_cache_put_get(self):
        """Test put y get básico"""
        cache = ModelCache(max_size=3)

        model = np.random.randn(100, 100)
        cache.put("model1", model)

        retrieved = cache.get("model1")
        assert retrieved is model  # Mismo objeto

    def test_cache_miss(self):
        """Test cuando model no está en caché"""
        cache = ModelCache(max_size=3)

        result = cache.get("nonexistent")
        assert result is None

    def test_cache_lru_eviction(self):
        """Test política de evicción LRU"""
        cache = ModelCache(max_size=2)

        model1 = np.random.randn(10, 10)
        model2 = np.random.randn(10, 10)
        model3 = np.random.randn(10, 10)

        cache.put("model1", model1)
        cache.put("model2", model2)
        cache.put("model3", model3)  # Debe evictar model1 (menos reciente)

        # model1 debe haber sido evictado
        assert cache.get("model1") is None
        assert cache.get("model2") is model2
        assert cache.get("model3") is model3

    def test_cache_statistics(self):
        """Test estadísticas del caché"""
        cache = ModelCache(max_size=3)

        model = np.random.randn(10, 10)
        cache.put("model", model)

        # Get que falla
        cache.get("nonexistent")
        # Get que falla
        cache.get("nonexistent")
        # Get que acierta
        cache.get("model")

        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 2
        assert stats['hit_rate_percent'] == pytest.approx(33.33, rel=1)


class TestBenchmarkRunner:
    """Tests para BenchmarkRunner"""

    def test_benchmark_simple_function(self):
        """Test benchmarking de función simple"""
        runner = BenchmarkRunner()

        def test_func():
            return sum(range(1000))

        result = runner.benchmark_function(
            test_func,
            iterations=10,
            func_name="sum_range"
        )

        assert result.success
        assert result.operation_name == "sum_range"
        assert result.execution_time_ms > 0
        assert result.memory_used_mb >= 0

    def test_benchmark_with_args(self):
        """Test benchmarking con argumentos"""
        runner = BenchmarkRunner()

        def matrix_mult(a, b):
            return np.dot(a, b)

        a = np.random.randn(100, 100)
        b = np.random.randn(100, 100)

        result = runner.benchmark_function(
            matrix_mult,
            a, b,
            iterations=10,
            func_name="matrix_mult"
        )

        assert result.success
        assert result.execution_time_ms > 0

    def test_benchmark_error_handling(self):
        """Test manejo de errores en benchmark"""
        runner = BenchmarkRunner()

        def failing_func():
            raise ValueError("Test error")

        result = runner.benchmark_function(
            failing_func,
            func_name="failing_func"
        )

        assert not result.success
        assert "Test error" in result.error

    def test_benchmark_results_storage(self):
        """Test almacenamiento de resultados"""
        runner = BenchmarkRunner()

        def test_func():
            pass

        runner.benchmark_function(test_func, iterations=5, func_name="test1")
        runner.benchmark_function(test_func, iterations=5, func_name="test2")

        assert len(runner.results) == 2


class TestPerformanceOptimizer:
    """Tests para PerformanceOptimizer principal"""

    def test_optimizer_initialization(self):
        """Test inicialización del optimizador"""
        optimizer = PerformanceOptimizer()

        assert optimizer.model_cache is not None
        assert optimizer.vectorizer is not None
        assert optimizer.memory_pool is None  # No inicializado aún

    def test_memory_pool_initialization(self):
        """Test inicialización del pool desde optimizador"""
        optimizer = PerformanceOptimizer()

        pool = optimizer.initialize_memory_pool(
            frame_shape=(480, 640, 3),
            pool_size=5
        )

        assert pool is not None
        assert optimizer.memory_pool is pool

        stats = pool.get_stats()
        assert stats['available'] == 5

    def test_optimization_report(self):
        """Test generación de reporte de optimización"""
        optimizer = PerformanceOptimizer()
        optimizer.initialize_memory_pool()

        report = optimizer.get_optimization_report()

        assert 'timestamp' in report
        assert 'optimizations' in report
        assert 'memory_pool' in report['optimizations']
        assert 'model_cache' in report['optimizations']
        assert 'vectorization' in report['optimizations']

        assert report['optimizations']['memory_pool']['enabled'] is True
        assert report['optimizations']['model_cache']['enabled'] is True
        assert report['optimizations']['vectorization']['enabled'] is True


class TestPerformanceMetrics:
    """Tests para PerformanceMetrics"""

    def test_metrics_creation(self):
        """Test creación de métricas"""
        metrics = PerformanceMetrics(
            operation_name="test_op",
            execution_time_ms=10.5,
            memory_used_mb=50.2,
            cpu_percent=45.5
        )

        assert metrics.operation_name == "test_op"
        assert metrics.execution_time_ms == 10.5
        assert metrics.success is True

    def test_metrics_to_dict(self):
        """Test conversión a diccionario"""
        metrics = PerformanceMetrics(
            operation_name="test_op",
            execution_time_ms=10.5,
            memory_used_mb=50.2,
            cpu_percent=45.5,
            metadata={"test_key": "test_value"}
        )

        data = metrics.to_dict()

        assert isinstance(data, dict)
        assert data['operation_name'] == "test_op"
        assert data['metadata']['test_key'] == "test_value"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
benchmark_pipeline.py - Comprehensive Pipeline Benchmarking for FASE 3

Script para medir performance de componentes del pipeline Scout AI,
identificar bottlenecks, y comparar optimizaciones.

Usage:
    python scripts/benchmark_pipeline.py --all
    python scripts/benchmark_pipeline.py --component frame_processor
    python scripts/benchmark_pipeline.py --component vectorization --iterations 1000
"""

import sys
import logging
import numpy as np
import time
from pathlib import Path
from typing import Dict, List, Any
import json
import argparse
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.performance_optimizer import (
    BenchmarkRunner, PerformanceOptimizer, VectorizationOptimizer,
    MemoryPool, ModelCache
)


class PipelineBenchmark:
    """Ejecutor de benchmarks integrales del pipeline"""

    def __init__(self, output_dir: str = "data/logs"):
        """Inicializa el benchmark"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = self._setup_logger()
        self.runner = BenchmarkRunner(output_dir=self.output_dir)
        self.optimizer = PerformanceOptimizer()
        self.results = {}

    def _setup_logger(self) -> logging.Logger:
        """Configura logging"""
        logger = logging.getLogger('PipelineBenchmark')
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def benchmark_vectorization(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmarkea operaciones vectorizadas"""
        self.logger.info("=" * 70)
        self.logger.info("BENCHMARK: Vectorization Operations")
        self.logger.info("=" * 70)

        # Datos de prueba
        boxes1 = np.array([[10, 10, 100, 100], [50, 50, 150, 150]], dtype=np.float32)
        boxes2 = np.array([[20, 20, 110, 110], [60, 60, 160, 160]], dtype=np.float32)
        points1 = np.array([[50, 50], [100, 100], [150, 150]], dtype=np.float32)
        points2 = np.array([[55, 55], [105, 105]], dtype=np.float32)
        colors1 = np.random.randint(0, 256, (100, 3), dtype=np.uint8)
        colors2 = np.random.randint(0, 256, (50, 3), dtype=np.uint8)

        results = {}

        # IoU Benchmark
        self.logger.info("\nBenchmarking: Vectorized IoU Calculation")
        result = self.runner.benchmark_function(
            VectorizationOptimizer.vectorized_bbox_overlap,
            boxes1, boxes2,
            iterations=iterations,
            func_name="vectorized_bbox_overlap",
            metadata={"boxes1_shape": boxes1.shape, "boxes2_shape": boxes2.shape}
        )
        results['iou'] = result.to_dict()
        self.logger.info(f"  Time: {result.execution_time_ms:.4f}ms per call")

        # Distance Matrix Benchmark
        self.logger.info("\nBenchmarking: Vectorized Distance Matrix")
        result = self.runner.benchmark_function(
            VectorizationOptimizer.vectorized_distance_matrix,
            points1, points2,
            iterations=iterations,
            func_name="vectorized_distance_matrix",
            metadata={"points1_shape": points1.shape, "points2_shape": points2.shape}
        )
        results['distance'] = result.to_dict()
        self.logger.info(f"  Time: {result.execution_time_ms:.4f}ms per call")

        # Color Distance Benchmark
        self.logger.info("\nBenchmarking: Vectorized Color Distance")
        result = self.runner.benchmark_function(
            VectorizationOptimizer.vectorized_color_distance,
            colors1, colors2,
            iterations=iterations,
            func_name="vectorized_color_distance",
            metadata={"colors1_shape": colors1.shape, "colors2_shape": colors2.shape}
        )
        results['color_distance'] = result.to_dict()
        self.logger.info(f"  Time: {result.execution_time_ms:.4f}ms per call")

        return results

    def benchmark_memory_operations(self) -> Dict[str, Any]:
        """Benchmarkea operaciones de memoria"""
        self.logger.info("=" * 70)
        self.logger.info("BENCHMARK: Memory Operations")
        self.logger.info("=" * 70)

        results = {}

        # Test frame shapes
        frame_shapes = [
            (480, 640, 3, "VGA"),
            (720, 1280, 3, "HD"),
            (1080, 1920, 3, "Full HD"),
        ]

        for height, width, channels, label in frame_shapes:
            self.logger.info(f"\nTesting Memory Pool: {label} ({height}x{width})")

            pool = MemoryPool(
                frame_shape=(height, width, channels),
                pool_size=5
            )

            # Benchmark acquire/release
            def pool_cycle():
                buf = pool.acquire()
                buf[0, 0] = 255
                pool.release(buf)

            result = self.runner.benchmark_function(
                pool_cycle,
                iterations=10,
                func_name=f"memory_pool_{label.lower().replace(' ', '_')}",
                metadata={"resolution": f"{height}x{width}"}
            )

            results[f"pool_{label}"] = result.to_dict()

            # Show pool stats
            stats = pool.get_stats()
            self.logger.info(f"  Pool Stats: {stats}")

        return results

    def benchmark_model_cache(self) -> Dict[str, Any]:
        """Benchmarkea operaciones del caché de modelos"""
        self.logger.info("=" * 70)
        self.logger.info("BENCHMARK: Model Cache Operations")
        self.logger.info("=" * 70)

        cache = ModelCache(max_size=3)
        results = {}

        # Crear modelos simulados
        dummy_models = {
            f"model_{i}": np.random.randn(1000, 1000) for i in range(5)
        }

        # Benchmark put operations
        self.logger.info("\nBenchmarking: Cache Put Operations")

        def cache_put():
            for name, model in dummy_models.items():
                cache.put(name, model)

        result = self.runner.benchmark_function(
            cache_put,
            iterations=10,
            func_name="model_cache_put",
            metadata={"models": len(dummy_models), "cache_size": cache.max_size}
        )
        results['cache_put'] = result.to_dict()
        self.logger.info(f"  Time: {result.execution_time_ms:.4f}ms per call")

        # Benchmark get operations (should be very fast due to cache hits)
        self.logger.info("\nBenchmarking: Cache Get Operations")

        def cache_get():
            cache.get("model_0")
            cache.get("model_1")
            cache.get("model_2")

        result = self.runner.benchmark_function(
            cache_get,
            iterations=1000,
            func_name="model_cache_get",
            metadata={"operations_per_call": 3}
        )
        results['cache_get'] = result.to_dict()
        self.logger.info(f"  Time: {result.execution_time_ms:.4f}ms per call")

        # Show cache stats
        stats = cache.get_stats()
        self.logger.info(f"\nCache Statistics:")
        self.logger.info(f"  Hit Rate: {stats['hit_rate_percent']:.1f}%")
        self.logger.info(f"  Hits: {stats['hits']}, Misses: {stats['misses']}")

        return results

    def benchmark_numpy_operations(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmarkea operaciones NumPy comunes"""
        self.logger.info("=" * 70)
        self.logger.info("BENCHMARK: NumPy Operations")
        self.logger.info("=" * 70)

        results = {}

        # Array operations
        test_arrays = [
            (np.ones((100, 100, 3), dtype=np.uint8), "Small (100x100x3)"),
            (np.ones((1000, 1000, 3), dtype=np.uint8), "Medium (1000x1000x3)"),
            (np.ones((1080, 1920, 3), dtype=np.uint8), "Large (1080x1920x3)"),
        ]

        for arr, label in test_arrays:
            self.logger.info(f"\nBenchmarking Array Operations: {label}")

            # Mean calculation
            def calc_mean():
                return arr.mean(axis=(0, 1))

            result = self.runner.benchmark_function(
                calc_mean,
                iterations=iterations,
                func_name=f"mean_{label.lower().replace(' ', '_').replace('(', '').replace(')', '')}",
                metadata={"shape": arr.shape}
            )
            results[f"mean_{label}"] = result.to_dict()
            self.logger.info(f"  Mean: {result.execution_time_ms:.4f}ms")

            # Reshape operation
            def reshape_op():
                return arr.reshape(-1, 3)

            result = self.runner.benchmark_function(
                reshape_op,
                iterations=iterations,
                func_name=f"reshape_{label.lower().replace(' ', '_').replace('(', '').replace(')', '')}",
                metadata={"shape": arr.shape}
            )
            results[f"reshape_{label}"] = result.to_dict()
            self.logger.info(f"  Reshape: {result.execution_time_ms:.4f}ms")

        return results

    def identify_bottlenecks(self) -> Dict[str, Any]:
        """Identifica los 3 principales bottlenecks"""
        self.logger.info("=" * 70)
        self.logger.info("BOTTLENECK ANALYSIS")
        self.logger.info("=" * 70)

        all_metrics = self.runner.results
        if not all_metrics:
            self.logger.warning("No metrics collected yet")
            return {}

        # Ordenar por tiempo de ejecución
        sorted_metrics = sorted(
            [m for m in all_metrics if m.success],
            key=lambda x: x.execution_time_ms,
            reverse=True
        )

        bottlenecks = []
        for i, metric in enumerate(sorted_metrics[:3], 1):
            self.logger.info(f"\n{i}. {metric.operation_name}")
            self.logger.info(f"   Time: {metric.execution_time_ms:.4f}ms")
            self.logger.info(f"   Memory: {metric.memory_used_mb:.2f}MB")
            self.logger.info(f"   CPU: {metric.cpu_percent:.1f}%")

            bottlenecks.append({
                'rank': i,
                'operation': metric.operation_name,
                'metrics': metric.to_dict(),
                'recommendations': self._get_recommendations(metric)
            })

        return {
            'top_3_bottlenecks': bottlenecks,
            'total_operations': len(all_metrics),
            'successful': sum(1 for m in all_metrics if m.success)
        }

    def _get_recommendations(self, metric: Any) -> List[str]:
        """Obtiene recomendaciones basadas en métricas"""
        recommendations = []

        if metric.execution_time_ms > 100:
            recommendations.append("Considere vectorización con NumPy o Numba")
        if metric.execution_time_ms > 500:
            recommendations.append("Considere paralelización con multiprocessing")
        if metric.memory_used_mb > 500:
            recommendations.append("Considere memory pooling o optimización de estructuras de datos")
        if metric.cpu_percent > 80:
            recommendations.append("La operación está limitada por CPU, considere GPU")

        if not recommendations:
            recommendations.append("Performance aceptable")

        return recommendations

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Ejecuta todos los benchmarks"""
        self.logger.info("\n")
        self.logger.info("#" * 70)
        self.logger.info("# SCOUT AI PIPELINE - PERFORMANCE BENCHMARKING - FASE 3")
        self.logger.info("#" * 70)

        start_time = time.time()

        results = {
            'timestamp': datetime.now().isoformat(),
            'vectorization': self.benchmark_vectorization(iterations=100),
            'memory': self.benchmark_memory_operations(),
            'model_cache': self.benchmark_model_cache(),
            'numpy_ops': self.benchmark_numpy_operations(iterations=100),
        }

        bottlenecks = self.identify_bottlenecks()
        results['bottleneck_analysis'] = bottlenecks

        total_time = time.time() - start_time

        results['summary'] = {
            'total_benchmarks': len(self.runner.results),
            'successful': sum(1 for m in self.runner.results if m.success),
            'failed': sum(1 for m in self.runner.results if not m.success),
            'total_duration_seconds': total_time,
            'optimization_report': self.optimizer.get_optimization_report()
        }

        # Save results
        self.runner.save_results("fase3_detailed_benchmarks.json")

        # Save summary
        summary_path = self.output_dir / "fase3_benchmark_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(results, f, indent=2)

        self.logger.info("\n" + "#" * 70)
        self.logger.info("# BENCHMARK COMPLETE")
        self.logger.info(f"# Total Duration: {total_time:.2f}s")
        self.logger.info(f"# Results saved to: {summary_path}")
        self.logger.info("#" * 70 + "\n")

        return results


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description="Scout AI Pipeline Benchmarking Tool"
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Run all benchmarks'
    )
    parser.add_argument(
        '--component',
        choices=['vectorization', 'memory', 'cache', 'numpy'],
        help='Run specific benchmark component'
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=100,
        help='Number of iterations per benchmark'
    )
    parser.add_argument(
        '--output-dir',
        default='data/logs',
        help='Output directory for results'
    )

    args = parser.parse_args()

    benchmark = PipelineBenchmark(output_dir=args.output_dir)

    if args.all:
        benchmark.run_all_benchmarks()
    elif args.component == 'vectorization':
        results = benchmark.benchmark_vectorization(iterations=args.iterations)
        benchmark.logger.info(f"Vectorization results: {len(results)} operations")
    elif args.component == 'memory':
        results = benchmark.benchmark_memory_operations()
        benchmark.logger.info(f"Memory results: {len(results)} tests")
    elif args.component == 'cache':
        results = benchmark.benchmark_model_cache()
        benchmark.logger.info(f"Cache results: {len(results)} tests")
    elif args.component == 'numpy':
        results = benchmark.benchmark_numpy_operations(iterations=args.iterations)
        benchmark.logger.info(f"NumPy results: {len(results)} operations")
    else:
        benchmark.run_all_benchmarks()


if __name__ == '__main__':
    main()

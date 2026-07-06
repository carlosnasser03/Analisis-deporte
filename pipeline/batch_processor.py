"""
Scout AI - Batch Video Processor Module

Procesa múltiples videos en paralelo usando multiprocessing.
Está diseñado para optimizar el rendimiento al procesar grandes
volúmenes de archivos de video.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from multiprocessing import Pool, Process, Queue
from concurrent.futures import ProcessPoolExecutor, as_completed
import time
from datetime import datetime


class BatchProcessor:
    """
    Procesa múltiples videos de manera eficiente.

    Características:
    - Procesamiento paralelo con multiprocessing
    - Gestión de recursos y workers
    - Consolidación de resultados
    - Manejo de errores en batch
    """

    def __init__(self, max_workers: int = 4, timeout: int = 300):
        """
        Inicializa el procesador de batch.

        Args:
            max_workers: Número máximo de procesos paralelos
            timeout: Timeout en segundos para cada video
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self.batch_results = {}
        self.processing_stats = {
            'total_files': 0,
            'processed_files': 0,
            'failed_files': 0,
            'start_time': None,
            'end_time': None,
            'total_duration': 0
        }
        self.logger = logging.getLogger(__name__)
        self._setup_logging()

    def _setup_logging(self):
        """Configura el logging para el procesador."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - BatchProcessor - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def process_batch(self, video_dir: str) -> Dict:
        """
        Procesa todos los videos en una carpeta.

        Args:
            video_dir: Ruta a la carpeta con videos

        Returns:
            Diccionario con resultados del batch
        """
        self.logger.info(f"Iniciando procesamiento de batch desde: {video_dir}")

        # Resetear estadísticas
        self.batch_results = {}
        self.processing_stats['total_files'] = 0
        self.processing_stats['processed_files'] = 0
        self.processing_stats['failed_files'] = 0
        self.processing_stats['start_time'] = datetime.now()

        # Encontrar todos los videos
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
        video_files = []

        video_path = Path(video_dir)
        if not video_path.exists():
            self.logger.error(f"Directorio no existe: {video_dir}")
            return {'error': 'Directory not found'}

        for ext in video_extensions:
            video_files.extend(video_path.glob(f'*{ext}'))
            video_files.extend(video_path.glob(f'**/*{ext}'))

        video_files = list(set(video_files))  # Eliminar duplicados
        self.processing_stats['total_files'] = len(video_files)

        self.logger.info(f"Encontrados {len(video_files)} videos para procesar")

        if not video_files:
            self.logger.warning("No se encontraron videos en el directorio")
            return {'files_found': 0, 'results': {}}

        # Procesar en paralelo
        results = self.process_parallel(video_files, self.max_workers)

        self.processing_stats['end_time'] = datetime.now()
        self.processing_stats['total_duration'] = (
            self.processing_stats['end_time'] -
            self.processing_stats['start_time']
        ).total_seconds()

        return {
            'total_files': len(video_files),
            'results': results,
            'statistics': self.processing_stats
        }

    def process_parallel(self, videos: List[str], num_workers: int) -> Dict:
        """
        Procesa videos en paralelo usando multiprocessing.

        Args:
            videos: Lista de rutas de videos
            num_workers: Número de procesos paralelos

        Returns:
            Diccionario con resultados de cada video
        """
        self.logger.info(f"Iniciando procesamiento paralelo con {num_workers} workers")

        results = {}

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_video = {
                executor.submit(self._process_single_video, str(video)): str(video)
                for video in videos
            }

            for future in as_completed(future_to_video, timeout=self.timeout):
                video_path = future_to_video[future]
                try:
                    result = future.result()
                    results[video_path] = result
                    self.processing_stats['processed_files'] += 1
                    self.logger.info(f"Procesado: {Path(video_path).name}")

                except Exception as e:
                    self.logger.error(f"Error procesando {video_path}: {str(e)}")
                    self.processing_stats['failed_files'] += 1
                    results[video_path] = {
                        'status': 'error',
                        'error': str(e)
                    }

        return results

    def _process_single_video(self, video_path: str) -> Dict:
        """
        Procesa un único video. Este método puede ser
        sobrescrito para implementar lógica personalizada.

        Args:
            video_path: Ruta al video

        Returns:
            Diccionario con resultados del procesamiento
        """
        try:
            file_size = os.path.getsize(video_path)
            file_info = Path(video_path)

            # Simulación de procesamiento
            result = {
                'status': 'success',
                'file': str(file_info),
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'processed_at': datetime.now().isoformat(),
                'frames': 0,
                'detections': 0,
                'duration': 0.0
            }

            return result

        except Exception as e:
            return {
                'status': 'error',
                'file': video_path,
                'error': str(e)
            }

    def get_batch_results(self) -> Dict:
        """
        Obtiene los resultados consolidados del batch.

        Returns:
            Diccionario con resultados y estadísticas
        """
        summary = {
            'total_files': self.processing_stats['total_files'],
            'successful': self.processing_stats['processed_files'],
            'failed': self.processing_stats['failed_files'],
            'success_rate': (
                self.processing_stats['processed_files'] /
                max(self.processing_stats['total_files'], 1) * 100
            ),
            'total_duration_seconds': self.processing_stats['total_duration'],
            'results': self.batch_results
        }

        return summary

    def process_with_callback(
        self,
        videos: List[str],
        callback=None
    ) -> Dict:
        """
        Procesa videos con callback para cada resultado.

        Args:
            videos: Lista de rutas de videos
            callback: Función a ejecutar para cada resultado

        Returns:
            Diccionario con resultados
        """
        results = {}

        for video in videos:
            try:
                result = self._process_single_video(str(video))
                results[str(video)] = result

                if callback:
                    callback(str(video), result)

            except Exception as e:
                self.logger.error(f"Error procesando {video}: {str(e)}")
                results[str(video)] = {'status': 'error', 'error': str(e)}

        return results

    def get_processing_statistics(self) -> Dict:
        """
        Retorna estadísticas detalladas del procesamiento.

        Returns:
            Diccionario con estadísticas
        """
        return {
            'total_files': self.processing_stats['total_files'],
            'processed': self.processing_stats['processed_files'],
            'failed': self.processing_stats['failed_files'],
            'pending': (
                self.processing_stats['total_files'] -
                self.processing_stats['processed_files'] -
                self.processing_stats['failed_files']
            ),
            'success_rate': (
                self.processing_stats['processed_files'] /
                max(self.processing_stats['total_files'], 1) * 100
            ),
            'start_time': (
                self.processing_stats['start_time'].isoformat()
                if self.processing_stats['start_time'] else None
            ),
            'end_time': (
                self.processing_stats['end_time'].isoformat()
                if self.processing_stats['end_time'] else None
            ),
            'duration_seconds': self.processing_stats['total_duration']
        }

    def save_batch_report(self, output_path: str) -> bool:
        """
        Guarda un reporte del batch procesado.

        Args:
            output_path: Ruta donde guardar el reporte

        Returns:
            True si se guardó correctamente
        """
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'statistics': self.get_processing_statistics(),
                'results': self.batch_results
            }

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)

            self.logger.info(f"Reporte guardado en: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error guardando reporte: {str(e)}")
            return False

    def clear_results(self):
        """Limpia los resultados almacenados."""
        self.batch_results = {}
        self.logger.info("Resultados limpiados")

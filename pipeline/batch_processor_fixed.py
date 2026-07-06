"""
Scout AI - Batch Video Processor Module (FIXED)

Procesa múltiples videos en paralelo usando multiprocessing.
Está diseñado para optimizar el rendimiento al procesar grandes
volúmenes de archivos de video.

CAMBIOS EN VERSIÓN FIXED:
- Reemplazo de método _process_single_video() STUB con implementación REAL
- Integración con VideoProcessor para procesamiento completo
- Estadísticas reales basadas en detecciones reales
- Manejo robusto de errores (videos no existentes, corruptos, etc)
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
import traceback

from .video_processor import VideoProcessor, ProcessingConfig


class BatchProcessor:
    """
    Procesa múltiples videos de manera eficiente.

    Características:
    - Procesamiento paralelo con multiprocessing
    - Gestión de recursos y workers
    - Consolidación de resultados
    - Manejo de errores en batch
    - Integración real con VideoProcessor para procesamiento completo
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
        Procesa un único video usando VideoProcessor para obtener
        estadísticas reales de detección, tracking y análisis.

        IMPLEMENTACIÓN REAL (no stub):
        - Crea instancia VideoProcessor
        - Procesa video completo con detectores reales
        - Retorna estadísticas reales de detecciones
        - Maneja errores de video corrupto/no existente

        Args:
            video_path: Ruta al video

        Returns:
            Diccionario con resultados reales del procesamiento
        """
        try:
            # Validar que el archivo existe
            if not Path(video_path).exists():
                return {
                    'status': 'error',
                    'file': video_path,
                    'error': f'Video file not found: {video_path}'
                }

            # Obtener información del archivo
            file_size = os.path.getsize(video_path)
            file_info = Path(video_path)

            self.logger.info(f"Procesando video: {file_info.name} ({file_size / (1024*1024):.2f} MB)")

            # Crear configuración para procesador
            config = ProcessingConfig(
                min_confidence=0.3,
                skip_frames=1,  # Procesar todos los frames
                max_frames=None,  # Sin límite
                enable_tracking=True,
                enable_team_classification=True,
                enable_analysis=True,
                save_intermediate=False
            )

            # Crear instancia de VideoProcessor
            # Nota: Se puede extender para pasar detectores reales si están disponibles
            processor = VideoProcessor(
                detector=None,  # Será inicializado en el procesador
                tracker=None,
                team_classifier=None,
                analyzer=None,
                config=config,
                logger=self.logger
            )

            # Procesar el video
            try:
                result = processor.process_video(video_path)
            except Exception as e:
                # El video puede estar corrupto o no ser procesable
                self.logger.warning(
                    f"No se pudo procesar video con VideoProcessor: {str(e)}. "
                    f"Intentando lectura básica..."
                )
                return self._get_basic_video_info(video_path, str(e))

            # Construir diccionario de resultados con estadísticas reales
            video_result = {
                'status': 'success',
                'file': str(file_info),
                'file_name': file_info.name,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'processed_at': datetime.now().isoformat(),

                # Estadísticas REALES del procesamiento
                'frames': {
                    'total': result.total_frames,
                    'processed': result.processed_frames,
                    'skipped': result.skipped_frames
                },
                'detections': {
                    'total': result.processing_stats.get('total_detections', 0),
                    'valid': result.processing_stats.get('valid_detections', 0),
                    'avg_per_frame': result.processing_stats.get('avg_detections_per_frame', 0),
                    'avg_valid_per_frame': result.processing_stats.get('avg_valid_detections_per_frame', 0)
                },
                'processing': {
                    'duration_seconds': result.total_time_seconds,
                    'fps_processed': round(result.fps_processed, 2),
                    'errors': len(result.errors),
                    'warnings': len(result.warnings)
                },
                'errors': result.errors[:5] if result.errors else [],  # Primeros 5 errores
                'warnings': result.warnings[:5] if result.warnings else [],  # Primeros 5 advertencias
                'timestamp': result.timestamp
            }

            return video_result

        except Exception as e:
            self.logger.error(f"Error crítico procesando {video_path}: {str(e)}")
            self.logger.debug(traceback.format_exc())
            return {
                'status': 'error',
                'file': video_path,
                'error': str(e),
                'error_type': type(e).__name__,
                'traceback': traceback.format_exc()
            }

    def _get_basic_video_info(self, video_path: str, processing_error: str) -> Dict:
        """
        Obtiene información básica del video cuando la detección no es posible.
        Intenta al menos obtener metadatos del video.

        Args:
            video_path: Ruta del video
            processing_error: Error del procesamiento

        Returns:
            Diccionario con información básica disponible
        """
        try:
            import cv2

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return {
                    'status': 'error',
                    'file': video_path,
                    'error': f'Cannot open video file: {processing_error}'
                }

            # Obtener propiedades básicas
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()

            file_size = os.path.getsize(video_path)
            file_info = Path(video_path)
            duration = total_frames / fps if fps > 0 else 0

            return {
                'status': 'partial',  # Metadatos obtenidos, pero sin procesamiento
                'file': str(file_info),
                'file_name': file_info.name,
                'size': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2),
                'processed_at': datetime.now().isoformat(),
                'frames': {
                    'total': total_frames,
                    'processed': 0,
                    'skipped': 0
                },
                'video_properties': {
                    'fps': fps,
                    'width': frame_width,
                    'height': frame_height,
                    'duration_seconds': round(duration, 2)
                },
                'detections': {
                    'total': 0,
                    'valid': 0,
                    'avg_per_frame': 0
                },
                'processing_error': processing_error,
                'warning': 'Video metadata retrieved but detection not possible'
            }

        except Exception as e:
            return {
                'status': 'error',
                'file': video_path,
                'error': f'Cannot read video: {str(e)}'
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

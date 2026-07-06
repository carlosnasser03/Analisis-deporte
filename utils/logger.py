"""
Scout AI - Logger Module

Sistema centralizado de logging para Scout AI.
Registra detecciones, errores y eventos en archivo y stdout.
"""

import logging
import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from collections import defaultdict


class ScoutLogger:
    """
    Logger centralizado para Scout AI.

    Funcionalidades:
    - Registro de detecciones
    - Registro de errores
    - Estadísticas de procesamiento
    - Output a archivo y stdout
    - Resumen de logs
    """

    def __init__(
        self,
        log_dir: str = 'logs',
        log_file: str = 'scout_ai.log',
        level: str = 'INFO'
    ):
        """
        Inicializa el logger de Scout AI.

        Args:
            log_dir: Directorio para guardar logs
            log_file: Nombre del archivo de log
            level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_dir = log_dir
        self.log_file = log_file
        self.log_path = os.path.join(log_dir, log_file)

        # Crear directorio de logs si no existe
        os.makedirs(log_dir, exist_ok=True)

        # Configurar logger de Python
        self.logger = logging.getLogger('ScoutAI')
        self.logger.setLevel(getattr(logging, level.upper()))

        # Limpiar handlers existentes
        self.logger.handlers.clear()

        # Handler para archivo
        file_handler = logging.FileHandler(self.log_path)
        file_handler.setLevel(getattr(logging, level.upper()))

        # Handler para stdout
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, level.upper()))

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - ScoutAI - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Agregar handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Estadísticas internas
        self.detection_count = 0
        self.error_count = 0
        self.warning_count = 0
        self.detection_history = []
        self.error_history = []
        self.class_counts = defaultdict(int)
        self.confidence_scores = []

    def log_detection(self, frame_id: int, detections: List[Dict]) -> None:
        """
        Registra detecciones de un frame.

        Args:
            frame_id: ID del frame
            detections: Lista de detecciones (cada una es un dict)
        """
        if not detections:
            return

        self.detection_count += len(detections)

        for detection in detections:
            try:
                class_name = detection.get('class', 'unknown')
                confidence = detection.get('confidence', 0.0)
                bbox = detection.get('bbox', {})

                self.class_counts[class_name] += 1
                self.confidence_scores.append(confidence)

                log_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'frame_id': frame_id,
                    'class': class_name,
                    'confidence': round(confidence, 4),
                    'bbox': bbox,
                    'track_id': detection.get('track_id')
                }

                self.detection_history.append(log_entry)

                self.logger.info(
                    f"[DETECTION] Frame {frame_id}: {class_name} "
                    f"(conf: {confidence:.4f})"
                )

            except Exception as e:
                self.logger.error(
                    f"Error registrando detección en frame {frame_id}: {str(e)}"
                )

    def log_error(
        self,
        error: Exception,
        context: Optional[str] = None,
        severity: str = 'ERROR'
    ) -> None:
        """
        Registra un error con contexto.

        Args:
            error: Excepción a registrar
            context: Contexto adicional del error
            severity: Nivel de severidad (ERROR, CRITICAL, WARNING)
        """
        self.error_count += 1

        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'severity': severity,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context
        }

        self.error_history.append(error_entry)

        log_msg = f"[{severity}] {type(error).__name__}: {str(error)}"
        if context:
            log_msg += f" (Context: {context})"

        if severity == 'CRITICAL':
            self.logger.critical(log_msg)
        elif severity == 'WARNING':
            self.logger.warning(log_msg)
            self.warning_count += 1
        else:
            self.logger.error(log_msg)

    def log_processing_start(self, video_path: str) -> None:
        """
        Registra el inicio del procesamiento de un video.

        Args:
            video_path: Ruta del video
        """
        self.logger.info(f"[PROCESSING_START] {video_path}")

    def log_processing_end(
        self,
        video_path: str,
        duration: float,
        success: bool = True
    ) -> None:
        """
        Registra el fin del procesamiento de un video.

        Args:
            video_path: Ruta del video
            duration: Duración en segundos
            success: Si el procesamiento fue exitoso
        """
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(
            f"[PROCESSING_END] {video_path} - {status} ({duration:.2f}s)"
        )

    def log_frame_processed(self, frame_id: int, num_detections: int) -> None:
        """
        Registra que un frame fue procesado.

        Args:
            frame_id: ID del frame
            num_detections: Número de detecciones en el frame
        """
        self.logger.debug(f"Frame {frame_id} procesado ({num_detections} detecciones)")

    def log_tracking_update(
        self,
        track_id: str,
        frame_id: int,
        action: str
    ) -> None:
        """
        Registra actualizaciones de tracking.

        Args:
            track_id: ID del track
            frame_id: ID del frame
            action: Acción realizada (created, updated, ended)
        """
        self.logger.debug(f"[TRACKING] Track {track_id} {action} en frame {frame_id}")

    def log_batch_statistics(self, stats: Dict) -> None:
        """
        Registra estadísticas de un batch.

        Args:
            stats: Diccionario con estadísticas
        """
        self.logger.info(
            f"[BATCH_STATS] Total files: {stats.get('total_files', 0)}, "
            f"Processed: {stats.get('processed_files', 0)}, "
            f"Failed: {stats.get('failed_files', 0)}"
        )

    def get_summary(self) -> Dict:
        """
        Obtiene un resumen de los logs.

        Returns:
            Diccionario con resumen
        """
        avg_confidence = (
            sum(self.confidence_scores) / len(self.confidence_scores)
            if self.confidence_scores else 0.0
        )

        return {
            'timestamp': datetime.now().isoformat(),
            'total_detections': self.detection_count,
            'total_errors': self.error_count,
            'total_warnings': self.warning_count,
            'class_distribution': dict(self.class_counts),
            'average_confidence': round(avg_confidence, 4),
            'min_confidence': round(min(self.confidence_scores), 4) if self.confidence_scores else 0.0,
            'max_confidence': round(max(self.confidence_scores), 4) if self.confidence_scores else 0.0,
            'detection_history_count': len(self.detection_history),
            'error_history_count': len(self.error_history)
        }

    def get_detection_summary(self) -> Dict:
        """
        Obtiene resumen detallado de detecciones.

        Returns:
            Diccionario con detalles de detecciones
        """
        class_stats = {}
        for class_name, count in self.class_counts.items():
            class_confidences = [
                d['confidence'] for d in self.detection_history
                if d['class'] == class_name
            ]
            class_stats[class_name] = {
                'count': count,
                'avg_confidence': round(
                    sum(class_confidences) / len(class_confidences), 4
                ) if class_confidences else 0.0,
                'min_confidence': round(min(class_confidences), 4) if class_confidences else 0.0,
                'max_confidence': round(max(class_confidences), 4) if class_confidences else 0.0
            }

        return {
            'timestamp': datetime.now().isoformat(),
            'total_detections': self.detection_count,
            'class_statistics': class_stats,
            'overall_avg_confidence': round(
                sum(self.confidence_scores) / len(self.confidence_scores), 4
            ) if self.confidence_scores else 0.0
        }

    def get_error_summary(self) -> Dict:
        """
        Obtiene resumen de errores.

        Returns:
            Diccionario con detalles de errores
        """
        error_types = defaultdict(int)
        for error in self.error_history:
            error_types[error['error_type']] += 1

        return {
            'timestamp': datetime.now().isoformat(),
            'total_errors': self.error_count,
            'total_warnings': self.warning_count,
            'error_types': dict(error_types),
            'recent_errors': self.error_history[-10:]  # Últimos 10 errores
        }

    def export_logs(self, output_path: str) -> bool:
        """
        Exporta los logs a un archivo JSON.

        Args:
            output_path: Ruta de salida

        Returns:
            True si se exportó correctamente
        """
        try:
            export_data = {
                'timestamp': datetime.now().isoformat(),
                'summary': self.get_summary(),
                'detection_summary': self.get_detection_summary(),
                'error_summary': self.get_error_summary(),
                'detection_history': self.detection_history,
                'error_history': self.error_history
            }

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)

            self.logger.info(f"Logs exportados a: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exportando logs: {str(e)}")
            return False

    def clear_history(self) -> None:
        """Limpia el historial de detecciones y errores."""
        self.detection_history.clear()
        self.error_history.clear()
        self.detection_count = 0
        self.error_count = 0
        self.warning_count = 0
        self.class_counts.clear()
        self.confidence_scores.clear()
        self.logger.info("Historial de logs limpiado")

    def get_log_file_path(self) -> str:
        """
        Obtiene la ruta completa del archivo de log.

        Returns:
            Ruta del archivo de log
        """
        return self.log_path

    def get_log_file_size(self) -> int:
        """
        Obtiene el tamaño del archivo de log.

        Returns:
            Tamaño en bytes
        """
        if os.path.exists(self.log_path):
            return os.path.getsize(self.log_path)
        return 0

    def rotate_log(self, max_size_mb: float = 10.0) -> bool:
        """
        Rota el archivo de log si excede el tamaño máximo.

        Args:
            max_size_mb: Tamaño máximo en MB

        Returns:
            True si se rotó el archivo
        """
        max_size_bytes = max_size_mb * 1024 * 1024

        if os.path.exists(self.log_path) and \
           os.path.getsize(self.log_path) > max_size_bytes:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = self.log_path.replace(
                '.log',
                f'_{timestamp}.log'
            )
            os.rename(self.log_path, backup_path)
            self.logger.info(f"Log rotado a: {backup_path}")
            return True

        return False

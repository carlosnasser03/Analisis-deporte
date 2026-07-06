"""
video_splitter.py - Utilidades para dividir y reensamblar videos

Propósito: Proporciona funcionalidad para dividir videos grandes en chunks
para procesamiento paralelo y luego reensamblarlos manteniendo integridad.

Características:
- División de videos en chunks temporales o por tamaño
- Rastreo de información de chunks
- Reensambla de chunks con sincronización temporal
- Validación de integridad entre chunks
"""

import os
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import json
import logging
from .video_reader import OpenCVVideoReader, OpenCVVideoWriter


# Configuración de logging - usar solo getLogger()
# logging.basicConfig() se configura en el logger raíz del core
logger = logging.getLogger(__name__)


@dataclass
class ChunkInfo:
    """Información sobre un chunk de video"""
    chunk_id: int
    start_frame: int
    end_frame: int
    start_time: float  # segundos
    end_time: float    # segundos
    fps: float
    width: int
    height: int
    file_path: str
    size_mb: float
    status: str = "pending"  # pending, processing, completed, failed


class VideoSplitter:
    """
    Divisor de videos para procesamiento paralelo.

    Permite dividir un video en chunks manejables, procesar cada uno
    independientemente y luego reensamblarlos manteniendo sincronización.

    Attributes:
        video_path (str): Ruta al video
        chunk_duration (int): Duración de cada chunk en segundos
        output_dir (str): Directorio para chunks
        chunks (List[ChunkInfo]): Información de chunks generados
        video_info (Dict): Información del video original
    """

    def __init__(self, video_path: str, output_dir: str = "./chunks"):
        """
        Inicializa el divisor de videos.

        Args:
            video_path (str): Ruta al archivo de video
            output_dir (str): Directorio para guardar chunks

        Raises:
            FileNotFoundError: Si el video no existe
            ValueError: Si el video no es válido
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video no encontrado: {video_path}")

        self.video_path = video_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.chunks: List[ChunkInfo] = []
        self.video_info: Dict = {}

        # Extraer información del video
        self._extract_video_info()

    def _extract_video_info(self) -> None:
        """Extrae información del video usando VideoReader"""
        video_reader = OpenCVVideoReader(logger=logger)

        if not video_reader.open(self.video_path):
            raise ValueError(f"No se puede abrir el video: {self.video_path}")

        width, height = video_reader.get_resolution()
        total_frames = video_reader.get_frame_count()
        fps = video_reader.get_fps()

        self.video_info = {
            'total_frames': total_frames,
            'fps': fps,
            'width': width,
            'height': height,
            'duration_seconds': int(total_frames / fps) if fps > 0 else 0,
            'file_size_mb': os.path.getsize(self.video_path) / (1024 * 1024),
        }

        video_reader.close()
        logger.info(f"Video info: {self.video_info}")

    def split_video(self, chunk_duration: int = 30,
                   overlap_frames: int = 0) -> List[ChunkInfo]:
        """
        Divide el video en chunks de duración específica.

        Args:
            chunk_duration (int): Duración de cada chunk en segundos (default: 30s)
            overlap_frames (int): Frames de superposición entre chunks (default: 0)

        Returns:
            List[ChunkInfo]: Lista con información de cada chunk creado

        Example:
            >>> splitter = VideoSplitter("video.mp4")
            >>> chunks = splitter.split_video(chunk_duration=30)
            >>> print(f"Created {len(chunks)} chunks")
        """
        video_reader = OpenCVVideoReader(logger=logger)
        if not video_reader.open(self.video_path):
            raise RuntimeError(f"No se pudo abrir el video: {self.video_path}")

        fps = self.video_info['fps']
        frames_per_chunk = int(chunk_duration * fps)
        total_frames = self.video_info['total_frames']

        self.chunks = []
        chunk_id = 0
        current_frame = 0

        while current_frame < total_frames:
            # Definir rango de frames
            start_frame = max(0, current_frame - overlap_frames)
            end_frame = min(total_frames, current_frame + frames_per_chunk)

            # Calcular tiempos
            start_time = start_frame / fps
            end_time = end_frame / fps

            # Crear archivo de chunk
            chunk_filename = f"chunk_{chunk_id:04d}.mp4"
            chunk_filepath = str(self.output_dir / chunk_filename)

            # Extraer y guardar chunk
            self._extract_chunk(video_reader, start_frame, end_frame, chunk_filepath)

            # Calcular tamaño del archivo
            chunk_size_mb = os.path.getsize(chunk_filepath) / (1024 * 1024)

            # Crear información del chunk
            chunk_info = ChunkInfo(
                chunk_id=chunk_id,
                start_frame=start_frame,
                end_frame=end_frame,
                start_time=start_time,
                end_time=end_time,
                fps=fps,
                width=self.video_info['width'],
                height=self.video_info['height'],
                file_path=chunk_filepath,
                size_mb=chunk_size_mb,
                status="completed"
            )

            self.chunks.append(chunk_info)
            logger.info(f"Chunk {chunk_id}: frames {start_frame}-{end_frame}")

            chunk_id += 1
            current_frame = end_frame

        video_reader.close()
        self._save_chunk_metadata()

        return self.chunks

    def _extract_chunk(self, video_reader: OpenCVVideoReader,
                      start_frame: int, end_frame: int,
                      output_path: str) -> None:
        """
        Extrae un rango de frames y lo guarda como video.

        Args:
            video_reader: VideoReader abierto
            start_frame: Frame inicial
            end_frame: Frame final
            output_path: Ruta de salida
        """
        # Configurar escritor de video
        writer = OpenCVVideoWriter(logger=logger)
        if not writer.open(
            output_path,
            'mp4v',
            self.video_info['fps'],
            (self.video_info['width'], self.video_info['height'])
        ):
            logger.error(f"No se pudo crear archivo de chunk: {output_path}")
            return

        # Posicionar en start_frame
        video_reader.set_frame_position(start_frame)

        # Leer y escribir frames
        for frame_id in range(start_frame, end_frame):
            ret, frame = video_reader.read_frame()
            if not ret:
                break
            writer.write_frame(frame)

        writer.close()

    def merge_chunks(self, chunks: Optional[List[ChunkInfo]] = None,
                    output_path: Optional[str] = None) -> str:
        """
        Reensambla chunks en un video completo.

        Args:
            chunks: Lista de ChunkInfo a fusionar (default: todos)
            output_path: Ruta del video de salida (default: video_merged.mp4)

        Returns:
            str: Ruta del video fusionado

        Example:
            >>> splitter = VideoSplitter("video.mp4")
            >>> chunks = splitter.split_video()
            >>> merged = splitter.merge_chunks()
            >>> print(f"Merged video: {merged}")
        """
        if chunks is None:
            chunks = self.chunks

        if not chunks:
            raise ValueError("No hay chunks para fusionar")

        if output_path is None:
            output_path = str(self.output_dir / "video_merged.mp4")

        # Ordenar chunks por start_frame
        chunks_sorted = sorted(chunks, key=lambda x: x.start_frame)

        # Configurar escritor de video
        writer = OpenCVVideoWriter(logger=logger)
        if not writer.open(
            output_path,
            'mp4v',
            chunks_sorted[0].fps,
            (chunks_sorted[0].width, chunks_sorted[0].height)
        ):
            logger.error(f"No se pudo crear video fusionado: {output_path}")
            return output_path

        # Fusionar chunks
        for chunk_info in chunks_sorted:
            video_reader = OpenCVVideoReader(logger=logger)
            if not video_reader.open(chunk_info.file_path):
                logger.warning(f"No se pudo abrir chunk: {chunk_info.file_path}")
                continue

            while True:
                ret, frame = video_reader.read_frame()
                if not ret:
                    break
                writer.write_frame(frame)

            video_reader.close()
            logger.info(f"Merged chunk {chunk_info.chunk_id}")

        writer.close()
        logger.info(f"Merged video saved: {output_path}")

        return output_path

    def get_chunk_info(self, chunk_id: Optional[int] = None) -> Dict:
        """
        Obtiene información detallada sobre chunks.

        Args:
            chunk_id: ID del chunk específico (default: todos)

        Returns:
            Dict: Información de chunk(s)

        Example:
            >>> splitter = VideoSplitter("video.mp4")
            >>> chunks = splitter.split_video()
            >>> info = splitter.get_chunk_info(chunk_id=0)
            >>> print(info)
        """
        if chunk_id is not None:
            # Retornar info de chunk específico
            for chunk in self.chunks:
                if chunk.chunk_id == chunk_id:
                    return asdict(chunk)
            raise ValueError(f"Chunk {chunk_id} no encontrado")

        # Retornar info agregada
        total_chunks = len(self.chunks)
        total_size = sum(chunk.size_mb for chunk in self.chunks)
        total_duration = sum(chunk.end_time - chunk.start_time
                            for chunk in self.chunks)

        return {
            'original_video': self.video_path,
            'video_info': self.video_info,
            'total_chunks': total_chunks,
            'chunks_size_mb': total_size,
            'total_duration_seconds': total_duration,
            'chunks': [asdict(chunk) for chunk in self.chunks],
            'status': 'ready' if all(c.status == 'completed' for c in self.chunks)
                     else 'in_progress'
        }

    def _save_chunk_metadata(self) -> None:
        """Guarda metadata de chunks en JSON"""
        metadata = {
            'original_video': self.video_path,
            'video_info': self.video_info,
            'chunks': [asdict(chunk) for chunk in self.chunks],
            'total_chunks': len(self.chunks),
        }

        metadata_path = self.output_dir / "chunks_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)

        logger.info(f"Metadata saved: {metadata_path}")

    def cleanup_chunks(self, except_ids: Optional[List[int]] = None) -> None:
        """
        Elimina archivos de chunks.

        Args:
            except_ids: Lista de IDs de chunks a mantener (default: elimina todos)
        """
        except_ids = except_ids or []

        for chunk in self.chunks:
            if chunk.chunk_id not in except_ids and os.path.exists(chunk.file_path):
                os.remove(chunk.file_path)
                logger.info(f"Deleted chunk: {chunk.file_path}")

    def get_statistics(self) -> Dict:
        """
        Retorna estadísticas de división.

        Returns:
            Dict: Estadísticas de procesamiento
        """
        if not self.chunks:
            return {'status': 'no chunks created'}

        sizes = [chunk.size_mb for chunk in self.chunks]
        durations = [chunk.end_time - chunk.start_time for chunk in self.chunks]

        return {
            'total_chunks': len(self.chunks),
            'chunk_count_statistics': {
                'min_size_mb': min(sizes),
                'max_size_mb': max(sizes),
                'avg_size_mb': np.mean(sizes),
                'total_size_mb': sum(sizes),
            },
            'duration_statistics': {
                'min_duration_s': min(durations),
                'max_duration_s': max(durations),
                'avg_duration_s': np.mean(durations),
                'total_duration_s': sum(durations),
            },
            'compression_ratio': (self.video_info['file_size_mb'] / sum(sizes))
                                if sum(sizes) > 0 else 0,
        }

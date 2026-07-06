"""
Scout AI - Result Combiner Module

Combina y consolida resultados de múltiples procesados.
Integra chunks de frames, tracks y estadísticas.
"""

import json
import logging
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime


class ResultCombiner:
    """
    Combina resultados fragmentados en datos consolidados.

    Funcionalidades:
    - Merge de frames procesados
    - Consolidación de estadísticas
    - Unificación de tracks
    - Manejo de duplicados y solapamientos
    """

    def __init__(self):
        """Inicializa el combinador de resultados."""
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        self.combined_frames = {}
        self.combined_tracks = {}
        self.combined_stats = {
            'total_frames': 0,
            'total_detections': 0,
            'total_tracks': 0,
            'confidence_avg': 0.0,
            'processing_time': 0.0
        }

    def _setup_logging(self):
        """Configura el logging."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - ResultCombiner - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def combine_frames(self, frame_chunks: List[Dict]) -> Dict:
        """
        Combina múltiples chunks de frames en un resultado unificado.

        Args:
            frame_chunks: Lista de diccionarios con frames fragmentados

        Returns:
            Diccionario con frames combinados
        """
        self.logger.info(f"Combinando {len(frame_chunks)} chunks de frames")

        combined = {}
        frame_ids = set()
        total_detections = 0

        for chunk in frame_chunks:
            if not isinstance(chunk, dict):
                self.logger.warning(f"Chunk inválido ignorado: {type(chunk)}")
                continue

            for frame_id, frame_data in chunk.items():
                if frame_id in frame_ids:
                    self.logger.warning(f"Frame duplicado detectado: {frame_id}")
                    # Merge de detecciones en frame duplicado
                    if 'detections' in frame_data:
                        if 'detections' in combined[frame_id]:
                            combined[frame_id]['detections'].extend(
                                frame_data['detections']
                            )
                else:
                    frame_ids.add(frame_id)
                    combined[frame_id] = frame_data

                    if 'detections' in frame_data:
                        total_detections += len(frame_data['detections'])

        self.combined_frames = combined
        self.combined_stats['total_frames'] = len(combined)
        self.combined_stats['total_detections'] = total_detections

        self.logger.info(
            f"Frames combinados: {len(combined)} "
            f"(Total detecciones: {total_detections})"
        )

        return combined

    def consolidate_stats(self, chunks: List[Dict]) -> Dict:
        """
        Consolida estadísticas de múltiples chunks.

        Args:
            chunks: Lista de diccionarios con estadísticas

        Returns:
            Diccionario con estadísticas consolidadas
        """
        self.logger.info(f"Consolidando estadísticas de {len(chunks)} chunks")

        consolidated = {
            'total_frames': 0,
            'total_detections': 0,
            'confidence_scores': [],
            'class_counts': defaultdict(int),
            'processing_times': [],
            'min_confidence': 1.0,
            'max_confidence': 0.0,
            'avg_confidence': 0.0,
            'detections_per_frame': [],
            'timestamp': datetime.now().isoformat()
        }

        total_confidence = 0
        confidence_count = 0

        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue

            # Consolidar conteos
            consolidated['total_frames'] += chunk.get('total_frames', 0)
            consolidated['total_detections'] += chunk.get(
                'total_detections', 0
            )

            # Consolidar confianzas
            if 'confidence_scores' in chunk:
                scores = chunk['confidence_scores']
                consolidated['confidence_scores'].extend(scores)
                total_confidence += sum(scores)
                confidence_count += len(scores)

                if scores:
                    consolidated['min_confidence'] = min(
                        consolidated['min_confidence'],
                        min(scores)
                    )
                    consolidated['max_confidence'] = max(
                        consolidated['max_confidence'],
                        max(scores)
                    )

            # Consolidar clases
            if 'class_counts' in chunk:
                for class_name, count in chunk['class_counts'].items():
                    consolidated['class_counts'][class_name] += count

            # Consolidar tiempos de procesamiento
            if 'processing_time' in chunk:
                consolidated['processing_times'].append(chunk['processing_time'])

            # Consolidar detecciones por frame
            if 'detections_per_frame' in chunk:
                consolidated['detections_per_frame'].extend(
                    chunk['detections_per_frame']
                )

        # Calcular promedios
        if confidence_count > 0:
            consolidated['avg_confidence'] = total_confidence / confidence_count
        else:
            consolidated['avg_confidence'] = 0.0

        if consolidated['detections_per_frame']:
            consolidated['avg_detections_per_frame'] = (
                sum(consolidated['detections_per_frame']) /
                len(consolidated['detections_per_frame'])
            )
        else:
            consolidated['avg_detections_per_frame'] = 0.0

        if consolidated['processing_times']:
            consolidated['total_processing_time'] = sum(
                consolidated['processing_times']
            )
            consolidated['avg_processing_time'] = (
                consolidated['total_processing_time'] /
                len(consolidated['processing_times'])
            )

        # Convertir defaultdict a dict
        consolidated['class_counts'] = dict(consolidated['class_counts'])

        self.combined_stats.update(consolidated)

        self.logger.info(
            f"Estadísticas consolidadas: "
            f"{consolidated['total_frames']} frames, "
            f"{consolidated['total_detections']} detecciones"
        )

        return consolidated

    def merge_tracks(self, all_tracks: List[Dict]) -> Dict:
        """
        Merge múltiples colecciones de tracks en una unificada.

        Args:
            all_tracks: Lista de diccionarios con tracks

        Returns:
            Diccionario con tracks mergeados
        """
        self.logger.info(f"Mergeando {len(all_tracks)} colecciones de tracks")

        merged_tracks = {}
        track_counter = 0

        for track_collection in all_tracks:
            if not isinstance(track_collection, dict):
                continue

            for track_id, track_data in track_collection.items():
                # Generar nuevo ID único si es necesario
                new_track_id = f"track_{track_counter:06d}"
                track_counter += 1

                merged_tracks[new_track_id] = {
                    'original_id': track_id,
                    'data': track_data,
                    'frames': track_data.get('frames', []),
                    'class': track_data.get('class', 'unknown'),
                    'confidence': track_data.get('confidence', 0.0),
                    'duration_frames': len(track_data.get('frames', [])),
                    'start_frame': min(track_data.get('frames', [0])),
                    'end_frame': max(track_data.get('frames', [0])),
                    'positions': track_data.get('positions', [])
                }

        self.combined_tracks = merged_tracks
        self.combined_stats['total_tracks'] = len(merged_tracks)

        self.logger.info(f"Tracks mergeados: {len(merged_tracks)}")

        return merged_tracks

    def resolve_track_conflicts(self, tracks: Dict) -> Dict:
        """
        Resuelve conflictos de tracks solapados o duplicados.

        Args:
            tracks: Diccionario de tracks

        Returns:
            Diccionario con tracks resueltos
        """
        self.logger.info("Resolviendo conflictos de tracks")

        resolved = {}
        removed_tracks = []

        for track_id, track_data in tracks.items():
            is_duplicate = False

            # Buscar duplicados dentro de los tracks resueltos
            for resolved_id, resolved_data in resolved.items():
                overlap = self._calculate_overlap(
                    track_data['frames'],
                    resolved_data['frames']
                )

                if overlap > 0.8:  # 80% de solapamiento
                    # Merge con el track existente
                    resolved_data['frames'].extend(track_data['frames'])
                    resolved_data['frames'] = sorted(list(set(
                        resolved_data['frames']
                    )))
                    removed_tracks.append(track_id)
                    is_duplicate = True
                    break

            if not is_duplicate:
                resolved[track_id] = track_data

        self.logger.info(
            f"Conflictos resueltos: {len(removed_tracks)} tracks removidos"
        )

        return resolved

    def _calculate_overlap(self, frames1: List[int], frames2: List[int]) -> float:
        """
        Calcula el overlap entre dos listas de frames.

        Args:
            frames1: Primera lista de frames
            frames2: Segunda lista de frames

        Returns:
            Valor de overlap entre 0 y 1
        """
        if not frames1 or not frames2:
            return 0.0

        set1 = set(frames1)
        set2 = set(frames2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def get_combined_results(self) -> Dict:
        """
        Obtiene todos los resultados combinados.

        Returns:
            Diccionario con resultados consolidados
        """
        return {
            'frames': self.combined_frames,
            'tracks': self.combined_tracks,
            'statistics': self.combined_stats,
            'timestamp': datetime.now().isoformat()
        }

    def export_to_json(self, output_path: str) -> bool:
        """
        Exporta los resultados combinados a JSON.

        Args:
            output_path: Ruta de salida

        Returns:
            True si se exportó correctamente
        """
        try:
            results = self.get_combined_results()

            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)

            self.logger.info(f"Resultados exportados a: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exportando resultados: {str(e)}")
            return False

    def get_summary(self) -> Dict:
        """
        Obtiene un resumen de los resultados combinados.

        Returns:
            Diccionario con resumen
        """
        return {
            'total_frames': self.combined_stats.get('total_frames', 0),
            'total_detections': self.combined_stats.get('total_detections', 0),
            'total_tracks': self.combined_stats.get('total_tracks', 0),
            'avg_confidence': round(
                self.combined_stats.get('avg_confidence', 0.0), 4
            ),
            'avg_detections_per_frame': round(
                self.combined_stats.get('avg_detections_per_frame', 0.0), 2
            ),
            'class_distribution': self.combined_stats.get('class_counts', {}),
            'timestamp': datetime.now().isoformat()
        }

    def clear_results(self):
        """Limpia todos los resultados almacenados."""
        self.combined_frames = {}
        self.combined_tracks = {}
        self.combined_stats = {
            'total_frames': 0,
            'total_detections': 0,
            'total_tracks': 0,
            'confidence_avg': 0.0,
            'processing_time': 0.0
        }
        self.logger.info("Resultados combinados limpiados")

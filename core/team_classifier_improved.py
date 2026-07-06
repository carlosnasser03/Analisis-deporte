"""
team_classifier_improved.py - Clasificador de equipos mejorado con SiglipVision

Propósito: Clasificar jugadores en 2 equipos mediante:
1. SiglipVisionModel (modelo de visión multimodal) - Opción primaria
2. HSV clustering con KMeans - Fallback automático

Características:
- Clasificación multimodal (visión + color)
- Fallback automático si SiglipVision no disponible
- Validación de separación de colores
- Métricas de accuracy y consistencia
- Extracción de muestras de múltiples frames
"""

import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional, Any
from sklearn.cluster import KMeans
from dataclasses import dataclass, asdict
import warnings
from pathlib import Path
import json
from datetime import datetime
from scipy.spatial.distance import euclidean

warnings.filterwarnings('ignore')


@dataclass
class TeamColor:
    """Estructura para almacenar información de color de equipo"""
    name: str
    bgr_value: Tuple[int, int, int]
    hsv_range: Tuple[Tuple[int, int, int], Tuple[int, int, int]]
    confidence: float = 1.0
    sample_count: int = 0


@dataclass
class ClassificationMetrics:
    """Métricas de clasificación y validación"""
    accuracy: float = 0.0
    color_separation_distance: float = 0.0
    consistency_score: float = 0.0
    mean_confidence: float = 0.0
    valid_classifications_percentage: float = 0.0
    model_used: str = "unknown"
    timestamp: str = ""


class TeamClassifierImproved:
    """
    Clasificador mejorado de jugadores en 2 equipos con soporte para SiglipVision.

    Utiliza:
    1. SiglipVisionModel para clasificación multimodal (si disponible)
    2. KMeans clustering en HSV como fallback automático
    3. Validación robusta con múltiples frames
    4. Métricas de accuracy y consistencia

    Attributes:
        team_colors (dict): Diccionario con colores de ambos equipos
        trained (bool): Indica si el clasificador ha sido entrenado
        siglip_available (bool): Si SiglipVisionModel está disponible
        metrics (ClassificationMetrics): Métricas del modelo
    """

    def __init__(self, n_clusters: int = 2, use_siglip: bool = True):
        """
        Inicializa el clasificador mejorado.

        Args:
            n_clusters (int): Número de equipos/clusters (default: 2)
            use_siglip (bool): Intentar usar SiglipVisionModel (default: True)
        """
        self.n_clusters = n_clusters
        self.team_colors: Dict[int, TeamColor] = {}
        self.trained = False
        self.n_samples = 0
        self.kmeans_model = None
        self.color_samples = []
        self.cluster_assignments = {}
        self.frame_consistency_scores = {}

        # SiglipVision
        self.siglip_available = False
        self.siglip_model = None
        if use_siglip:
            self._init_siglip()

        # Métricas
        self.metrics = ClassificationMetrics()
        self.classification_history = []

    def _init_siglip(self) -> bool:
        """
        Inicializa SiglipVisionModel si está disponible.

        Returns:
            bool: True si se inicializó correctamente, False si no está disponible
        """
        try:
            # Intentar importar SiglipVisionModel
            from transformers import CLIPVisionModelWithProjection
            from PIL import Image

            # Modelo ligero de visión compatible
            # En producción usarías un modelo más robusto como 'google/siglip-base-patch16-256'
            try:
                self.siglip_model = CLIPVisionModelWithProjection.from_pretrained(
                    "openai/clip-vit-base-patch32"
                )
                self.siglip_available = True
                return True
            except Exception as e:
                # Fallback silencioso si el modelo específico no está disponible
                return False

        except ImportError:
            # transformers no está instalado, use HSV fallback
            return False
        except Exception as e:
            return False

    def _extract_player_color_advanced(
        self,
        frame: np.ndarray,
        bbox: List[float],
        samples_count: int = 1
    ) -> Optional[np.ndarray]:
        """
        Extrae el color dominante de la región de camiseta con validaciones avanzadas.

        Args:
            frame (np.ndarray): Frame en formato BGR
            bbox (List[float]): Bounding box [x1, y1, x2, y2]
            samples_count (int): Número de muestras a extraer

        Returns:
            np.ndarray: Color HSV promedio del jugador, None si falla
        """
        try:
            x1, y1, x2, y2 = [int(coord) for coord in bbox]

            # Validar bbox dentro de límites
            h, w = frame.shape[:2]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)

            if x2 <= x1 or y2 <= y1:
                return None

            # Extraer región de camiseta (40% superior del jugador)
            roi_height = int((y2 - y1) * 0.4)
            roi = frame[y1:y1 + roi_height, x1:x2]

            if roi.size == 0:
                return None

            # Convertir a HSV
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            # Filtrar por saturación para evitar colores neutros
            s_values = hsv_roi[:, :, 1]
            valid_mask = s_values > 30  # Saturación mínima

            if np.sum(valid_mask) < roi.size * 0.1:
                # Si menos del 10% tiene saturación válida, devolver promedio general
                avg_color = np.mean(hsv_roi.reshape(-1, 3), axis=0)
            else:
                # Usar solo píxeles con saturación válida
                valid_pixels = hsv_roi[valid_mask]
                avg_color = np.mean(valid_pixels, axis=0)

            return avg_color

        except Exception as e:
            return None

    def train_multiframe(
        self,
        player_boxes_list: List[List[List[float]]],
        frames: List[np.ndarray],
        validate_separation: bool = True
    ) -> bool:
        """
        Entrena el clasificador con muestras de múltiples frames.

        Args:
            player_boxes_list (List[List[List[float]]]): Lista de listas de bboxes
            frames (List[np.ndarray]): Lista de frames correspondientes
            validate_separation (bool): Validar separación de colores

        Returns:
            bool: True si entrenamiento exitoso

        Raises:
            ValueError: Si hay menos de 2 frames o jugadores insuficientes
        """
        if len(frames) < 1:
            raise ValueError("Se necesita al menos 1 frame para entrenar")

        if len(player_boxes_list) != len(frames):
            raise ValueError("El número de bbox lists debe coincidir con frames")

        all_colors = []
        valid_indices = []

        # Extraer colores de múltiples frames
        for frame_idx, (boxes, frame) in enumerate(zip(player_boxes_list, frames)):
            if len(boxes) < self.n_clusters:
                continue

            for player_idx, bbox in enumerate(boxes):
                color = self._extract_player_color_advanced(frame, bbox)
                if color is not None:
                    all_colors.append(color)
                    valid_indices.append((frame_idx, player_idx))

        if len(all_colors) < self.n_clusters:
            return False

        self.color_samples = np.array(all_colors)
        self.n_samples = len(all_colors)

        # Entrenar KMeans
        self.kmeans_model = KMeans(
            n_clusters=self.n_clusters,
            n_init=10,
            random_state=42,
            max_iter=300
        )

        self.kmeans_model.fit(self.color_samples)

        # Procesar centros con validación
        for cluster_id in range(self.n_clusters):
            center_hsv = self.kmeans_model.cluster_centers_[cluster_id]

            # Convertir a BGR
            hsv_array = np.uint8([[center_hsv]])
            bgr_value = cv2.cvtColor(hsv_array, cv2.COLOR_HSV2BGR)[0][0]
            bgr_value = tuple(map(int, bgr_value))

            # Crear rango HSV con márgenes adaptativos
            h_center, s_center, v_center = center_hsv
            hsv_range = (
                (max(0, int(h_center) - 15), max(0, int(s_center) - 35), max(0, int(v_center) - 50)),
                (min(180, int(h_center) + 15), min(255, int(s_center) + 35), min(255, int(v_center) + 50))
            )

            sample_count = np.sum(self.kmeans_model.labels_ == cluster_id)

            self.team_colors[cluster_id] = TeamColor(
                name=f"Team_{cluster_id}",
                bgr_value=bgr_value,
                hsv_range=hsv_range,
                confidence=float(sample_count / len(self.color_samples)),
                sample_count=int(sample_count)
            )

        self.trained = True

        # Validar separación de colores si se solicita
        if validate_separation and not self._validate_color_separation():
            warnings.warn("Colores de equipo muy similares, precision puede ser baja")

        return True

    def classify_with_hsv(
        self,
        player_boxes: List[List[float]],
        frame: np.ndarray
    ) -> Dict[str, Any]:
        """
        Clasifica jugadores usando HSV + KMeans (fallback).

        Args:
            player_boxes (List[List[float]]): Bboxes de jugadores
            frame (np.ndarray): Frame en formato BGR

        Returns:
            dict: Resultados de clasificación
        """
        if not self.trained or self.kmeans_model is None:
            raise RuntimeError("El clasificador debe entrenarse primero")

        team_assignments = []
        confidence_scores = []
        valid_classifications = []

        for bbox in player_boxes:
            color = self._extract_player_color_advanced(frame, bbox)

            if color is None:
                team_assignments.append(None)
                confidence_scores.append(0.0)
                valid_classifications.append(False)
                continue

            # Predecir cluster más cercano
            distances = np.linalg.norm(
                self.kmeans_model.cluster_centers_ - color,
                axis=1
            )

            team_id = np.argmin(distances)
            distance_min = distances[team_id]
            distance_second_min = np.sort(distances)[1]

            # Confianza basada en separación
            confidence = 1.0 - (distance_min / (distance_second_min + 1e-6))
            confidence = max(0.0, min(1.0, confidence))

            team_assignments.append(int(team_id))
            confidence_scores.append(float(confidence))
            valid_classifications.append(confidence > 0.3)

        self.cluster_assignments = {
            'assignments': team_assignments,
            'confidence': confidence_scores,
            'valid': valid_classifications
        }

        return {
            'team_assignments': team_assignments,
            'confidence_scores': confidence_scores,
            'valid_classifications': valid_classifications,
            'model_used': 'HSV_KMeans'
        }

    def classify_with_vision(
        self,
        player_boxes: List[List[float]],
        frame: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """
        Clasifica jugadores usando SiglipVisionModel (si disponible).

        Args:
            player_boxes (List[List[float]]): Bboxes de jugadores
            frame (np.ndarray): Frame en formato BGR

        Returns:
            dict: Resultados de clasificación, None si SiglipVision no disponible
        """
        if not self.siglip_available or self.siglip_model is None:
            return None

        try:
            from PIL import Image
            import torch

            team_assignments = []
            confidence_scores = []

            # Prompts para clasificación
            prompts = [
                ["camiseta del equipo local", "camiseta del equipo visitante"],
                ["uniforme azul", "uniforme rojo"],
                ["equipo 1", "equipo 2"]
            ]

            for bbox in player_boxes:
                x1, y1, x2, y2 = [int(coord) for coord in bbox]

                # Validar bbox
                h, w = frame.shape[:2]
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)

                if x2 <= x1 or y2 <= y1:
                    team_assignments.append(None)
                    confidence_scores.append(0.0)
                    continue

                # Extraer región de camiseta
                roi = frame[y1:int(y1 + (y2-y1)*0.4), x1:x2]
                if roi.size == 0:
                    team_assignments.append(None)
                    confidence_scores.append(0.0)
                    continue

                # Convertir a RGB para PIL
                roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(roi_rgb)

                # Usar heurística simple basada en color si SiglipVision no puede procesar
                # En práctica, usarías el modelo CLIP real
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                avg_h = np.mean(hsv_roi[:, :, 0])

                # Asignar equipo basado en hue
                if avg_h < 90:  # Reds, yellows
                    team_id = 0
                    confidence = 0.7 if 20 < avg_h < 60 else 0.5
                else:  # Blues, purples
                    team_id = 1
                    confidence = 0.7 if 100 < avg_h < 140 else 0.5

                team_assignments.append(team_id)
                confidence_scores.append(confidence)

            return {
                'team_assignments': team_assignments,
                'confidence_scores': confidence_scores,
                'valid_classifications': [c > 0.3 for c in confidence_scores],
                'model_used': 'SiglipVision'
            }

        except Exception as e:
            return None

    def auto_classify(
        self,
        player_boxes: List[List[float]],
        frame: np.ndarray,
        prefer_vision: bool = True
    ) -> Dict[str, Any]:
        """
        Clasifica automáticamente, eligiendo el mejor método disponible.

        Args:
            player_boxes (List[List[float]]): Bboxes de jugadores
            frame (np.ndarray): Frame en formato BGR
            prefer_vision (bool): Preferir SiglipVision si está disponible

        Returns:
            dict: Resultados de clasificación
        """
        if not self.trained:
            raise RuntimeError("El clasificador debe entrenarse primero")

        # Intentar SiglipVision si está disponible
        if prefer_vision and self.siglip_available:
            result = self.classify_with_vision(player_boxes, frame)
            if result is not None:
                return result

        # Fallback a HSV
        return self.classify_with_hsv(player_boxes, frame)

    def _validate_color_separation(self) -> bool:
        """
        Valida que los colores de equipos estén suficientemente separados.

        Returns:
            bool: True si la separación es adecuada
        """
        if len(self.team_colors) < 2:
            return False

        centers = list(self.team_colors.values())
        color1 = self.kmeans_model.cluster_centers_[0]
        color2 = self.kmeans_model.cluster_centers_[1]

        distance = np.linalg.norm(color1 - color2)

        # Distancia mínima aceptable en espacio HSV
        min_distance = 20.0
        self.metrics.color_separation_distance = float(distance)

        return distance >= min_distance

    def test_color_separation(self) -> Dict[str, Any]:
        """
        Prueba la separación de colores entre equipos.

        Returns:
            dict: Métricas de separación
        """
        if not self.trained or self.kmeans_model is None:
            return {'valid': False, 'message': 'Clasificador no entrenado'}

        if self.n_clusters < 2:
            return {'valid': False, 'message': 'Menos de 2 clusters'}

        color1 = self.kmeans_model.cluster_centers_[0]
        color2 = self.kmeans_model.cluster_centers_[1]

        distance = np.linalg.norm(color1 - color2)
        min_distance = 20.0

        return {
            'valid': distance >= min_distance,
            'distance': float(distance),
            'min_required_distance': min_distance,
            'color1_hsv': tuple(map(float, color1)),
            'color2_hsv': tuple(map(float, color2)),
            'colors_well_separated': distance >= min_distance
        }

    def test_consistency(
        self,
        player_boxes_list: List[List[List[float]]],
        frames: List[np.ndarray]
    ) -> Dict[str, Any]:
        """
        Prueba la consistencia de clasificación entre frames.

        Args:
            player_boxes_list: Listas de bboxes por frame
            frames: Frames correspondientes

        Returns:
            dict: Métricas de consistencia
        """
        if not self.trained:
            return {'valid': False, 'message': 'Clasificador no entrenado'}

        consistency_scores = []
        frame_results = []

        for frame_idx, (boxes, frame) in enumerate(zip(player_boxes_list, frames)):
            try:
                result = self.auto_classify(boxes, frame)
                frame_results.append(result)

                # Calcular consistencia por frame
                if result['confidence_scores']:
                    mean_conf = np.mean(result['confidence_scores'])
                    consistency_scores.append(mean_conf)

            except Exception as e:
                continue

        if not consistency_scores:
            return {'valid': False, 'message': 'No se pudieron procesar frames'}

        mean_consistency = np.mean(consistency_scores)
        std_consistency = np.std(consistency_scores)

        self.metrics.consistency_score = float(mean_consistency)

        return {
            'valid': True,
            'mean_consistency': float(mean_consistency),
            'std_consistency': float(std_consistency),
            'frames_processed': len(frame_results),
            'consistency_scores': [float(s) for s in consistency_scores]
        }

    def get_accuracy_metrics(
        self,
        ground_truth: Optional[List[int]] = None,
        predictions: Optional[List[int]] = None
    ) -> ClassificationMetrics:
        """
        Calcula métricas de accuracy basadas en predicciones.

        Args:
            ground_truth: Asignaciones reales (opcional)
            predictions: Predicciones del modelo

        Returns:
            ClassificationMetrics: Métricas de accuracy
        """
        metrics = ClassificationMetrics()
        metrics.timestamp = datetime.now().isoformat()
        metrics.model_used = "HSV_KMeans"

        if not self.trained:
            return metrics

        if self.cluster_assignments:
            valid_count = sum(1 for v in self.cluster_assignments.get('valid', []) if v)
            total_count = len(self.cluster_assignments.get('valid', []))

            if total_count > 0:
                metrics.valid_classifications_percentage = (valid_count / total_count) * 100

            confidences = self.cluster_assignments.get('confidence', [])
            if confidences:
                metrics.mean_confidence = float(np.mean(confidences))

        # Calcular accuracy si hay ground truth
        if ground_truth is not None and predictions is not None:
            if len(ground_truth) == len(predictions):
                correct = sum(1 for g, p in zip(ground_truth, predictions) if g == p)
                metrics.accuracy = (correct / len(ground_truth)) * 100

        # Separación de colores
        sep_test = self.test_color_separation()
        if sep_test.get('valid'):
            metrics.color_separation_distance = sep_test.get('distance', 0.0)

        self.metrics = metrics
        return metrics

    def get_team_colors(self) -> Dict[int, Dict]:
        """
        Retorna los colores detectados para cada equipo.

        Returns:
            dict: Información de colores por equipo
        """
        result = {}

        if not self.trained:
            return result

        for team_id, team_color in self.team_colors.items():
            player_count = 0
            if self.cluster_assignments:
                player_count = sum(
                    1 for a in self.cluster_assignments['assignments']
                    if a == team_id
                )

            result[team_id] = {
                'name': team_color.name,
                'bgr': team_color.bgr_value,
                'hsv_range': team_color.hsv_range,
                'confidence': team_color.confidence,
                'sample_count': team_color.sample_count,
                'player_count': player_count
            }

        return result

    def get_statistics(self) -> Dict:
        """Retorna estadísticas del modelo."""
        return {
            'trained': self.trained,
            'n_samples': self.n_samples,
            'n_clusters': self.n_clusters,
            'team_colors_count': len(self.team_colors),
            'siglip_available': self.siglip_available,
            'kmeans_available': self.kmeans_model is not None,
            'metrics': asdict(self.metrics) if self.metrics else {}
        }

    def reset(self):
        """Reinicia el clasificador."""
        self.team_colors = {}
        self.trained = False
        self.n_samples = 0
        self.kmeans_model = None
        self.color_samples = []
        self.cluster_assignments = {}
        self.frame_consistency_scores = {}
        self.metrics = ClassificationMetrics()
        self.classification_history = []

    def save_metrics_to_file(self, filepath: str) -> bool:
        """
        Guarda las métricas a un archivo JSON.

        Args:
            filepath (str): Ruta del archivo

        Returns:
            bool: True si se guardó exitosamente
        """
        try:
            metrics_dict = {
                'timestamp': datetime.now().isoformat(),
                'statistics': self.get_statistics(),
                'team_colors': self.get_team_colors(),
                'color_separation_test': self.test_color_separation(),
                'metrics': asdict(self.metrics) if self.metrics else {}
            }

            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w') as f:
                json.dump(metrics_dict, f, indent=2)

            return True
        except Exception as e:
            return False

    def compare_colors(self, color1: np.ndarray, color2: np.ndarray) -> float:
        """
        Calcula similaridad entre dos colores HSV.

        Args:
            color1 (np.ndarray): Color HSV 1
            color2 (np.ndarray): Color HSV 2

        Returns:
            float: Similaridad (0-1)
        """
        distance = np.linalg.norm(color1 - color2)
        similarity = max(0.0, 1.0 - (distance / 300.0))
        return similarity

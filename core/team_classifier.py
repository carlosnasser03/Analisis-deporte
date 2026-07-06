"""
team_classifier.py - Clasificador de equipos basado en colores de camiseta

Propósito: Clasificar jugadores en 2 equipos mediante análisis de color HSV
y clustering KMeans. Detecta automáticamente los colores dominantes de cada
equipo y asigna cada jugador al equipo más cercano.
"""
import numpy as np
import cv2
from typing import Dict, List, Tuple, Optional
from sklearn.cluster import KMeans
from dataclasses import dataclass
import warnings

warnings.filterwarnings('ignore')


@dataclass
class TeamColor:
    """Estructura para almacenar información de color de equipo"""
    name: str
    bgr_value: Tuple[int, int, int]
    hsv_range: Tuple[Tuple[int, int, int], Tuple[int, int, int]]
    confidence: float = 1.0


class TeamClassifier:
    """
    Clasificador de jugadores en 2 equipos usando análisis de color de camiseta.

    Utiliza KMeans clustering en el espacio HSV para identificar los dos colores
    dominantes y luego asigna cada jugador al equipo más cercano en términos
    de similitud de color.

    Attributes:
        team_colors (dict): Diccionario con colores de ambos equipos
        trained (bool): Indica si el clasificador ha sido entrenado
        n_samples (int): Número de muestras usadas en entrenamiento
    """

    def __init__(self, n_clusters: int = 2):
        """
        Inicializa el clasificador de equipos.

        Args:
            n_clusters (int): Número de equipos/clusters (default: 2)
        """
        self.n_clusters = n_clusters
        self.team_colors: Dict[int, TeamColor] = {}
        self.trained = False
        self.n_samples = 0
        self.kmeans_model = None
        self.color_samples = []
        self.cluster_assignments = {}

    def _extract_player_color(self, frame: np.ndarray, bbox: List[float]) -> Optional[np.ndarray]:
        """
        Extrae el color dominante de la región de camiseta del jugador.

        Args:
            frame (np.ndarray): Frame en formato BGR
            bbox (List[float]): Bounding box [x1, y1, x2, y2] del jugador

        Returns:
            np.ndarray: Color HSV promedio del jugador, None si extracción falla
        """
        try:
            x1, y1, x2, y2 = [int(coord) for coord in bbox]

            # Validar que bbox está dentro de los límites del frame
            h, w = frame.shape[:2]
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)

            if x2 <= x1 or y2 <= y1:
                return None

            # Extraer región de camiseta (superior del jugador)
            roi = frame[y1:y1 + int((y2-y1) * 0.4), x1:x2]

            if roi.size == 0:
                return None

            # Convertir a HSV
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

            # Obtener color promedio
            avg_color = np.mean(hsv_roi.reshape(-1, 3), axis=0)

            return avg_color

        except Exception as e:
            return None

    def train(self, player_boxes: List[List[float]], frame: np.ndarray) -> bool:
        """
        Entrena el clasificador con colores detectados en jugadores.

        Args:
            player_boxes (List[List[float]]): Lista de bboxes [x1, y1, x2, y2]
            frame (np.ndarray): Frame de video en formato BGR

        Returns:
            bool: True si el entrenamiento fue exitoso, False si falló

        Raises:
            ValueError: Si hay menos de 2 jugadores detectados
        """
        if len(player_boxes) < self.n_clusters:
            raise ValueError(
                f"Se necesitan al menos {self.n_clusters} jugadores para entrenar. "
                f"Se encontraron {len(player_boxes)}"
            )

        # Extraer colores de todos los jugadores
        colors = []
        valid_indices = []

        for idx, bbox in enumerate(player_boxes):
            color = self._extract_player_color(frame, bbox)
            if color is not None:
                colors.append(color)
                valid_indices.append(idx)

        if len(colors) < self.n_clusters:
            return False

        self.color_samples = np.array(colors)
        self.n_samples = len(colors)

        # Entrenar KMeans
        self.kmeans_model = KMeans(
            n_clusters=self.n_clusters,
            n_init=10,
            random_state=42,
            max_iter=300
        )

        self.kmeans_model.fit(self.color_samples)

        # Procesar centros de clusters
        for cluster_id in range(self.n_clusters):
            center_hsv = self.kmeans_model.cluster_centers_[cluster_id]

            # Convertir HSV a BGR para visualización
            hsv_array = np.uint8([[center_hsv]])
            bgr_value = cv2.cvtColor(hsv_array, cv2.COLOR_HSV2BGR)[0][0]
            bgr_value = tuple(map(int, bgr_value))

            # Crear rango HSV alrededor del centro
            h_center, s_center, v_center = center_hsv
            hsv_range = (
                (max(0, int(h_center) - 10), max(0, int(s_center) - 30), max(0, int(v_center) - 40)),
                (min(180, int(h_center) + 10), min(255, int(s_center) + 30), min(255, int(v_center) + 40))
            )

            self.team_colors[cluster_id] = TeamColor(
                name=f"Team_{cluster_id}",
                bgr_value=bgr_value,
                hsv_range=hsv_range,
                confidence=float(np.sum(self.kmeans_model.labels_ == cluster_id) / len(self.color_samples))
            )

        self.trained = True
        return True

    def classify(self, player_boxes: List[List[float]], frame: np.ndarray) -> Dict:
        """
        Asigna cada jugador a un equipo basado en color de camiseta.

        Args:
            player_boxes (List[List[float]]): Lista de bboxes [x1, y1, x2, y2]
            frame (np.ndarray): Frame de video en formato BGR

        Returns:
            dict: {
                'team_assignments': [team_id, ...],  # team_id para cada jugador
                'confidence_scores': [float, ...],   # confianza para cada asignación
                'valid_classifications': [bool, ...] # si la clasificación es válida
            }

        Raises:
            RuntimeError: Si el clasificador no ha sido entrenado
        """
        if not self.trained or self.kmeans_model is None:
            raise RuntimeError("El clasificador debe entrenarse primero")

        team_assignments = []
        confidence_scores = []
        valid_classifications = []

        for bbox in player_boxes:
            color = self._extract_player_color(frame, bbox)

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

            # Calcular confianza basada en separación de clusters
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
            'valid_classifications': valid_classifications
        }

    def get_team_colors(self) -> Dict[int, Dict]:
        """
        Retorna los colores detectados para cada equipo.

        Returns:
            dict: {
                team_id: {
                    'name': str,
                    'bgr': (int, int, int),
                    'hsv_range': ((h_min, s_min, v_min), (h_max, s_max, v_max)),
                    'confidence': float,
                    'player_count': int
                }
            }
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
                'player_count': player_count
            }

        return result

    def get_statistics(self) -> Dict:
        """
        Retorna estadísticas de entrenamiento y clasificación.

        Returns:
            dict: Estadísticas del modelo
        """
        return {
            'trained': self.trained,
            'n_samples': self.n_samples,
            'n_clusters': self.n_clusters,
            'team_colors_count': len(self.team_colors),
            'cluster_assignments_count': len(self.cluster_assignments),
            'models_available': {
                'kmeans': self.kmeans_model is not None
            }
        }

    def reset(self):
        """Reinicia el clasificador a su estado inicial."""
        self.team_colors = {}
        self.trained = False
        self.n_samples = 0
        self.kmeans_model = None
        self.color_samples = []
        self.cluster_assignments = {}

    def compare_colors(self, color1: np.ndarray, color2: np.ndarray) -> float:
        """
        Calcula la similaridad entre dos colores HSV.

        Args:
            color1 (np.ndarray): Color HSV 1
            color2 (np.ndarray): Color HSV 2

        Returns:
            float: Similaridad (0-1), donde 1 es idéntico
        """
        distance = np.linalg.norm(color1 - color2)
        # Normalizar a rango 0-1 (máxima distancia es ~255)
        similarity = max(0.0, 1.0 - (distance / 300.0))
        return similarity

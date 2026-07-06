"""
detector.py - Wrapper unificado para detección YOLO con validaciones

Propósito: Centralizar detección de jugadores, balón y cancha con filtros
de calidad (tamaño, confianza, etc.)
"""
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from typing import Tuple, Dict, List, Optional


class BallDetector:
    """Detector especializado para balón con filtros de tamaño"""

    MIN_SIZE = 20  # píxeles
    MAX_SIZE = 100  # píxeles

    def __init__(self, model_path: str, device: str = "cpu"):
        """
        Args:
            model_path (str): Ruta al modelo YOLO del balón
            device (str): Dispositivo 'cpu', 'intel:cpu', etc.
        """
        self.model = YOLO(model_path)
        self.device = device
        self.detection_stats = {
            'total_detections': 0,
            'size_filtered': 0,
            'confidence_filtered': 0,
            'valid_detections': 0,
        }

    def detect(self, frame: np.ndarray, min_confidence: float = 0.3) -> Dict:
        """
        Detecta el balón con filtros de tamaño

        Args:
            frame (np.ndarray): Frame de video (H, W, 3)
            min_confidence (float): Confianza mínima

        Returns:
            dict: {
                'detected': bool,
                'bbox': [x1, y1, x2, y2] or None,
                'center': [x, y] or None,
                'size': pixels or None,
                'confidence': float or None,
                'diagnostics': dict
            }
        """
        results = self.model(frame, verbose=False, conf=min_confidence)

        diagnostics = {
            'raw_detections': 0,
            'filtered_by_size': 0,
            'filtered_by_confidence': 0,
        }

        if not results or len(results[0].boxes) == 0:
            return {
                'detected': False,
                'bbox': None,
                'center': None,
                'size': None,
                'confidence': None,
                'diagnostics': diagnostics
            }

        self.detection_stats['total_detections'] += 1
        diagnostics['raw_detections'] = len(results[0].boxes)

        # Procesar detecciones
        detections = []
        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf)

            # Calcular tamaño
            width = x2 - x1
            height = y2 - y1
            size = np.sqrt(width * height)

            # Filtro de tamaño
            if size < self.MIN_SIZE or size > self.MAX_SIZE:
                self.detection_stats['size_filtered'] += 1
                diagnostics['filtered_by_size'] += 1
                continue

            # Filtro de confianza adicional
            if conf < min_confidence:
                self.detection_stats['confidence_filtered'] += 1
                diagnostics['filtered_by_confidence'] += 1
                continue

            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

            detections.append({
                'bbox': [x1, y1, x2, y2],
                'center': [center_x, center_y],
                'size': float(size),
                'confidence': conf,
            })

        # Retornar detección con mayor confianza
        if detections:
            best = max(detections, key=lambda d: d['confidence'])
            self.detection_stats['valid_detections'] += 1
            return {
                'detected': True,
                'bbox': best['bbox'],
                'center': best['center'],
                'size': best['size'],
                'confidence': best['confidence'],
                'diagnostics': diagnostics
            }

        return {
            'detected': False,
            'bbox': None,
            'center': None,
            'size': None,
            'confidence': None,
            'diagnostics': diagnostics
        }

    def get_stats(self) -> Dict:
        """Retorna estadísticas de detección"""
        return self.detection_stats.copy()


class CornerDetector:
    """Detector especializado de esquinas de cancha mejorado"""

    def __init__(self, model_path: str, device: str = "cpu"):
        """
        Args:
            model_path (str): Ruta al modelo YOLO de cancha
            device (str): Dispositivo 'cpu', 'intel:cpu', etc.
        """
        self.model = YOLO(model_path)
        self.device = device
        self.corner_history = []  # Para suavizado temporal

    def detect_corners(self, frame: np.ndarray,
                      min_confidence: float = 0.3) -> Dict:
        """
        Detecta esquinas de cancha con algoritmo mejorado

        Args:
            frame (np.ndarray): Frame de video (H, W, 3)
            min_confidence (float): Confianza mínima para keypoints

        Returns:
            dict: {
                'corners': [[x1,y1], [x2,y2], ...],  # hasta 4 esquinas
                'keypoints': [[x,y,conf], ...],  # todos los keypoints
                'valid': bool,
                'quality_score': float,
                'diagnostics': dict
            }
        """
        results = self.model(frame, verbose=False, conf=min_confidence)

        diagnostics = {
            'raw_keypoints': 0,
            'high_confidence_keypoints': 0,
            'corner_estimation_method': 'convex_hull',
        }

        keypoints_data = []

        if results and hasattr(results[0], 'keypoints') and results[0].keypoints is not None:
            kpts = results[0].keypoints
            if kpts.xy is not None:
                xy = kpts.xy.cpu().numpy()
                conf = kpts.conf.cpu().numpy() if kpts.conf is not None else None

                diagnostics['raw_keypoints'] = len(xy)

                # Filtrar por confianza
                for i, (pt, c) in enumerate(zip(xy, conf)):
                    if c >= min_confidence:
                        keypoints_data.append({
                            'point': pt,
                            'confidence': float(c),
                            'index': i
                        })

        diagnostics['high_confidence_keypoints'] = len(keypoints_data)

        if len(keypoints_data) == 0:
            return {
                'corners': [],
                'keypoints': [],
                'valid': False,
                'quality_score': 0.0,
                'diagnostics': diagnostics
            }

        # Extraer puntos y confianzas
        points = np.array([kp['point'] for kp in keypoints_data])
        confidences = np.array([kp['confidence'] for kp in keypoints_data])

        # Método mejorado: convex hull para encontrar esquinas
        corners = self._find_corners_convex_hull(points, confidences)

        # Calcular quality score
        quality_score = self._compute_quality_score(corners, confidences)

        keypoints_list = [
            [float(kp['point'][0]), float(kp['point'][1]), float(kp['confidence'])]
            for kp in keypoints_data
        ]

        return {
            'corners': corners,
            'keypoints': keypoints_list,
            'valid': len(corners) >= 3,  # Aceptar 3+ esquinas en lugar de 4
            'quality_score': quality_score,
            'diagnostics': diagnostics
        }

    def _find_corners_convex_hull(self, points: np.ndarray,
                                  confidences: np.ndarray) -> List[List[float]]:
        """
        Encuentra esquinas usando convex hull y clustering espacial

        Args:
            points: Array (N, 2) de coordenadas
            confidences: Array (N,) de confianzas

        Returns:
            List de hasta 4 esquinas [x, y]
        """
        if len(points) < 3:
            return []

        try:
            from scipy.spatial import ConvexHull

            hull = ConvexHull(points)
            hull_points = points[hull.vertices]

            # Si el hull ya tiene pocos puntos, retornarlos
            if len(hull_points) <= 4:
                return [[float(p[0]), float(p[1])] for p in hull_points]

            # Si tiene más de 4, seleccionar los 4 más distantes
            corners = self._select_extreme_corners(hull_points, confidences[hull.vertices])
            return corners

        except Exception:
            # Fallback: usar puntos más extremos en cada cuadrante
            return self._find_corners_quadrant(points, confidences)

    def _select_extreme_corners(self, hull_points: np.ndarray,
                                confidences: np.ndarray) -> List[List[float]]:
        """
        Selecciona 4 esquinas más prominentes del hull

        Args:
            hull_points: Puntos del convex hull
            confidences: Confianzas de cada punto

        Returns:
            Lista de 4 esquinas (o menos si no hay)
        """
        if len(hull_points) <= 4:
            return [[float(p[0]), float(p[1])] for p in hull_points]

        # Encontrar los 4 puntos más extremos por confianza + posición
        center = np.mean(hull_points, axis=0)
        distances = np.linalg.norm(hull_points - center, axis=1)
        scores = confidences * 0.6 + (distances / np.max(distances)) * 0.4

        # Seleccionar índices con mayor score
        top_indices = np.argsort(scores)[-4:]
        selected = hull_points[top_indices]

        return [[float(p[0]), float(p[1])] for p in selected]

    def _find_corners_quadrant(self, points: np.ndarray,
                              confidences: np.ndarray) -> List[List[float]]:
        """
        Alternativo: divide en cuadrantes y selecciona punto más confiable de cada uno

        Args:
            points: Array (N, 2) de coordenadas
            confidences: Array (N,) de confianzas

        Returns:
            Lista de esquinas por cuadrante
        """
        center_x = np.median(points[:, 0])
        center_y = np.median(points[:, 1])

        corners = []

        # Definir cuadrantes
        quadrants = [
            (points[:, 0] < center_x) & (points[:, 1] < center_y),  # top-left
            (points[:, 0] >= center_x) & (points[:, 1] < center_y),  # top-right
            (points[:, 0] < center_x) & (points[:, 1] >= center_y),  # bottom-left
            (points[:, 0] >= center_x) & (points[:, 1] >= center_y),  # bottom-right
        ]

        for quad_mask in quadrants:
            quad_points = points[quad_mask]
            quad_confs = confidences[quad_mask]

            if len(quad_points) > 0:
                # Seleccionar punto con mayor confianza en este cuadrante
                best_idx = np.argmax(quad_confs)
                corner = quad_points[best_idx]
                corners.append([float(corner[0]), float(corner[1])])

        return corners

    def _compute_quality_score(self, corners: List,
                              confidences: np.ndarray) -> float:
        """
        Calcula un score de calidad de las esquinas detectadas

        Args:
            corners: Lista de esquinas
            confidences: Array de confianzas

        Returns:
            Score 0-1
        """
        if len(corners) == 0:
            return 0.0

        if len(confidences) == 0:
            return 0.5

        # Basado en: número de esquinas y confianza promedio
        num_factor = min(len(corners) / 4, 1.0)  # 0 si 0 esquinas, 1 si 4+
        conf_factor = float(np.mean(confidences))

        return num_factor * 0.5 + conf_factor * 0.5


class UnifiedDetector:
    """Detector unificado que orquesta detecciones de jugadores, balón y cancha"""

    def __init__(self, player_model_path: str, ball_model_path: str,
                 pitch_model_path: str, device: str = "cpu"):
        """
        Args:
            player_model_path (str): Ruta al modelo de jugadores
            ball_model_path (str): Ruta al modelo del balón
            pitch_model_path (str): Ruta al modelo de cancha
            device (str): Dispositivo 'cpu', 'intel:cpu', etc.
        """
        self.player_model = YOLO(player_model_path)
        self.ball_detector = BallDetector(ball_model_path, device)
        self.corner_detector = CornerDetector(pitch_model_path, device)
        self.device = device

    def detect_frame(self, frame: np.ndarray,
                    player_conf: float = 0.4,
                    ball_conf: float = 0.3,
                    pitch_conf: float = 0.5) -> Dict:
        """
        Ejecuta todas las detecciones en un frame

        Args:
            frame (np.ndarray): Frame de video (H, W, 3)
            player_conf (float): Confianza mínima para jugadores
            ball_conf (float): Confianza mínima para balón
            pitch_conf (float): Confianza mínima para cancha

        Returns:
            dict: {
                'players': [...],
                'ball': {...},
                'pitch': {...},
                'frame_shape': (H, W)
            }
        """
        h, w = frame.shape[:2]

        # Detectar jugadores
        results = self.player_model(frame, verbose=False, conf=player_conf)
        players = []
        if results and len(results[0].boxes) > 0:
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf)
                players.append({
                    'bbox': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': conf,
                    'class': int(box.cls) if box.cls is not None else 0,
                })

        # Detectar balón
        ball = self.ball_detector.detect(frame, min_confidence=ball_conf)

        # Detectar cancha
        pitch = self.corner_detector.detect_corners(frame, min_confidence=pitch_conf)

        return {
            'players': players,
            'ball': ball,
            'pitch': pitch,
            'frame_shape': (h, w),
            'detection_stats': {
                'ball_stats': self.ball_detector.get_stats(),
            }
        }

    def reset_stats(self):
        """Reinicia estadísticas de detección"""
        self.ball_detector.detection_stats = {
            'total_detections': 0,
            'size_filtered': 0,
            'confidence_filtered': 0,
            'valid_detections': 0,
        }

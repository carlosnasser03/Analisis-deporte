"""
conftest.py - Configuración y fixtures compartidas para los tests

Proporciona fixtures reutilizables para todos los tests, incluyendo:
- Mocks de OpenCV
- Datos de prueba
- Configuraciones de prueba
- Fixtures de logging
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import tempfile
import json
from typing import List, Dict, Any
import logging


@pytest.fixture
def temp_dir():
    """Crea un directorio temporal para tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_cv2():
    """Mock de OpenCV para evitar dependencias en tests"""
    with patch('cv2.VideoCapture') as mock_capture:
        # Configurar VideoCapture mock
        instance = MagicMock()
        instance.isOpened.return_value = True
        instance.get.side_effect = lambda prop: {
            'CV_CAP_PROP_FRAME_COUNT': 100,
            'CV_CAP_PROP_FPS': 30,
            'CV_CAP_PROP_FRAME_WIDTH': 1920,
            'CV_CAP_PROP_FRAME_HEIGHT': 1080,
        }.get(prop, 30)
        instance.read.return_value = (True, np.zeros((1080, 1920, 3), dtype=np.uint8))
        instance.release.return_value = None

        mock_capture.return_value = instance
        yield mock_capture


@pytest.fixture
def mock_frame():
    """Crea un frame de video simulado"""
    return np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def mock_bboxes() -> List[List[float]]:
    """Crea bounding boxes simulados para jugadores"""
    return [
        [100, 100, 200, 300],  # Jugador 1
        [300, 150, 400, 350],  # Jugador 2
        [500, 200, 600, 400],  # Jugador 3
        [700, 100, 800, 300],  # Jugador 4
    ]


@pytest.fixture
def mock_tracks() -> List[Dict[str, Any]]:
    """Crea tracks simulados para jugadores"""
    tracks = []
    for frame_idx in range(0, 100, 5):
        for player_id in [1, 2, 3, 4]:
            tracks.append({
                'frame_idx': frame_idx,
                'player_id': player_id,
                'bbox': [100 + player_id * 200, 100, 200 + player_id * 200, 300],
                'center': [150 + player_id * 200, 200],
                'confidence': 0.9 + np.random.uniform(-0.1, 0.1)
            })
    return tracks


@pytest.fixture
def mock_detections() -> Dict[str, Any]:
    """Crea detecciones simuladas"""
    return {
        'frame_id': 0,
        'timestamp': 0.0,
        'balls': [
            {'x': 960, 'y': 540, 'confidence': 0.95},
        ],
        'players': [
            {'bbox': [100, 100, 200, 300], 'team': 'A', 'confidence': 0.92},
            {'bbox': [300, 150, 400, 350], 'team': 'B', 'confidence': 0.88},
            {'bbox': [500, 200, 600, 400], 'team': 'A', 'confidence': 0.90},
        ]
    }


@pytest.fixture
def mock_field_corners() -> List[tuple]:
    """Crea esquinas de campo simuladas"""
    return [
        (50, 50),      # Top-left
        (1870, 50),    # Top-right
        (1870, 1030),  # Bottom-right
        (50, 1030),    # Bottom-left
    ]


@pytest.fixture
def temp_video_file(temp_dir):
    """Crea un archivo de video simulado (solo header válido)"""
    video_path = temp_dir / "test_video.mp4"
    # Crear archivo minimal válido
    with open(video_path, 'wb') as f:
        f.write(b'\x00\x00\x00\x20ftypisom')  # Mínimo header MP4 válido
    return video_path


@pytest.fixture
def temp_log_dir(temp_dir):
    """Crea un directorio temporal para logs"""
    log_dir = temp_dir / "logs"
    log_dir.mkdir()
    return log_dir


@pytest.fixture
def mock_logger(temp_log_dir):
    """Crea un logger mock para tests"""
    from utils.logger import ScoutLogger
    return ScoutLogger(log_dir=str(temp_log_dir), log_file='test.log')


@pytest.fixture
def logger_no_basicconfig():
    """Verifica que no hay logging.basicConfig() llamado durante el test"""
    with patch('logging.basicConfig') as mock_basicconfig:
        yield mock_basicconfig
        # Verificar que no fue llamado
        assert not mock_basicconfig.called, \
            "logging.basicConfig() fue llamado. Usa ScoutLogger en su lugar."


@pytest.fixture
def capture_logger_calls():
    """Captura todas las llamadas a logging.basicConfig()"""
    logger_calls = []
    original_basicconfig = logging.basicConfig

    def tracked_basicconfig(*args, **kwargs):
        logger_calls.append(('basicConfig', args, kwargs))
        return original_basicconfig(*args, **kwargs)

    with patch('logging.basicConfig', side_effect=tracked_basicconfig):
        yield logger_calls


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Configuración simulada para tests"""
    return {
        'model_path': '/path/to/model.pt',
        'confidence': 0.5,
        'max_workers': 4,
        'fps': 30,
        'field_length_m': 105,
        'field_width_m': 68,
    }


@pytest.fixture
def valid_classes_config():
    """Configuración de clases válidas configurable"""
    return {
        'VALID_CLASSES': ['player', 'ball', 'referee'],
        'VALID_TEAMS': ['A', 'B'],
    }


@pytest.fixture
def mock_numpy_array():
    """Array NumPy simulado para pruebas matemáticas"""
    return np.array([
        [100, 100],
        [150, 150],
        [200, 200],
        [250, 250],
    ], dtype=np.float32)


@pytest.fixture
def mock_hsv_colors():
    """Colores HSV simulados para clasificación de equipos"""
    return [
        np.array([10, 200, 150], dtype=np.uint8),   # Rojo (Equipo A)
        np.array([10, 200, 150], dtype=np.uint8),   # Rojo (Equipo A)
        np.array([110, 200, 150], dtype=np.uint8),  # Azul (Equipo B)
        np.array([110, 200, 150], dtype=np.uint8),  # Azul (Equipo B)
    ]


@pytest.fixture
def mock_kmeans_model():
    """Mock de modelo KMeans para tests"""
    from unittest.mock import MagicMock
    model = MagicMock()
    model.cluster_centers_ = np.array([
        [10, 200, 150],   # Equipo A
        [110, 200, 150],  # Equipo B
    ])
    model.labels_ = np.array([0, 0, 1, 1])
    return model


@pytest.fixture
def mock_track_state():
    """Estado de track simulado"""
    from dataclasses import dataclass
    from typing import List, Tuple, Optional

    @dataclass
    class MockTrackState:
        track_id: int = 1
        bbox: List[float] = None
        confidence: float = 0.9
        frame_id: int = 0
        age: int = 1
        hits: int = 1
        hit_streak: int = 1
        time_since_update: int = 0
        position_history: List[Tuple[float, float]] = None
        velocity: Tuple[float, float] = (0.0, 0.0)
        team_id: Optional[int] = None
        jersey_number: Optional[str] = None
        is_occluded: bool = False
        occlusion_frames: int = 0

        def __post_init__(self):
            if self.bbox is None:
                self.bbox = [100, 100, 200, 300]
            if self.position_history is None:
                self.position_history = [(150, 200)]

    return MockTrackState()


@pytest.fixture
def mock_player_stats():
    """Estadísticas de jugador simuladas"""
    from dataclasses import dataclass
    from typing import List, Tuple, Optional, Dict

    @dataclass
    class MockPlayerStats:
        player_id: int = 1
        total_distance_m: float = 10500.0
        max_velocity_m_s: float = 9.2
        avg_velocity_m_s: float = 4.5
        movement_intensity_percent: float = 85.0
        static_time_percent: float = 15.0
        possession_time_s: Optional[float] = None
        touches_count: int = 45
        heatmap_positions: List[Tuple[float, float]] = None
        speed_distribution: Dict[str, float] = None
        comparison_metrics: Dict[str, float] = None
        team_percentile: Dict[str, float] = None

        def __post_init__(self):
            if self.heatmap_positions is None:
                self.heatmap_positions = [(52.5, 34), (52.5, 35), (52.5, 33)]
            if self.speed_distribution is None:
                self.speed_distribution = {
                    'static': 15.0,
                    'walking': 20.0,
                    'jogging': 35.0,
                    'running': 20.0,
                    'sprinting': 10.0,
                }
            if self.comparison_metrics is None:
                self.comparison_metrics = {
                    'distance_percentile': 75.0,
                    'velocity_percentile': 80.0,
                    'intensity_percentile': 85.0,
                }
            if self.team_percentile is None:
                self.team_percentile = {
                    'distance': 75.0,
                    'velocity': 80.0,
                    'intensity': 85.0,
                }

    return MockPlayerStats()


@pytest.fixture
def mock_ocr_result():
    """Resultado OCR simulado"""
    return {
        'number': '7',
        'confidence': 0.95,
        'raw_text': '7',
        'ocr_engine': 'paddle',
        'is_valid': True,
    }


@pytest.fixture
def suppress_logging():
    """Suprime logs durante tests para no contaminar stdout"""
    logging.getLogger().setLevel(logging.CRITICAL)
    yield
    logging.getLogger().setLevel(logging.WARNING)


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Limpia archivos temporales después de cada test"""
    yield
    # Cleanup se realiza automáticamente con tempfile


@pytest.fixture
def test_config_file(temp_dir):
    """Crea archivo de configuración de prueba"""
    config = {
        'model_path': 'models/yolo.pt',
        'confidence': 0.5,
        'max_workers': 4,
    }
    config_path = temp_dir / "config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f)
    return config_path


@pytest.fixture
def test_invalid_config_file(temp_dir):
    """Crea archivo de configuración inválido"""
    config_path = temp_dir / "invalid_config.json"
    with open(config_path, 'w') as f:
        f.write("{ invalid json")
    return config_path


# Marcadores de test personalizados
def pytest_configure(config):
    """Configura marcadores personalizados"""
    config.addinivalue_line(
        "markers", "edge_case: marca tests de casos límite"
    )
    config.addinivalue_line(
        "markers", "integration: marca tests de integración"
    )
    config.addinivalue_line(
        "markers", "slow: marca tests lentos"
    )
    config.addinivalue_line(
        "markers", "requires_opencv: marca tests que requieren OpenCV real"
    )

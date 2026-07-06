# Arquitectura e Implementación - FASE 2

**Versión:** 2.0  
**Estado:** FASE 2 Completada ✅  
**Fecha:** 2026-07-06  
**Propósito:** Documentación técnica completa de la arquitectura implementada

---

## Tabla de Contenidos

1. [Estructura de Directorios](#estructura-de-directorios)
2. [Módulos Core](#módulos-core)
3. [Módulos Utils](#módulos-utils)
4. [Diagrama de Arquitectura](#diagrama-de-arquitectura)
5. [Flujo de Datos](#flujo-de-datos)
6. [Patrones de Diseño](#patrones-de-diseño)
7. [Ejemplo de Uso](#ejemplo-de-uso)
8. [Extensibilidad](#extensibilidad)

---

## Estructura de Directorios

```
scout-ai/
│
├── 📁 core/                          # Módulos centrales de detección
│   ├── __init__.py                   # Exporta todas las clases core
│   ├── detector.py                   # Detectores YOLO (BallDetector, PlayerDetector, etc.)
│   ├── homography_validator.py       # Validador de perspectiva de cancha
│   ├── metrics.py                    # Logging y métricas de detección
│   ├── team_classifier.py            # Clasificador de equipos por color
│   ├── tracker.py                    # Rastreador de jugadores (tracking)
│   └── jersey_number_detector.py     # Detector de números de camiseta
│
├── 📁 utils/                         # Utilidades auxiliares
│   ├── __init__.py                   # Exporta todas las funciones utils
│   ├── video_splitter.py             # Divisor de videos para procesamiento paralelo
│   └── validators.py                 # Validadores de video, config, y dependencias
│
├── 📁 config/                        # Configuración
│   └── detection_config.yaml         # Configuración centralizada
│
├── 📁 pipeline/                      # Pipeline de procesamiento (future)
│   └── processor.py                  # Orquestador principal
│
├── 📁 data/                          # Datos
│   ├── logs/                         # Logs y resultados
│   │   └── FASE_2_COMPLETADA.json    # Checklist de FASE 2
│   └── models/                       # Modelos YOLO preentrenados
│
├── 📁 scripts/                       # Scripts independientes
│   ├── 0_validate_single.py          # Script de validación
│   ├── 1_preparar.py                 # Preparación de datos
│   └── 2_analizar.py                 # Análisis principal
│
└── 📁 docs/                          # Documentación (future)
    ├── ARCHITECTURE_IMPLEMENTATION.md # Este archivo
    ├── CONTRIBUTING.md                # Guía de contribución
    └── API.md                         # Documentación de API (future)
```

---

## Módulos Core

### 1. **Detector** (`core/detector.py`)

Centraliza la detección de objetos usando YOLO v8.

```python
# Clases principales:
- BallDetector          # Detección especializada de balón
  - MIN_SIZE: 20 píxeles
  - MAX_SIZE: 100 píxeles
  - Filtros: tamaño, confianza

- CornerDetector        # Detección de esquinas de cancha
  - Validación de perspectiva
  - Cálculo de homografía

- UnifiedDetector       # Detector unificado
  - Integra todas las detecciones
  - Sincronización de resultados
```

**Métodos principales:**
```python
detector.detect(frame, min_confidence=0.3) → Dict
detector.get_statistics() → Dict
detector.reset_stats() → None
```

### 2. **HomographyValidator** (`core/homography_validator.py`)

Valida la perspectiva de la cancha y calcula transformaciones.

```python
validator = HomographyValidator(video_path)
validator.validate_perspective(frame) → Dict
validator.transform_coordinates(points) → np.ndarray
validator.get_court_bounds() → Tuple
```

### 3. **TeamClassifier** (`core/team_classifier.py`)

Clasifica jugadores en dos equipos usando análisis de color HSV.

```python
classifier = TeamClassifier(n_clusters=2)
classifier.fit(jersey_colors) → None
classifier.predict(jersey_color) → int  # 0 o 1 (equipo)
classifier.get_team_colors() → Dict[int, TeamColor]
```

**Estructura TeamColor:**
```python
@dataclass
class TeamColor:
    name: str                          # Nombre del equipo
    bgr_value: Tuple[int, int, int]   # Color BGR
    hsv_range: Tuple                   # Rango HSV para detección
    confidence: float                  # Confianza de clasificación
```

### 4. **PlayerTracker** (`core/tracker.py`)

Rastrea jugadores a lo largo del video.

```python
tracker = PlayerTracker()
tracker.update(detections, frame) → List[Track]
tracker.get_trajectories() → Dict
tracker.match_identities() → Dict
```

### 5. **JerseyNumberDetector** (`core/jersey_number_detector.py`)

Detecta números de camiseta de jugadores.

```python
detector = JerseyNumberDetector(model_path)
detector.detect(player_crop) → str  # Número detectado
detector.get_confidence() → float
```

### 6. **DetectionMetrics** (`core/metrics.py`)

Logging y recolección de métricas.

```python
metrics = DetectionMetrics()
metrics.log_detection(frame_id, detection_data) → None
metrics.get_report() → Dict
metrics.export_csv(output_path) → None
metrics.export_json(output_path) → None
```

---

## Módulos Utils

### 1. **VideoSplitter** (`utils/video_splitter.py`)

**Propósito:** Dividir videos grandes en chunks para procesamiento paralelo.

**Clase Principal:**
```python
class VideoSplitter:
    def __init__(self, video_path: str, output_dir: str = "./chunks")
    def split_video(self, chunk_duration: int = 30, overlap_frames: int = 0) → List[ChunkInfo]
    def merge_chunks(self, chunks: List[ChunkInfo], output_path: str) → str
    def get_chunk_info(self, chunk_id: Optional[int]) → Dict
    def cleanup_chunks(self, except_ids: Optional[List[int]]) → None
    def get_statistics() → Dict
```

**Estructura ChunkInfo:**
```python
@dataclass
class ChunkInfo:
    chunk_id: int           # ID único del chunk
    start_frame: int        # Frame inicial
    end_frame: int          # Frame final
    start_time: float       # Tiempo en segundos
    end_time: float         # Tiempo en segundos
    fps: float              # Frames por segundo
    width: int              # Ancho en píxeles
    height: int             # Altura en píxeles
    file_path: str          # Ruta del archivo
    size_mb: float          # Tamaño en MB
    status: str             # pending, processing, completed, failed
```

**Ejemplo de uso:**
```python
from utils import VideoSplitter

# Crear divisor
splitter = VideoSplitter("video.mp4", output_dir="./chunks")

# Dividir en chunks de 30 segundos
chunks = splitter.split_video(chunk_duration=30, overlap_frames=5)

# Procesar chunks en paralelo
for chunk in chunks:
    process_chunk(chunk)

# Fusionar resultados
merged = splitter.merge_chunks(chunks, output_path="output.mp4")

# Limpiar archivos temporales
splitter.cleanup_chunks(except_ids=[0, 1])
```

### 2. **Validators** (`utils/validators.py`)

**Propósito:** Validación exhaustiva de entrada y salida.

#### VideoValidator

```python
@staticmethod
def validate_video_file(video_path: str) → ValidationResult
```

Valida:
- Existencia del archivo
- Formato soportado (.mp4, .avi, .mov, etc.)
- Permisos de lectura
- Tamaño del archivo
- Rango de duración (1s - 1h)
- FPS (15-120)
- Resolución (mínimo 320x240)
- Legibilidad de frames

#### DetectionValidator

```python
@staticmethod
def validate_detection_output(detections: Dict) → ValidationResult
```

Valida:
- Estructura de datos
- Campos requeridos
- Rangos de confianza
- Formato de bounding boxes
- Asignación de equipos

#### ConfigValidator

```python
@staticmethod
def validate_config(config: Dict) → ValidationResult
@staticmethod
def validate_config_file(config_path: str) → ValidationResult
```

Valida:
- Existencia de archivos referenciados
- Rangos de parámetros
- Valores numéricos
- Rutas válidas

#### DependencyValidator

```python
@staticmethod
def check_dependencies() → ValidationResult
@staticmethod
def check_system_resources() → ValidationResult
```

Verifica:
- Paquetes requeridos (numpy, opencv, ultralytics, sklearn, yaml)
- Paquetes opcionales (torch, tensorflow)
- Recursos (CPU, RAM, disco)

**Estructura ValidationResult:**
```python
@dataclass
class ValidationResult:
    is_valid: bool              # Resultado de la validación
    message: str                # Mensaje de resumen
    details: Dict[str, Any]     # Detalles de la validación
    warnings: List[str]         # Advertencias
    errors: List[str]           # Errores encontrados
```

**Función integral:**
```python
def validate_all(video_path: str, config_path: str) → Dict[str, ValidationResult]
```

---

## Diagrama de Arquitectura

```
                           ENTRADA
                             |
                        Video File
                             |
                    ┌────────▼────────┐
                    │ VideoValidator  │
                    └────────┬────────┘
                             |
                    ┌────────▼────────────────┐
                    │   VideoSplitter        │
                    │ (Chunks for parallel)  │
                    └────────┬────────────────┘
                             |
            ┌────────────────┼────────────────┐
            │                │                │
        ┌───▼──┐         ┌───▼──┐        ┌───▼──┐
        │Chunk │         │Chunk │        │Chunk │
        │  0   │         │  1   │        │  N   │
        └───┬──┘         └───┬──┘        └───┬──┘
            │                │                │
        ┌───▼──────────────────────────────────▼──┐
        │        UnifiedDetector (Pipeline)       │
        │  ┌─────────────┐  ┌─────────────┐      │
        │  │BallDetector │  │PlayerTracker│      │
        │  └─────────────┘  └─────────────┘      │
        └───┬──────────────────────────────────────┘
            │
        ┌───▼──────────────────────────┐
        │     TeamClassifier            │
        │  (Equipo por color camiseta) │
        └───┬──────────────────────────┘
            │
        ┌───▼────────────────────────────┐
        │  JerseyNumberDetector          │
        │  (Números de camiseta)         │
        └───┬────────────────────────────┘
            │
        ┌───▼──────────────────────────┐
        │    DetectionMetrics          │
        │  (Logging y análisis)        │
        └───┬──────────────────────────┘
            │
        ┌───▼──────────────────────────┐
        │      Reportes Finales        │
        │  (CSV, JSON, Dashboard)      │
        └───────────────────────────────┘
```

---

## Flujo de Datos

### 1. Preparación y Validación

```python
# 1. Validar entrada
from utils import validate_all

results = validate_all("video.mp4", "config.yaml")
if not all(r.is_valid for r in results.values()):
    raise Exception("Validación fallida")

# 2. Cargar configuración
import yaml
with open("config.yaml") as f:
    config = yaml.safe_load(f)
```

### 2. División y Procesamiento Paralelo

```python
# 3. Dividir video
from utils import VideoSplitter

splitter = VideoSplitter("video.mp4")
chunks = splitter.split_video(chunk_duration=30)

# 4. Procesar chunks en paralelo
from concurrent.futures import ThreadPoolExecutor

def process_chunk(chunk):
    detector = UnifiedDetector(config)
    return detector.process_chunk(chunk)

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_chunk, chunks))
```

### 3. Detección y Clasificación

```python
from core import (
    BallDetector,
    UnifiedDetector,
    TeamClassifier,
    JerseyNumberDetector,
    DetectionMetrics
)

# Crear detectores
ball_detector = BallDetector("models/ball.pt")
player_tracker = PlayerTracker()
team_classifier = TeamClassifier()
jersey_detector = JerseyNumberDetector("models/jersey.pt")
metrics = DetectionMetrics()

# Procesar frame
cap = cv2.VideoCapture("video.mp4")
frame_id = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Detectar balón y jugadores
    detections = unified_detector.detect(frame)
    
    # Clasificar equipos
    for player in detections['players']:
        team = team_classifier.predict(player['jersey_color'])
        player['team'] = team
    
    # Detectar números
    for player in detections['players']:
        number = jersey_detector.detect(player['crop'])
        player['number'] = number
    
    # Registrar métricas
    metrics.log_detection(frame_id, detections)
    
    frame_id += 1

cap.release()
```

### 4. Generación de Reportes

```python
# Exportar resultados
metrics.export_csv("logs/detections.csv")
metrics.export_json("logs/summary.json")

report = metrics.get_report()
print(report)
```

---

## Patrones de Diseño

### 1. **Factory Pattern** (Detectores)

```python
class DetectorFactory:
    @staticmethod
    def create_detector(detector_type, model_path):
        if detector_type == 'ball':
            return BallDetector(model_path)
        elif detector_type == 'player':
            return PlayerDetector(model_path)
        # ...
```

### 2. **Strategy Pattern** (Validadores)

```python
class Validator:
    def validate(self, data):
        # Estrategia configurable
        pass

class VideoValidator(Validator):
    def validate(self, video_path):
        # Implementación específica
        pass
```

### 3. **Observer Pattern** (Métricas)

```python
detector.register_observer(metrics)
detector.detect(frame)  # Notifica automáticamente
metrics.get_report()
```

### 4. **Pipeline Pattern** (Procesamiento)

```python
class Pipeline:
    def __init__(self):
        self.stages = []
    
    def add_stage(self, stage):
        self.stages.append(stage)
    
    def execute(self, data):
        for stage in self.stages:
            data = stage.process(data)
        return data
```

---

## Ejemplo de Uso

### Uso Mínimo

```python
from core import UnifiedDetector
from utils import VideoValidator
import cv2

# Validar video
from utils import VideoValidator
result = VideoValidator.validate_video_file("video.mp4")
assert result.is_valid

# Crear detector
detector = UnifiedDetector("config.yaml")

# Procesar video
cap = cv2.VideoCapture("video.mp4")
while True:
    ret, frame = cap.read()
    if not ret:
        break
    detections = detector.detect(frame)
    print(detections)
cap.release()
```

### Uso Avanzado con Paralelización

```python
from core import *
from utils import VideoSplitter, validate_all
from concurrent.futures import ThreadPoolExecutor

# Validar todo
results = validate_all("video.mp4", "config.yaml")
if not all(r.is_valid for r in results.values()):
    for k, v in results.items():
        print(f"{k}: {v.message}")
    exit(1)

# Dividir video
splitter = VideoSplitter("video.mp4")
chunks = splitter.split_video(chunk_duration=30, overlap_frames=5)

# Procesar en paralelo
def process_chunk(chunk):
    detector = UnifiedDetector("config.yaml")
    results = []
    
    cap = cv2.VideoCapture(chunk.file_path)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        results.append(detector.detect(frame))
    
    cap.release()
    return results

with ThreadPoolExecutor(max_workers=4) as executor:
    all_results = list(executor.map(process_chunk, chunks))

# Fusionar resultados
merged_results = [item for sublist in all_results for item in sublist]

# Exportar
metrics = DetectionMetrics()
for result in merged_results:
    metrics.log_detection(result['frame_id'], result)

metrics.export_csv("logs/detections.csv")
metrics.export_json("logs/summary.json")

# Limpiar
splitter.cleanup_chunks()
```

---

## Extensibilidad

### Agregar un Nuevo Detector

```python
# 1. Crear nuevo archivo: core/my_detector.py
from ultralytics import YOLO

class MyDetector:
    def __init__(self, model_path):
        self.model = YOLO(model_path)
    
    def detect(self, frame):
        results = self.model(frame)
        return self._format_results(results)
    
    def _format_results(self, results):
        return {
            'detections': [...],
            'timestamp': ...
        }

# 2. Actualizar core/__init__.py
from .my_detector import MyDetector

__all__ = [..., 'MyDetector']

# 3. Usar
from core import MyDetector
detector = MyDetector("model.pt")
```

### Agregar un Nuevo Validador

```python
# 1. Crear en utils/validators.py
class MyValidator:
    @staticmethod
    def validate(data):
        errors = []
        # Lógica de validación
        return ValidationResult(
            is_valid=len(errors) == 0,
            message="...",
            details={...},
            warnings=[...],
            errors=errors
        )

# 2. Usar
result = MyValidator.validate(data)
if not result.is_valid:
    print(result.errors)
```

### Integrar con Pipeline Externo

```python
# Usar módulos como librería
from core import BallDetector, UnifiedDetector
from utils import VideoSplitter

# En tu propio pipeline
my_pipeline = MyCustomPipeline()
my_pipeline.add_stage(VideoSplitter)
my_pipeline.add_stage(UnifiedDetector)
my_pipeline.execute(video_path)
```

---

## Próximos Pasos (FASE 3)

- [ ] REST API para procesamiento remoto
- [ ] WebSocket para streaming de resultados
- [ ] Base de datos para persistencia
- [ ] UI web para análisis interactivo
- [ ] Exportación a múltiples formatos

---

**Última actualización:** 2026-07-06  
**Mantenedor:** Scout AI Team

# ARQUITECTURA DEL SISTEMA: Scout AI

## 📐 Estructura de Carpetas (Production-Ready)

```
scout-ai/
│
├── 📁 config/                      # Configuraciones centralizadas
│   ├── detection_config.yaml       # Umbrales YOLO, dispositivos
│   ├── team_config.yaml            # Clasificación de equipos
│   ├── processing_config.yaml      # Pipeline, timeouts
│   └── paths_config.yaml           # Rutas de modelos, datos
│
├── 📁 core/                        # Módulos reutilizables
│   ├── __init__.py
│   ├── detector.py                 # Wrapper unificado YOLO
│   ├── team_classifier.py          # Clasificación de equipos
│   ├── homography_validator.py     # Validación de perspectiva
│   ├── tracker.py                  # Tracking mejorado
│   ├── metrics.py                  # Logging de métricas
│   ├── jersey_number_detector.py   # Detección número camiseta (NUEVO)
│   ├── player_analyzer.py          # Análisis por jugador (NUEVO)
│   └── report_generator.py         # Generación de reportes (NUEVO)
│
├── 📁 pipeline/                    # Pipeline de procesamiento
│   ├── __init__.py
│   ├── video_processor.py          # Orquestador principal
│   ├── frame_processor.py          # Procesamiento frame-by-frame
│   ├── batch_processor.py          # Procesamiento de múltiples videos
│   └── result_combiner.py          # Combina resultados de chunks
│
├── 📁 utils/                       # Utilidades
│   ├── __init__.py
│   ├── logger.py                   # Logging centralizado
│   ├── file_handler.py             # Manejo de archivos
│   ├── video_splitter.py           # Dividir videos en chunks
│   ├── validators.py               # Validaciones
│   └── helpers.py                  # Funciones helper
│
├── 📁 models/                      # Modelos YOLO (descargados en setup)
│   ├── football-player-detection_openvino_model/
│   ├── football-pitch-detection_openvino_model/
│   ├── football-ball-detection_openvino_model/
│   └── jersey-number-detector.pt   (entrenar en Fase 4)
│
├── 📁 data/                        # Datos y resultados
│   ├── inputs/                     # Videos a procesar
│   ├── outputs/                    # Resultados procesados
│   │   ├── {video_id}/
│   │   │   ├── frames.csv          # Métricas por frame
│   │   │   ├── players/
│   │   │   │   ├── player_7.json
│   │   │   │   ├── player_7.pdf
│   │   │   │   └── ...
│   │   │   ├── team_stats.json
│   │   │   └── video_annotated.mp4
│   │   └── ...
│   ├── logs/                       # Logs de procesamiento
│   ├── cache/                      # Cache de modelos
│   └── temp/                       # Archivos temporales
│
├── 📁 scripts/                     # Scripts ejecutables
│   ├── 0_setup.py                  # Setup inicial (descargar modelos)
│   ├── 0_validate_single.py        # Validación single video (FASE 1)
│   ├── 1_process_video.py          # Procesar 1 video (CLI)
│   ├── 2_process_batch.py          # Procesar múltiples videos
│   ├── 3_analyze_player.py         # Análisis por jugador
│   ├── 4_generate_reports.py       # Generar reportes
│   └── colab_main.py               # Versión Google Colab
│
├── 📁 notebook/                    # Jupyter Notebooks
│   ├── 00_exploration.ipynb        # Análisis exploratorio
│   ├── 01_pipeline_test.ipynb      # Test del pipeline
│   └── colab_notebook.ipynb        # Para Google Colab
│
├── 📁 web/                         # Backend web (v2.0)
│   ├── app.py                      # Flask/FastAPI
│   ├── routes.py                   # API endpoints
│   ├── models.py                   # Modelos BD
│   └── templates/                  # HTML templates
│
├── 📁 tests/                       # Tests unitarios
│   ├── test_detector.py
│   ├── test_team_classifier.py
│   ├── test_pipeline.py
│   └── conftest.py
│
├── 📄 requirements.txt             # Dependencias Python
├── 📄 requirements-colab.txt       # Dependencias Colab
├── 📄 setup.py                     # Setup package
├── 📄 README.md                    # Documentación principal
├── 📄 CONTRIBUTING.md              # Guía para contribuidores
├── 📄 LICENSE                      # Licencia
└── 📄 .env.example                 # Variables de entorno ejemplo
```

---

## 🔄 Pipeline de Procesamiento

```
INPUT: Video MP4
   ↓
┌─────────────────────────────────────────┐
│  STEP 1: VALIDACIÓN                     │
│  - Verificar formato, codec             │
│  - Detectar duración                    │
│  - Calcular chunks si necesario         │
└─────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────┐
│  STEP 2: DETECCIÓN (por frame)          │
│  - Cargar modelos YOLO                  │
│  - Detectar jugadores                   │
│  - Detectar cancha                      │
│  - Detectar balón                       │
│  - Validar transformación perspectiva   │
└─────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────┐
│  STEP 3: CLASIFICACIÓN                  │
│  - Separar por equipo (colors)          │
│  - Identificar números de camiseta      │
│  - Validar confianza                    │
└─────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────┐
│  STEP 4: TRACKING                       │
│  - ByteTrack + validaciones             │
│  - Mantener IDs consistentes            │
│  - Re-ID en oclusiones                  │
└─────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────┐
│  STEP 5: ANÁLISIS                       │
│  - Calcular estadísticas por jugador    │
│  - Distancia, velocidad, intensidad     │
│  - Generador de heatmaps                │
│  - Comparativa equipo                   │
└─────────────────────────────────────────┘
   ↓
┌─────────────────────────────────────────┐
│  STEP 6: GENERACIÓN DE REPORTES         │
│  - CSV con datos crudos                 │
│  - JSON con estadísticas                │
│  - PDF profesional por jugador          │
│  - Video anotado (opcional)             │
│  - Dashboard HTML                       │
└─────────────────────────────────────────┘
   ↓
OUTPUT: Archivos de resultado
  ├── player_7.json
  ├── player_7.pdf
  ├── team_stats.json
  ├── frames.csv
  └── video_annotated.mp4
```

---

## 📋 Componentes Principales

### 1. **VideoProcessor** (Orquestador)
```python
class VideoProcessor:
    def __init__(self, config_path):
        self.config = load_config(config_path)
        self.detector = Detector(config)
        self.classifier = TeamClassifier(config)
        self.tracker = Tracker(config)
    
    def process(self, video_path, output_dir):
        # Valida → Detecta → Clasifica → Rastrea → Analiza
        results = self._pipeline(video_path)
        self._save_results(results, output_dir)
        return results
```

### 2. **Detector** (Wrapper YOLO)
```python
class Detector:
    def __init__(self, config):
        self.player_model = YOLO(...)
        self.pitch_model = YOLO(...)
        self.ball_model = YOLO(...)
    
    def detect_frame(self, frame):
        # Retorna detecciones unificadas con calidad
        return {
            'players': [...],
            'pitch': {...},
            'ball': {...},
            'quality_score': 0.85
        }
```

### 3. **PlayerAnalyzer** (Análisis individual)
```python
class PlayerAnalyzer:
    def analyze(self, player_tracks, video_info):
        # Por cada jugador rastreaado:
        # - Distancia total
        # - Velocidad máx/promedio
        # - Intensidad
        # - Heatmap
        # - Comparativa equipo
        return {
            'jersey_number': 7,
            'distance_km': 8.2,
            'max_speed': 28.5,
            'avg_speed': 12.3,
            'intensity': 0.78,
            'heatmap': numpy_array,
            'vs_team_avg': {...}
        }
```

### 4. **ReportGenerator** (Salida)
```python
class ReportGenerator:
    def generate_pdf(self, player_stats):
        # PDF profesional con:
        # - Foto jugador
        # - Estadísticas
        # - Gráficos
        # - Comparativa
        return pdf_bytes
    
    def generate_json(self, all_results):
        # JSON completo para integración
        
    def generate_dashboard(self, all_results):
        # HTML interactivo
```

---

## 🔌 Interfaces (APIs)

### CLI (Command Line)
```bash
# Procesar 1 video
python scripts/1_process_video.py input.mp4 --output results/

# Procesar batch
python scripts/2_process_batch.py videos/ --output results/

# Analizar jugador específico
python scripts/3_analyze_player.py results/ --jersey 7 --pdf

# Generar reportes
python scripts/4_generate_reports.py results/ --format all
```

### Python API
```python
from scout_ai import VideoProcessor

processor = VideoProcessor('config/detection_config.yaml')
results = processor.process('video.mp4', 'output/')

# Acceder a resultados
for player_id, stats in results.players.items():
    print(f"Player #{player_id}: {stats.distance_km}km")
```

### Web API (v2.0)
```
POST /api/upload          # Subir video
GET  /api/status/{id}     # Estado procesamiento
GET  /api/results/{id}    # Descargar resultados
GET  /api/player/{id}/{jersey}  # Stats jugador
```

---

## ⚙️ Configuración Centralizada

### detection_config.yaml
```yaml
device:
  primary: intel:cpu
  fallback: cpu

models:
  player:
    confidence: 0.40
    use_openvino: true
  ball:
    confidence: 0.30
  pitch:
    confidence: 0.50

processing:
  batch_size: 32
  frame_skip: 1
  max_frames: null
  enable_gpu: false

output:
  formats: [json, csv, pdf, video]
  video_codec: h264
  pdf_dpi: 150
```

---

## 📊 Flujo de Datos

```
CONFIG FILES
    ↓
VIDEO INPUT
    ↓
DETECTOR (YOLO) ──→ Detecciones + confianza
    ↓
CLASSIFIER ──→ Equipos + números
    ↓
TRACKER ──→ IDs consistentes
    ↓
ANALYZER ──→ Estadísticas por jugador
    ↓
REPORT GEN ──→ PDF/JSON/CSV/Video
    ↓
OUTPUT FOLDER
```

---

## 🧪 Testing Strategy

```
Unit Tests:
- test_detector.py         (YOLO funciona)
- test_classifier.py       (Clasificación correcta)
- test_tracker.py          (Tracking consistente)

Integration Tests:
- test_pipeline.py         (Todo junto)
- test_report_gen.py       (Reportes correctos)

End-to-End Tests:
- test_sample_video.py     (Video real completo)
```

---

## 🚀 Deployment Options

### Option 1: Local (Tu PC)
```
Ejecutar: python scripts/1_process_video.py
Ventaja: Gratis, privado
Desventaja: Lento (15h para 120 min video)
```

### Option 2: Google Colab
```
Ejecutar: notebook en Colab
Ventaja: GPU gratis, 5h para 120 min
Desventaja: Sesiones limitadas (12h)
```

### Option 3: Google Cloud / AWS
```
Backend serverless + Cloud Storage
Ventaja: Escalable, confiable, 2-3h para 120 min
Desventaja: Cuesta $3-5 por video
```

### Option 4: Web App + Queue
```
FastAPI backend + Celery + Redis
Usuario sube → Background processing → Email resultado
Ventaja: Usuario-friendly, escalable
Desventaja: Más infraestructura
```

---

## 📦 Dependencias Principales

```
ultralytics>=8.0          # YOLO
supervision>=0.21         # Detecciones
opencv-python>=4.8        # Procesamiento video
numpy                     # Cálculos
pandas                    # Datos
scipy                     # Estadísticas
pillow                    # Imágenes
pyyaml                    # Configs
reportlab                 # PDF generation
flask/fastapi            # Web (v2.0)
```

---

## 📈 Métricas de Calidad

```
Desempeño:
- FPS procesamiento: min 1 fps (120min = 2h máx)
- Accuracy detección: > 90%
- Accuracy tracking: > 85%
- Precisión velocidad: ±5%

Confiabilidad:
- Uptime: 99.9%
- Error rate: < 1%
- Timeout handling: Graceful degradation
```

---

## 🔐 Consideraciones de Seguridad

```
- Validación de entrada de video
- Sanitización de nombres de archivo
- Encriptación de almacenamiento
- Rate limiting en API
- Autenticación de usuarios (v2.0)
- GDPR compliance (video privado)
```

---

## 🗂️ Versionado y Evolución

```
v1.0 (MVP - Semanas 1-14):
- Análisis básico de jugadores
- Reportes PDF
- Procesa 1 video a la vez

v1.5 (Enhancement - Semanas 15-20):
- Batch processing
- Dashboard HTML
- Comparación equipo

v2.0 (Platform - Semanas 21-30):
- Web app completa
- Multi-usuario
- Sistema de suscripción
```

---

**AHORA:** Esperar diagnóstico → Implementar esta arquitectura → ¡Listo para procesar!

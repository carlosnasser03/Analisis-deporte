# Scout AI - Plataforma de Análisis Táctico de Fútbol

**Versión:** 4.0 (FASE 6 - Validación con StatsBomb)  
**Estado:** ✅ FASE 5 Completada | ✅ FASE 6 En Progreso  
**Última actualización:** 2026-07-28

---

## 🎯 ¿QUÉ ES SCOUT AI?

Scout AI es una **plataforma de análisis táctico de fútbol** que permite registrar y analizar el desempeño de jugadores en partidos de forma profesional.

### 🚀 Características Principales

- **Detección Automática**: Identifica jugadores, balón y cancha usando IA (YOLO v8)
- **Análisis Táctico**: Calcula métricas de rendimiento (movimiento, posicionamiento, inteligencia)
- **Clasificación de Equipos**: Distingue equipos automáticamente por color de camiseta
- **Seguimiento de Jugadores**: Rastrea movimiento de cada jugador a lo largo del partido
- **Reportes Profesionales**: Genera análisis en PDF y dashboards interactivos
- **Modular y Extensible**: Arquitectura basada en componentes independientes

### 👥 Usuarios Objetivo

- 👨‍👩‍👦 **Padres** - Mostrar progreso de hijos a scouts
- 🏫 **Academias** - Analizar equipos y jugadores
- 🔍 **Scouts** - Evaluar talento
- ⚽ **Equipos Profesionales** - Análisis táctico

---

## 🌟 FASE 6: Validación con StatsBomb (NUEVA)

**Nuevas en FASE 6 (2026-07-28):**

### Integración StatsBomb

1. **Benchmarking Profesional** - Compara contra Premier League
   - Distancia, velocidad e intensidad
   - Benchmarks por posición (GK, DEF, MID, FWD)
   - Percentiles automáticos

2. **Análisis Comparativo** - Entiende el contexto
   - ¿Cómo se compara tu jugador con profesionales?
   - Identificación de fortalezas/debilidades
   - Recomendaciones automáticas

3. **Reportes Completos** - Exportación JSON
   - Análisis individual por jugador
   - Resumen de equipo
   - Métricas z-score

### Ejemplo de Uso

```python
from core.statsbomb_integration import StatsBombIntegration

integrator = StatsBombIntegration()

# Comparar con benchmark
report = integrator.generate_comparison_report({
    "player_id": 7,
    "player_name": "Carlos",
    "position": "MID",
    "distance_m": 12000,
    "max_velocity_m_s": 10.5,
    "intensity_percent": 82
})

print(f"Percentil: {report['overall_percentile']:.1f}")
print(f"Resumen: {report['summary']}")
```

### Tests Incluidos

- **18 tests** cubriendo toda la integración
- Validación de datos
- Comparativas por posición
- Casos límite y errores
- Integración con pipeline

### Documentación Completa

- **[STATSBOMB_INTEGRATION.md](STATSBOMB_INTEGRATION.md)** - Guía completa con benchmarks
- **[QUICKSTART_FASE5.md](QUICKSTART_FASE5.md)** - Sección "Comparar con Profesionales"
- **tests/test_statsbomb_integration.py** - 18 tests de cobertura completa

---

## ⚡ FASE 3: Optimización de Performance

**Completada en FASE 3 (2026-07-06):**

### Optimizaciones Implementadas

1. **Vectorización NumPy** - 8-20x más rápido
   - IoU calculation vectorizada
   - Distancia de puntos optimizada
   - Color distance computation vectorizada

2. **Caché de Modelos YOLO** - Evita 2-3s por reload
   - Política LRU automática
   - Hit rate 85-95% en batch processing
   - Reduce overhead 60-70%

3. **Memory Pooling** - 60-70% menos fragmentación
   - Preasignación de buffers
   - Reutilización automática de memoria
   - Zero-copy operations

4. **Benchmarking Framework** - Medición completa
   - Medir tiempo/memoria/CPU por componente
   - Análisis automático de bottlenecks
   - Reporte JSON detallado

### Métricas de Performance

```
Resolución        Target    Estimado    Memory    CPU
─────────────────────────────────────────────────────
720x1280 @ 25fps  25 fps    28-32 fps   120MB     60%
1080x1920 @ 25fps 25 fps    22-26 fps   250MB     75%
```

### Documentación Completa

- **[FASE_3_PROCESAMIENTO.md](FASE_3_PROCESAMIENTO.md)** - Guía completa de optimizaciones
- **Benchmarking**: `python scripts/benchmark_pipeline.py --all`
- **Tests**: 35 tests de performance optimizer con 95%+ cobertura

---

## 📋 Instalación

### Requisitos Previos

- Python 3.9+
- OpenCV (cv2)
- YOLO v8 (ultralytics)
- NumPy, Scikit-learn

### Pasos de Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/scout-ai.git
cd scout-ai

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Verificar instalación
python -c "from core import *; from utils import *; print('✓ Dependencias OK')"
```

### Archivo `requirements.txt`

```
opencv-python==4.8.0.74
ultralytics==8.0.200
numpy==1.24.3
scikit-learn==1.3.0
pyyaml==6.0
psutil==5.9.5
```

---

## 🚀 Uso Rápido

### Ejemplo Básico

```python
from core import UnifiedDetector
from utils import VideoValidator
import cv2

# 1. Validar video
result = VideoValidator.validate_video_file("video.mp4")
if not result.is_valid:
    print(f"Error: {result.message}")
    exit(1)

# 2. Crear detector
detector = UnifiedDetector("config/detection_config.yaml")

# 3. Procesar video
cap = cv2.VideoCapture("video.mp4")
frame_id = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Detectar objetos
    detections = detector.detect(frame)
    
    # Acceder a resultados
    print(f"Frame {frame_id}:")
    print(f"  - Balón: {detections['ball']}")
    print(f"  - Jugadores: {len(detections['players'])}")
    
    frame_id += 1

cap.release()
```

### Procesamiento Paralelo con Chunks

```python
from core import UnifiedDetector
from utils import VideoSplitter
from concurrent.futures import ThreadPoolExecutor

# Dividir video
splitter = VideoSplitter("video.mp4")
chunks = splitter.split_video(chunk_duration=30, overlap_frames=5)

# Procesar en paralelo
def process_chunk(chunk):
    detector = UnifiedDetector("config/detection_config.yaml")
    # ... procesar chunk ...
    return results

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_chunk, chunks))

# Limpiar archivos temporales
splitter.cleanup_chunks()
```

### Validación Completa

```python
from utils import validate_all

# Validar video, config, dependencias y recursos
results = validate_all("video.mp4", "config/detection_config.yaml")

# Ver resultados
for check_name, result in results.items():
    status = "✓" if result.is_valid else "✗"
    print(f"{status} {check_name}: {result.message}")
    if result.warnings:
        for warning in result.warnings:
            print(f"  ⚠ {warning}")
    if result.errors:
        for error in result.errors:
            print(f"  ✗ {error}")
```

---

## 📁 Estructura del Proyecto

```
scout-ai/
├── core/                               # Módulos centrales
│   ├── __init__.py
│   ├── detector.py                     # Detectores YOLO
│   ├── homography_validator.py         # Validador de perspectiva
│   ├── metrics.py                      # Logging y métricas
│   ├── team_classifier.py              # Clasificador de equipos
│   ├── tracker.py                      # Rastreador de jugadores
│   ├── jersey_number_detector.py       # Detector de números
│   ├── player_analyzer.py              # Análisis de jugadores
│   └── report_generator.py             # Generador de reportes
│
├── utils/                              # Utilidades
│   ├── __init__.py
│   ├── video_splitter.py               # Divisor de videos
│   └── validators.py                   # Validadores
│
├── config/
│   └── detection_config.yaml           # Configuración centralizada
│
├── data/
│   ├── logs/                           # Resultados
│   │   ├── FASE_2_COMPLETADA.json
│   │   ├── frames_*.csv
│   │   └── summary_*.json
│   └── models/                         # Modelos YOLO
│
├── scripts/
│   ├── 0_validate_single.py            # Validación
│   ├── 1_preparar.py                   # Preparación
│   └── 2_analizar.py                   # Análisis
│
├── README.md                           # Este archivo
├── ARCHITECTURE_IMPLEMENTATION.md      # Documentación técnica
├── CONTRIBUTING.md                     # Guía de contribución
├── requirements.txt                    # Dependencias
└── .claude/settings.local.json         # Configuración local
```

---

## 📚 Documentación

### Documentos Principales

- **[ARCHITECTURE_IMPLEMENTATION.md](ARCHITECTURE_IMPLEMENTATION.md)** - Documentación técnica completa
  - Estructura de directorios
  - Descripción detallada de módulos
  - Patrones de diseño
  - Ejemplos de uso avanzado
  - Guía de extensibilidad

- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guía para contribuidores
  - Estándares de código
  - Proceso de desarrollo
  - Testing
  - Pull requests

- **[PRODUCTO_VISION.md](PRODUCTO_VISION.md)** - Visión de producto
  - Propuesta de valor
  - Modelo de negocio
  - Roadmap de features

- **[PLAN_IMPLEMENTACION.md](PLAN_IMPLEMENTACION.md)** - Plan de 14 semanas
  - Fases de desarrollo
  - Cronograma
  - Deliverables

---

## 🔧 Configuración

### config/detection_config.yaml

```yaml
# Modelos YOLO
models:
  ball: "data/models/yolo_ball.pt"
  player: "data/models/yolo_player.pt"
  
# Parámetros de detección
detection:
  confidence_threshold: 0.5
  iou_threshold: 0.45
  
# Parámetros de tracking
tracking:
  max_missing_frames: 30
  max_age: 60
  
# Parámetros de clasificación
classification:
  n_clusters: 2
  color_space: "hsv"
  
# Output
output:
  save_csv: true
  save_json: true
  save_video: false
```

---

## 📊 Módulos Disponibles

### Core

```python
from core import (
    BallDetector,           # Detector de balón
    CornerDetector,         # Detector de esquinas
    UnifiedDetector,        # Detector unificado
    TeamClassifier,         # Clasificador de equipos
    TeamColor,              # Estructura de color
    PlayerTracker,          # Rastreador de jugadores
    JerseyNumberDetector,   # Detector de números
    DetectionMetrics,       # Logging de métricas
    HomographyValidator,    # Validador de perspectiva
    PlayerAnalyzer,         # Análisis de jugadores
    ReportGenerator,        # Generador de reportes
)
```

### Utils

```python
from utils import (
    VideoSplitter,          # Divisor de videos
    ChunkInfo,              # Información de chunks
    VideoValidator,         # Validador de video
    DetectionValidator,     # Validador de detecciones
    ConfigValidator,        # Validador de configuración
    DependencyValidator,    # Validador de dependencias
    ValidationResult,       # Resultado de validación
    validate_all,           # Validación completa
)
```

---

## 🧪 Testing

```bash
# Ejecutar validación de una detección
python scripts/0_validate_single.py --video video.mp4

# Validar archivo de video
python -c "
from utils import VideoValidator
result = VideoValidator.validate_video_file('video.mp4')
print(result.message)
print(f'Detalles: {result.details}')
"

# Verificar dependencias
python -c "
from utils import DependencyValidator
result = DependencyValidator.check_dependencies()
print(result.message)
if result.errors:
    print('Errores:', result.errors)
"
```

---

## 📈 Métricas y Reportes

### Exportar Métricas

```python
from core import DetectionMetrics

metrics = DetectionMetrics()
# ... procesar video ...

# Exportar a CSV
metrics.export_csv("logs/detections.csv")

# Exportar a JSON
metrics.export_json("logs/summary.json")

# Obtener reporte
report = metrics.get_report()
print(report)
```

### Estructura de Salida

**CSV** (`logs/frames_*.csv`):
```csv
frame_id,timestamp,ball_x,ball_y,ball_conf,players_count,team_a_count,team_b_count
0,0.0,320,240,0.95,22,11,11
1,0.033,321,242,0.94,22,11,11
...
```

**JSON** (`logs/summary_*.json`):
```json
{
  "total_frames": 1000,
  "duration_seconds": 33.3,
  "fps": 30,
  "ball_detection_rate": 0.95,
  "player_detection_rate": 0.98,
  "team_distribution": {
    "A": 11,
    "B": 11
  }
}
```

---

## 🐛 Solución de Problemas

### Video no se abre

```python
from utils import VideoValidator
result = VideoValidator.validate_video_file("video.mp4")
print(result.errors)  # Ver detalles del error
```

### Dependencias faltantes

```python
from utils import DependencyValidator
result = DependencyValidator.check_dependencies()
if not result.is_valid:
    print("\nFaltan instalar:")
    for error in result.errors:
        print(f"  - {error}")
```

### Memoria insuficiente

Usa `VideoSplitter` para procesar en chunks:
```python
from utils import VideoSplitter
splitter = VideoSplitter("video.mp4")
chunks = splitter.split_video(chunk_duration=15)  # Chunks más pequeños
```

---

## 📝 Changelog (FASE 2)

### ✅ Completado

- [x] Módulo `utils/video_splitter.py` (120+ líneas)
- [x] Módulo `utils/validators.py` (150+ líneas)
- [x] Documentación técnica completa
- [x] Actualización de `core/__init__.py`
- [x] Guía de contribución
- [x] Validación de dependencias

### 📋 Próxima Fase (FASE 3)

- [ ] REST API
- [ ] WebSocket para streaming
- [ ] Base de datos
- [ ] Dashboard web mejorado
- [ ] Exportación a múltiples formatos

---

## 📞 Soporte

Para preguntas o problemas:

1. Revisa [ARCHITECTURE_IMPLEMENTATION.md](ARCHITECTURE_IMPLEMENTATION.md)
2. Revisa [CONTRIBUTING.md](CONTRIBUTING.md)
3. Abre un issue en el repositorio
4. Contacta al equipo Scout AI

---

## 📄 Licencia

[Especificar licencia]

---

## 👥 Contribuidores

Scout AI Team | 2026

---

**Última actualización:** 2026-07-06  
**Versión:** 2.0

# QUICKSTART - FASE 3

## ⚡ Inicio Rápido en 5 Minutos

### 1. Verificar Instalación ✅

```bash
# Verificar Python
python --version  # 3.8+

# Verificar dependencias principales
python -c "import cv2, numpy, sklearn, ultralytics; print('✓ Dependencias OK')"
```

### 2. Ejecutar Tests (Recomendado)

```bash
# Ejecutar todos los tests FASE 3
python run_fase3_tests.py

# Esperar completación (~2-3 minutos)
# Verás output como:
# [14:30:00] VideoProcessorFase3 [INFO] ✓ Detector YOLO disponible
# Procesando video FASE 3: 100%|██████████| 50/50
```

### 3. Procesar un Video

#### Opción A: Script Simple
```bash
python -c "
from pipeline.video_processor_fase3 import VideoProcessorFase3

processor = VideoProcessorFase3()
processor.setup_detectors()

result = processor.process_video(
    'data/08fd33_0.mp4',
    output_path='results.json'
)

print(f'✓ Procesado: {result.processed_frames} frames')
print(f'✓ FPS: {result.fps_processed:.1f}')
print(f'✓ Tiempo: {result.total_time_seconds:.1f}s')
print(f'✓ Resultado: results.json')
"
```

#### Opción B: Script Python
```python
# proceso.py
from pipeline.video_processor_fase3 import VideoProcessorFase3, ProcessingConfigFase3
from core.tracker import PlayerTracker
from core.team_classifier import TeamClassifier
from core.jersey_number_detector import JerseyNumberDetector

config = ProcessingConfigFase3(
    max_frames=100,
    enable_tracking=True,
    enable_team_classification=True,
    enable_jersey_detection=False
)

processor = VideoProcessorFase3(
    tracker=PlayerTracker(),
    team_classifier=TeamClassifier(),
    config=config
)

result = processor.process_video('data/08fd33_0.mp4')
result.save_json('output.json')
print(f"✓ Completado: {result.fps_processed:.1f} FPS")
```

```bash
python proceso.py
```

---

## 🎯 Uso Común

### Procesar Video Real
```python
from pipeline.video_processor_fase3 import VideoProcessorFase3
from ultralytics import YOLO

detector = YOLO('data/football-player-detection.pt')
processor = VideoProcessorFase3(detector=detector)
processor.setup_detectors()

result = processor.process_video('data/08fd33_0.mp4')
print(f"Frames: {result.processed_frames}, FPS: {result.fps_processed:.1f}")
```

### Acceder a Resultados
```python
# Team colors detectados
print("Teams:", result.team_classification_stats)

# Tracking active
print("Tracks:", result.tracking_stats)

# Jersey numbers
print("Jerseys:", result.jersey_detection_stats)

# Performance
for name, bench in result.performance_benchmarks.items():
    print(f"{name}: {bench.avg_time_ms:.1f}ms")

# Memory usado
print("Memory:", result.system_resources['end_memory']['rss_mb'], "MB")
```

### Habilitar Profiling
```python
from pipeline.video_processor_fase3 import ProcessingConfigFase3

config = ProcessingConfigFase3(
    enable_profiling=True,
    profile_output_path='profile.txt',
    max_frames=50
)

processor = VideoProcessorFase3(config=config)
result = processor.process_video('video.mp4')

# Revisar profile.txt para ver funciones más lentas
```

### Con Componentes Personalizados
```python
from pipeline.video_processor_fase3 import VideoProcessorFase3
from core.tracker import PlayerTracker
from core.team_classifier import TeamClassifier
from core.jersey_number_detector import JerseyNumberDetector

processor = VideoProcessorFase3(
    detector=tu_detector,
    tracker=PlayerTracker(max_age=60),
    team_classifier=TeamClassifier(n_clusters=2),
    jersey_detector=JerseyNumberDetector(use_paddle=True),
    config=ProcessingConfigFase3(max_frames=500)
)

result = processor.process_video('video.mp4', output_path='results.json')
```

---

## 🧪 Tests

### Ejecutar Todos
```bash
python run_fase3_tests.py
```

### Ejecutar Tests Específicos
```bash
# Test de precisión de teams
pytest tests/test_end_to_end_fase3.py::TestTeamClassificationAccuracy -v

# Test de tracking
pytest tests/test_end_to_end_fase3.py::TestTrackingStability -v

# Test de jerseys
pytest tests/test_end_to_end_fase3.py::TestJerseyDetectionAccuracy -v

# Test de performance
pytest tests/test_end_to_end_fase3.py::TestPerformanceBenchmarks -v
```

### Con Coverage
```bash
pytest tests/test_end_to_end_fase3.py --cov=pipeline --cov=core --cov-report=term-missing
```

---

## 📊 Ver Resultados

### Archivo JSON
```bash
# Ver resultado en JSON
cat output.json | python -m json.tool

# O con less
less output.json
```

### Benchmarks
```bash
# Ver benchmarks generados
cat data/logs/performance_benchmarks.json | python -m json.tool
```

### Validación
```bash
# Ver validación del pipeline
cat data/logs/pipeline_validation.json | python -m json.tool
```

---

## 📝 Archivos Clave

| Archivo | Descripción |
|---------|-------------|
| `pipeline/video_processor_fase3.py` | Pipeline principal |
| `tests/test_end_to_end_fase3.py` | Tests end-to-end |
| `run_fase3_tests.py` | Ejecutor de tests |
| `FASE_3_README.md` | Guía completa de uso |
| `FASE_3_IMPLEMENTATION.md` | Documentación técnica |
| `FASE_3_SUMMARY.md` | Resumen de implementación |

---

## ⚙️ Configuración Rápida

### Procesamiento Rápido (5-10 fps)
```python
config = ProcessingConfigFase3(
    skip_frames=5,          # Procesar cada 5 frames
    max_frames=100,         # Máximo 100 frames
    enable_jersey_detection=False  # Desactivar OCR
)
```

### Procesamiento Completo (2-5 fps)
```python
config = ProcessingConfigFase3(
    skip_frames=1,          # Procesar todos
    max_frames=1000,        # Muchos frames
    enable_jersey_detection=True   # OCR activado
)
```

### Con Profiling (1-2 fps)
```python
config = ProcessingConfigFase3(
    skip_frames=2,
    enable_profiling=True,
    profile_output_path='profile.txt'
)
```

---

## 🔍 Verificar Status

### Inicialización
```python
processor = VideoProcessorFase3()
success = processor.setup_detectors()
print(f"Status: {'✓ OK' if success else '✗ FAILED'}")
```

### Información de Sistema
```python
import psutil
print(f"CPU: {psutil.cpu_count()} cores")
print(f"Memory: {psutil.virtual_memory().total / (1024**3):.1f} GB")
print(f"Available: {psutil.virtual_memory().available / (1024**3):.1f} GB")
```

### Verificar Componentes
```python
from core.jersey_number_detector import JerseyNumberDetector
jersey = JerseyNumberDetector()
print(f"OCR: {jersey.ocr_type}")  # 'paddle', 'easyocr', o 'none'
```

---

## 🐛 Quick Fixes

### Problema: Import error
```bash
# Asegurar que el proyecto está en PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python script.py
```

### Problema: Model not found
```python
# Usar modelo alternativo o mock
from unittest.mock import MagicMock
detector = MagicMock()  # Para testing
```

### Problema: Memory overflow
```python
# Limitar frames y desactivar profiling
config = ProcessingConfigFase3(
    max_frames=10,
    enable_profiling=False,
    skip_frames=10
)
```

### Problema: Slow processing
```python
# Aumentar skip_frames
config = ProcessingConfigFase3(
    skip_frames=5,  # Procesar cada 5 frames
    enable_jersey_detection=False  # Desactivar OCR lento
)
```

---

## 📊 Ejemplo Completo

```python
#!/usr/bin/env python
"""Ejemplo completo FASE 3"""

from pathlib import Path
from pipeline.video_processor_fase3 import VideoProcessorFase3, ProcessingConfigFase3
from core.tracker import PlayerTracker
from core.team_classifier import TeamClassifier
from core.jersey_number_detector import JerseyNumberDetector

# 1. Configurar
print("1️⃣ Configurando...")
config = ProcessingConfigFase3(
    min_confidence=0.3,
    skip_frames=3,
    max_frames=100,
    enable_tracking=True,
    enable_team_classification=True,
    enable_jersey_detection=False,  # OCR puede ser lento
)

# 2. Crear procesador
print("2️⃣ Creando procesador...")
processor = VideoProcessorFase3(
    tracker=PlayerTracker(),
    team_classifier=TeamClassifier(),
    jersey_detector=JerseyNumberDetector(use_paddle=False, use_easyocr=False),
    config=config
)

# 3. Validar componentes
print("3️⃣ Validando componentes...")
if not processor.setup_detectors():
    print("✗ Falló validación")
    exit(1)

# 4. Procesar video
print("4️⃣ Procesando video...")
video_file = "data/08fd33_0.mp4"
if not Path(video_file).exists():
    print(f"✗ Video no encontrado: {video_file}")
    exit(1)

result = processor.process_video(video_file, output_path='results.json')

# 5. Mostrar resultados
print("\n5️⃣ RESULTADOS:")
print(f"   Frames procesados: {result.processed_frames}/{result.total_frames}")
print(f"   Tiempo total: {result.total_time_seconds:.2f}s")
print(f"   FPS: {result.fps_processed:.1f}")
print(f"   Detecciones: {result.processing_stats.get('valid_detections', 0)}")
print(f"   Tracks activos: {result.tracking_stats.get('active_tracks', 0)}")
print(f"   Memory: {result.system_resources['end_memory']['rss_mb']:.0f} MB")

# 6. Benchmarks
print("\n6️⃣ BENCHMARKS:")
for name, bench in result.performance_benchmarks.items():
    print(f"   {name}: {bench.avg_time_ms:.2f}ms (calls: {bench.calls_count})")

# 7. Guardar resultado
print(f"\n7️⃣ Resultado guardado en: results.json")
```

---

## 🎓 Más Información

- **Documentación Completa:** `FASE_3_IMPLEMENTATION.md`
- **Guía de Uso:** `FASE_3_README.md`
- **Resumen:** `FASE_3_SUMMARY.md`
- **Tests:** `tests/test_end_to_end_fase3.py`

---

## ✨ Tips

1. **Para debugging:** Usar `logging.basicConfig(level=logging.DEBUG)`
2. **Para profiling:** Habilitar `enable_profiling=True`
3. **Para tests rápidos:** Usar `skip_frames=5, max_frames=50`
4. **Para producción:** Usar `skip_frames=1, max_frames=None`

---

**¡Listo para usar! 🚀**

Comienza con: `python run_fase3_tests.py`

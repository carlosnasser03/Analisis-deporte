# Módulo de Calibración Adaptativa - Guía de Uso

## Descripción General

El módulo `core/adaptive_calibration.py` proporciona análisis automático de video y calibración inteligente de parámetros de procesamiento sin necesidad de modelos de lenguaje. Funciona 100% offline usando solo OpenCV y NumPy.

### Características Principales

- **Análisis de Calidad de Video**: Detecta brillo, blur, oclusión, clima, densidad de multitud
- **Calibración Automática**: Ajusta parámetros basado en condiciones del video
- **Sin Dependencias Pesadas**: Solo OpenCV y NumPy
- **Rápido**: Analiza 10 frames de muestra en < 5 segundos
- **Robusto**: Manejo de errores y logging completo
- **Type Hints**: Código completamente tipado

---

## Instalación

El módulo ya está disponible en `core/adaptive_calibration.py`. Solo requiere dependencias ya incluidas en `requirements.txt`:

```bash
pip install opencv-python numpy
```

---

## Uso Básico

### Opción 1: Análisis + Calibración en Un Paso

```python
from core.adaptive_calibration import analyze_and_calibrate

# Analizar video y obtener configuración calibrada
metrics, config = analyze_and_calibrate('path/to/video.mp4')

# Ver métricas
print(f"Brillo: {metrics.brightness}")
print(f"Blur: {metrics.blur_level}")
print(f"Calidad: {metrics.video_quality.value}")

# Usar configuración
print(f"confidence_threshold: {config.confidence_threshold}")
print(f"gk_sensitivity: {config.gk_sensitivity}")
print(f"skip_frames: {config.skip_frames}")

# Ver reporte completo
print(config.quality_report)
```

### Opción 2: Análisis y Calibración Separados

```python
from core.adaptive_calibration import VideoQualityAnalyzer, AdaptiveCalibration

# Paso 1: Analizar video
analyzer = VideoQualityAnalyzer(sample_frames=10)
metrics = analyzer.analyze_video('path/to/video.mp4')

# Paso 2: Calibrar parámetros
calibrator = AdaptiveCalibration()
config = calibrator.get_optimal_config(metrics)

# Usar configuración en pipeline
detector = YourDetector(confidence_threshold=config.confidence_threshold)
```

---

## Métricas de Calidad

### VideoQualityMetrics

La clase `VideoQualityMetrics` contiene:

```python
@dataclass
class VideoQualityMetrics:
    brightness: float              # 0-255 (promedio)
    brightness_std: float          # Desviación estándar
    blur_level: float              # 0-1 (0=nítido, 1=borroso)
    motion_blur: float             # 0-1 (movimiento entre frames)
    occlusion_rate: float          # 0-1 (% píxeles oscuros)
    lighting_condition: LightingCondition  # NORMAL|DARK|BRIGHT|VARIABLE
    weather_condition: WeatherCondition    # CLEAR|RAIN|FOG
    crowd_density: float           # 0-1 (densidad de actividad)
    video_quality: VideoQuality    # EXCELLENT|GOOD|FAIR|POOR
    analysis_frames: int           # Número de frames analizados
    frame_rate: float              # FPS del video
```

### Enum de Condiciones

```python
from core.adaptive_calibration import (
    LightingCondition,
    WeatherCondition,
    VideoQuality
)

# LightingCondition
LightingCondition.NORMAL      # Iluminación normal
LightingCondition.DARK        # Muy oscuro
LightingCondition.BRIGHT      # Muy claro
LightingCondition.VARIABLE    # Iluminación inconsistente

# WeatherCondition
WeatherCondition.CLEAR        # Clima despejado
WeatherCondition.RAIN         # Lluvia detectada
WeatherCondition.FOG          # Niebla detectada

# VideoQuality
VideoQuality.EXCELLENT        # Calidad excelente
VideoQuality.GOOD             # Buena calidad
VideoQuality.FAIR             # Calidad aceptable
VideoQuality.POOR             # Calidad deficiente
```

---

## Configuración de Procesamiento

### ProcessingConfig

La clase `ProcessingConfig` contiene parámetros calibrados:

```python
@dataclass
class ProcessingConfig:
    confidence_threshold: float    # 0.45-0.75 (umbral de confianza)
    gk_sensitivity: float          # 0.8-1.3 (sensibilidad de portero)
    tracker_max_distance: float    # 50-150 px (máxima distancia de tracking)
    skip_frames: int               # 1-5 (frames a saltar)
    use_motion_blur: bool          # Usar compensación de motion blur
    quality_report: str            # Reporte detallado de ajustes
```

---

## Reglas de Ajuste Automático

El módulo aplica los siguientes ajustes basados en condiciones:

### Brillo Bajo (< 50)
```
- confidence_threshold -= 0.15  (menos exigente)
- gk_sensitivity += 0.2         (más sensible)
```

### Blur Alto (> 0.5)
```
- tracker_max_distance += 30    (tolera más movimiento)
- skip_frames = max(skip_frames, 2)
```

### Oclusión Alta (> 0.4)
```
- gk_sensitivity += 0.15
- confidence_threshold -= 0.10
```

### Iluminación Variable
```
- use_motion_blur = True        (compensa motion blur)
- skip_frames = max(skip_frames, 2)
```

### Clima Adverso (lluvia/niebla)
```
- gk_sensitivity += 0.1
- tracker_max_distance += 20
```

### Motion Blur Alto (> 0.5)
```
- skip_frames = max(skip_frames, 3)  (máximo)
- tracker_max_distance += 20
```

### Calidad POOR
```
- skip_frames = max(skip_frames, 3)   (máximo)
- confidence_threshold -= 0.25        (mucho menos exigente)
- gk_sensitivity += 0.15
```

---

## Ejemplos de Uso

### Ejemplo 1: Análisis Simple

```python
from core.adaptive_calibration import VideoQualityAnalyzer

analyzer = VideoQualityAnalyzer(sample_frames=10)
metrics = analyzer.analyze_video('video.mp4')

if metrics:
    print(f"✓ Video analizando correctamente")
    print(f"  Calidad: {metrics.video_quality.value}")
    print(f"  Brillo: {metrics.brightness:.1f}")
else:
    print("✗ No se pudo analizar el video")
```

### Ejemplo 2: Calibración con Reporte

```python
from core.adaptive_calibration import (
    VideoQualityAnalyzer,
    AdaptiveCalibration,
)

# Analizar
analyzer = VideoQualityAnalyzer(sample_frames=15)
metrics = analyzer.analyze_video('video.mp4')

# Calibrar
calibrator = AdaptiveCalibration()
config = calibrator.get_optimal_config(metrics)

# Mostrar reporte
print(config.quality_report)

# Usar parámetros
processing_pipeline.set_config(
    confidence_threshold=config.confidence_threshold,
    gk_sensitivity=config.gk_sensitivity,
    skip_frames=config.skip_frames,
)
```

### Ejemplo 3: Uso Directo en Pipeline

```python
from core.adaptive_calibration import analyze_and_calibrate
from core.detector import PlayerDetector

# Calibrar automáticamente
metrics, config = analyze_and_calibrate('input_video.mp4')

# Crear detector con parámetros calibrados
detector = PlayerDetector(
    confidence_threshold=config.confidence_threshold,
    use_motion_blur=config.use_motion_blur,
)

# Procesar video
results = detector.process_video('input_video.mp4', skip_frames=config.skip_frames)
```

### Ejemplo 4: Serialización y Almacenamiento

```python
import json
from core.adaptive_calibration import analyze_and_calibrate

# Analizar y calibrar
metrics, config = analyze_and_calibrate('video.mp4')

# Guardar como JSON
metrics_json = metrics.to_dict()
with open('metrics.json', 'w') as f:
    json.dump(metrics_json, f, indent=2)

# Guardar configuración
config_json = config.to_dict()
with open('config.json', 'w') as f:
    json.dump(config_json, f, indent=2)

# Cargar después
with open('metrics.json', 'r') as f:
    loaded_metrics = json.load(f)

# Usar métricas cargadas
calibrator = AdaptiveCalibration()
config = calibrator.get_optimal_config(loaded_metrics)
```

### Ejemplo 5: Procesamiento por Lotes

```python
from pathlib import Path
from core.adaptive_calibration import analyze_and_calibrate

video_dir = Path("videos")
results = {}

for video_path in video_dir.glob("*.mp4"):
    print(f"\nAnalizando: {video_path.name}")
    
    try:
        metrics, config = analyze_and_calibrate(str(video_path))
        results[video_path.name] = {
            'quality': metrics.video_quality.value,
            'brightness': metrics.brightness,
            'confidence_threshold': config.confidence_threshold,
            'skip_frames': config.skip_frames,
        }
        print(f"  ✓ {metrics.video_quality.value}")
    except Exception as e:
        print(f"  ✗ Error: {e}")

# Mostrar resumen
for name, data in results.items():
    print(f"\n{name}:")
    for key, value in data.items():
        print(f"  {key}: {value}")
```

---

## Métodos Privados (Helper)

El módulo incluye métodos helper que se pueden extender o personalizar:

### VideoQualityAnalyzer Helpers

```python
analyzer = VideoQualityAnalyzer()

# Calcular brillo (promedio de píxeles en escala de grises)
brightness = analyzer._calculate_brightness(frame)

# Detectar blur (varianza de Laplacian)
blur = analyzer._detect_blur(frame)

# Detectar motion blur (diferencia entre frames)
motion = analyzer._detect_motion_blur(frame1, frame2)

# Estimar oclusión (píxeles oscuros)
occlusion = analyzer._estimate_occlusion(frame)

# Detectar clima (FOG/RAIN/CLEAR)
weather = analyzer._detect_weather(blur_values, occlusion_values)

# Clasificar iluminación
lighting = analyzer._classify_lighting(brightness, brightness_std)

# Clasificar calidad general
quality = analyzer._classify_quality(
    brightness, blur_level, occlusion_rate, crowd_density
)
```

---

## Logging

El módulo utiliza logging estándar de Python. Configurar como:

```python
import logging

# Configurar logging (DEBUG para más detalles)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] - %(name)s: %(message)s'
)

# Ahora tendrás salida detallada
metrics, config = analyze_and_calibrate('video.mp4')
```

### Niveles de Log

- **DEBUG**: Detalles de cada frame (frame_idx, métricas individuales)
- **INFO**: Puntos de control principales (video abierto, análisis completado, configuración generada)
- **WARNING**: Problemas recuperables (frame no legible, error en cálculo)
- **ERROR**: Problemas graves (video no encontrado, no se puede abrir)

---

## Manejo de Errores

El módulo está preparado para errores comunes:

```python
from core.adaptive_calibration import analyze_and_calibrate

try:
    metrics, config = analyze_and_calibrate('video.mp4')
except FileNotFoundError:
    print("El video no existe")
except ValueError:
    print("El video no se puede leer (formato no soportado)")
except Exception as e:
    print(f"Error inesperado: {e}")
```

---

## Performance

Tiempos típicos de análisis:

- **Apertura video**: ~100ms
- **Muestreo 10 frames**: ~1-2 segundos
- **Análisis por frame**: ~100-200ms cada uno
- **Calibración**: ~10ms
- **Total**: ~2-3 segundos para video de 30 segundos @ 25fps

Para videos muy grandes, aumentar `skip_frames` en el pipeline, no modificar `sample_frames` del analizador.

---

## Debugging y Troubleshooting

### El video no se analiza

```python
from core.adaptive_calibration import VideoQualityAnalyzer
import logging

logging.basicConfig(level=logging.DEBUG)

analyzer = VideoQualityAnalyzer()
# Verás logs detallados de qué falla
metrics = analyzer.analyze_video('video.mp4')
```

### Parámetros no se ajustan como esperado

Revisar `config.quality_report` para ver qué ajustes se aplicaron:

```python
metrics, config = analyze_and_calibrate('video.mp4')
print(config.quality_report)  # Muestra todos los ajustes
```

### Métricas incorrectas

Verificar que el video tenga:
- Frames válidos (no corrupto)
- Resolución mínima de 320x240
- Codec soportado por OpenCV (H.264, MPEG-4, etc.)

---

## Extensión y Customización

### Agregar métodos de análisis personalizados

```python
from core.adaptive_calibration import VideoQualityAnalyzer

class CustomAnalyzer(VideoQualityAnalyzer):
    def _detect_custom_condition(self, frame):
        """Tu análisis personalizado"""
        # implementar
        return value
```

### Modificar reglas de calibración

```python
from core.adaptive_calibration import AdaptiveCalibration

class CustomCalibrator(AdaptiveCalibration):
    def get_optimal_config(self, quality_metrics):
        config = super().get_optimal_config(quality_metrics)
        
        # Agregar lógica personalizada
        if quality_metrics.brightness > 200:
            config.confidence_threshold -= 0.05
        
        return config
```

---

## Referencias

- **Archivo principal**: `core/adaptive_calibration.py`
- **Script de prueba**: `test_adaptive_calibration.py`
- **Documentación técnica**: Docstrings en el código fuente

---

## Notas Importantes

1. **Sin SLM**: Todo análisis es heurístico basado en CV, no requiere modelos entrenados
2. **100% Offline**: No envía datos a servidores, funciona completamente local
3. **Compatible**: Funciona con cualquier formato soportado por OpenCV
4. **Extensible**: Diseño modular permite agregar nuevos análisis
5. **Robustez**: Manejo completo de errores con fallbacks a valores por defecto

---

## Licencia y Créditos

Parte del proyecto Scout AI - Análisis de Deportes

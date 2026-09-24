# Integración de Calibración Adaptativa en el Pipeline

## Resumen de Archivos Creados

```
core/
├── adaptive_calibration.py          ← NUEVO: Módulo principal
├── detector.py                      ← Existente (modificar para usar calibración)
├── tracker_improved.py              ← Existente (modificar para usar calibración)
└── [otros módulos existentes]

test_adaptive_calibration.py         ← NUEVO: Script de pruebas

ADAPTIVE_CALIBRATION_GUIDE.md        ← NUEVO: Guía de uso
ADAPTIVE_CALIBRATION_INTEGRATION.md  ← NUEVO: Este archivo
```

---

## Flujo de Integración

### Sin Calibración Adaptativa (Actual)

```
Video → Parámetros Fijos → Detector YOLO → Tracker → Análisis → Resultados
```

### Con Calibración Adaptativa (Nuevo)

```
Video → Analizador de Calidad → Calibrador → Parámetros Dinámicos → Detector → Resultados
                                    ↓
                            (Reporte de Ajustes)
```

---

## Puntos de Integración

### 1. En el Detector (core/detector.py)

**Modificación propuesta:**

```python
from core.adaptive_calibration import analyze_and_calibrate

class BallDetector:
    def __init__(self, model_path: str, video_path: str = None, device: str = "cpu"):
        """
        Args:
            model_path: Ruta al modelo YOLO
            video_path: Ruta al video para calibración automática
            device: Dispositivo de cómputo
        """
        self.model = YOLO(model_path)
        self.device = device
        
        # Calibración adaptativa
        self.calibrated = False
        self.min_confidence = 0.3  # Por defecto
        
        if video_path:
            self._calibrate_from_video(video_path)
    
    def _calibrate_from_video(self, video_path: str):
        """Analiza video y ajusta parámetros"""
        try:
            metrics, config = analyze_and_calibrate(video_path)
            self.min_confidence = config.confidence_threshold
            self.calibrated = True
            print(f"✓ Parámetros calibrados: conf_threshold={self.min_confidence:.3f}")
            print(config.quality_report)
        except Exception as e:
            print(f"⚠ Calibración fallida, usando valores por defecto: {e}")
```

### 2. En el Tracker (core/tracker_improved.py)

**Modificación propuesta:**

```python
from core.adaptive_calibration import analyze_and_calibrate

class ByteTrackImproved:
    def __init__(self, video_path: str = None):
        """
        Args:
            video_path: Ruta al video para calibración automática
        """
        # Valores por defecto
        self.max_distance = 100
        self.skip_frames = 1
        
        # Calibración adaptativa
        if video_path:
            self._apply_adaptive_config(video_path)
    
    def _apply_adaptive_config(self, video_path: str):
        """Ajusta configuración basada en calidad del video"""
        try:
            metrics, config = analyze_and_calibrate(video_path)
            self.max_distance = config.tracker_max_distance
            self.skip_frames = config.skip_frames
            print(f"✓ Tracker calibrado: max_distance={self.max_distance}, skip={self.skip_frames}")
        except Exception as e:
            print(f"⚠ Tracker calibration failed: {e}")
```

### 3. En el Pipeline Principal (2_analizar.py o similar)

**Modificación propuesta:**

```python
from core.adaptive_calibration import analyze_and_calibrate
from core.detector import PlayerDetector, BallDetector
from core.tracker_improved import ByteTrackImproved

def process_video_with_calibration(video_path: str, output_dir: str = "resultados"):
    """Procesa video con calibración adaptativa automática"""
    
    print("=" * 70)
    print("FASE 1: ANÁLISIS Y CALIBRACIÓN")
    print("=" * 70)
    
    # Paso 1: Análisis y calibración
    metrics, config = analyze_and_calibrate(video_path)
    
    print("\n" + "=" * 70)
    print("FASE 2: INICIALIZACIÓN DE MÓDULOS CON PARÁMETROS CALIBRADOS")
    print("=" * 70)
    
    # Paso 2: Inicializar módulos con parámetros calibrados
    player_detector = PlayerDetector(
        model_path="models/player_detection.pt",
        confidence_threshold=config.confidence_threshold
    )
    
    ball_detector = BallDetector(
        model_path="models/ball_detection.pt",
        min_confidence=config.confidence_threshold
    )
    
    tracker = ByteTrackImproved(
        max_distance=config.tracker_max_distance,
        skip_frames=config.skip_frames
    )
    
    print("\n" + "=" * 70)
    print("FASE 3: PROCESAMIENTO DE VIDEO")
    print("=" * 70)
    
    # Paso 3: Procesar video
    # ... código existente de procesamiento ...
    
    print("\n" + "=" * 70)
    print("REPORTE DE CALIBRACIÓN Y PROCESAMIENTO")
    print("=" * 70)
    print(config.quality_report)
    
    return results
```

---

## Ejemplos de Integración por Componente

### Ejemplo 1: Integración con Detector Existente

```python
# Antes (sin calibración)
detector = BallDetector(model_path="models/ball.pt", device="cpu")
results = detector.detect(frame, min_confidence=0.3)

# Después (con calibración)
detector = BallDetector(
    model_path="models/ball.pt",
    video_path="data/video.mp4",  # ← Parámetro nuevo
    device="cpu"
)
# confidence_threshold se ajusta automáticamente
results = detector.detect(frame)  # Usa parámetro calibrado
```

### Ejemplo 2: Integración con Tracker

```python
# Antes (parámetros fijos)
tracker = ByteTrack()
detections = tracker.update(player_boxes, frame)

# Después (parámetros calibrados)
metrics, config = analyze_and_calibrate("video.mp4")
tracker = ByteTrack(
    max_distance=config.tracker_max_distance,
    skip_frames=config.skip_frames
)
detections = tracker.update(player_boxes, frame)
```

### Ejemplo 3: Pipeline Completo

```python
from pathlib import Path
from core.adaptive_calibration import analyze_and_calibrate
from core.detector import PlayerDetector, BallDetector
from core.tracker_improved import ByteTrackImproved
from core.intensity_analyzer import IntensityAnalyzer
from core.performance_validator import PerformanceValidator

def full_pipeline(video_path: str, output_dir: str = "resultados"):
    """Pipeline completo con calibración automática"""
    
    # 1. Calibración adaptativa
    print("🔍 Calibrando parámetros...")
    metrics, config = analyze_and_calibrate(video_path)
    
    # 2. Inicializar componentes
    print("🛠 Inicializando componentes...")
    player_detector = PlayerDetector(
        confidence_threshold=config.confidence_threshold
    )
    ball_detector = BallDetector(
        confidence_threshold=config.confidence_threshold
    )
    tracker = ByteTrackImproved(
        max_distance=config.tracker_max_distance
    )
    intensity = IntensityAnalyzer()
    validator = PerformanceValidator()
    
    # 3. Procesar video
    print("▶ Procesando video...")
    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Saltar frames si está calibrado
        if frame_idx % config.skip_frames != 0:
            frame_idx += 1
            continue
        
        # Detecciones
        players = player_detector.detect(frame)
        ball = ball_detector.detect(frame)
        
        # Tracking
        tracks = tracker.update(players)
        
        # Análisis
        intensity_data = intensity.analyze(frame, tracks)
        
        frame_idx += 1
    
    # 4. Validación
    print("✓ Validando resultados...")
    validator.validate(results)
    
    # 5. Reporte
    print("\n" + config.quality_report)
    
    cap.release()
    return results
```

---

## Configuración Recomendada por Escenario

### Fútbol en Cancha Profesional

```python
# Esperar calibración automática, típicamente:
# - confidence_threshold: 0.55-0.60 (buena confianza)
# - gk_sensitivity: 1.0 (sensibilidad normal)
# - tracker_max_distance: 100-120px
# - skip_frames: 1-2 (procesar casi todos)
```

### Futsal o Espacios Interiores

```python
# Iluminación variable esperada:
# - confidence_threshold: 0.50-0.55 (ligeramente menos exigente)
# - gk_sensitivity: 1.1 (más sensible)
# - tracker_max_distance: 110-130px
# - skip_frames: 2 (saltar algunos frames)
# - use_motion_blur: True
```

### Análisis en Condiciones Adversas

```python
# Lluvia, niebla, multitud:
# - confidence_threshold: 0.45-0.50 (mucho menos exigente)
# - gk_sensitivity: 1.2-1.3 (máxima sensibilidad)
# - tracker_max_distance: 130-150px (máximo)
# - skip_frames: 3-4 (saltar más frames)
```

---

## Testing de Integración

### Script de Validación

```python
# test_integration.py
from pathlib import Path
from core.adaptive_calibration import analyze_and_calibrate
from core.detector import PlayerDetector

def test_detector_with_calibration():
    """Valida que el detector usa parámetros calibrados"""
    
    # Calibrar
    metrics, config = analyze_and_calibrate("data/test_video.mp4")
    
    # Inicializar con parámetros
    detector = PlayerDetector(
        confidence_threshold=config.confidence_threshold
    )
    
    # Verificar
    assert detector.min_confidence == config.confidence_threshold
    print("✓ Detector usa parámetros calibrados correctamente")

def test_quality_detection():
    """Valida que la calidad se detecta correctamente"""
    
    metrics, config = analyze_and_calibrate("data/test_video.mp4")
    
    # Verificar que todos los campos están presentes
    assert metrics.brightness is not None
    assert metrics.blur_level is not None
    assert metrics.video_quality is not None
    
    print(f"✓ Calidad detectada: {metrics.video_quality.value}")

if __name__ == "__main__":
    test_detector_with_calibration()
    test_quality_detection()
```

---

## Próximos Pasos

### Recomendado

1. **Integrar en detector.py**
   - Agregar parámetro `video_path` opcional en `__init__`
   - Llamar a calibración si se proporciona el path

2. **Integrar en tracker_improved.py**
   - Usar `tracker_max_distance` y `skip_frames` de calibración

3. **Actualizar pipeline principal**
   - Llamar a `analyze_and_calibrate` al inicio
   - Propagar parámetros a todos los componentes

### Opcional

1. **Cache de resultados**
   - Guardar métricas/config en JSON por video
   - Reutilizar en procesamientos posteriores

2. **Estadísticas por tipo de video**
   - Recolectar datos de múltiples videos
   - Ajustar thresholds del detector automáticamente

3. **UI Dashboard**
   - Mostrar métricas en tiempo real
   - Visualizar impacto de parámetros

---

## Validación de Funcionamiento

Después de integración, ejecutar:

```bash
# Pruebas básicas
python test_adaptive_calibration.py

# Pruebas de integración
python test_integration.py

# Procesar video completo
python 2_analizar.py --video data/test.mp4
```

---

## Documentación Relacionada

- **adaptive_calibration.py**: Implementación principal
- **ADAPTIVE_CALIBRATION_GUIDE.md**: Guía de uso completa
- **test_adaptive_calibration.py**: Suite de pruebas
- **core/detector.py**: Detector que usará calibración
- **core/tracker_improved.py**: Tracker que usará calibración

---

## Notas Importantes

1. **Retrocompatibilidad**: Todos los parámetros son opcionales, funciona sin calibración
2. **Performance**: Análisis tarda ~2-3 segundos (una sola vez al inicio)
3. **Offline**: No requiere conexión a internet ni servicios externos
4. **Logging**: Usa logging estándar de Python para debugging
5. **Extensible**: Diseño permite agregar nuevos análisis sin modificar código existente

---

## Soporte

Para problemas o preguntas:
1. Revisar logs detallados con `logging.DEBUG`
2. Consultar `ADAPTIVE_CALIBRATION_GUIDE.md`
3. Revisar ejemplos en `test_adaptive_calibration.py`
4. Verificar que video es válido y soportado por OpenCV

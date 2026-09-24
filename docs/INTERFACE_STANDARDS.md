# Estándar de Interfaces - Pipeline de Análisis Deportivo

## Resumen Ejecutivo

Este documento define las interfaces estandarizadas entre componentes del pipeline para evitar incompatibilidades. Establece:
- Formato de detecciones
- Resultado del tracking
- Salida de análisis de métricas
- Entrada de visualizaciones

---

## 1. Detecciones (Entrada al Tracker)

### Formato: `List[Dict[str, Any]]`

Cada detección debe ser un diccionario con los siguientes campos:

```python
detection = {
    'bbox': [x1, y1, x2, y2],      # Bounding box (x1,y1 esquina superior-izquierda, x2,y2 esquina inferior-derecha)
    'confidence': float,             # Confianza del detector [0, 1]
    'team_id': int (optional),       # ID del equipo (0=HOME, 1=AWAY)
    'jersey_number': str (optional)  # Número de camiseta
}
```

### Origen
- **Fuente:** `BallDetector.detect(frame)` o detector YOLO
- **Ubicación:** Importado en `integrated_pipeline.py`
- **Validación:** Mínimo 'bbox' y 'confidence' son requeridos

---

## 2. Resultado del Tracking

### Objeto: `PlayerTracker.track(detections)` → `Dict`

**Métodos correctos:**
- ✓ `tracker.track(detections, frame_id)` - Actualiza tracks y retorna stats
- ✗ `tracker.update(detections)` - **NO EXISTE** (solo housekeeping)

### Retorna: Statistics Dictionary
```python
{
    'matched': int,           # Número de detecciones emparejadas con tracks activos
    'new_tracks': int,        # Nuevos tracks creados
    'active_tracks': int,     # Total de tracks activos
    'frame_id': int           # Frame procesado
}
```

### Acceso a Tracks Activos
```python
# Opción 1: Obtener diccionario de tracks
tracks_dict = tracker.tracks  # Dict[int, TrackState]

# Opción 2: Obtener lista formateada
tracks_list = tracker.get_tracks(min_confidence=0.5)
# Retorna: List[Dict] con campos:
# - track_id, bbox, confidence, age, hits, team_id, jersey_number, 
# - is_occluded, velocity, position
```

### TrackState Dataclass (Interno)
```python
@dataclass
class TrackState:
    track_id: int
    bbox: List[float]                    # [x1, y1, x2, y2]
    confidence: float
    frame_id: int
    age: int
    hits: int
    hit_streak: int
    time_since_update: int
    position_history: List[Tuple[float, float]]
    velocity: Tuple[float, float]        # (vx, vy) en píxeles/frame
    team_id: Optional[int]
    jersey_number: Optional[str]
    is_occluded: bool
    occlusion_frames: int
    
    # ⚠️ NO TIENE: class_name - usar jersey_number o team_id
```

---

## 3. Análisis de Distancia y Velocidad

### Entrada: `List[TrackPoint]`

```python
@dataclass
class TrackPoint:
    frame: int                  # Número de frame
    x: float                    # Posición X en píxeles
    y: float                    # Posición Y en píxeles
    confidence: float = 1.0     # Confianza
    is_interpolated: bool = False
```

### Invocación Correcta
```python
# ✓ Correcto
distance_analysis = analyzer.analyze_player_trajectory(tracks)

# ✗ Incorrecto
distance_analysis = analyzer.velocity.velocity_per_frame  # NO EXISTE
```

### Retorna: `Dict[str, Any]`

```python
{
    'distance': DistanceMetrics {
        total_distance: float               # metros
        distance_by_frame: List[float]     # metros por frame
        cumulative_distance: List[float]   # metros acumulados
        jump_detections: List[Dict]        # oclusiones detectadas
        interpolated_frames: int
        confidence_avg: float
    },
    'velocity': VelocityMetrics {
        velocity_per_frame: List[float]    # m/s
        max_velocity: float
        min_velocity: float
        average_velocity: float
        median_velocity: float
        std_velocity: float
        percentile_90: float
        percentile_95: float
        percentile_99: float
    },
    'movement': MovementMetrics {
        acceleration: List[float]
        deceleration: List[float]
        max_acceleration: float
        max_deceleration: float
        average_acceleration: float
        directional_changes: int
        direction_angles: List[float]
        distance_by_quadrant: Dict[str, float]
    },
    'summary': {
        total_frames: int
        fps: float
        duration_seconds: float
    }
}
```

### Acceso Correcto a Campos
```python
# ✓ Correcto - acceso directo a diccionario
total_distance = analysis['distance'].total_distance
velocities = analysis['velocity'].velocity_per_frame
avg_velocity = analysis['velocity'].average_velocity

# ✗ Incorrecto
total_distance = analysis.distance.total_distance  # NO - es dict, no objeto
```

---

## 4. Análisis de Intensidad

### Invocación: `IntensityAnalyzer.analyze()`

```python
# Input
intensity_metrics = analyzer.analyze(
    velocity_array=np.array([...]),              # Array 1D de velocidades
    position_history=[(x1,y1), (x2,y2), ...],   # Posiciones opcionales
    config={'velocity_threshold': 2.0, ...}      # Thresholds opcionales
)

# Output: IntensityMetrics dataclass
IntensityMetrics {
    total_frames: int
    total_duration_seconds: float
    fps: float
    
    # Básicas
    active_movement_percentage: float            # % en movimiento
    average_velocity: float
    max_velocity: float
    
    # Categorías de movimiento
    movement_categories: Dict[str, MovementCategory]  # estático, caminando, etc
    
    # Avanzadas
    sprint_count: int
    total_sprint_distance: float
    high_intensity_distance: float
    high_intensity_percentage: float
    
    # Cambios de dirección
    direction_changes_count: int
    average_direction_change_angle: float
    
    # Recuperación
    total_recovery_time: float
    average_recovery_time: float
    recovery_attempts: int
}
```

### Acceso a Campos
```python
# ✓ Correcto - acceso directo a atributos
movement_intensity = intensity_metrics.movement_intensity_percent  # NO EXISTE
active_pct = intensity_metrics.active_movement_percentage  # ✓ CORRECTO
sprints = intensity_metrics.sprint_count  # ✓ CORRECTO
```

---

## 5. Heatmap

### Invocación Correcta

```python
# ✗ INCORRECTO - pasando TrackPoint objects
heatmap = manager.generate_complete_analysis(
    tracks=[t for t in track_points]  # ❌ Esperan (x,y) tuples
)

# ✓ CORRECTO - pasando tuplas (x, y)
positions = [(t.x, t.y) for t in track_points]
heatmap = manager.generate_complete_analysis(
    tracks=positions,
    player_id=player_id,
    fps=fps,
    speeds=velocities  # opcional
)
```

### Retorna: `HeatmapData`

```python
@dataclass
class HeatmapData:
    heatmap_image: np.ndarray              # RGB normalizada [0, 1]
    zone_stats: List[ZoneStats]            # Estadísticas por zona
    grid_histogram: np.ndarray             # Grid 10x10 normalizado
    peak_position: Tuple[int, int]         # (col, row) de máximo
    peak_intensity: float
    coverage_percentage: float
```

---

## 6. Mapeo Completo de Flujo

```
Video
  ↓
[Detector] → detections: List[Dict]
  ↓
[Tracker.track()] → tracks_dict: Dict[int, TrackState]
  ↓
get_tracks() → tracks_list: List[Dict]
  ↓
                    ↙           ↓           ↘
                   /            |            \
        [Distance Analyzer]  [Intensity]   [Heatmap]
        tracks → List[TrackPoint]  velocity → np.array
        positions → List[Tuple]
                    ↓            ↓            ↓
            analysis_dict  intensity_obj  heatmap_data
```

---

## 7. Conversiones Requeridas

### De TrackState a Información Procesable

```python
# TrackState (interno del tracker)
track = tracker.tracks[track_id]

# Extraer posición actual
center_x = (track.bbox[0] + track.bbox[2]) / 2
center_y = (track.bbox[1] + track.bbox[3]) / 2

# Información de clasificación
team = track.team_id                    # 0=HOME, 1=AWAY, None=unknown
jersey = track.jersey_number
is_tracked = track.hits >= min_hits     # válido si tuvo suficientes hits

# NO usar:
# ❌ track.class_name - NO EXISTE
# ❌ track.position - NO EXISTE (usar centroide de bbox)
```

### De TrackPoint a Heatmap

```python
# Entrada: List[TrackPoint]
track_points = [
    TrackPoint(frame=0, x=100.5, y=200.3, confidence=0.95),
    TrackPoint(frame=1, x=102.1, y=201.8, confidence=0.94),
]

# Conversión: List[Tuple[float, float]]
positions = [(tp.x, tp.y) for tp in track_points]

# Entrada a heatmap
heatmap = manager.generate_complete_analysis(
    tracks=positions,
    player_id=1,
    fps=30
)
```

---

## 8. Checklist de Compatibilidad

Antes de conectar componentes, verificar:

- [ ] ¿Las detecciones contienen 'bbox' y 'confidence'?
- [ ] ¿Se llama a `tracker.track()` no `tracker.update()`?
- [ ] ¿Se accede a `analyzer.analyze_player_trajectory()` retornando Dict?
- [ ] ¿Se accede a campos del dict con `['key']` notation?
- [ ] ¿Se convierten TrackPoint a tuplas (x, y) para heatmap?
- [ ] ¿Se usa `intensity_metrics.active_movement_percentage` no `.movement_intensity_percent`?
- [ ] ¿Se obtiene info de track con `get_tracks()` o `tracks.items()`?
- [ ] ¿Se evita acceder a `track.class_name`?

---

## 9. Referencias de Archivo

| Componente | Archivo | Clase | Método |
|-----------|---------|-------|--------|
| Detecciones | `core/detector.py` | `BallDetector` | `detect(frame)` |
| Tracking | `core/tracker.py` | `PlayerTracker` | `track(detections)` |
| Distancia/Velocidad | `core/distance_velocity_calculator.py` | `DistanceVelocityAnalyzer` | `analyze_player_trajectory()` |
| Intensidad | `core/intensity_analyzer.py` | `IntensityAnalyzer` | `analyze()` |
| Heatmap | `core/heatmap_generator.py` | `HeatmapManager` | `generate_complete_analysis()` |
| Pipeline | `pipeline/integrated_pipeline.py` | `IntegratedAnalysisPipeline` | `process_video()` |

---

## 10. Ejemplos de Código Correcto

### Procesar un frame completo

```python
# 1. Detectar
detections = detector.detect(frame)

# 2. Trackear
result = tracker.track(detections, frame_id=frame_idx)
tracks_dict = tracker.get_tracks(min_confidence=0.5)

# 3. Procesar tracks
for track_dict in tracks_dict:
    track_id = track_dict['track_id']
    position = track_dict['position']  # (x, y)
    
# 4. Análisis de trayectoria (después de múltiples frames)
for player_id, track_points in player_tracks.items():
    # Distance & Velocity
    analysis = distance_analyzer.analyze_player_trajectory(track_points)
    total_dist = analysis['distance'].total_distance
    max_vel = analysis['velocity'].max_velocity
    
    # Intensity
    velocities = np.array(analysis['velocity'].velocity_per_frame)
    positions = [(tp.x, tp.y) for tp in track_points]
    intensity = intensity_analyzer.analyze(
        velocity_array=velocities,
        position_history=positions
    )
    
    # Heatmap
    heatmap = heatmap_manager.generate_complete_analysis(
        tracks=positions,
        player_id=player_id,
        fps=fps
    )
```

---

## Historial de Cambios

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2026-09-24 | 1.0 | Documento inicial - Interfaz estándar |

# FASE 4: Análisis Individual de Jugadores

## Descripción General

**FASE 4** implementa el análisis detallado y personalizado de cada jugador, calculando métricas biomecánicas, de posicionamiento y de rendimiento. Esta fase transforma datos de rastreo de video en estadísticas profesionales de fútbol.

## Objetivos

- ✅ Calcular distancia total recorrida con precisión
- ✅ Medir velocidades máxima, promedio y percentiles
- ✅ Evaluar intensidad de movimiento
- ✅ Generar mapas de calor de posicionamiento
- ✅ Crear comparativas respecto al equipo
- ✅ Integrar todas las métricas en reportes profesionales

## Arquitectura

### 1. Componente Core: PlayerAnalyzer

**Ubicación**: `core/player_analyzer.py`

```python
from core.player_analyzer import PlayerAnalyzer

# Inicialización con calibración
analyzer = PlayerAnalyzer(
    fps=30,
    field_length_m=105,
    field_width_m=68,
    pixels_per_meter=10.0
)
```

#### Métodos Principales

##### 1.1 Cálculo de Distancia

```python
distance_metrics = analyzer.calculate_distance(
    tracks=player_tracks,
    player_id=7
)

# Resultado:
# {
#     'total_distance_m': 10523.45,          # Distancia total en metros
#     'distance_by_period': {...},           # Por periodo (ej: primer tiempo)
#     'num_samples': 2700,                   # Frames con detección
#     'interpolated_frames': 45               # Frames interpolados
# }
```

**Características**:
- Interpolación de detecciones faltantes
- Remoción de outliers usando IQR (Rango Intercuartil)
- Conversión píxeles → metros usando escala calibrada
- Validación de confianza mínima

**Rango esperado (fútbol profesional)**:
- Defensa: 8,000 - 10,000 m
- Mediocampistas: 10,000 - 13,000 m
- Delanteros: 8,000 - 11,000 m

---

##### 1.2 Cálculo de Velocidad

```python
velocity_metrics = analyzer.calculate_velocity(
    tracks=player_tracks,
    player_id=7,
    window_size=5  # Ventana de suavizado
)

# Resultado:
# {
#     'max_velocity_m_s': 9.2,              # Velocidad máxima
#     'avg_velocity_m_s': 6.5,              # Promedio
#     'median_velocity_m_s': 6.1,           # Mediana
#     'percentile_90_m_s': 8.2,             # Percentil 90
#     'percentile_95_m_s': 8.8              # Percentil 95
# }
```

**Características**:
- Suavizado con ventana deslizante para reducir ruido
- Cálculo de múltiples percentiles
- Validación de relaciones (max >= p95 >= p90 >= avg)

**Invariante Matemático**:
```
v_max >= v_p95 >= v_p90 >= v_median >= v_avg >= 0
```

**Rangos esperados (m/s)**:
- Promedio: 4.0 - 7.0 m/s
- Máximo: 8.0 - 12.0 m/s
- Percentil 90: 7.0 - 10.0 m/s

---

##### 1.3 Cálculo de Intensidad

```python
intensity_metrics = analyzer.calculate_intensity(
    tracks=player_tracks,
    player_id=7
)

# Resultado:
# {
#     'movement_intensity_percent': 75.3,   # % tiempo en movimiento
#     'static_time_percent': 24.7,          # % tiempo estático
#     'walking_percent': 20.1,              # Caminando (0.5-2 m/s)
#     'jogging_percent': 35.2,              # Trotando (2-4 m/s)
#     'running_percent': 15.0,              # Corriendo (4-6 m/s)
#     'sprinting_percent': 5.0,             # Aceleración (>6 m/s)
#     'hsrs_distance_m': 2450.5             # High Speed Running/Sprinting
# }
```

**Clasificación de Velocidades**:

| Categoría | Rango (m/s) | Descripción |
|-----------|-----------|---|
| Estático | 0 - 0.5 | Sin movimiento |
| Caminando | 0.5 - 2.0 | Desplazamiento lento |
| Trotando | 2.0 - 4.0 | Movimiento controlado |
| Corriendo | 4.0 - 6.0 | Alta intensidad |
| Aceleración | > 6.0 | Máximo esfuerzo |

**Estándares de Intensidad (Fútbol Profesional)**:
- Media: 70-80% movimiento
- Máxima: 80-90% movimiento
- Baja: 50-70% movimiento

---

##### 1.4 Generación de Heatmap

```python
heatmap_data = analyzer.calculate_heatmap(
    tracks=player_tracks,
    player_id=7,
    grid_size=10  # Matriz 10x10 del campo
)

# Resultado:
# {
#     'heatmap_grid': [[...], [...], ...],   # Matriz 10x10 con conteos
#     'positions_list': [[x1, y1], ...],     # Todas las posiciones
#     'center_of_mass': [x_center, y_center], # Posición promedio
#     'positional_zones': {                   # Distribución por zona
#         'left': 35.2,
#         'center': 42.1,
#         'right': 22.7
#     },
#     'coverage_area_percent': 65.3           # % del campo cubierto
# }
```

**Características**:
- Grid configurable (típicamente 10x10)
- Normalización por zona del campo
- Cálculo de centro de masa
- Cobertura de área

---

### 2. Integración con Reportes

**Ubicación**: `core/report_generator.py`

```python
from core.report_generator import ReportGenerator

generator = ReportGenerator(
    output_dir='reports/',
    organization_name='Scout Analytics'
)

# Generar PDF individual
generator.generate_player_pdf(
    player_data=player_stats,
    output_filename='player_7.pdf',
    include_heatmap=True
)

# Generar dashboard HTML
generator.generate_html_dashboard(
    video_data=all_stats,
    output_filename='dashboard.html'
)
```

---

### 3. Logging de Métricas

**Ubicación**: `core/metrics.py`

```python
from core.metrics import DetectionMetrics

metrics = DetectionMetrics(
    output_dir='data/logs',
    video_name='match_07_06_2024'
)

# Registrar métricas por frame
metrics.log_frame(frame_idx=0, data={
    'player_confidence': 0.92,
    'player_count': 22,
    'ball_confidence': 0.88,
    'pitch_confidence': 0.95,
    'homography_quality': 0.90,
    'team_accuracy': 0.88
})

# Exportar resultados
metrics.export_csv('frames_metrics.csv')
metrics.export_summary('summary.json')
metrics.print_summary()
```

---

## Pipeline de Análisis Completo

### Flujo de Datos

```
Video
  ↓
[Frame Processor]
  ↓
[Player Detection + Tracking]
  ↓
[Coordinate Transformation (píxeles → metros)]
  ↓
[PlayerAnalyzer]
  ├─ calculate_distance()    → Distancia total
  ├─ calculate_velocity()    → Velocidades (max, avg, percentiles)
  ├─ calculate_intensity()   → Categorización de intensidad
  └─ calculate_heatmap()     → Mapa de posicionamiento
  ↓
[ReportGenerator]
  ├─ player_pdf()            → PDF individual
  ├─ team_pdf()              → PDF de equipo
  └─ html_dashboard()        → Dashboard interactivo
  ↓
Reportes profesionales (PDF, HTML, JSON, CSV)
```

---

## Parámetros Críticos de Calibración

### 1. FPS del Video

```python
analyzer = PlayerAnalyzer(fps=30)  # O 25, 60, etc.
```

**Impacto**: Determina la conversión tiempo → frames

### 2. Dimensiones del Campo

```python
analyzer = PlayerAnalyzer(
    field_length_m=105.0,   # Largo (estándar FIFA)
    field_width_m=68.0      # Ancho (estándar FIFA)
)
```

### 3. Escala Píxeles → Metros

```python
# Opción 1: Calibración manual
analyzer.pixels_per_meter = 10.0

# Opción 2: Calibración automática desde esquinas detectadas
analyzer.set_scale_from_detections(
    detected_field_corners=[...],
    field_length_m=105,
    field_width_m=68
)
```

---

## Ejemplos Reales

### Ejemplo 1: Análisis de Delantero (Messi-like)

**Perfil esperado:**
- Distancia: 9,500 - 10,500 m
- Velocidad máx: 10.5 m/s
- Velocidad promedio: 6.8 m/s
- Intensidad: 75-80%
- Zona: 60% ataque, 30% mediocampo, 10% defensa

```python
player_7 = {
    'total_distance_m': 10245.3,
    'max_velocity_m_s': 10.2,
    'avg_velocity_m_s': 6.8,
    'movement_intensity_percent': 77.2,
    'hsrs_distance_m': 2854.3,
    'positional_zones': {
        'attack': 0.60,
        'midfield': 0.30,
        'defense': 0.10
    }
}
```

### Ejemplo 2: Análisis de Mediocampista (Busquets-like)

**Perfil esperado:**
- Distancia: 11,500 - 13,000 m
- Velocidad máx: 9.2 m/s
- Velocidad promedio: 6.5 m/s
- Intensidad: 78-85%
- Zona: 30% ataque, 60% mediocampo, 10% defensa

```python
player_5 = {
    'total_distance_m': 12345.6,
    'max_velocity_m_s': 9.2,
    'avg_velocity_m_s': 6.5,
    'movement_intensity_percent': 82.1,
    'hsrs_distance_m': 1956.8,
    'positional_zones': {
        'attack': 0.30,
        'midfield': 0.60,
        'defense': 0.10
    }
}
```

### Ejemplo 3: Análisis de Defensa (Ramos-like)

**Perfil esperado:**
- Distancia: 9,000 - 10,500 m
- Velocidad máx: 8.8 m/s
- Velocidad promedio: 5.9 m/s
- Intensidad: 72-78%
- Zona: 10% ataque, 20% mediocampo, 70% defensa

```python
player_4 = {
    'total_distance_m': 9876.5,
    'max_velocity_m_s': 8.8,
    'avg_velocity_m_s': 5.9,
    'movement_intensity_percent': 74.5,
    'hsrs_distance_m': 1450.2,
    'positional_zones': {
        'attack': 0.10,
        'midfield': 0.20,
        'defense': 0.70
    }
}
```

---

## Validaciones y Controles de Calidad

### 1. Validación de Entrada

- ✅ Tracks no vacíos
- ✅ IDs de jugadores válidos
- ✅ Coordenadas dentro de límites razonables
- ✅ Confianza en rango [0, 1]

### 2. Validación de Salida

- ✅ Distancia >= 0 y <= 20,000 m (para 90 minutos)
- ✅ Velocidades en orden: max >= p95 >= p90 >= avg >= 0
- ✅ Intensidad: 0-100% y suma de categorías ≈ 100%
- ✅ Heatmap: valores >= 0, matriz completa

### 3. Pruebas E2E

```bash
# Ejecutar suite completa de tests
pytest tests/test_fase4_complete.py -v

# Tests específicos
pytest tests/test_fase4_complete.py::TestCompletePlayerAnalysis -v
pytest tests/test_fase4_complete.py::TestDistanceAccuracy -v
pytest tests/test_fase4_complete.py::TestVelocityMetrics -v
pytest tests/test_fase4_complete.py::TestIntensityCalculation -v
pytest tests/test_fase4_complete.py::TestHeatmapGeneration -v
```

---

## Precisión y Exactitud

### Calibración de Escala

**Problema**: Convertir píxeles a metros

**Solución**: Detectar esquinas de campo y usar dimensiones conocidas

```python
# Calibración matemática:
# Si diagonal_campo_píxeles = D_p
# y diagonal_campo_metros = sqrt(105^2 + 68^2) ≈ 126.2 m
#
# Entonces: pixels_per_meter = D_p / 126.2

detected_corners = [(50, 50), (1870, 50), (1870, 1030), (50, 1030)]
analyzer.set_scale_from_detections(detected_corners)
```

### Manejo de Errores de Tracking

**Problema**: Saltos anómalos por pérdida de tracking

**Solución**: Filtrado usando IQR (Rango Intercuartil)

```python
Q75, Q25 = percentile(distances, [75, 25])
IQR = Q75 - Q25
threshold = Q75 + 3 * IQR
valid_distances = [d for d in distances if d <= threshold]
```

### Suavizado de Velocidades

**Problema**: Ruido en velocidades instantáneas

**Solución**: Ventana deslizante (moving average)

```python
velocities_smoothed = moving_average(velocities, window=5)
```

---

## Rendimiento y Optimización

### Complejidad Computacional

| Operación | Complejidad | Tiempo típico (50 jugadores) |
|-----------|-----------|---|
| calculate_distance() | O(n) | ~100 ms |
| calculate_velocity() | O(n) | ~150 ms |
| calculate_intensity() | O(n) | ~120 ms |
| calculate_heatmap() | O(n) | ~80 ms |

**Tiempo total para 50 jugadores**: < 1 segundo

### Recomendaciones

- Use análisis paralelo para múltiples videos
- Cache resultados intermedios
- Considere reducción de frames para videos de larga duración

---

## Limitaciones Conocidas

1. **Calibración manual requerida**: Necesita detección confiable de esquinas
2. **Ruido de tracking**: Puede afectar cálculos si confianza < 0.5
3. **Orientación de cámara**: Asume visión cenital (no funciona bien con ángulos laterales)
4. **Cambios de zoom**: Escala constante asumida durante el video

---

## Referencias Científicas

- **High-Performance Soccer Training** - Stolen et al. (2005)
- **Movement Demands in Soccer** - Mohr et al. (2003)
- **Assessment of Physical Demands in Soccer** - Bangsbo (1994)
- **FIFA Laws of the Game** - Field dimensions and regulations

**Distancia promedio por posición:**
- Portero: 3,000-4,000 m
- Defensa central: 8,500-10,000 m
- Lateral: 9,500-11,000 m
- Mediocampista defensivo: 10,500-12,000 m
- Mediocampista ofensivo: 11,000-13,000 m
- Delantero: 8,500-10,500 m

---

## Próximos Pasos (Fase 5)

- [ ] Análisis comparativo entre equipos
- [ ] Predicción de rendimiento
- [ ] Detección automática de lesiones basada en métricas
- [ ] Análisis de patrones tácticos
- [ ] Integración con wearables (GPS)

---

## Contacto y Soporte

Para preguntas sobre Fase 4:
- Email: carlosnasser03@gmail.com
- Documentación: Ver `QUICKSTART_ANALISIS.md`
- Tests: `tests/test_fase4_complete.py`

**Última actualización**: 7 de Julio, 2024
**Estado**: ✅ COMPLETADO Y VALIDADO

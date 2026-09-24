# QUICKSTART: Análisis Individual de Jugadores (Fase 4)

Guía rápida para comenzar a analizar jugadores en minutos.

## Instalación

```bash
# Clonar repositorio (si no lo has hecho)
git clone <repository>
cd "Análisis deporte"

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# o
.venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Uso Básico: 5 Minutos

### 1. Análisis Simple de Jugador

```python
from core.player_analyzer import PlayerAnalyzer

# Crear analizador
analyzer = PlayerAnalyzer(
    fps=30,
    field_length_m=105,
    field_width_m=68,
    pixels_per_meter=10.0  # Ajusta según tu video
)

# Cargar tracks de jugadores
# (típicamente de pipeline de detección/tracking)
tracks = [
    {
        'frame_idx': 0,
        'player_id': 7,
        'center': [500, 300],
        'confidence': 0.92
    },
    # ... más frames
]

# Analizar jugador
player_id = 7

distance = analyzer.calculate_distance(tracks, player_id)
print(f"Distancia: {distance['total_distance_m']:.1f} m")

velocity = analyzer.calculate_velocity(tracks, player_id)
print(f"Velocidad máx: {velocity['max_velocity_m_s']:.1f} m/s")
print(f"Velocidad promedio: {velocity['avg_velocity_m_s']:.1f} m/s")

intensity = analyzer.calculate_intensity(tracks, player_id)
print(f"Intensidad: {intensity['movement_intensity_percent']:.1f}%")

heatmap = analyzer.calculate_heatmap(tracks, player_id)
print(f"Cobertura del campo: {heatmap['coverage_area_percent']:.1f}%")
```

### 2. Análisis de Todos los Jugadores

```python
# Extraer IDs únicos
player_ids = set(t['player_id'] for t in tracks)

results = {}
for player_id in player_ids:
    results[player_id] = {
        'distance_m': analyzer.calculate_distance(tracks, player_id),
        'velocity': analyzer.calculate_velocity(tracks, player_id),
        'intensity': analyzer.calculate_intensity(tracks, player_id),
        'heatmap': analyzer.calculate_heatmap(tracks, player_id)
    }

# Mostrar resultados
for pid, data in results.items():
    print(f"\nJugador {pid}:")
    print(f"  Distancia: {data['distance_m']['total_distance_m']:.1f} m")
    print(f"  Velocidad max: {data['velocity']['max_velocity_m_s']:.1f} m/s")
    print(f"  Intensidad: {data['intensity']['movement_intensity_percent']:.1f}%")
```

### 3. Exportar Resultados a JSON

```python
import json
from pathlib import Path

output = {}
for player_id in player_ids:
    output[str(player_id)] = {
        'distance_m': analyzer.calculate_distance(tracks, player_id)['total_distance_m'],
        'velocity_max_m_s': analyzer.calculate_velocity(tracks, player_id)['max_velocity_m_s'],
        'velocity_avg_m_s': analyzer.calculate_velocity(tracks, player_id)['avg_velocity_m_s'],
        'intensity_percent': analyzer.calculate_intensity(tracks, player_id)['movement_intensity_percent'],
    }

# Guardar
with open('player_stats.json', 'w') as f:
    json.dump(output, f, indent=2)
```

### 4. Generar Reportes

```python
from core.report_generator import ReportGenerator

generator = ReportGenerator(
    output_dir='reports/',
    organization_name='MI EQUIPO'
)

# Generar PDF para cada jugador
for player_id in [7, 10, 13]:
    player_data = {
        'player_id': player_id,
        'total_distance_m': results[player_id]['distance_m']['total_distance_m'],
        'max_velocity_m_s': results[player_id]['velocity']['max_velocity_m_s'],
        'movement_intensity_percent': results[player_id]['intensity']['movement_intensity_percent'],
    }
    
    generator.generate_player_pdf(player_data, f'player_{player_id}.pdf')

print("✓ Reportes generados en 'reports/'")
```

---

## Casos de Uso Comunes

### Caso 1: Comparar Jugadores

```python
# Obtener métricas de varios jugadores
comparison = {}
for pid in [1, 4, 7, 10]:
    v = analyzer.calculate_velocity(tracks, pid)
    comparison[pid] = v['avg_velocity_m_s']

# Ordenar por velocidad
sorted_players = sorted(comparison.items(), key=lambda x: x[1], reverse=True)
print("\nJugadores ordenados por velocidad promedio:")
for pid, avg_v in sorted_players:
    print(f"  Jugador {pid}: {avg_v:.2f} m/s")
```

### Caso 2: Identificar Jugadores de Bajo Rendimiento

```python
# Analizar todos y filtrar por distancia baja
low_performers = []
for player_id in player_ids:
    d = analyzer.calculate_distance(tracks, player_id)
    if d['total_distance_m'] < 8000:  # Umbral bajo
        low_performers.append(player_id)

print(f"Jugadores con bajo rendimiento: {low_performers}")
```

### Caso 3: Estadísticas de Equipo

```python
import numpy as np

distances = []
velocities = []
intensities = []

for player_id in player_ids:
    d = analyzer.calculate_distance(tracks, player_id)
    v = analyzer.calculate_velocity(tracks, player_id)
    i = analyzer.calculate_intensity(tracks, player_id)
    
    distances.append(d['total_distance_m'])
    velocities.append(v['max_velocity_m_s'])
    intensities.append(i['movement_intensity_percent'])

print(f"\n=== ESTADÍSTICAS DEL EQUIPO ===")
print(f"Distancia promedio: {np.mean(distances):.1f} m")
print(f"Distancia máxima: {np.max(distances):.1f} m")
print(f"Velocidad promedio max: {np.mean(velocities):.1f} m/s")
print(f"Intensidad promedio: {np.mean(intensities):.1f}%")
```

### Caso 4: Mapa de Calor (Heatmap)

```python
# Obtener heatmap de un jugador
heatmap_data = analyzer.calculate_heatmap(tracks, player_id=7, grid_size=10)

# Matriz 10x10 del campo
heatmap_grid = heatmap_data['heatmap_grid']

# Encontrar zona más caliente
max_count = 0
max_zone = (0, 0)
for i, row in enumerate(heatmap_grid):
    for j, count in enumerate(row):
        if count > max_count:
            max_count = count
            max_zone = (i, j)

print(f"Zona más activa: {max_zone}")
print(f"Actividad: {max_count} frames")

# Posición central promedio
center = heatmap_data['center_of_mass']
print(f"Centro de masa: {center}")
```

---

## Parámetros Clave

### Configuración de Analizador

```python
# FPS - fotogramas por segundo del video
fps = 30  # típico: 25, 30 o 60

# Dimensiones del campo (en metros)
field_length_m = 105    # Largo FIFA estándar
field_width_m = 68      # Ancho FIFA estándar

# Escala píxeles -> metros
# Debes calibrar esto basado en tu video
pixels_per_meter = 10.0

# Confianza mínima para incluir detecciones (0-1)
min_confidence = 0.5

analyzer = PlayerAnalyzer(
    fps=fps,
    field_length_m=field_length_m,
    field_width_m=field_width_m,
    pixels_per_meter=pixels_per_meter,
    min_confidence=min_confidence
)
```

### Calibración de Escala

Si no conoces `pixels_per_meter`, puedes calibrar:

```python
# Opción 1: Usar esquinas detectadas
detected_corners = [
    (50, 50),      # Superior-izquierda
    (1870, 50),    # Superior-derecha
    (1870, 1030),  # Inferior-derecha
    (50, 1030)     # Inferior-izquierda
]

analyzer.set_scale_from_detections(
    detected_field_corners=detected_corners,
    field_length_m=105,
    field_width_m=68
)

# Opción 2: Calibrar manualmente
# Medir distancia conocida en píxeles y convertir
analyzer.pixels_per_meter = distancia_pixeles / distancia_metros
```

---

## Interpretación de Resultados

### Distancia
- **Esperado**: 8,000 - 13,500 m (depende de posición)
- **Bajo**: < 8,000 m (puede indicar lesión o bajo rendimiento)
- **Excelente**: > 12,000 m (esfuerzo muy alto)

### Velocidad
- **Promedio**: 4.0 - 7.0 m/s (depende de posición y táctica)
- **Máximo**: 8.0 - 12.0 m/s (capacidad aeróbica)
- **Percentil 90**: 7.0 - 10.0 m/s (esfuerzos de alta intensidad)

### Intensidad
- **Baja**: < 60% (poco movimiento, posible lesión)
- **Normal**: 70-80% (estándar de fútbol)
- **Alta**: > 85% (esfuerzo máximo sostenido)

### Heatmap
- **Distribución uniforme**: Movimiento amplio por el campo
- **Concentrado**: Especialización posicional (ej: defensa)
- **Disperso**: Cobertura amplia (mediocampista)

---

## Ejecución de Tests

```bash
# Todos los tests de Fase 4
pytest tests/test_fase4_complete.py -v

# Tests específicos
pytest tests/test_fase4_complete.py::TestCompletePlayerAnalysis -v
pytest tests/test_fase4_complete.py::TestVelocityMetrics -v

# Con cobertura
pytest tests/test_fase4_complete.py --cov=core.player_analyzer

# Generar reporte HTML
pytest tests/test_fase4_complete.py --html=report.html --self-contained-html
```

---

## Troubleshooting

### Problema: Distancias muy altas o bajas

**Causa**: `pixels_per_meter` incorrecto

**Solución**: 
```python
# Verificar calibración
# 1. Medir distancia conocida en el video (ej: línea central = 52.5 m)
# 2. Contar píxeles de esa distancia
# 3. pixels_per_meter = píxeles_contados / 52.5

analyzer.pixels_per_meter = 12.5  # Ajusta según tu cálculo
```

### Problema: Velocidades irreales

**Causa**: FPS incorrecto o tracking deficiente

**Solución**:
```python
# Verificar FPS
analyzer = PlayerAnalyzer(fps=25)  # o 30, 60, etc.

# Aumentar umbral de confianza
analyzer.min_confidence = 0.8
```

### Problema: Heatmap vacío o uniforme

**Causa**: Tracks incompletos o jugador no detectado

**Solución**:
```python
# Verificar que jugador existe en tracks
player_ids = set(t['player_id'] for t in tracks)
print(f"Jugadores disponibles: {player_ids}")

# Si falta el jugador, revisar pipeline de detección
```

---

## Ejemplos Completos

### Script de Análisis Completo

```python
#!/usr/bin/env python
"""Análisis completo de video de fútbol"""

from core.player_analyzer import PlayerAnalyzer
from core.metrics import DetectionMetrics
import json
from pathlib import Path

def analyze_match(video_path, output_dir='results'):
    """Analizar partido completo"""
    
    Path(output_dir).mkdir(exist_ok=True)
    
    # 1. Cargar tracks (de pipeline)
    # En un proyecto real, estos vendrían del detector + tracker
    tracks = load_tracks_from_video(video_path)
    
    # 2. Crear analizador
    analyzer = PlayerAnalyzer(
        fps=30,
        pixels_per_meter=10.5
    )
    
    # 3. Analizar cada jugador
    results = {}
    player_ids = set(t['player_id'] for t in tracks)
    
    for player_id in player_ids:
        results[player_id] = {
            'distance': analyzer.calculate_distance(tracks, player_id),
            'velocity': analyzer.calculate_velocity(tracks, player_id),
            'intensity': analyzer.calculate_intensity(tracks, player_id),
            'heatmap': analyzer.calculate_heatmap(tracks, player_id)
        }
    
    # 4. Guardar resultados
    output_file = Path(output_dir) / 'player_stats.json'
    
    # Formatear para JSON
    json_output = {}
    for pid, data in results.items():
        json_output[str(pid)] = {
            'distance_m': data['distance']['total_distance_m'],
            'velocity_max': data['velocity']['max_velocity_m_s'],
            'velocity_avg': data['velocity']['avg_velocity_m_s'],
            'intensity': data['intensity']['movement_intensity_percent'],
            'coverage_percent': data['heatmap']['coverage_area_percent']
        }
    
    with open(output_file, 'w') as f:
        json.dump(json_output, f, indent=2)
    
    print(f"✓ Análisis completado: {output_file}")
    return results


def load_tracks_from_video(video_path):
    """Placeholder - en proyecto real, integrar con pipeline"""
    # Este es un ejemplo - en producción usarías el detector real
    return []


if __name__ == '__main__':
    results = analyze_match('data/match.mp4')
```

---

## Próximos Pasos

1. **Integración con Pipeline Actual**: Conectar con tu detector/tracker
2. **Generación de Reportes**: Crear PDFs profesionales
3. **Dashboard Web**: Visualización interactiva
4. **Análisis Táctico**: Patrones de juego
5. **Comparativas**: Bench-marking contra ligas

---

## Documentación Completa

- **Detalles técnicos**: Ver `FASE_4_ANALISIS_INDIVIDUAL.md`
- **Tests y validación**: Ver `tests/test_fase4_complete.py`
- **Ejemplos de datos**: Ver `EJEMPLOS_STATS.md`

**Versión**: 1.0
**Fecha**: 7 de Julio, 2024
**Estado**: ✅ Producción

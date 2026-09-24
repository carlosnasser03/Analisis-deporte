# Quick Start: Player Stats Aggregator

## Instalación

No requiere dependencias adicionales. Solo asegúrate de tener numpy:

```bash
pip install numpy
```

## Importación

```python
from core.player_stats_aggregator import (
    PlayerStatsAggregator,
    StatsExporter,
    IntensityCategory,
    MovementProfile,
)
```

## Uso Básico (5 minutos)

### 1. Crear Agregador

```python
# Para equipo local
aggregator = PlayerStatsAggregator(team_id="HomeTeam")

# Para equipo visitante
aggregator = PlayerStatsAggregator(team_id="AwayTeam")
```

### 2. Agregar Estadísticas de Jugador

```python
# Datos provenientes de análisis anteriores (player_analyzer.py, etc.)
distance_metrics = {
    'total_distance_m': 10500.0,
    'distance_by_period': {'first_half': 5250.0, 'second_half': 5250.0},
    'num_samples': 1800,
    'interpolated_frames': 10
}

velocity_metrics = {
    'max_velocity_m_s': 9.5,
    'avg_velocity_m_s': 4.2,
    'median_velocity_m_s': 3.8,
    'percentile_90_m_s': 8.5,
    'percentile_95_m_s': 9.0,
    'std_velocity_m_s': 2.1,
}

intensity_metrics = {
    'movement_intensity_percent': 75.0,
    'static_time_percent': 25.0,
    'walking_percent': 15.0,
    'jogging_percent': 30.0,
    'running_percent': 20.0,
    'sprinting_percent': 10.0,
    'hsrs_distance_m': 2100.0,  # High-speed running/sprinting
    'sprints_count': 12,
    'directional_changes': 45,
}

# Agregar jugador
stats = aggregator.aggregate_player_stats(
    player_id=7,
    player_number=7,
    player_name="Cristiano",
    position="FWD",
    distance_metrics=distance_metrics,
    velocity_metrics=velocity_metrics,
    intensity_metrics=intensity_metrics,
)
```

### 3. Agregar Múltiples Jugadores

```python
for player_id in range(1, 12):
    stats = aggregator.aggregate_player_stats(
        player_id=player_id,
        player_number=player_id,
        player_name=f"Player_{player_id}",
        position=['GK', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'FWD', 'FWD', 'FWD'][player_id - 1],
        distance_metrics=distance_metrics,
        velocity_metrics=velocity_metrics,
        intensity_metrics=intensity_metrics,
    )
```

### 4. Calcular Percentiles vs Equipo

```python
# Esto calcula automáticamente percentiles para cada jugador
aggregator.calculate_team_percentiles()
```

### 5. Ver Resumen del Equipo

```python
team_summary = aggregator.get_team_summary()

print(f"Equipo: {team_summary['team_id']}")
print(f"Jugadores: {team_summary['players_count']}")
print(f"Distancia promedio: {team_summary['distance_avg_km']:.2f} km")
print(f"Velocidad promedio: {team_summary['velocity_avg_m_s']:.2f} m/s")
print(f"Intensidad promedio: {team_summary['intensity_avg_pct']:.1f}%")
print(f"Sprints totales: {team_summary['sprints_total']}")
```

### 6. Obtener Estadísticas de Jugador Individual

```python
# Por ID
player_stats = aggregator.get_player_stats(7)
print(f"{player_stats.player_name}: {player_stats.distance_total_km:.2f} km")
print(f"Perfil: {player_stats.movement_profile}")
print(f"Percentil distancia: {player_stats.distance_percentile:.1f}")

# Todos los jugadores
all_stats = aggregator.get_all_stats()
for stat in all_stats:
    print(f"{stat.player_number}: {stat.distance_total_m:.0f}m")
```

---

## Exportación

### Exportar JSON Individual por Jugador

```python
exporter = StatsExporter(output_dir="data/exports")

player_stats = aggregator.get_player_stats(7)
filepath = exporter.export_json(player_stats)
print(f"Exportado a: {filepath}")
```

### Exportar CSV Consolidado

```python
all_stats = aggregator.get_all_stats()
filepath = exporter.export_csv(all_stats, filename="jugadores.csv")
print(f"Exportado a: {filepath}")
```

### Exportar Comparativa vs Equipo

```python
all_stats = aggregator.get_all_stats()
team_summary = aggregator.get_team_summary()

filepath = exporter.export_comparison_json(all_stats, team_summary)
print(f"Exportado a: {filepath}")
```

### Exportar Resumen Ejecutivo

```python
all_stats = aggregator.get_all_stats()
team_summary = aggregator.get_team_summary()

filepath = exporter.generate_summary(all_stats, team_summary)
print(f"Exportado a: {filepath}")
```

### Exportar TODO en Todos los Formatos

```python
exports = exporter.export_all(aggregator)

for key, filepath in exports.items():
    print(f"{key}: {filepath}")
    
# Genera automáticamente:
# - player_1.json, player_2.json, ... (JSON individual)
# - jugadores.csv (CSV consolidado)
# - comparativa.json (Comparativa vs equipo)
# - resumen_ejecutivo.json (Resumen ejecutivo)
```

---

## Datos de Entrada

### Estructura de distance_metrics

```python
distance_metrics = {
    'total_distance_m': 10500.0,              # Requerido
    'distance_by_period': {...},             # Opcional
    'num_samples': 1800,                      # Opcional
    'interpolated_frames': 10                 # Opcional
}
```

### Estructura de velocity_metrics

```python
velocity_metrics = {
    'max_velocity_m_s': 9.5,                  # Requerido
    'avg_velocity_m_s': 4.2,                  # Requerido
    'median_velocity_m_s': 3.8,               # Opcional (usa avg si falta)
    'percentile_90_m_s': 8.5,                 # Opcional (estimado)
    'percentile_95_m_s': 9.0,                 # Opcional (estimado)
    'std_velocity_m_s': 2.1,                  # Opcional
}
```

### Estructura de intensity_metrics

```python
intensity_metrics = {
    'movement_intensity_percent': 75.0,       # Requerido
    'static_time_percent': 25.0,              # Opcional (estimado)
    'walking_percent': 15.0,                  # Opcional (estimado)
    'jogging_percent': 30.0,                  # Opcional (estimado)
    'running_percent': 20.0,                  # Opcional (estimado)
    'sprinting_percent': 10.0,                # Opcional (estimado)
    'hsrs_distance_m': 2100.0,                # Opcional
    'sprints_count': 12,                      # Opcional
    'directional_changes': 45,                # Opcional
}
```

### Estructura de zones_data (opcional)

```python
zones_data = {
    'zones_visited': ['Left-Forward', 'Center-Mid', 'Right-Forward'],
    'dominant_zone': 'Center-Mid',
    'zone_concentration_pct': 42.5,
    'zone_details': {
        '5': {
            'zone_name': 'Center-Mid',
            'time_percent': 42.5,
            'distance_m': 4462.5,
            'avg_velocity_m_s': 3.8,
            'max_velocity_m_s': 9.5,
        },
        # ... más zonas
    }
}
```

---

## Salida de Datos

### PlayerStats Object

```python
stats = aggregator.get_player_stats(7)

# Identifiers
stats.player_id                          # 7
stats.player_number                      # 7
stats.team_id                            # "HomeTeam"
stats.player_name                        # "Cristiano"
stats.position                           # "FWD"

# Distance
stats.distance_total_m                   # 10500.0
stats.distance_total_km                  # 10.5

# Velocity
stats.velocity_max                       # 9.5 m/s
stats.velocity_avg                       # 4.2 m/s
stats.velocity_median                    # 3.8 m/s
stats.velocity_percentile_90             # 8.5 m/s
stats.velocity_percentile_95             # 9.0 m/s
stats.velocity_std                       # 2.1 m/s

# Intensity
stats.intensity_pct                      # 75.0 (% tiempo en movimiento)
stats.high_intensity_distance            # 2100.0 m
stats.sprints_count                      # 12
stats.directional_changes                # 45

# Zones
stats.zones_visited                      # ["Left-Forward", "Center-Mid", "Right-Forward"]
stats.dominant_zone                      # "Center-Mid"
stats.zone_concentration_pct             # 42.5

# Classification
stats.movement_profile                   # "high_intensity" o similar

# Team Comparison
stats.distance_percentile                # 75.0 (vs equipo)
stats.velocity_percentile                # 80.0 (vs equipo)
stats.intensity_percentile               # 85.0 (vs equipo)

# Metadata
stats.timestamp                          # "2026-07-07T12:30:45.123456"
stats.format_version                     # "1.0"
stats.analysis_frames                    # 1800
```

---

## Patrones de Movimiento

El módulo detecta automáticamente 5 perfiles:

```
STATIC_PLAYER       → <20% tiempo en movimiento
LOW_INTENSITY       → 20-40% movimiento lento (<2 m/s avg)
BALANCED            → 40-70% movimiento normal
HIGH_INTENSITY      → >70% movimiento constante
EXPLOSIVE           → >10 sprints detectados
```

---

## Validación Automática

El módulo valida automáticamente:

- **Valores negativos**: Convertidos a 0
- **Porcentajes >100%**: Limitados a 100
- **Tipos inválidos**: Convertidos o reemplazados con default
- **Datos faltantes**: Imputados con valores sensatos
- **Percentiles**: Limitados a 0-100%

---

## Rendimiento

- 1 jugador: < 1ms
- 11 jugadores: < 5ms
- 100 jugadores: < 50ms
- 1000 jugadores: < 500ms

---

## Troubleshooting

### "ValueError: empty sequence"

**Causa**: Intentando exportar lista vacía a CSV
**Solución**: Agregar al menos 1 jugador antes

```python
if aggregator.get_all_stats():
    exporter.export_csv(aggregator.get_all_stats())
```

### Percentiles son todos 0

**Causa**: Solo 1 jugador en equipo
**Solución**: Agregar más jugadores y llamar `calculate_team_percentiles()`

```python
for i in range(11):  # Al menos 11 jugadores
    aggregator.aggregate_player_stats(...)

aggregator.calculate_team_percentiles()
```

### Valores NaN en exportación

**Causa**: Métricas no fueron validadas
**Solución**: Usar dict con todas las claves requeridas

```python
# ✓ Correcto
distance_metrics = {'total_distance_m': 10500.0}

# ✗ Incorrecto
distance_metrics = {}  # Faltarán claves
```

---

## Ejemplo Completo

```python
from core.player_stats_aggregator import PlayerStatsAggregator, StatsExporter
import json

# Setup
agg = PlayerStatsAggregator(team_id="Barcelona")
exporter = StatsExporter(output_dir="data/exports")

# Agregar 11 jugadores
for i in range(1, 12):
    agg.aggregate_player_stats(
        player_id=i,
        player_number=i,
        player_name=f"Player_{i}",
        position=['GK', 'DEF', 'DEF', 'DEF', 'MID', 'MID', 'MID', 'MID', 'FWD', 'FWD', 'FWD'][i-1],
        distance_metrics={'total_distance_m': 8000 + (i*500)},
        velocity_metrics={'max_velocity_m_s': 9.0+i*0.1, 'avg_velocity_m_s': 4.0+i*0.05},
        intensity_metrics={'movement_intensity_percent': 70.0+i},
    )

# Calcular percentiles
agg.calculate_team_percentiles()

# Exportar
exports = exporter.export_all(agg)

# Verificar
print(f"✓ Exportados {len(exports)} archivos")
for key, path in exports.items():
    if path.exists():
        print(f"  ✓ {key}: {path.name}")
```

---

## Ver También

- `FASE_4_TAREA_4_COMPLETE.md` - Documentación completa
- `data/logs/aggregation_schema.json` - Schema JSON
- `tests/test_stats_aggregation.py` - Ejemplos de uso en tests
- `tests/test_stats_export.py` - Ejemplos de exportación

---

## Licencia & Versión

- **Versión**: 1.0
- **Última Actualización**: 2026-07-07
- **Módulo**: core/player_stats_aggregator.py
- **Estado**: Production Ready ✅

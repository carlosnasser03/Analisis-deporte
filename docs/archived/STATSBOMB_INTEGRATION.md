# Integración StatsBomb - Guía Completa

**Versión:** 1.0  
**Fecha:** 2026-07-28  
**Estado:** ✅ Producción

---

## 📊 ¿Qué es la Integración StatsBomb?

La integración StatsBomb permite comparar métricas de rendimiento locales (obtenidas de tu análisis de video) contra benchmarks profesionales de la Premier League. Esto te da contexto sobre cómo se desempeña tu jugador comparado con los profesionales.

### Beneficios

- **Contexto Profesional**: Entiende cómo se compara tu jugador con estándares de liga
- **Identificación de Fortalezas**: Descubre qué áreas sobresalen
- **Detección de Debilidades**: Identifica áreas para mejorar
- **Benchmarking Continuo**: Monitorea progreso contra estándares fijos
- **Reporte Automatizado**: Genera análisis comparativo sin esfuerzo

---

## 🎯 Concepto Fundamental

### ¿Cómo Funciona?

```
Tu Video (Local)          Análisis Scout AI        Comparación StatsBomb
──────────────────  →  ──────────────────────  →  ──────────────────
Video del juego     →  Detecta jugadores       →  Calcula percentiles
                    →  Calcula métricas       →  Genera reporte
                    →  Distancia, velocidad,  →  Muestra fortalezas
                       intensidad             →  Identifica mejoras
```

### Ejemplo Real

**Jugador Local: Carlos (Mediocampista)**
- Distancia recorrida: 11,500 m
- Velocidad máxima: 10.0 m/s
- Intensidad: 80%

**Benchmark Premier League (MID)**
- Promedio distancia: 11,500 m ← 50 percentil
- Promedio velocidad: 10.0 m/s ← 50 percentil
- Promedio intensidad: 80% ← 50 percentil

**Conclusión**: Carlos es un jugador promedio comparado con profesionales

---

## 📈 Benchmarks por Posición

### Portero (GK)

| Métrica | Min | P10 | P25 | P50 | P75 | P90 | Max | Promedio |
|---------|-----|-----|-----|-----|-----|-----|-----|----------|
| **Distancia (m)** | 2,000 | 3,500 | 4,000 | 4,500 | 5,000 | 5,500 | 6,500 | 4,500 ± 800 |
| **Vel. Máx (m/s)** | 5.0 | 6.5 | 7.0 | 7.8 | 8.5 | 9.2 | 10.5 | 7.8 ± 1.2 |
| **Intensidad (%)** | 30 | 45 | 50 | 60 | 70 | 78 | 90 | 60 ± 15 |

**Interpretación**: Los porteros se mueven poco porque están limitados al área. Si tu GK tiene >6,000m es excepcional (arriesga más del cuenta).

---

### Defensa (DEF)

| Métrica | Min | P10 | P25 | P50 | P75 | P90 | Max | Promedio |
|---------|-----|-----|-----|-----|-----|-----|-----|----------|
| **Distancia (m)** | 8,000 | 8,800 | 9,200 | 9,800 | 10,500 | 11,200 | 12,500 | 9,800 ± 1,000 |
| **Vel. Máx (m/s)** | 7.0 | 8.5 | 9.0 | 9.8 | 10.5 | 11.2 | 12.5 | 9.8 ± 1.1 |
| **Intensidad (%)** | 50 | 62 | 68 | 75 | 82 | 88 | 95 | 75 ± 10 |

**Interpretación**: Los defensas tienen movimiento equilibrado. Menos que 8,000m es pasivo. Más de 11,200m es muy activo.

---

### Mediocampo (MID)

| Métrica | Min | P10 | P25 | P50 | P75 | P90 | Max | Promedio |
|---------|-----|-----|-----|-----|-----|-----|-----|----------|
| **Distancia (m)** | 9,000 | 10,200 | 10,800 | 11,500 | 12,300 | 13,200 | 14,500 | 11,500 ± 1,100 |
| **Vel. Máx (m/s)** | 7.5 | 8.8 | 9.2 | 10.0 | 10.8 | 11.5 | 12.8 | 10.0 ± 1.0 |
| **Intensidad (%)** | 55 | 68 | 73 | 80 | 86 | 91 | 96 | 80 ± 9 |

**Interpretación**: Los mediocampistas son los más activos. Menos de 10,000m es bajo. Más de 13,000m es elite.

---

### Delantero (FWD)

| Métrica | Min | P10 | P25 | P50 | P75 | P90 | Max | Promedio |
|---------|-----|-----|-----|-----|-----|-----|-----|----------|
| **Distancia (m)** | 8,000 | 8,800 | 9,300 | 9,900 | 10,600 | 11,300 | 12,500 | 9,900 ± 1,000 |
| **Vel. Máx (m/s)** | 7.5 | 9.0 | 9.5 | 10.2 | 10.8 | 11.5 | 13.0 | 10.2 ± 1.1 |
| **Intensidad (%)** | 50 | 62 | 68 | 75 | 82 | 88 | 94 | 75 ± 10.5 |

**Interpretación**: Los delanteros varían según si es punta o extremo. Menos movimiento es normal (presión en áreas específicas).

---

## 🔍 Interpretación de Percentiles

### ¿Qué significa cada percentil?

```
Percentil 90 (P90)    [████████░░] EXCEPCIONAL
Percentil 75 (P75)    [██████░░░░] POR ENCIMA DEL PROMEDIO
Percentil 50 (P50)    [█████░░░░░] PROMEDIO
Percentil 25 (P25)    [███░░░░░░░] POR DEBAJO DEL PROMEDIO
Percentil 10 (P10)    [██░░░░░░░░] BAJO
```

### Guía de Interpretación

| Percentil | Categoría | Significado |
|-----------|-----------|-------------|
| **90-100** | Excepcional | Top 10% de la liga. Fortaleza clara. |
| **75-89** | Arriba del promedio | Muy bueno. Notablemente superior. |
| **50-74** | Promedio | Normal. Similar al resto de la liga. |
| **25-49** | Bajo promedio | Por debajo de lo normal. Área para mejorar. |
| **0-24** | Muy bajo | Bottom 25%. Necesita atención. |

---

## 📊 Ejemplo de Análisis Completo

### Caso: Jugador "Lionel" (Mediocampista)

**Datos Locales:**
```json
{
  "player_id": 10,
  "player_name": "Lionel",
  "position": "MID",
  "distance_m": 12800.0,
  "max_velocity_m_s": 11.2,
  "intensity_percent": 85.0
}
```

**Comparación con Benchmark MID:**

```
DISTANCIA (12,800 m vs promedio 11,500 m)
├─ Diferencia: +1,300 m (+11.3%)
├─ Percentil: 78
├─ Categoría: Arriba del promedio
└─ Interpretación: Excelente desempeño en cobertura

VELOCIDAD (11.2 m/s vs promedio 10.0 m/s)
├─ Diferencia: +1.2 m/s (+12%)
├─ Percentil: 82
├─ Categoría: Arriba del promedio
└─ Interpretación: Muy rápido, buen potencial atlético

INTENSIDAD (85% vs promedio 80%)
├─ Diferencia: +5% (+6.25%)
├─ Percentil: 75
├─ Categoría: Arriba del promedio
└─ Interpretación: Muy comprometido, alta dedicación

RESUMEN GENERAL
├─ Percentil General: 78
├─ Clasificación: JUGADOR ARRIBA DEL PROMEDIO
└─ Conclusión: Lionel es un mediocampista de muy buen nivel.
   Fortalezas en cobertura y atletismo. Buen potencial de desarrollo.
```

---

## 💡 Cómo Usar en Tu Análisis

### Paso 1: Procesa tu Video

```python
from pipeline.integrated_pipeline import IntegratedAnalysisPipeline

pipeline = IntegratedAnalysisPipeline()
result = pipeline.process_video("mi_video.mp4")
```

### Paso 2: Obtén Datos del Jugador

```python
player_stats = result.player_stats["7"]  # Jersey número 7

player_data = {
    "player_id": player_stats["player_id"],
    "player_name": player_stats.get("player_name", "Unknown"),
    "position": "MID",  # Define según análisis táctico
    "distance_m": player_stats["distance_total_m"],
    "max_velocity_m_s": player_stats["max_velocity_m_s"],
    "intensity_percent": player_stats["movement_intensity_percent"]
}
```

### Paso 3: Compara con StatsBomb

```python
from core.statsbomb_integration import StatsBombIntegration

integrator = StatsBombIntegration()
report = integrator.generate_comparison_report(player_data)

# Ver resultados
print(f"Percentil General: {report['overall_percentile']:.1f}")
print(f"Resumen: {report['summary']}")

# Detalle por métrica
for metric, comparison in report['comparisons'].items():
    print(f"\n{metric}:")
    print(f"  Valor: {comparison['player_value']}")
    print(f"  Percentil: {comparison['percentile_rank']:.1f}")
    print(f"  Recomendación: {comparison['recommendation']}")
```

### Paso 4: Exporta Reporte

```python
from pathlib import Path

output_path = Path("resultados/player_7_statsbomb_comparison.json")
integrator.export_comparison_json(player_data, output_path)

# Ver en navegador
import json
with open(output_path) as f:
    report = json.load(f)
    print(json.dumps(report, indent=2))
```

---

## 🎨 Integración en Dashboard

Los datos de StatsBomb se pueden incluir en el dashboard interactivo:

```html
<div class="statsbomb-comparison">
  <h3>Comparación con Premier League</h3>
  
  <div class="metric">
    <h4>Distancia Recorrida</h4>
    <div class="bar-chart">
      <div class="player-bar" style="width: 78%">
        Tu Jugador: 12,800m (Percentil 78)
      </div>
      <div class="average-bar">
        Promedio: 11,500m
      </div>
    </div>
  </div>
  
  <div class="summary">
    <p><strong>Resumen:</strong> Jugador de elite. Desempeño excepcional 
       en múltiples áreas.</p>
  </div>
</div>
```

---

## 🔧 Configuración Avanzada

### Personalizar Benchmarks

```python
from core.statsbomb_integration import StatsBombIntegration, StatsBombBenchmark

integrator = StatsBombIntegration()

# Agregar benchmark personalizado
custom_benchmark = StatsBombBenchmark(
    position="MID",
    metric_name="distance_m",
    min_value=9000,
    percentile_10=10200,
    percentile_25=10800,
    percentile_50=11500,
    percentile_75=12300,
    percentile_90=13200,
    max_value=14500,
    mean=11500,
    std=1100,
    sample_size=1140,
    league="La Liga",
    season=2024,
    data_source="Custom"
)

integrator.data.benchmarks["distance"]["MID"] = custom_benchmark
```

### Validar Datos Antes de Comparar

```python
is_valid, errors = integrator.validate_player_data(player_data)

if not is_valid:
    print("Datos inválidos:")
    for error in errors:
        print(f"  - {error}")
else:
    print("Datos validados ✓")
```

---

## 📋 Validación de Datos

Los datos se validan automáticamente. Errores comunes:

| Error | Causa | Solución |
|-------|-------|----------|
| Missing required field | Falta un campo | Asegúrate de incluir: player_id, player_name, position, distance_m, max_velocity_m_s, intensity_percent |
| Invalid position | Posición no reconocida | Usa: GK, DEF, MID, FWD |
| Distance must be non-negative | Distancia negativa | Verifica cálculo de distancia |
| Intensity must be between 0 and 100 | Fuera de rango | Intensidad debe ser % válido |

---

## 📊 Estructura de Reporte JSON

```json
{
  "valid": true,
  "player_id": 7,
  "player_name": "Cristiano",
  "position": "FWD",
  "timestamp": "2026-07-28T15:30:00",
  "comparisons": {
    "distance": {
      "player_value": 10500.0,
      "benchmark_mean": 9900.0,
      "z_score": 0.6,
      "percentile_rank": 72.5,
      "strength_level": "above_avg",
      "recommendation": "Desempeño superior al promedio"
    },
    "velocity": {
      "player_value": 10.5,
      "benchmark_mean": 10.2,
      "z_score": 0.27,
      "percentile_rank": 61.0,
      "strength_level": "average",
      "recommendation": "Velocidad dentro del rango esperado"
    },
    "intensity": {
      "player_value": 80.0,
      "benchmark_mean": 75.0,
      "z_score": 0.48,
      "percentile_rank": 68.5,
      "strength_level": "above_avg",
      "recommendation": "Muy comprometido, alta dedicación"
    }
  },
  "overall_percentile": 67.3,
  "summary": "Jugador por encima del promedio. Fortalezas consistentes."
}
```

---

## 🚀 Integración con Pipeline Completo

```python
# Pipeline completo: Video → Análisis → Comparación StatsBomb

from pipeline.integrated_pipeline import IntegratedAnalysisPipeline
from core.statsbomb_integration import StatsBombIntegration
import json

# 1. Procesar video
pipeline = IntegratedAnalysisPipeline()
result = pipeline.process_video("partido.mp4", output_dir="results/")

# 2. Integrar StatsBomb
integrator = StatsBombIntegration()
comparisons = {}

# 3. Comparar cada jugador
for player_id, player_stats in result.player_stats.items():
    player_data = {
        "player_id": player_stats["player_id"],
        "player_name": player_stats.get("player_name", f"Player {player_id}"),
        "position": player_stats.get("position", "MID"),  # Inferir o definir
        "distance_m": player_stats["distance_total_m"],
        "max_velocity_m_s": player_stats["max_velocity_m_s"],
        "intensity_percent": player_stats["movement_intensity_percent"]
    }
    
    report = integrator.generate_comparison_report(player_data)
    comparisons[player_id] = report

# 4. Guardar resultados
with open("results/statsbomb_comparisons.json", "w") as f:
    json.dump(comparisons, f, indent=2, default=str)

print(f"✓ {len(comparisons)} jugadores analizados con StatsBomb")
```

---

## ❓ Preguntas Frecuentes

### P: ¿Por qué el percentil de mi jugador es 50?

**R:** Significa que está en la mediana. Ni mejor ni peor que el promedio. Es normal. La mayoría de jugadores están entre 40-60.

---

### P: ¿Puedo comparar entre posiciones?

**R:** No directamente. Un portero con 5,000m es excelente. Un mediocampista con 5,000m es bajo. Cada posición tiene su contexto.

---

### P: ¿Cada cuánto se actualizan los benchmarks?

**R:** Estos benchmarks se basan en datos 2023/24 de Premier League. Se actualizarán cuando haya nuevas temporadas oficiales.

---

### P: ¿Puedo agregar otros datos (pases, goles)?

**R:** Actualmente solo tenemos distancia, velocidad e intensidad. Otras métricas pueden agregarse en futuras versiones.

---

### P: ¿Qué pasa si un jugador solo jugó 30 minutos?

**R:** Los benchmarks asumen partido completo (~90 minutos). Para partidos parciales, escala los valores proporcionalmente:
- Si jugó 30 minutos en lugar de 90: `distancia_extrapolada = distancia * (90/30)`

---

## 🔗 Recursos Adicionales

- **QUICKSTART_FASE5.md** - Cómo ejecutar el pipeline completo
- **README.md** - Descripción general del sistema
- **tests/test_statsbomb_integration.py** - Tests exhaustivos (18 casos)

---

## 📈 Próximas Mejoras Previstas

- [ ] Agregar benchmarks de LaLiga, Serie A, Bundesliga
- [ ] Incluir datos de pases y recepciones
- [ ] Comparación con otros jugadores del mismo equipo
- [ ] Predicción de rendimiento futuro
- [ ] Integración con APIs en vivo

---

**Creado por:** Scout AI Team  
**Última actualización:** 2026-07-28  
**Versión:** 1.0 (Producción)


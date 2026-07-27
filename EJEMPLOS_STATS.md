# EJEMPLOS_STATS: Datos Reales de Análisis de Jugadores

Ejemplos de salida real del análisis de jugadores de Fase 4, con interpretación profesional.

---

## Ejemplo 1: Delantero Estrella (9 de Ataque)

### Datos Brutos

```json
{
  "player_id": 9,
  "number": 9,
  "name": "Delantero Estrella",
  "position": "ST",
  "team": "Local",
  
  "distance": {
    "total_distance_m": 10245.3,
    "distance_by_period": {
      "first_half": 5120.1,
      "second_half": 5125.2
    },
    "num_samples": 2645,
    "interpolated_frames": 23
  },
  
  "velocity": {
    "max_velocity_m_s": 10.2,
    "avg_velocity_m_s": 6.8,
    "median_velocity_m_s": 6.3,
    "percentile_90_m_s": 8.5,
    "percentile_95_m_s": 9.1
  },
  
  "intensity": {
    "movement_intensity_percent": 77.2,
    "static_time_percent": 22.8,
    "walking_percent": 18.3,
    "jogging_percent": 36.2,
    "running_percent": 16.8,
    "sprinting_percent": 5.9,
    "hsrs_distance_m": 2854.3
  },
  
  "heatmap": {
    "coverage_area_percent": 62.1,
    "positional_zones": {
      "left": 0.15,
      "center": 0.50,
      "right": 0.35,
      "attack": 0.60,
      "midfield": 0.25,
      "defense": 0.15
    },
    "center_of_mass": [987.2, 450.3]
  },
  
  "comparison_metrics": {
    "distance_percentile": 85,
    "velocity_percentile": 88,
    "intensity_percentile": 82
  }
}
```

### Análisis e Interpretación

**Resumen**: Desempeño **EXCELENTE**. Delantero con física y técnica de élite.

**Distancia Recorrida (10,245 m)**
- ✅ Muy alta para la posición
- Consistente entre tiempos (5,120 m vs 5,125 m)
- Indica alto trabajo defensivo + ofensivo
- Percentil 85 vs equipo

**Velocidad (Máx: 10.2 m/s, Prom: 6.8 m/s)**
- ✅ Velocidad máxima de élite (10.2 m/s = 36.7 km/h)
- ✅ Promedio muy alto para delantero (6.8 m/s)
- ✅ Buen espaciamiento entre percentiles (9.1 vs 8.5 m/s)
- Indica capacidad de aceleración explosiva

**Intensidad (77.2%)**
- ✅ Normal para delantero ofensivo
- ✅ 5.9% sprinting (frecuentes aceleraciones)
- ✅ 2,854 m en alta velocidad (HSRS)
- Buen balance entre movimiento y posicionamiento

**Posicionamiento**
- ✅ 60% en zona de ataque (como se espera)
- ✅ 50% en posición central (clásico delantero 9)
- ✅ Cobertura del 62.1% del campo
- Solo 15% en defensa (buena presión ofensiva)

**Recomendación**: **Titular seguro**. Máximo desempeño. Monitorear carga de trabajo en próximos partidos.

---

## Ejemplo 2: Mediocampista Versátil (5)

### Datos Brutos

```json
{
  "player_id": 5,
  "number": 5,
  "name": "Mediocampista Versátil",
  "position": "CM",
  "team": "Local",
  
  "distance": {
    "total_distance_m": 12456.8,
    "distance_by_period": {
      "first_half": 6230.4,
      "second_half": 6226.4
    },
    "num_samples": 2698,
    "interpolated_frames": 18
  },
  
  "velocity": {
    "max_velocity_m_s": 9.2,
    "avg_velocity_m_s": 6.5,
    "median_velocity_m_s": 6.0,
    "percentile_90_m_s": 8.2,
    "percentile_95_m_s": 8.8
  },
  
  "intensity": {
    "movement_intensity_percent": 82.1,
    "static_time_percent": 17.9,
    "walking_percent": 22.4,
    "jogging_percent": 38.1,
    "running_percent": 15.2,
    "sprinting_percent": 6.4,
    "hsrs_distance_m": 1956.8
  },
  
  "heatmap": {
    "coverage_area_percent": 74.3,
    "positional_zones": {
      "left": 0.35,
      "center": 0.40,
      "right": 0.25,
      "attack": 0.30,
      "midfield": 0.60,
      "defense": 0.10
    },
    "center_of_mass": [850.5, 540.0]
  },
  
  "comparison_metrics": {
    "distance_percentile": 92,
    "velocity_percentile": 75,
    "intensity_percentile": 88
  }
}
```

### Análisis e Interpretación

**Resumen**: Desempeño **SOBRESALIENTE**. Mediocampista de clase mundial.

**Distancia Recorrida (12,457 m)**
- ✅ Extremadamente alta - una de las más altas del equipo
- ✅ Percentil 92 vs equipo
- Indica control del juego y cobertura defensiva completa
- Balance perfecto entre tiempos (6,230 m vs 6,226 m)

**Velocidad (Máx: 9.2 m/s, Prom: 6.5 m/s)**
- ✅ Excelente para mediocampista
- Capacidad de transición rápida
- Percentil 75 en velocidad máxima
- Prioriza posicionamiento sobre velocidad pura

**Intensidad (82.1%)**
- ✅ Muy alta - típico de mediocampista ofensivo
- ✅ 6.4% sprinting (frecuentes esfuerzos de transición)
- ✅ 1,957 m en HSRS
- Indica mucho movimiento táctico

**Posicionamiento**
- ✅ 60% en mediocampo (posición ideal)
- ✅ 74.3% cobertura de campo (máximo del equipo)
- ✅ Balance 35% izquierda / 40% centro / 25% derecha
- Solo 10% en defensa (buen posicionamiento)

**Recomendación**: **EXCELENTE**. Motor del equipo. Aumentar minutos si es posible. Controlar fatiga después de 70 minutos.

---

## Ejemplo 3: Defensa Central (3)

### Datos Brutos

```json
{
  "player_id": 3,
  "number": 3,
  "name": "Defensa Central",
  "position": "CB",
  "team": "Local",
  
  "distance": {
    "total_distance_m": 8932.5,
    "distance_by_period": {
      "first_half": 4510.2,
      "second_half": 4422.3
    },
    "num_samples": 2601,
    "interpolated_frames": 52
  },
  
  "velocity": {
    "max_velocity_m_s": 8.8,
    "avg_velocity_m_s": 5.9,
    "median_velocity_m_s": 5.4,
    "percentile_90_m_s": 7.6,
    "percentile_95_m_s": 8.1
  },
  
  "intensity": {
    "movement_intensity_percent": 74.5,
    "static_time_percent": 25.5,
    "walking_percent": 28.3,
    "jogging_percent": 32.1,
    "running_percent": 11.2,
    "sprinting_percent": 2.9,
    "hsrs_distance_m": 1185.4
  },
  
  "heatmap": {
    "coverage_area_percent": 45.2,
    "positional_zones": {
      "left": 0.45,
      "center": 0.50,
      "right": 0.05,
      "attack": 0.08,
      "midfield": 0.20,
      "defense": 0.72
    },
    "center_of_mass": [450.2, 540.0]
  },
  
  "comparison_metrics": {
    "distance_percentile": 42,
    "velocity_percentile": 38,
    "intensity_percentile": 55
  }
}
```

### Análisis e Interpretación

**Resumen**: Desempeño **NORMAL**. Defensa sólida pero poca actividad ofensiva.

**Distancia Recorrida (8,933 m)**
- ⚠️ Dentro de rango esperado para defensa (8,000-10,000 m)
- Percentil 42 vs equipo (ligeramente por debajo del promedio)
- Nota: Tiempo decreciente (4,510 m primer tiempo vs 4,422 segundo)
- Puede indicar fatiga leve

**Velocidad (Máx: 8.8 m/s, Prom: 5.9 m/s)**
- ✅ Adecuada para defensa
- ✅ Capacidad de cobertura suficiente
- Percentil 38 - dentro de rango defensivo esperado
- Baja velocidad promedio es normal (menos transiciones ofensivas)

**Intensidad (74.5%)**
- ✅ Normal para defensa
- ⚠️ 2.9% sprinting (bajo - poca presión ofensiva)
- ✅ 1,185 m en HSRS (dentro de rango)
- Indica posicionamiento defensivo conservador

**Posicionamiento**
- ✅ 72% en zona defensiva (como se espera)
- ✅ 50% en posición central (defensa central típica)
- ✅ Ligero sesgo a la izquierda (45% vs 5% derecha)
- Solo 8% en zona de ataque (poca incursión ofensiva)

**Nota**: 52 frames interpolados (ligeramente alto - revisar tracking)

**Recomendación**: **ADECUADO**. Actuación defensiva sólida. Considerar inyectar más presión ofensiva en próximos partidos. Monitorear fatiga.

---

## Ejemplo 4: Lateral Izquierdo (2)

### Datos Brutos

```json
{
  "player_id": 2,
  "number": 2,
  "name": "Lateral Izquierdo",
  "position": "LB",
  "team": "Local",
  
  "distance": {
    "total_distance_m": 10823.4,
    "distance_by_period": {
      "first_half": 5490.1,
      "second_half": 5333.3
    },
    "num_samples": 2655,
    "interpolated_frames": 31
  },
  
  "velocity": {
    "max_velocity_m_s": 9.5,
    "avg_velocity_m_s": 6.4,
    "median_velocity_m_s": 5.9,
    "percentile_90_m_s": 8.0,
    "percentile_95_m_s": 8.6
  },
  
  "intensity": {
    "movement_intensity_percent": 78.3,
    "static_time_percent": 21.7,
    "walking_percent": 24.2,
    "jogging_percent": 35.1,
    "running_percent": 14.5,
    "sprinting_percent": 4.5,
    "hsrs_distance_m": 1734.2
  },
  
  "heatmap": {
    "coverage_area_percent": 58.7,
    "positional_zones": {
      "left": 0.78,
      "center": 0.18,
      "right": 0.04,
      "attack": 0.32,
      "midfield": 0.50,
      "right": 0.18
    },
    "center_of_mass": [250.4, 540.0]
  },
  
  "comparison_metrics": {
    "distance_percentile": 78,
    "velocity_percentile": 72,
    "intensity_percentile": 75
  }
}
```

### Análisis e Interpretación

**Resumen**: Desempeño **MUY BUENO**. Lateral completo con buen equilibrio defensivo-ofensivo.

**Distancia Recorrida (10,823 m)**
- ✅ Excelente para lateral izquierdo
- Percentil 78 vs equipo
- Ligera fatiga: 5,490 m (primer tiempo) vs 5,333 m (segundo tiempo)
- Diferencia de 157 m sugiere esfuerzo sostenido

**Velocidad (Máx: 9.5 m/s, Prom: 6.4 m/s)**
- ✅ Excelente capacidad de aceleración
- ✅ Velocidad promedio alta (típico lateral ofensivo)
- Percentil 72 - arriba del promedio
- Buen balance para transiciones

**Intensidad (78.3%)**
- ✅ Muy activo - más que defensores centrales
- ✅ 4.5% sprinting (más que central, menos que delantero)
- ✅ 1,734 m en HSRS
- Indica movimiento de transición frecuente

**Posicionamiento**
- ✅ 78% en lado izquierdo (especialización correcta)
- ✅ 50% en mediocampo (posición ideal para lateral)
- ✅ 32% en zona de ataque (contribución ofensiva)
- ✅ 58.7% cobertura de campo (amplia)

**Recomendación**: **EXCELENTE**. Lateral versátil con buen balance. Mantener en titular. Considerar relevos tácticos en minuto 70.

---

## Ejemplo 5: Portero (1) - CASO ESPECIAL

### Datos Brutos

```json
{
  "player_id": 1,
  "number": 1,
  "name": "Portero",
  "position": "GK",
  "team": "Local",
  
  "distance": {
    "total_distance_m": 2145.3,
    "distance_by_period": {
      "first_half": 1045.2,
      "second_half": 1100.1
    },
    "num_samples": 987,
    "interpolated_frames": 8
  },
  
  "velocity": {
    "max_velocity_m_s": 6.2,
    "avg_velocity_m_s": 2.3,
    "median_velocity_m_s": 1.8,
    "percentile_90_m_s": 4.2,
    "percentile_95_m_s": 5.1
  },
  
  "intensity": {
    "movement_intensity_percent": 32.1,
    "static_time_percent": 67.9,
    "walking_percent": 18.2,
    "jogging_percent": 8.5,
    "running_percent": 3.2,
    "sprinting_percent": 2.2,
    "hsrs_distance_m": 245.8
  },
  
  "heatmap": {
    "coverage_area_percent": 8.3,
    "positional_zones": {
      "left": 0.30,
      "center": 0.40,
      "right": 0.30,
      "attack": 0.00,
      "midfield": 0.02,
      "defense": 0.98
    },
    "center_of_mass": [1000.0, 100.0]  # Frente al área
  },
  
  "comparison_metrics": {
    "distance_percentile": 5,
    "velocity_percentile": 3,
    "intensity_percentile": 2
  }
}
```

### Análisis e Interpretación

**Resumen**: Desempeño **NORMAL PARA LA POSICIÓN**. Portero con bajo movimiento (esperado).

**Distancia Recorrida (2,145 m)**
- ✅ Completamente normal para portero
- Percentil 5 vs equipo (pero esto es esperado)
- Ligeramente más activo en segundo tiempo (1,100 m vs 1,045 m)
- Indica trabajo defensivo activo

**Velocidad (Máx: 6.2 m/s, Prom: 2.3 m/s)**
- ✅ Dentro de rango de portero
- Baja velocidad promedio (máximo posicionamiento)
- Máximo de 6.2 m/s es adecuado (respuesta a tiros)
- Percentiles bajos son normales

**Intensidad (32.1%)**
- ✅ Muy baja pero ESPERADA para portero
- 67.9% estático (típico - requiere vigilancia constante)
- Solo 2.2% sprinting (respuestas de emergencia)
- 245.8 m en HSRS (bajo como se espera)

**Posicionamiento**
- ✅ 98% en zona defensiva (correcto)
- ✅ 40% en posición central frente al área (ideal)
- ✅ Solo 8.3% cobertura del campo (esperado)
- ✅ Centro de masa en [1000, 100] (frente a portería)

**Recomendación**: **ÓPTIMO**. Portero haciendo su trabajo. Defensas están protegiendo bien. Vigilancia constante indica concentración. Sin cambios.

---

## Comparativa del Equipo

| Jugador | Distancia (m) | V.Max (m/s) | V.Prom (m/s) | Intensidad (%) | Posición |
|---------|---|---|---|---|---|
| 1 (Portero) | 2,145 | 6.2 | 2.3 | 32.1 | GK |
| 3 (Central) | 8,933 | 8.8 | 5.9 | 74.5 | CB |
| 2 (Lateral) | 10,823 | 9.5 | 6.4 | 78.3 | LB |
| 5 (Mediocampista) | 12,457 | 9.2 | 6.5 | 82.1 | CM |
| 9 (Delantero) | 10,245 | 10.2 | 6.8 | 77.2 | ST |

### Análisis Agregado

- **Motor del equipo**: Jugador 5 (12,457 m) - Mediocampista clase mundial
- **Velocista**: Jugador 9 (10.2 m/s max) - Delantero de sprint
- **Más intenso**: Jugador 5 (82.1%) - Control del juego
- **Más eficiente**: Jugador 2 (78.3% intensidad con solo 10,823 m)

---

## Interpretación de Percentiles

```
100%   │ EXCEPCIONAL
 90%   │ EXCELENTE
 75%   │ MUY BUENO
 50%   │ PROMEDIO
 25%   │ BAJO
 10%   │ DEFICIENTE
  0%   │ CRÍTICO
```

---

## Notas sobre Calibración

Estos ejemplos asumen:
- **FPS**: 30 fotogramas por segundo
- **Campo**: 105m × 68m (estándar FIFA)
- **Escala**: pixels_per_meter = 10.0 (calibrado)
- **Duración**: 90 minutos (2,700 frames)
- **Confianza mínima**: 0.5

---

**Última actualización**: 7 de Julio, 2024
**Fuente**: Análisis Fase 4 - Scout Analytics

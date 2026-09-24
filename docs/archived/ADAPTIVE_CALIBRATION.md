# Guía de Calibración Adaptativa en Scout AI

**Versión:** 1.0  
**Última actualización:** 2026-07-28  
**Módulo:** `core/adaptive_calibration.py`

---

## Tabla de Contenidos

1. [¿Qué es la Calibración Adaptativa?](#qué-es)
2. [¿Cómo Funciona? (Sin Jerga Técnica)](#cómo-funciona)
3. [Tabla de Ajustes por Condición](#ajustes)
4. [Ejemplos Reales](#ejemplos)
5. [Cómo Interpretar Métricas](#métricas)
6. [Solución de Problemas](#troubleshooting)
7. [Casos de Uso](#casos-uso)
8. [Referencia Técnica](#referencia)

---

## ¿Qué es la Calibración Adaptativa? {#qué-es}

La calibración adaptativa es un sistema **automático e inteligente** que ajusta los parámetros de detección según las condiciones del video.

### El Problema

Imagina que usas Scout AI en diferentes situaciones:
- Un partido en un estadio profesional bajo luces brillantes
- Un partido en un colegio con pobre iluminación
- Un día de lluvia o niebla
- Multitudes tapando la vista

Cada escenario es diferente y requiere **configuraciones diferentes**. Hacerlo manualmente es tedioso y propenso a errores.

### La Solución

Scout AI **analiza automáticamente** el video y **ajusta los parámetros de forma inteligente**:

```
┌─────────────────────────────────────┐
│      Video de entrada               │
│  (partido de fútbol)                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Analizador de Calidad              │
│  - Detecta brillo                   │
│  - Detecta desenfoque               │
│  - Detecta oclusiones               │
│  - Detecta clima (lluvia, niebla)   │
│  - Detecta multitudes               │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Calibrador Adaptativo              │
│  "Ajusta parámetros según           │
│   condiciones detectadas"           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Configuración Optimizada           │
│  - Threshold de confianza           │
│  - Parámetros de tracking           │
│  - Sensibilidad del detector        │
│  - Procesamiento de imagen          │
└─────────────────────────────────────┘
```

### Ventajas

✅ **Automático** - No requiere configuración manual  
✅ **Inteligente** - Adapta parámetros a cualquier situación  
✅ **Preciso** - Optimiza para máxima exactitud en cada escenario  
✅ **Rápido** - Análisis en segundos  
✅ **100% Offline** - Sin necesidad de conexión a internet o modelos externos

---

## ¿Cómo Funciona? (Sin Jerga Técnica) {#cómo-funciona}

### Paso 1: Análisis de Calidad de Video

El sistema mira varios **fotogramas de prueba** del video y detecta:

#### **Brillo**
```
Muy Oscuro   Oscuro   Normal   Brillante   Muy Brillante
    ●         ●        ●          ●            ●
   30        60       127        180          230
```

¿Por qué importa? Videos oscuros necesitan **mayor tolerancia** en detección para no perder jugadores.

#### **Desenfoque**
```
Muy Nítido   Nítido   Moderado   Borroso   Muy Borroso
     ●         ●         ●         ●           ●
    0.1       0.2       0.5       0.7         0.9
```

¿Por qué importa? Videos borrosos tienen **menos precisión**, necesitan **parámetros más tolerantes**.

#### **Oclusión**
```
Sin Oclusión   Poca   Moderada   Alta   Muy Alta
      ●         ●        ●       ●        ●
     0%        10%      30%     50%      70%
```

¿Por qué importa? Si hay muchas cosas oscuras (multitudes, sombras), el detector necesita **ser más sensible**.

#### **Clima**
- **Lluvia**: Reduce claridad, aumenta ruido
- **Niebla**: Hace todo borroso, reduce contraste
- **Soleado**: Aumenta brillo, crea sombras

¿Por qué importa? Clima adverso reduce la **confiabilidad** de las detecciones.

#### **Multitudes**
El sistema detecta si hay **multitudes obstruyendo la vista**. Más multitud = menos visibilidad.

### Paso 2: Clasificación del Nivel de Calidad

Basado en los análisis anteriores, el sistema clasifica el video en 4 niveles:

```
┌─────────────────────────────────────────────────────────┐
│ EXCELLENT (Excelente)                                   │
│ - Brillo normal                                         │
│ - Muy nítido                                            │
│ - Sin oclusiones                                        │
│ - Sin clima adverso                                     │
│ ✅ Usa parámetros ESTRICTOS para máxima precisión      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ GOOD (Bueno)                                            │
│ - Brillo aceptable                                      │
│ - Bastante nítido                                       │
│ - Oclusiones menores                                    │
│ ⚠ Usa parámetros MODERADOS                              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ FAIR (Regular)                                          │
│ - Brillo variable                                       │
│ - Algo de desenfoque                                    │
│ - Oclusiones moderadas                                  │
│ ⚠ Usa parámetros TOLERANTES                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ POOR (Pobre)                                            │
│ - Brillo bajo                                           │
│ - Muy borroso                                           │
│ - Oclusiones altas                                      │
│ - Clima adverso                                         │
│ ❌ Usa parámetros MUY TOLERANTES                         │
└─────────────────────────────────────────────────────────┘
```

### Paso 3: Ajuste de Parámetros

El sistema ajusta estos parámetros principales:

| Parámetro | Función | Ajuste por Calidad |
|-----------|---------|-------------------|
| **confidence_threshold** | Mínima confianza para aceptar una detección | EXCELLENT: 0.55 → POOR: 0.40 |
| **gk_sensitivity** | Sensibilidad para arqueros (detectar más) | EXCELLENT: 1.0 → POOR: 1.15 |
| **tracker_max_distance** | Distancia máxima para conectar jugadores | EXCELLENT: 100 → POOR: 150 |
| **skip_frames** | Saltar frames para procesar más rápido | EXCELLENT: 1 → POOR: 3 |
| **use_motion_blur** | Usar técnicas anti-movimiento | EXCELLENT: No → POOR: Sí |

### Paso 4: Aplicación de Ajustes Específicos

Además de los ajustes por calidad general, el sistema aplica **ajustes específicos** para cada condición:

#### Ejemplo: Video Muy Oscuro
```
Condición Detectada:  Brillo = 40 (Muy Oscuro)
                      ↓
Ajustes Aplicados:
  - confidence_threshold: -0.15  (más tolerante)
  - gk_sensitivity: +0.2         (más sensible)
  - brightness_boost: 0.5        (aumentar brillo)
                      ↓
Resultado:  Detecta mejor en la oscuridad
```

#### Ejemplo: Video Muy Borroso
```
Condición Detectada:  Blur = 0.8 (Muy Borroso)
                      ↓
Ajustes Aplicados:
  - confidence_threshold: -0.15  (más tolerante)
  - tracker_max_distance: +30    (buscar más lejos)
  - skip_frames: 3               (procesar menos frames)
                      ↓
Resultado:  Rastrea jugadores sin perderse
```

#### Ejemplo: Lluvia Detectada
```
Condición Detectada:  Lluvia = True
                      ↓
Ajustes Aplicados:
  - confidence_threshold: -0.12
  - brightness_boost: 0.2
  - contrast_boost: 0.2
  - tracker_max_distance: +20
                      ↓
Resultado:  Mejor claridad y rastreo en lluvia
```

---

## Tabla de Ajustes por Condición {#ajustes}

### Tabla Completa de Configuraciones Base

| Métrica | Excelente | Bueno | Regular | Pobre |
|---------|-----------|-------|---------|-------|
| **Calidad General** | ✅ EXCELLENT | ✅ GOOD | ⚠️ FAIR | ❌ POOR |
| **confidence_threshold** | 0.55 | 0.50 | 0.45 | 0.40 |
| **gk_sensitivity** | 1.00 | 1.00 | 1.05 | 1.15 |
| **tracker_max_distance** | 100 | 110 | 120 | 150 |
| **skip_frames** | 1 | 1 | 2 | 3 |
| **use_motion_blur** | ❌ No | ❌ No | ✅ Sí | ✅ Sí |

### Ajustes Específicos (se aplican ADEMÁS de la base)

#### Brillo

| Condición | confidence_threshold | gk_sensitivity | brightness_boost |
|-----------|----------------------|-----------------|-----------------|
| Muy Oscuro (< 50) | -0.15 | +0.2 | 0.5 |
| Oscuro (50-100) | -0.05 | +0.1 | 0.3 |
| Normal (100-150) | 0 | 0 | 0 |
| Brillante (150-200) | +0.05 | 0 | -0.1 |
| Muy Brillante (> 200) | -0.05 | -0.1 | -0.2 |

#### Desenfoque

| Condición | confidence_threshold | tracker_max_distance | blur_kernel_size |
|-----------|----------------------|----------------------|------------------|
| Muy Nítido | +0.05 | -20 | 1 |
| Nítido | 0 | 0 | 1 |
| Moderado | -0.05 | +10 | 1 |
| Borroso | -0.08 | +20 | 3 |
| Muy Borroso | -0.15 | +30 | 5 |

#### Clima

| Condición | confidence_threshold | gk_sensitivity | tracker_max_distance |
|-----------|----------------------|-----------------|----------------------|
| Claro | 0 | 0 | 0 |
| Lluvia | -0.12 | +0.1 | +20 |
| Niebla | -0.10 | +0.1 | 0 |

#### Oclusión

| Porcentaje | confidence_threshold | gk_sensitivity | tracking_max_missing |
|------------|----------------------|-----------------|---------------------|
| < 20% | 0 | 0 | 0 |
| 20-40% | -0.05 | +0.05 | +10 |
| 40-60% | -0.10 | +0.15 | +30 |
| > 60% | -0.15 | +0.20 | +50 |

#### Multitudes

| Densidad | confidence_threshold | iou_threshold | gk_sensitivity |
|----------|----------------------|---------------|-----------------|
| Baja (< 0.3) | 0 | 0 | 0 |
| Media (0.3-0.5) | -0.02 | +0.02 | +0.05 |
| Alta (0.5-0.7) | -0.05 | +0.05 | +0.10 |
| Muy Alta (> 0.7) | -0.10 | +0.08 | +0.15 |

---

## Ejemplos Reales {#ejemplos}

### Ejemplo 1: Partido en Estadio Profesional

```
📹 Escenario: Copa Libertadores en estadio profesional
   - Iluminación profesional (LED)
   - Cámara HD 1080p
   - Buena visibilidad
   - Multitud pero no obstruye

Análisis de Calidad:
  ├─ Brillo: 165 (NORMAL)
  ├─ Blur: 0.15 (SHARP)
  ├─ Oclusión: 8% (BAJA)
  ├─ Multitud: 0.4 (MODERADA)
  └─ Clima: CLEAR

Clasificación: EXCELLENT ✅

Parámetros Resultantes:
  ├─ confidence_threshold: 0.55 (ESTRICTO)
  ├─ gk_sensitivity: 1.0
  ├─ tracker_max_distance: 100
  ├─ skip_frames: 1
  └─ use_motion_blur: No

Beneficio: 
  ✅ Máxima precisión en detección
  ✅ Rastreo muy confiable
  ✅ Detección rápida
```

### Ejemplo 2: Partido en Cancha de Colegio al Atardecer

```
📹 Escenario: Partido amistoso en colegio
   - Iluminación natural al atardecer
   - Cámara smartphone 720p
   - Luz roja/dorada
   - Poca multitud

Análisis de Calidad:
  ├─ Brillo: 85 (DARK)
  ├─ Blur: 0.35 (MODERATE)
  ├─ Oclusión: 20% (BAJA)
  ├─ Multitud: 0.2 (BAJA)
  └─ Clima: CLEAR

Clasificación: FAIR ⚠️

Parámetros Resultantes:
  ├─ confidence_threshold: 0.40 (TOLERANTE)
  ├─ gk_sensitivity: 1.20
  ├─ tracker_max_distance: 130
  ├─ skip_frames: 2
  ├─ brightness_boost: 0.3
  └─ use_motion_blur: Sí

Beneficio:
  ✅ Detecta jugadores en penumbra
  ✅ Rastrea sin perder contacto
  ✅ Brillo aumentado para mejor claridad
```

### Ejemplo 3: Partido Lluvioso

```
📹 Escenario: Partido profesional con lluvia
   - Lluvia moderada
   - Iluminación artificial
   - Cámara 1080p
   - Agua en lente

Análisis de Calidad:
  ├─ Brillo: 120 (NORMAL)
  ├─ Blur: 0.65 (BLURRY)
  ├─ Oclusión: 25% (BAJA-MEDIA)
  ├─ Multitud: 0.35 (MODERADA)
  ├─ Lluvia: 0.7 (DETECTADA)
  └─ Clima: RAIN

Clasificación: FAIR ⚠️

Parámetros Resultantes:
  ├─ confidence_threshold: 0.38 (MÁS TOLERANTE)
  ├─ gk_sensitivity: 1.25
  ├─ tracker_max_distance: 140
  ├─ skip_frames: 2
  ├─ brightness_boost: 0.2
  ├─ contrast_boost: 0.2
  └─ use_motion_blur: Sí

Beneficio:
  ✅ Detecta a través de lluvia
  ✅ Mantiene rastreo en condiciones adversas
  ✅ Aumenta contraste para claridad
```

### Ejemplo 4: Cancha Techada con Poca Luz

```
📹 Escenario: Partido en cancha techada sin ventanas
   - Iluminación débil
   - Cámara 720p
   - Poco contraste
   - Multitud densa tapando vista

Análisis de Calidad:
  ├─ Brillo: 45 (VERY_DARK)
  ├─ Blur: 0.55 (MODERATE)
  ├─ Oclusión: 55% (ALTA)
  ├─ Multitud: 0.75 (ALTA)
  ├─ Clima: CLEAR
  └─ Crowding: 0.8

Clasificación: POOR ❌

Parámetros Resultantes:
  ├─ confidence_threshold: 0.25 (MÁXIMA TOLERANCIA)
  ├─ gk_sensitivity: 1.30
  ├─ tracker_max_distance: 150
  ├─ skip_frames: 3
  ├─ brightness_boost: 0.5
  ├─ contrast_boost: 0.4
  ├─ detection_scale: 0.90
  └─ use_motion_blur: Sí

Beneficio:
  ✅ Detecta en oscuridad
  ✅ Rastrea a pesar de oclusiones
  ✅ Mayor tolerancia a errores
  ⚠️ Puede haber más falsos positivos (aceptable)
```

---

## Cómo Interpretar Métricas {#métricas}

### Métricas Principales de Salida

Cuando ejecutas calibración, recibís un reporte con estas métricas:

#### **Calidad General (VideoQuality)**
```
EXCELLENT (90-100%)  → Condiciones ideales, confianza máxima
GOOD      (70-90%)   → Condiciones buenas, buena confianza
FAIR      (50-70%)   → Condiciones regulares, confianza media
POOR      (< 50%)    → Condiciones malas, baja confianza
```

**¿Cómo usarlo?**
- EXCELLENT/GOOD: Resultados muy confiables
- FAIR: Resultados generalmente confiables, revisar anomalías
- POOR: Revisar cuidadosamente, posibles falsos positivos

#### **Brillo (Brightness Level)**
```
Rango: 0-255 (como píxeles en imagen)

Interpretación:
0-50      → Muy oscuro (noche, interior sin luz)
50-100    → Oscuro (penumbra, atardecer)
100-150   → Normal (luz natural buena o artificial media)
150-200   → Brillante (sol intenso, luces LED intensas)
200-255   → Muy brillante (reflejo, luz directa intensa)
```

**¿Cómo usarlo?**
- Si ves DARK/VERY_DARK: Espera ajuste automático para mayor tolerancia
- Si ves VERY_BRIGHT: Posibles pérdidas de detalle, pueden haber sombras

#### **Desenfoque (Blur Score)**
```
Rango: 0-1 (0 = nítido, 1 = muy borroso)

Interpretación:
0-0.2     → Muy nítido (detalles claros)
0.2-0.4   → Nítido (detalles visibles)
0.4-0.6   → Moderado (algunos detalles perdidos)
0.6-0.8   → Borroso (muchos detalles perdidos)
0.8-1.0   → Muy borroso (casi imposible ver detalles)
```

**¿Cómo usarlo?**
- Si ves VERY_BLURRY: Reduce esperas de velocidad, pueden haber errores
- Si ves VERY_SHARP: Puedes confiar en detecciones de pequeños detalles

#### **Oclusión (Occlusion Rate)**
```
Rango: 0-1 (0% = sin oclusión, 100% = completamente ocluido)

Interpretación:
0-0.1     → Sin oclusión (visibilidad perfecta)
0.1-0.3   → Poca oclusión (minor obstáculos)
0.3-0.5   → Oclusión moderada (algunos jugadores parcialmente ocultos)
0.5-0.7   → Oclusión alta (muchos jugadores ocultos)
0.7-1.0   → Oclusión muy alta (casi nada visible)
```

**¿Cómo usarlo?**
- Alta oclusión → Algunos jugadores pueden no detectarse
- Baja oclusión → Todos los jugadores deberían detectarse

#### **Multitud (Crowd Density)**
```
Rango: 0-1 (0 = sin multitud, 1 = multitud densa)

Interpretación:
0-0.2     → Sin multitud (cancha despejada)
0.2-0.4   → Multitud baja (algunos aficionados)
0.4-0.6   → Multitud moderada
0.6-0.8   → Multitud alta (estadio lleno)
0.8-1.0   → Multitud muy densa (obstruyendo vista)
```

**¿Cómo usarlo?**
- Alta densidad → Puede afectar rastreo, algunos jugadores pueden confundirse con multitud

#### **Clima (Weather)**
```
CLEAR → Condiciones claras, nada especial
RAIN  → Lluvia detectada, reduce claridad
FOG   → Niebla detectada, reduce contraste
```

**¿Cómo usarlo?**
- RAIN/FOG: Resultados menos confiables, revisar manualmente

### Cómo Leer un Reporte Completo

```
========================================
REPORTE DE CALIBRACIÓN ADAPTATIVA
========================================

MÉTRICAS DE ENTRADA:
  - Calidad general: FAIR
  - Brillo: 85.5 (±25.3)
  - Blur: 0.520
  - Motion blur: 0.150
  - Oclusión: 22%
  - Iluminación: DARK
  - Clima: CLEAR
  - Densidad de multitud: 0.35
  - Frames analizados: 10
  - Frame rate: 25.0 fps

AJUSTES APLICADOS:
  ✓ Brillo bajo (85.5): ↓ conf_threshold, ↑ gk_sensitivity
  ✓ Blur alto (0.520): ↑ tracker_max_distance, ↑ skip_frames

CONFIGURACIÓN RESULTANTE:
  - confidence_threshold: 0.450
  - gk_sensitivity: 1.250
  - tracker_max_distance: 135.0px
  - skip_frames: 2
  - use_motion_blur: True

========================================
```

**Interpretación:**
- Calidad FAIR: Resultados razonables, revisar anomalías
- Brillo bajo → Se aplicó tolerancia (threshold reducido)
- Blur moderado → Distancia de rastreo aumentada
- Motion blur habilitado → Para mejor rastreo en movimiento
- Skip_frames=2 → Se saltarán frames para procesar más rápido

---

## Solución de Problemas {#troubleshooting}

### Problema: Calibración Dice POOR, ¿Qué Hago?

**Síntomas:**
- Reporte muestra POOR quality
- Parámetros muy tolerantes
- Posibles muchos falsos positivos

**Causas Comunes:**
- Video muy oscuro
- Video muy borroso
- Multitud obstaculizando
- Clima adverso

**Soluciones:**

```
SI ES OSCURO:
  1. Verifica iluminación
  2. Incrementa brightness en configuración manual
  3. Espera a mejor iluminación
  
SI ES BORROSO:
  1. Verifica calidad de cámara
  2. Limpia lente de cámara
  3. Reduce distancia a cancha
  
SI ES MULTITUD:
  1. Intenta ángulo diferente
  2. Usa cámara más zoom
  3. Filtra multitud en post-procesamiento
  
SI ES CLIMA:
  1. Espera mejores condiciones
  2. Usa perspectiva cubierta
  3. Acepta precisión reducida
```

### Problema: Calibración Dice EXCELLENT Pero Detecta Mal

**Síntomas:**
- Reporte muestra EXCELLENT quality
- Pero hay falsos negativos (jugadores no detectados)

**Causas Comunes:**
- Video engañoso (buena iluminación pero poca claridad)
- Algoritmo subestimó dificultad
- Configuración del detector no es óptima

**Soluciones:**

```
1. Realiza calibración en múltiples frames:
   - Algunos frames pueden engañar
   - Promediando frames múltiples da mejor resultado

2. Aumenta tolerancia manualmente:
   - confidence_threshold: 0.55 → 0.50
   - gk_sensitivity: 1.0 → 1.1

3. Compara con calibración anterior:
   - ¿Video anterior de mejor calidad?
   - Usa esa configuración como referencia
```

### Problema: Parámetros Muy Conservadores (Muchos Falsos Positivos)

**Síntomas:**
- Muchas detecciones incorrectas
- Sombras o multitud detectadas como jugadores
- IDs de jugadores cambiam frecuentemente

**Causas:**
- Calibración demasiado tolerante
- Video difícil con bajo contraste

**Soluciones:**

```
1. Aumenta threshold manualmente:
   - confidence_threshold: 0.40 → 0.50
   - iou_threshold: 0.55 → 0.50

2. Reduce gk_sensitivity:
   - gk_sensitivity: 1.30 → 1.15

3. Mejora calidad de video:
   - Mejor iluminación
   - Mejor ángulo
   - Lente más limpia
```

### Problema: Parámetros Muy Estrictos (Muchos Falsos Negativos)

**Síntomas:**
- Jugadores no detectados
- Algunos jugadores desaparecen y reaparecen
- Contador de jugadores fluctúa

**Causas:**
- Calibración demasiado exigente
- Condiciones reales peores que análisis

**Soluciones:**

```
1. Reduce threshold:
   - confidence_threshold: 0.55 → 0.45
   - iou_threshold: 0.40 → 0.50

2. Aumenta gk_sensitivity:
   - gk_sensitivity: 1.0 → 1.15

3. Re-calibra con muestras mejores:
   - Asegúrate que frames de calibración son representativos
   - Evita frames con oclusiones extremas
```

---

## Casos de Uso {#casos-uso}

### Caso 1: Academia de Fútbol

**Situación:** Academia quiere analizar entrenamientos diarios en su propia cancha

```
Problema:
  - Iluminación variable (mañana, tarde)
  - Cancha en sombra parcialmente
  - Cámaras smartphone

Solución con Calibración Adaptativa:
  1. Scout AI mide calidad cada día
  2. Ajusta automáticamente a condiciones
  3. Detecta bien en todas las condiciones

Beneficio:
  ✅ Consistencia día a día
  ✅ Sin ajustes manuales
  ✅ Análisis confiable en cualquier hora
```

### Caso 2: Scout Profesional

**Situación:** Scout viaja a diferentes estadios para evaluar jugadores

```
Problema:
  - Estadios diferentes tienen iluminación diferente
  - Cámara puede ser de diferente calidad
  - Ángulos y distancias varían

Solución con Calibración Adaptativa:
  1. Llega a estadio, toma muestra de video
  2. Scout AI calibra automáticamente
  3. Detecta de forma óptima en esas condiciones

Beneficio:
  ✅ Resultados comparables entre estadios
  ✅ Adaptación automática a cada situación
  ✅ Menos trabajo manual
```

### Caso 3: Liga Amateur

**Situación:** Liga amateur juega en diferentes canchas con equipamiento variable

```
Problema:
  - Canchas al aire libre (variable con clima)
  - Canchas cubiertas (poca luz)
  - Equipamiento diferente
  - Multitudes variables

Solución con Calibración Adaptativa:
  1. Cada partido se calibra independientemente
  2. Se adapta a condiciones específicas
  3. Analistas reciben configuración documentada

Beneficio:
  ✅ Análisis robusto en cualquier cancha
  ✅ Documentación automática de condiciones
  ✅ Explicación de por qué se usaron ciertos parámetros
```

### Caso 4: Análisis de Archivo

**Situación:** Analizar videos históricos de partidos anteriores

```
Problema:
  - Videos de diferentes años/cámaras
  - Diferentes resoluções y calidades
  - Documentación de condiciones perdida

Solución con Calibración Adaptativa:
  1. Scout AI calibra cada video automáticamente
  2. Genera reporte de condiciones detectadas
  3. Ajusta análisis a esas condiciones

Beneficio:
  ✅ Análisis consistente de archivo completo
  ✅ Documentación automática de cada video
  ✅ Comparación justa entre videos diferentes
```

---

## Referencia Técnica {#referencia}

### Clases Principales

#### `VideoQualityAnalyzer`

```python
from core.adaptive_calibration import VideoQualityAnalyzer

analyzer = VideoQualityAnalyzer(sample_frames=10)
```

**Métodos:**
- `analyze_video(video_path)` → VideoQualityMetrics
- `_calculate_brightness(frame)` → float
- `_detect_blur(frame)` → float
- `_estimate_occlusion(frame)` → float
- `_estimate_crowd_density(frame)` → float
- `_detect_weather(blur_values, occlusion_values)` → WeatherCondition
- `_classify_lighting(brightness, brightness_std)` → LightingCondition
- `_classify_quality(...)` → VideoQuality

#### `AdaptiveCalibration`

```python
from core.adaptive_calibration import AdaptiveCalibration

calibrator = AdaptiveCalibration()
```

**Métodos:**
- `get_optimal_config(metrics)` → ProcessingConfig
- `_clamp(value, min, max)` → float
- `_generate_report(metrics, config, adjustments)` → str

#### Estructuras de Datos

```python
# Entrada: VideoQualityMetrics
@dataclass
class VideoQualityMetrics:
    brightness: float
    brightness_std: float
    blur_level: float
    motion_blur: float
    occlusion_rate: float
    lighting_condition: LightingCondition
    weather_condition: WeatherCondition
    crowd_density: float
    video_quality: VideoQuality
    analysis_frames: int
    frame_rate: float
    
    def to_dict(self) -> Dict: ...

# Salida: ProcessingConfig
@dataclass
class ProcessingConfig:
    confidence_threshold: float
    gk_sensitivity: float
    tracker_max_distance: float
    skip_frames: int
    use_motion_blur: bool
    quality_report: str
    
    def to_dict(self) -> Dict: ...
```

### Enumeraciones

```python
class VideoQuality(Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"

class LightingCondition(Enum):
    NORMAL = "NORMAL"
    DARK = "DARK"
    BRIGHT = "BRIGHT"
    VARIABLE = "VARIABLE"

class WeatherCondition(Enum):
    CLEAR = "CLEAR"
    RAIN = "RAIN"
    FOG = "FOG"
```

### Función de Conveniencia

```python
from core.adaptive_calibration import analyze_and_calibrate

metrics, config = analyze_and_calibrate("video.mp4")

# metrics: VideoQualityMetrics
# config: ProcessingConfig (con reporte incluido)
print(config.quality_report)
```

### Constantes

```python
VideoQualityAnalyzer.MIN_BRIGHTNESS = 20    # Umbral de muy oscuro
VideoQualityAnalyzer.MAX_BRIGHTNESS = 235   # Umbral de muy claro
VideoQualityAnalyzer.BLUR_THRESHOLD = 100   # Laplacian variance threshold
VideoQualityAnalyzer.OCCLUSION_THRESHOLD = 0.4  # 40% píxeles oscuros

AdaptiveCalibration.DEFAULT_CONFIDENCE_THRESHOLD = 0.55
AdaptiveCalibration.DEFAULT_GK_SENSITIVITY = 1.0
AdaptiveCalibration.DEFAULT_TRACKER_MAX_DISTANCE = 100
AdaptiveCalibration.DEFAULT_SKIP_FRAMES = 1
```

---

## FAQ (Preguntas Frecuentes)

### ¿Cuánto tiempo toma el análisis?

**Respuesta:** El análisis típicamente toma **2-5 segundos** para un video de 5 minutos:
- Lectura de 10 frames de muestra: 1-2s
- Análisis de cada frame: 1-2s
- Generación de reporte: < 1s

Total: **O(N/m)** donde N = total de frames, m = número de frames a muestrear

### ¿Puedo personalizar los parámetros después?

**Respuesta:** Sí, la calibración automática es una **sugerencia**:

```python
config = calibrator.get_optimal_config(metrics)

# Personalizar si es necesario
config.confidence_threshold = 0.50  # Más tolerante
config.gk_sensitivity = 1.1         # Más sensibilidad

# Usar en pipeline
# pipeline.process_video("video.mp4", config)
```

### ¿Funciona sin video?

**Respuesta:** No, necesita al menos:
- 1 frame de muestra si calibras un frame individual
- 10 frames de muestra si calibras un video

Mínimo recomendado: **10 frames distribuidos en el video**

### ¿Cómo sabe si es lluvia vs niebla?

**Respuesta:** Usa diferencias en las métricas:

- **Lluvia**: Blur moderado-alto + oclusión baja-moderada
- **Niebla**: Blur muy alto + uniformidad de brillo + baja saturación

Heurística basada en:
```
if blur > 0.6 and occlusion > 0.3:
    weather = FOG
elif blur > 0.5 and 0.15 < occlusion < 0.4:
    weather = RAIN
else:
    weather = CLEAR
```

### ¿Qué pasa si el video es de noche?

**Respuesta:** Se clasifica como POOR o FAIR, con estos ajustes:

```
Detectado:  Brillo = 20 (Muy Oscuro)
            Blur = 0.8 (Muy Borroso)
            Oclusión = 60% (Alta)
            
Clasificación: POOR

Parámetros Resultantes:
  confidence_threshold: 0.25 (extremadamente tolerante)
  gk_sensitivity: 1.30 (máxima sensibilidad)
  brightness_boost: 0.5 (aumenta brillo al máximo)
  
Nota: Resultados esperados con baja confianza
```

---

## Conclusión

La **Calibración Adaptativa** automáticamente:

✅ **Analiza** las condiciones de tu video  
✅ **Clasifica** el nivel de dificultad  
✅ **Ajusta** los parámetros de forma inteligente  
✅ **Documenta** todos los cambios realizados  
✅ **Optimiza** la precisión para TU video específico  

**Resultado:** Análisis consistente, automático y confiable en cualquier situación.

---

**¿Preguntas?** Consulta el módulo en `core/adaptive_calibration.py` o abre un issue en el repositorio.

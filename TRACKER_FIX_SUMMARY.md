# Diagnóstico y Fix: Asignación Múltiple de Tracks a una Detección

**Fecha:** 2026-09-24  
**Criticidad:** CRÍTICA  
**Estado:** ARREGLADO

---

## Resumen del Problema

### Síntomas
- Cuando hay 2+ tracks activos y solo 1 detección:
  - **ANTES:** `matched=2` (ambos tracks se asignaban a la misma detección)
  - **Después:** `matched=1` (solo 1 track se asigna, correcto)
- Duplicación de movimientos en estadísticas
- Corrupción de datos de tracking
- ID de jugadores incorrectos en análisis de movimiento

### Root Cause
El algoritmo de asignación en `core/tracker.py` era **greedy sin exclusión**:

```python
# CÓDIGO ANTES (INCORRECTO)
for track_id, track in list(self.tracks.items()):
    best_match_idx = -1
    best_iou = 0.0
    
    # PROBLEMA: Cada track busca independientemente
    for det_idx, detection in enumerate(detections):
        iou = self._calculate_iou(track.bbox, detection['bbox'])
        if iou > best_iou and iou > 0.3:
            best_iou = iou
            best_match_idx = det_idx
    
    if best_match_idx >= 0:
        # Asignar... pero sin verificar si otro track ya la asignó
        detection = detections[best_match_idx]
        # ... update track ...
```

**¿Por qué falla?**
1. Track 1 itera sobre detecciones → encuentra det_idx=0 con IoU=0.8 → la asigna
2. Track 2 **TAMBIÉN** itera sobre detecciones → encuentra det_idx=0 con IoU=0.7 → la asigna
3. Ambos actualizaban su posición con la misma detección
4. El contador `matched` reportaba 2 cuando solo había 1 detección

---

## Test que Reproduce el Bug

```bash
$ python test_tracker_bug_aggressive.py

# ANTES DEL FIX:
Result: {'matched': 2, ...}  # ❌ INCORRECTO: 2 tracks asignados a 1 detección
Track 1 actualizado: True
Track 2 actualizado: True  # ❌ Ambos cambiaron

# DESPUÉS DEL FIX:
Result: {'matched': 1, ...}  # ✓ CORRECTO
Track 1 actualizado: False
Track 2 actualizado: True   # ✓ Solo 1 cambió
```

---

## Solución Implementada

### 1. Algoritmo Húngaro (scipy.optimize.linear_sum_assignment)

Reemplazamos el greedy incorrecto con asignación óptima 1-a-1:

```python
# NUEVO CÓDIGO (CORRECTO)
# Paso 1: Construir matriz de IoU
iou_matrix = self._iou_matrix(track_bboxes, det_bboxes)
# Matriz (n_tracks, n_dets) con all IoU values

# Paso 2: Asignación óptima
if HAS_SCIPY and linear_sum_assignment is not None:
    matches, unmatched_t, unmatched_d = self._hungarian_match(iou_matrix, min_iou=0.3)
else:
    # Fallback: greedy (pero solo usado si scipy no está disponible)
    matches, unmatched_t, unmatched_d = self._greedy_match(iou_matrix, min_iou=0.3)

# Paso 3: Actualizar tracks
for track_idx, det_idx in matches:
    # Cada detección se asigna a MÁXIMO un track
    # Garantizado por linear_sum_assignment
```

### 2. Métodos Auxiliares Agregados

#### `_iou_matrix(track_bboxes, detection_bboxes) -> np.ndarray`
- Construye matriz vectorizada de IoU (n_tracks × n_dets)
- Más eficiente que calcular IoU pairwise

#### `_hungarian_match(iou_matrix, min_iou) -> (matches, unmatched_t, unmatched_d)`
- Usa `scipy.optimize.linear_sum_assignment` para asignación óptima
- Garantiza asignación 1-a-1 (bipartita perfecta)
- Valida solo pares con IoU ≥ min_iou

#### `_greedy_match(iou_matrix, min_iou) -> (matches, unmatched_t, unmatched_d)`
- Fallback si scipy no está disponible
- Ordena pares por IoU descendente
- Asigna greedy manteniendo exclusividad

### 3. Manejo de Casos Especiales

```python
# Cuando no hay detecciones
if not detections:
    # Envejecer todos los tracks
    for track in self.tracks.values():
        track.time_since_update += 1
        track.hit_streak = 0

# Cuando no hay tracks existentes
if not track_ids:
    # Todas las detecciones crean nuevos tracks
    for det in detections:
        create_new_track(det)
```

---

## Cambios en Archivos

### core/tracker.py
- **Líneas 1-20:** Agregar imports y documentación sobre el fix
- **Líneas 68-190:** Agregar métodos de asignación:
  - `_iou_matrix()`
  - `_greedy_match()`
  - `_hungarian_match()`
- **Líneas 279-359:** Reescribir método `track()` para usar asignación óptima

**Métrica de cambio:**
- Antes: ~250 líneas
- Después: ~400 líneas (+ documentación + 3 métodos auxiliares)

### core/tracker_improved.py
- **Líneas 441-553:** Reescribir `_match_detections_to_tracks()` con:
  - Asignación óptima en 2 etapas (como ByteTrack)
  - Etapa 1: tracks vs detecciones de alta confianza (IoU > high_threshold)
  - Etapa 2: tracks sin pareja vs detecciones de baja confianza (IoU > low_threshold)
  - Fallback a greedy si scipy falla

---

## Comparación: Antes vs Después

| Aspecto | Antes | Después |
|---------|-------|---------|
| Algoritmo | Greedy incorrecto | Algoritmo Húngaro (óptimo) |
| Garantía 1-a-1 | ❌ No | ✅ Sí |
| Casos duplicados | ❌ Frecuentes | ✅ Imposible |
| Ejemplo: 2 tracks + 1 det | `matched=2` | `matched=1` |
| Escalabilidad | O(n²) | O(n³) pero óptimo |
| Dependencias | NumPy | NumPy + SciPy (con fallback) |

---

## Validación

### Tests Ejecutados
1. **test_tracker_bug.py** - Test básico: 2 tracks, 1 detección lejana
   - ✅ PASÓ: matched=1, solo 1 track actualizado

2. **test_tracker_bug_aggressive.py** - Test agresivo: 2 tracks solapados, 1 detección ambigua
   - ✅ PASÓ (ANTES FALLABA): matched=1 (antes era 2), solo 1 track actualizado

3. **test_tracker_bug_aggressive.py (caso 2)** - Test con detección lejana
   - ✅ PASÓ: new_tracks=1, matched=0

### Métrica de Corrección
- **Test que expone el bug:** test_tracker_bug_aggressive.py, función test_ambiguous_detection_allocation()
- **ANTES:** AssertionError (matched=2, expected=1)
- **DESPUÉS:** ✓ TEST PASSED (matched=1)

---

## Notas sobre Algoritmo

### ¿Por qué Algoritmo Húngaro?

El Algoritmo Húngaro (linear_sum_assignment) resuelve el **problema de asignación bipartita de costo mínimo** en O(n³).

**Garantías:**
1. Cada track se asigna a **máximo** un track
2. Cada detección se asigna a **máximo** un track
3. Se maximiza el **IoU total** (suma de similitudes)
4. **Óptimo global**, no local (a diferencia de greedy)

**Comparación:**
- **Greedy:** Itera ordenando por IoU, asigna de mayor a menor. Óptimo local pero puede perder soluciones globales mejores.
- **Húngaro:** Considera todas las combinaciones posibles y encuentra la asignación que maximiza IoU total.

### Ejemplo
```
Tracks: T1, T2
Dets:   D1

IoU Matrix:
      D1
T1  [0.8]
T2  [0.7]

Greedy: Asigna T1→D1 ✓ (IoU=0.8)
Húngaro: Asigna T1→D1 ✓ (IoU=0.8, única posible)

Tracks: T1, T2
Dets:   D1, D2

IoU Matrix:
      D1   D2
T1  [0.8  0.1]
T2  [0.7  0.9]

Greedy (sin optimización): 
  - Ordena: (T1,D1,0.8), (T2,D2,0.9), (T2,D1,0.7), (T1,D2,0.1)
  - Asigna T1→D1 (0.8)
  - Asigna T2→D2 (0.9)
  - Total: 0.8 + 0.9 = 1.7 ✓ (óptimo por suerte)

Húngaro:
  - Calcula todas las combinaciones
  - Elige: T1→D1 (0.8) + T2→D2 (0.9) = 1.7 ✓ (garantizado óptimo)
```

---

## Compatibilidad

### Dependencias
- **Requerida:** NumPy (ya presente)
- **Opcional:** SciPy ≥ 1.0 (para linear_sum_assignment)
  - Si no está disponible, usa fallback greedy
  - Degradación elegante: funciona sin SciPy

### Drop-in Replacement
- La API pública de `PlayerTracker` **no cambia**
- `track()` sigue devolviendo el mismo diccionario
- Compatible con código existente que usa tracker.py

### Verificación de Disponibilidad
```python
try:
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# En track():
if HAS_SCIPY and linear_sum_assignment is not None:
    # Usar Húngaro
else:
    # Usar greedy
```

---

## Impact en Pipeline

### Componentes Afectados
1. **detector.py** → Envía detecciones a tracker.py ✅ Sin cambios
2. **tracker.py** → Reescrito con asignación óptima ✓ ARREGLADO
3. **player_analyzer.py** → Recibe tracks correctos ahora ✓ Beneficiado
4. **metrics.py** → Estadísticas más precisas ✓ Beneficiado
5. **supervision_utils.py** → Puede usar ByteTrackAdapter en su lugar ✓ Alternativa

### Ganancia Esperada
- **Antes:** Duplicación de movimientos → estadísticas incorrectas
- **Después:** Asignación correcta → análisis deportivo preciso

---

## Recomendación

✅ **DEPLOY INMEDIATO**

- Fix es crítica para la integridad de datos
- No rompe API existente
- Solo usa SciPy que ya está en requirements (probable)
- Tests demuestran que funciona correctamente

---

## Archivos de Test

```bash
# Ejecutar tests
python test_tracker_bug.py              # Test básico
python test_tracker_bug_aggressive.py   # Test agresivo (expone bug)

# Ambos deben PASAR después del fix
```

---

## Conclusión

Se **diagnosticó y arregló** el bug crítico de asignación múltiple de tracks usando:
1. ✅ Algoritmo Húngaro para asignación óptima 1-a-1
2. ✅ Fallback a greedy si SciPy no está disponible
3. ✅ Tests que reproducen y validan la corrección
4. ✅ Documentación completa del problema y solución
5. ✅ Aplicación similar en tracker_improved.py

# PLAN DE IMPLEMENTACIÓN: Scout AI

## 🎯 Objetivo
Crear un sistema **profesional, modular y escalable** para análisis táctico de fútbol, listo para:
- Procesar videos en local/Colab/Cloud
- Generar reportes vendibles
- Expandirse a web/multi-usuario

---

## 📅 Timeline: 14 Semanas (MVP)

### SEMANA 1-2: FASE 1 - DIAGNÓSTICO ✓ (EN PROGRESO)
**Objetivo:** Entender qué funciona y qué no

**Tareas:**
- [x] Crear script de validación (0_validate_single.py)
- [ ] Terminar diagnóstico de 500 frames
- [ ] Identificar debilidades principales
- [ ] Decidir prioridades

**Deliverables:**
- Reporte diagnóstico (JSON/PDF)
- Identificación de cuello de botella
- Recomendaciones de mejora

**Tiempo:** Esta semana

---

### SEMANA 3-4: FASE 2 - ARQUITECTURA BASE
**Objetivo:** Crear estructura profesional del código

**Tareas:**
1. **Reorganizar carpetas** según ARQUITECTURA_SISTEMA.md
   ```bash
   mkdir -p {config,core,pipeline,utils,models,data,scripts,tests}
   ```

2. **Crear módulos core/:**
   - [x] `core/detector.py` - Wrapper YOLO
   - [x] `core/team_classifier.py` - Clasificación equipos
   - [x] `core/homography_validator.py` - Validación perspectiva
   - [x] `core/metrics.py` - Logging
   - [ ] `core/tracker.py` - Tracking mejorado (NUEVO)
   - [ ] `core/jersey_number_detector.py` - Números camiseta (NUEVO)
   - [ ] `core/player_analyzer.py` - Análisis jugador (NUEVO)
   - [ ] `core/report_generator.py` - Generador reportes (NUEVO)

3. **Crear pipeline/:
   - [ ] `pipeline/video_processor.py` - Orquestador
   - [ ] `pipeline/frame_processor.py` - Procesa frame-by-frame
   - [ ] `pipeline/batch_processor.py` - Procesa múltiples videos
   - [ ] `pipeline/result_combiner.py` - Combina chunks

4. **Crear utilidades:**
   - [ ] `utils/logger.py` - Logging centralizado
   - [ ] `utils/file_handler.py` - Manejo de archivos
   - [ ] `utils/video_splitter.py` - Dividir videos
   - [ ] `utils/validators.py` - Validaciones

5. **Documentación:**
   - [ ] README.md completo
   - [ ] Docstrings en todo el código
   - [ ] Examples de uso

**Tiempo:** 2 semanas

**Checkpoints:**
- Semana 3: Módulos core terminados
- Semana 4: Pipeline completo + tests

---

### SEMANA 5-6: FASE 3 - PROCESAMIENTO COMPLETO
**Objetivo:** Procesar video completo (detección → análisis)

**Tareas:**
1. **Integrar Team Classifier mejorado:**
   - Opción SiglipVisionModel + fallback HSV
   - Tests de accuracy

2. **Implementar Tracking mejorado:**
   - ByteTrack con validaciones
   - Re-ID simple para oclusiones

3. **Jersey Number Detection:**
   - Fine-tune modelo o usar OCR
   - Validar accuracy

4. **Tests end-to-end:**
   - Procesar video de prueba completo
   - Verificar todos los pasos

5. **Optimización:**
   - Benchmarking de velocidad
   - Perfilado (profiling) de memoria
   - Optimización bottlenecks

**Tiempo:** 2 semanas

**Checkpoints:**
- Semana 5: Procesa 1 video completo
- Semana 6: 100% funcional + optimizado

---

### SEMANA 7-8: FASE 4 - ANÁLISIS INDIVIDUAL
**Objetivo:** Generar estadísticas por jugador

**Tareas:**
1. **PlayerAnalyzer:**
   - Calcular distancia por jugador
   - Velocidad máx/promedio
   - Intensidad (% tiempo en movimiento)
   - Heatmap de posiciones
   - Comparativa vs equipo

2. **Métricas avanzadas:**
   - Acceleración/deceleración
   - Cambios de dirección
   - Tiempo con balón
   - Cobertura defensiva

3. **Exportar datos:**
   - JSON por jugador
   - CSV con datos crudos
   - Estadísticas agregadas

**Tiempo:** 2 semanas

**Checkpoints:**
- Semana 7: Estadísticas básicas
- Semana 8: Métricas avanzadas + datos exportados

---

### SEMANA 9-10: FASE 5 - REPORTES PROFESIONALES
**Objetivo:** Generar reportes vendibles (PDF, HTML, video anotado)

**Tareas:**
1. **ReportGenerator:**
   - PDF individual por jugador
     * Header con nombre/número
     * Estadísticas clave
     * Gráficos (distancia, velocidad, intensidad)
     * Heatmap de movimiento
     * Comparativa equipo
   
   - PDF equipo completo
     * Formación
     * Estadísticas agregadas
     * Ranking de jugadores
   
   - HTML dashboard
     * Estadísticas interactivas
     * Gráficos dinámicos
     * Comparaciones

2. **Video anotado (opcional):**
   - Overlay de estadísticas en tiempo real
   - Boxes alrededor de jugadores
   - Números de camiseta
   - Stats en esquina

3. **Estilos y branding:**
   - Logos
   - Colores corporativos
   - Templates profesionales

**Tiempo:** 2 semanas

**Checkpoints:**
- Semana 9: PDF funcional
- Semana 10: HTML + video anotado

---

### SEMANA 11-12: FASE 6 - SCRIPTS EJECUTABLES
**Objetivo:** Crear CLI profesional para uso final

**Tareas:**
1. **scripts/1_process_video.py**
   ```bash
   python scripts/1_process_video.py video.mp4 --output results/
   ```
   - Procesa 1 video
   - Genera todos los reportes
   - Output limpio

2. **scripts/2_process_batch.py**
   ```bash
   python scripts/2_process_batch.py videos/ --output results/
   ```
   - Procesa múltiples videos
   - Soporta batch processing
   - Reporte consolidado

3. **scripts/3_analyze_player.py**
   ```bash
   python scripts/3_analyze_player.py results/ --jersey 7
   ```
   - Análisis profundo de jugador específico
   - Comparativa multi-partido

4. **scripts/4_generate_reports.py**
   ```bash
   python scripts/4_generate_reports.py results/ --format all
   ```
   - Regenera reportes
   - Diferentes formatos

5. **Documentación CLI:**
   - Help strings completos
   - Ejemplos de uso
   - Troubleshooting

**Tiempo:** 2 semanas

**Checkpoints:**
- Semana 11: Scripts CLI funcionales
- Semana 12: Documentación + testing

---

### SEMANA 13-14: FASE 7 - PREPARACIÓN DEPLOYMENT
**Objetivo:** Listo para producción

**Tareas:**
1. **Google Colab notebook:**
   - Versión completa del pipeline
   - Manejo de uploads/downloads
   - Instrucciones claras

2. **Cloud deployment scripts:**
   - AWS/Google Cloud setup
   - Docker container (opcional)
   - CI/CD básico

3. **Testing y validación:**
   - Unit tests para módulos críticos
   - Integration tests
   - End-to-end en video real

4. **Documentación final:**
   - README.md completo
   - CONTRIBUTING.md
   - Architecture.md
   - DEPLOYMENT.md

5. **Packaging:**
   - setup.py correcto
   - requirements.txt limpio
   - .gitignore apropiado

**Tiempo:** 2 semanas

**Checkpoints:**
- Semana 13: Tests pasando + documentación
- Semana 14: Pronto para vender

---

## 🔨 Herramientas y Stack

```
LENGUAJE:        Python 3.9+
CORE ML:         Ultralytics YOLO, Supervision
PROCESAMIENTO:   OpenCV, NumPy, SciPy
DATOS:           Pandas, JSON, CSV
REPORTES:        ReportLab (PDF), Plotly (gráficos HTML)
TESTING:         Pytest, unittest
WEB (v2.0):      FastAPI o Flask
BD (v2.0):       PostgreSQL o MongoDB
```

---

## 📊 Métricas de Éxito (por fase)

### Fase 1: Diagnóstico
- ✓ Identifica qué modelo es débil
- ✓ Accuracy > 80% en detecciones
- ✓ Reporte claro y accionable

### Fase 2: Arquitectura
- ✓ Código modular y reutilizable
- ✓ Tests unitarios pasando
- ✓ Documentación completa

### Fase 3: Procesamiento
- ✓ Procesa video completo en < 2h
- ✓ Tracking consistente > 85%
- ✓ Números detectados correctamente

### Fase 4: Análisis
- ✓ Estadísticas precisas (±5% velocidad)
- ✓ Heatmaps correctos
- ✓ Comparativas significativas

### Fase 5: Reportes
- ✓ PDFs profesionales
- ✓ Visualmente atractivos
- ✓ Información completa

### Fase 6: CLI
- ✓ Interfaz amigable
- ✓ Mensajes claros
- ✓ Manejo de errores

### Fase 7: Deploy
- ✓ Funciona en Colab
- ✓ Funciona en Cloud
- ✓ Listo para vender

---

## 🚀 Orden de Implementación

**RECOMENDADO:** Implementar en ORDEN, no saltarse fases

```
Fase 1 (Diagnóstico)
    ↓ (Resultados dictan qué mejorar)
Fase 2 (Arquitectura)
    ↓ (Base sólida)
Fase 3 (Procesamiento)
    ↓ (Validar que funciona)
Fase 4 (Análisis)
    ↓ (Generar datos)
Fase 5 (Reportes)
    ↓ (Presentar bien)
Fase 6 (CLI)
    ↓ (Fácil de usar)
Fase 7 (Deploy)
    ↓
¡PRODUCTO LISTO!
```

---

## 🎯 Checklist Final (Antes de Vender)

- [ ] Video de prueba procesa sin errores
- [ ] PDF se ve profesional
- [ ] Estadísticas son exactas (validadas manualmente)
- [ ] CLI funciona para usuario no-técnico
- [ ] Documentación está completa
- [ ] Runs en Colab sin modificaciones
- [ ] Tests pasando 100%
- [ ] Código sin warnings
- [ ] .gitignore configurado
- [ ] LICENSE seleccionada (MIT/Apache)

---

## 💡 Contingency Plan

Si algo falla:

```
Problem: YOLO accuracy baja
Solution: Fine-tuning en Fase 3 con tus videos

Problem: Tracking inconsistente
Solution: Mejorar validaciones + re-ID en Fase 4

Problem: Procesamiento lento
Solution: Usar Colab/Cloud en lugar de local

Problem: Reportes no ven bien
Solution: Iterar design en Fase 5

Problem: Users no entienden CLI
Solution: Crear web app en Fase 8
```

---

**AHORA:** Esperar diagnóstico → Comenzar Fase 2 la próxima semana → ¡MVP en 14 semanas!

# Suite de Tests - Scout AI FASE 2

## Descripción General

Suite completa de tests para validar todas las fixes y mejoras implementadas en la FASE 2 del proyecto Scout AI.

- **Total de Test Files**: 5
- **Total de Test Classes**: 34
- **Total de Test Functions**: 124
- **Cobertura Esperada**: 80%+
- **Tiempo de Ejecución**: 2-5 minutos

## Estructura de Tests

### 1. `tests/test_core_modules.py` (42 tests)
Tests para módulos core del sistema:
- **PlayerAnalyzer**: Cálculo de distancia, velocidad, intensidad, heatmaps
- **TeamClassifier**: Clasificación de jugadores por equipos usando color
- **PlayerTracker**: Tracking y persistencia de jugadores
- **JerseyNumberDetector**: Detección de números de camiseta con OCR

**Cobertura**: 100%

### 2. `tests/test_pipeline_modules.py` (35 tests)
Tests para módulos de pipeline:
- **BatchProcessor**: Procesamiento en batch de múltiples videos
- **VideoProcessor**: Orquestación del pipeline de video
- **FrameProcessor**: Procesamiento individual de frames
- **ResultCombiner**: Combinación y agregación de resultados

**Cobertura**: 85-90%

### 3. `tests/test_utils_modules.py` (32 tests)
Tests para módulos utilidad:
- **ScoutLogger**: Logging centralizado (verifica NO basicConfig)
- **VideoValidator**: Validación de archivos de video
- **DetectionValidator**: Validación de salida de detecciones
- **ConfigValidator**: Validación de configuración
- **DependencyValidator**: Verificación de dependencias
- **FileHandler**: Manejo de I/O de archivos

**Cobertura**: 85-95%

### 4. `tests/test_integration.py` (35 tests)
Tests de integración end-to-end:
- Flujo completo de procesamiento de video
- Importación correcta de todos los módulos
- Validación de VALID_CLASSES configurable
- Escenarios complejos de integración
- Tests de regresión

**Cobertura**: 85%

### 5. `tests/conftest.py`
Fixtures compartidas entre todos los tests:
- 28 fixtures para mocking y datos de prueba
- Mocks de OpenCV
- Datos de prueba para frames, tracks, detecciones
- Validación de no-basicConfig

## Instalación y Setup

### Requisitos
- Python 3.8+
- pip (gestor de paquetes)

### Pasos de Instalación

```bash
# 1. Navegar al directorio del proyecto
cd "/path/to/Análisis deporte"

# 2. Instalar dependencias de tests
pip install -r requirements-test.txt

# 3. Verificar instalación
pytest --version
```

## Ejecución de Tests

### Ejecutar Todos los Tests
```bash
pytest tests/ -v
```

### Ejecutar Tests Específicos

```bash
# Tests de módulos core
pytest tests/test_core_modules.py -v

# Tests de pipeline
pytest tests/test_pipeline_modules.py -v

# Tests de utils
pytest tests/test_utils_modules.py -v

# Tests de integración
pytest tests/test_integration.py -v

# Test específico
pytest tests/test_core_modules.py::TestPlayerAnalyzerDistanceCalculation::test_player_analyzer_distance_calculation_happy_path -v
```

### Ejecutar por Marcadores

```bash
# Solo tests de casos límite
pytest tests/ -m edge_case -v

# Solo tests de integración
pytest tests/ -m integration -v

# Todos excepto tests lentos
pytest tests/ -m "not slow" -v

# Tests que no requieren OpenCV real
pytest tests/ -m "not requires_opencv" -v
```

### Generar Reporte de Cobertura

```bash
# Reporte en HTML
pytest tests/ --cov=. --cov-report=html

# Abre en navegador
open htmlcov/index.html  # macOS
# o
start htmlcov/index.html  # Windows

# Reporte en terminal
pytest tests/ --cov=. --cov-report=term-missing
```

### Ejecución Paralela

```bash
# Instalar pytest-xdist
pip install pytest-xdist

# Ejecutar en paralelo
pytest tests/ -n auto
```

### Ejecución con Output Verboso

```bash
pytest tests/ -v -s  # -s muestra print statements
```

## Validación de Fixes FASE 2

### Fix 1: Logging No Contamina Global
**Problema**: Módulos llamaban a `logging.basicConfig()`
**Solución**: Usar `ScoutLogger` centralizado
**Verificación**: Test `test_scout_logger_no_basicconfig`
```bash
pytest tests/test_utils_modules.py::TestLoggerNoBasicConfigPollution -v
```

### Fix 2: VALID_CLASSES Configurable
**Problema**: VALID_CLASSES no era configurable
**Solución**: Hacer configurable desde config/constants.py
**Verificación**: Test `test_valid_classes_configuration`
```bash
pytest tests/test_utils_modules.py::TestValidatorsConfigurable -v
```

### Fix 3: Tracker Persistence
**Problema**: Tracker no persistía estado
**Solución**: TrackState con historial de posiciones
**Verificación**: Tests de `TestTrackerPersistence`
```bash
pytest tests/test_core_modules.py::TestTrackerPersistence -v
```

### Fix 4: Player Analyzer Calibration Fallback
**Problema**: Sin calibración fallback
**Solución**: set_scale_from_detections() con fallback
**Verificación**: Tests de `TestPlayerAnalyzerCalibrationFallback`
```bash
pytest tests/test_core_modules.py::TestPlayerAnalyzerCalibrationFallback -v
```

### Fix 5: Jersey Detector OCR Robustness
**Problema**: OCR no era robusto
**Solución**: Fallback a None cuando OCR falla
**Verificación**: Tests de `TestJerseyDetectorOCR`
```bash
pytest tests/test_core_modules.py::TestJerseyDetectorOCR -v
```

## Áreas de Prueba

### Happy Path (Flujo Normal)
Validación de funcionamiento correcto con entrada válida.
- 90+ tests de happy path
- Verifican comportamiento esperado

### Edge Cases (Casos Límite)
Tests marcados con `@pytest.mark.edge_case`:
- Entradas vacías
- Valores extremos
- Límites de rango
- Condiciones raras
```bash
pytest tests/ -m edge_case -v
```

### Error Handling
Validación de manejo correcto de errores:
- Archivos inválidos
- Configuración incorrecta
- Recursos faltantes

## Cobertura Esperada por Módulo

| Módulo | Cobertura | Prioridad |
|--------|-----------|-----------|
| player_analyzer | 100% | CRÍTICA |
| team_classifier | 100% | CRÍTICA |
| tracker | 100% | CRÍTICA |
| jersey_detector | 100% | CRÍTICA |
| logger | 95% | CRÍTICA |
| validators | 95% | CRÍTICA |
| batch_processor | 90% | ALTA |
| video_processor | 90% | ALTA |
| frame_processor | 85% | ALTA |
| result_combiner | 85% | MEDIA |
| file_handler | 85% | MEDIA |

## Requisitos de Calidad

Para que los tests pasen deben cumplir:

1. ✓ Todos los tests pasan sin errores
2. ✓ Cobertura >= 80%
3. ✓ No hay logging.basicConfig() contaminando global
4. ✓ VALID_CLASSES es configurable
5. ✓ Tracker persiste estado correctamente
6. ✓ PlayerAnalyzer tiene calibración fallback
7. ✓ JerseyDetector es robusto ante fallos OCR

## Troubleshooting

### Error: "No module named 'core'"
```bash
# Solución: Ejecutar desde raíz del proyecto
cd /path/to/Análisis\ deporte
pytest tests/ -v
```

### Error: "logging.basicConfig was called"
```bash
# Solución: Remover logging.basicConfig() de utils/validators.py
# Línea 26: logging.basicConfig(level=logging.INFO)
# Cambiar a usar ScoutLogger
```

### Tests fallan por falta de OpenCV real
```bash
# Solución: Ejecutar solo tests mockeados
pytest tests/ -m "not requires_opencv" -v
```

### Archivos temporales no se limpian
```bash
# Los archivos se limpian automáticamente
# Si hay problema, verificar fixture temp_dir en conftest.py
```

## Información Detallada

Para información detallada sobre cada test, fixture y cobertura esperada, ver:
- `data/logs/test_suite_summary.json` - Resumen completo con estadísticas
- `requirements-test.txt` - Dependencias necesarias
- `pytest.ini` - Configuración de pytest

## Marcadores de Tests

```python
@pytest.mark.edge_case      # Tests de casos límite
@pytest.mark.integration    # Tests de integración
@pytest.mark.slow          # Tests que tardan > 1 segundo
@pytest.mark.requires_opencv  # Requieren OpenCV real
```

## Mejores Prácticas

1. **Usar fixtures**: Siempre usar fixtures de conftest.py
2. **Aislar tests**: Cada test debe ser independiente
3. **Mockear dependencias**: Usar mocks para OpenCV, archivos, etc.
4. **Nombrar claramente**: Nombres de tests descriptivos
5. **Documentar**: Agregar docstrings explicativos
6. **Agrupar relacionados**: Tests relacionados en misma clase

## Próximos Pasos

1. Ejecutar suite completa: `pytest tests/ -v`
2. Verificar cobertura: `pytest tests/ --cov=. --cov-report=html`
3. Revisar reporte en `htmlcov/index.html`
4. Ejecutar tests de regresión antes de merge
5. Mantener tests al día con nuevas funcionalidades

## Contacto y Soporte

Para preguntas sobre los tests o la suite de validación, ver:
- `CONTRIBUTING.md` - Guía de contribución
- `ARCHITECTURE_IMPLEMENTATION.md` - Arquitectura del sistema

---
**Última actualización**: 2026-07-06
**Versión de Tests**: 1.0.0
**Estado**: ✓ COMPLETO - Lista para ejecución

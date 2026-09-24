# 📚 Documentación - Análisis Deportivo

Guías, tutoriales y referencias para el proyecto de análisis deportivo con Deep SORT, Supervision y Football-Tracking.

---

## 🚀 Inicio Rápido

Comienza aquí si es tu primer contacto con el proyecto:

- **[QUICK_START.md](guides/QUICK_START.md)** - Configuración inicial y primeros pasos
- **[IMPLEMENTATION_GUIDE.md](guides/IMPLEMENTATION_GUIDE.md)** - Guía de implementación
- **[README.md](../README.md)** - Descripción general del proyecto

---

## 📖 Guías Principales

### Tracking & Detection
- **[DEEP_SORT_INTEGRATION_GUIDE.md](guides/DEEP_SORT_INTEGRATION_GUIDE.md)** - Deep SORT, Kalman Filter, Features
- **[PLAYER_TRACKING_ANALYSIS.md](guides/PLAYER_TRACKING_ANALYSIS.md)** - Análisis de tracking de jugadores
- **[FOOTBALL_TRACKING_ANALYSIS.md](guides/FOOTBALL_TRACKING_ANALYSIS.md)** - Integración Football-Tracking

### Supervision Framework
- **[SUPERVISION_GUIDE.md](guides/SUPERVISION_GUIDE.md)** - Uso de Supervision v0.29.0
- **[SUPERVISION_IMPROVEMENTS.md](guides/SUPERVISION_IMPROVEMENTS.md)** - Mejoras implementadas

### Análisis y Métricas
- **[DISTANCE_VELOCITY_GUIDE.md](guides/DISTANCE_VELOCITY_GUIDE.md)** - Cálculo de velocidad y distancia
- **[QUICK_START_STATS_AGGREGATOR.md](guides/QUICK_START_STATS_AGGREGATOR.md)** - Agregación de estadísticas
- **[QUICKSTART_ANALISIS.md](guides/QUICKSTART_ANALISIS.md)** - Análisis de datos

### Optimización
- **[OPTIMIZATION_GUIDE.md](guides/OPTIMIZATION_GUIDE.md)** - Optimización de rendimiento
- **[IMPROVEMENTS_SUMMARY.md](guides/IMPROVEMENTS_SUMMARY.md)** - Resumen de mejoras

---

## 📦 Reportes Técnicos

- **[IMPLEMENTATION_REPORT.txt](guides/IMPLEMENTATION_REPORT.txt)** - Informe de implementación

---

## 📂 Archivos Archivados

Documentación de desarrollo anterior y reportes de fases completadas:

- **[/archived/](archived/)** - Contiene:
  - Reportes de FASE_1 a FASE_6
  - Documentación de calibración adaptativa
  - Integración con StatsBomb
  - Análisis históricos de arquitectura
  - Planes y checklists completados

---

## 🗂️ Estructura del Proyecto

```
.
├── docs/                                  # Esta carpeta
│   ├── guides/                           # Guías principales
│   │   ├── DEEP_SORT_INTEGRATION_GUIDE.md
│   │   ├── QUICK_START.md
│   │   └── ...
│   ├── archived/                         # Documentación histórica
│   │   ├── FASE_1_*.md
│   │   ├── FASE_2_*.md
│   │   └── ...
│   └── README.md                         # Este archivo
│
├── core/                                  # Módulos core
│   ├── detector.py
│   ├── bytetrack_adapter.py
│   └── supervision_utils.py
│
├── deep_sort_integration/                 # Deep SORT integrado
│   ├── kalman_filter.py
│   ├── feature_extractor.py
│   └── deep_sort_tracker.py
│
├── football_tracking_integration/         # Análisis de fútbol
│   ├── improved_detector.py
│   ├── improved_team_assigner.py
│   └── improved_metrics.py
│
├── tests/                                 # Suite de tests
├── utils/                                 # Utilidades
├── main_deep_sort_integrated.py           # Pipeline principal
├── 1_preparar.py                          # Preparación
├── 2_analizar.py                          # Análisis
└── README.md                              # README principal
```

---

## 🎯 Próximos Pasos

1. **Leer QUICK_START.md** - Setup inicial (5 min)
2. **Leer DEEP_SORT_INTEGRATION_GUIDE.md** - Entender tracking (10 min)
3. **Ejecutar main_deep_sort_integrated.py** - Test en video real (variable)
4. **Revisar IMPLEMENTATION_GUIDE.md** - Integración en tu código (15 min)

---

## 📞 Soporte

Para preguntas sobre:
- **Deep SORT**: Ver `guides/DEEP_SORT_INTEGRATION_GUIDE.md`
- **Supervision**: Ver `guides/SUPERVISION_GUIDE.md`
- **Tracking**: Ver `guides/PLAYER_TRACKING_ANALYSIS.md`
- **Histórico**: Ver `archived/FASE_*.md`

---

**Última actualización**: 24 Septiembre 2026

🤖 Generated with [Claude Code](https://claude.com/claude-code)

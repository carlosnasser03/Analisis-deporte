# QUICKSTART: Sistema de Análisis Scout AI - FASE 5 ⚽

**¡Inicia en 5 minutos!**

---

## 🚀 Instalación Rápida

### Paso 1: Preparar entorno
```bash
# Clonar repositorio
git clone https://github.com/carlosnasser03/Analisis-deporte.git
cd Analisis-deporte

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o en Windows:
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### Paso 2: Verificar instalación
```bash
python -c "from pipeline.integrated_pipeline import IntegratedAnalysisPipeline; print('✓ Sistema listo')"
```

---

## 📊 Uso Básico (3 líneas)

```python
from pipeline.integrated_pipeline import process_video_simple
from core.interactive_dashboard import generate_dashboard_simple

# Procesar video
result = process_video_simple("video.mp4", output_dir="results/")

# Generar dashboard
generate_dashboard_simple(result.player_stats, result.team_summary, "results/dashboard.html")

# Abrir en navegador
import webbrowser
webbrowser.open("results/dashboard.html")
```

**Eso es. Ya tienes tu dashboard interactivo.** 🎉

---

## 📁 Estructura del Proyecto

```
Analisis-deporte/
├── pipeline/
│   └── integrated_pipeline.py     ← Pipeline completo
├── core/
│   ├── detector.py                ← Detección YOLO
│   ├── tracker.py                 ← Rastreo
│   ├── distance_velocity_calculator.py
│   ├── intensity_analyzer.py
│   ├── heatmap_generator.py
│   ├── player_stats_aggregator.py
│   └── interactive_dashboard.py   ← Dashboard HTML
├── tests/                         ← Tests
├── data/
│   └── videos/                    ← Videos de entrada
├── results/                       ← Outputs generados
├── requirements.txt               ← Dependencias
└── README.md
```

---

## 🎯 Ejemplos Comunes

### ✅ Procesar un video
```python
from pipeline.integrated_pipeline import IntegratedAnalysisPipeline

pipeline = IntegratedAnalysisPipeline()
result = pipeline.process_video("mi_video.mp4", output_dir="resultados/")

print(f"Frames procesados: {result.frames_processed}")
print(f"Jugadores: {len(result.player_stats)}")
```

### ✅ Generar dashboard personalizado
```python
from core.interactive_dashboard import DashboardGenerator, DashboardConfig

config = DashboardConfig(
    title="Mi Equipo - Análisis",
    organization_name="Mi Club",
)

gen = DashboardGenerator(config)
gen.generate_dashboard(
    result.player_stats,
    result.team_summary,
    "dashboard.html"
)
```

### ✅ Ver estadísticas de un jugador
```python
player_7_stats = result.player_stats["7"]
print(f"Distancia: {player_7_stats.get('distance_total_m', 0):.0f}m")
print(f"Velocidad máx: {player_7_stats.get('max_velocity_m_s', 0):.1f} m/s")
print(f"Intensidad: {player_7_stats.get('movement_intensity_percent', 0):.1f}%")
```

### ✅ Exportar datos a JSON
```python
import json
from pathlib import Path

# Los resultados ya están en formato dict
with open("datos_completos.json", "w") as f:
    json.dump(result.__dict__, f, indent=2, default=str)
```

---

## 📊 El Dashboard Interactivo Incluye

```
┌─────────────────────────────────┐
│  TABLA DE JUGADORES             │
│  [🔍 Buscar...]                │
│  • Distancia recorrida          │
│  • Velocidades (max, prom, P90) │
│  • Intensidad de movimiento     │
│  • Sprints y cambios de dirección
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│  MAPA DEL CAMPO                 │
│  • Posiciones de jugadores      │
│  • Heatmap de densidad          │
│  • Formación táctica visible    │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│  GRÁFICOS INTERACTIVOS          │
│  • Distancia comparativa        │
│  • Velocidad by player          │
│  • Intensidad por jugador       │
└─────────────────────────────────┘
         ↓
┌─────────────────────────────────┐
│  RESUMEN DE EQUIPO              │
│  • Jugadores analizados         │
│  • Distancia promedio           │
│  • Intensidad promedio          │
│  • Total de sprints             │
└─────────────────────────────────┘
```

---

## ⚙️ Configuración Común

### Cambiar FPS del video
```python
from pipeline.integrated_pipeline import ProcessingConfig

config = ProcessingConfig(fps=25.0)  # Cambiar a 25 fps
pipeline = IntegratedAnalysisPipeline(config)
```

### Ajustar umbrales de confianza
```python
config = ProcessingConfig(confidence_threshold=0.6)
```

### Calibrar escala (píxeles a metros)
```python
config = ProcessingConfig(pixels_per_meter=12.5)
```

---

## 🔍 Buscar en el Dashboard

1. Abre `dashboard.html` en tu navegador
2. En la sección "Estadísticas de Jugadores"
3. Usa la barra de búsqueda para filtrar por:
   - Número de jugador
   - Distancia
   - Velocidad
   - Intensidad

La búsqueda es en **tiempo real** mientras escribes.

---

## 📈 Interpretar los Datos

### Distancia (metros)
- **Defensa:** 8,000-10,500 m
- **Mediocampo:** 10,000-13,000 m
- **Delantero:** 8,000-11,000 m

### Velocidad Máxima (m/s)
- **Baja:** < 8.0 m/s
- **Normal:** 8-9 m/s
- **Buena:** > 9 m/s

### Intensidad (%)
- **Baja:** < 60%
- **Normal:** 60-75%
- **Alta:** > 75%

### Sprints
- **Pocos:** < 5 por partido
- **Normal:** 8-12 por partido
- **Muchos:** > 12 por partido

---

## 🐛 Troubleshooting

### "ModuleNotFoundError"
```bash
# Asegúrate de instalar dependencias
pip install -r requirements.txt
```

### "Video no encontrado"
```python
# Usa rutas absolutas o relativas correctas
result = process_video_simple("/ruta/absoluta/video.mp4")
# o desde la carpeta data:
result = process_video_simple("data/videos/video.mp4")
```

### "Dashboard no se ve bien"
```python
# Asegúrate de abrir en navegador moderno
# Chrome, Firefox, Safari, Edge son compatibles
```

### Gráficos no se ven
```bash
# Instala Plotly para gráficos interactivos
pip install plotly
```

---

## 📚 Documentación Completa

- **README.md** - Guía principal del proyecto
- **FASE_5_PLAN.md** - Plan de implementación
- **FASE_5_FINAL_REPORT.md** - Informe técnico completo
- **CONTRIBUTING.md** - Cómo contribuir

---

## 🎬 Próximos Pasos

1. ✅ **Ejecutar en tu video** - Procesa tu propio video
2. ✅ **Explorar dashboard** - Interactúa con los datos
3. ✅ **Compartir resultados** - El HTML es standalone
4. ✅ **Mejorar** - Ajusta parámetros según necesites

---

## 💡 Tips Pro

- 📊 **Exportar datos:** Los JSON están listos en `results/`
- 🌐 **Compartir dashboard:** Solo necesitas enviar el `.html`
- 🔄 **Procesar batch:** Cambia script para loops de videos
- 📈 **Comparar partidos:** Genera dashboard para cada video

---

## 🤝 Soporte

- 📖 Lee la documentación incluida
- 💬 Revisa los comentarios en el código
- 🧪 Ejecuta los tests: `pytest tests/ -v`
- 📧 Contacto: carlosnasser03@gmail.com

---

**¡Listo para empezar!** Ejecuta tu primer análisis ahora. 🚀


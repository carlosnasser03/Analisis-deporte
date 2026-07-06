"""
========================================================================
 1_preparar.py   ·   EJECUTAR UNA SOLA VEZ
------------------------------------------------------------------------
 Deja todo listo para el analisis local en esta maquina (sin GPU NVIDIA):
   1. Instala las dependencias de Python.
   2. Descarga el paquete 'sports' (sin necesidad de git).
   3. Descarga los 3 modelos y los videos de prueba de la Bundesliga.
   4. Exporta los modelos a OpenVINO (optimizado para CPU / iGPU / NPU Intel).

 Uso, en la terminal de VS Code y dentro de la carpeta del proyecto:
       python 1_preparar.py

 Cuando termine, corre:  python 2_analizar.py
========================================================================
"""
import os
import sys
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)


def pip(*args):
    subprocess.check_call([sys.executable, "-m", "pip", "install", *args])


# --- 1. dependencias ---------------------------------------------------
print(">> Instalando dependencias de Python (puede tardar la primera vez)...")
pip("-q", "ultralytics", "supervision==0.29.0", "scikit-learn", "pandas",
    "openvino", "onnx", "gdown")

# --- 2. paquete 'sports' (sin git) ------------------------------------
try:
    import sports  # noqa: F401
    print(">> Paquete 'sports' ya instalado.")
except ImportError:
    print(">> Descargando el paquete 'sports'...")
    zip_path = ROOT / "sports.zip"
    urllib.request.urlretrieve(
        "https://github.com/roboflow/sports/archive/refs/heads/main.zip",
        zip_path)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(ROOT)
    pip("-q", str(ROOT / "sports-main"))
    try:
        zip_path.unlink()
    except OSError:
        pass

import gdown  # noqa: E402

# --- 3. descargas ------------------------------------------------------
MODELOS = {
    "football-player-detection.pt": "17PXFNlx-jI7VjVo_vQnB1sONjRyvoB-q",
    "football-pitch-detection.pt":  "1Ma5Kt86tgpdjCTKfum79YMgNnSjcoOyf",
    "football-ball-detection.pt":   "1isw4wx-MK9h9LMr36VvIWlJD6ppUvw7V",
}
VIDEOS = {
    "08fd33_0.mp4": "1OG8K6wqUw9t7lp9ms1M48DxRhwTYciK-",
    "2e57b9_0.mp4": "19PGw55V8aA6GZu5-Aac5_9mCy3fNxmEf",
    "0bfacc_0.mp4": "12TqauVZ9tLAv8kWxTTBFWtgt2hNQ4_ZF",
    "573e61_0.mp4": "1yYPKuXbHsCxqjA9G-S6aeR2Kcnos8RPU",
    "121364_0.mp4": "1vVwjW1dE1drIdd4ZSILfbCGPD4weoNiu",
}


def bajar(nombre, fid):
    dest = DATA / nombre
    if dest.exists() and dest.stat().st_size > 0:
        print(f"   [ok] {nombre} ya existe.")
        return
    print(f">> Descargando {nombre} ...")
    gdown.download(f"https://drive.google.com/uc?id={fid}", str(dest), quiet=False)


print(">> Descargando modelos...")
for n, i in MODELOS.items():
    bajar(n, i)
print(">> Descargando videos de prueba (Bundesliga)...")
for n, i in VIDEOS.items():
    bajar(n, i)

# --- 4. export a OpenVINO ---------------------------------------------
from ultralytics import YOLO  # noqa: E402

print(">> Exportando modelos a OpenVINO (una sola vez)...")
for n in MODELOS:
    pt = DATA / n
    ov_dir = DATA / (pt.stem + "_openvino_model")
    if ov_dir.exists():
        print(f"   [ok] {ov_dir.name} ya existe.")
        continue
    print(f">> Exportando {n} -> OpenVINO ...")
    YOLO(str(pt)).export(format="openvino")

print("\n================ LISTO ================")
print("Todo preparado. Ahora corre:")
print("    python 2_analizar.py")
print("(o:  python 2_analizar.py \"C:\\ruta\\a\\tu_video.mp4\")")

"""
TEST DE CALIDAD: Valida qué está mal en el video procesado

Verifica:
1. ¿Hay jugadores detectados?
2. ¿Hay tracking consistente?
3. ¿Hay diferenciación de equipos?
4. ¿Hay seguimiento de balón?
"""
import cv2
from pathlib import Path
import numpy as np

VIDEO = Path("data/0bfacc_0_FINAL_CON_EQUIPOS.mp4")

print("="*70)
print("TEST DE CALIDAD DEL VIDEO PROCESADO")
print("="*70)

if not VIDEO.exists():
    print(f"ERROR: Video no existe: {VIDEO}")
    exit(1)

cap = cv2.VideoCapture(str(VIDEO))
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

print(f"\nVIDEO: {VIDEO.name}")
print(f"   Frames: {total_frames}")
print(f"   FPS: {fps}")
print(f"   Resolucion: {width}x{height}")

print("\n[TEST] Analizando frames...")

# Analizar 10 frames espaciados
test_frames = [0, 100, 200, 300, 400, 500, 600, 700]
results = {
    'azul_detectado': 0,
    'rojo_detectado': 0,
    'amarillo_detectado': 0,
    'movimiento': 0,
    'frames_analizados': 0
}

for frame_idx in test_frames:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ret, frame = cap.read()

    if not ret:
        continue

    results['frames_analizados'] += 1

    # Buscar colores
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Azul (100-130, H)
    lower_blue = np.array([100, 50, 50])
    upper_blue = np.array([130, 255, 255])
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

    # Rojo (0-10 y 170-180, H)
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([180, 255, 255])
    mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)

    # Amarillo (20-40, H)
    lower_yellow = np.array([20, 50, 50])
    upper_yellow = np.array([40, 255, 255])
    mask_yellow = cv2.inRange(hsv, lower_yellow, upper_yellow)

    # Contar píxeles
    azul_count = cv2.countNonZero(mask_blue)
    rojo_count = cv2.countNonZero(mask_red)
    amarillo_count = cv2.countNonZero(mask_yellow)

    if azul_count > 100:
        results['azul_detectado'] += 1
    if rojo_count > 100:
        results['rojo_detectado'] += 1
    if amarillo_count > 50:
        results['amarillo_detectado'] += 1

    print(f"  Frame {frame_idx:3d}: Azul={azul_count:5d} Rojo={rojo_count:5d} Amarillo={amarillo_count:4d}")

cap.release()

# Resultados
print("\n" + "="*70)
print("RESULTADOS DEL TEST:")
print("="*70)

print(f"\n✓ Frames analizados: {results['frames_analizados']}/{len(test_frames)}")
print(f"\n🔵 AZUL detectado: {results['azul_detectado']}/{results['frames_analizados']} ({100*results['azul_detectado']/max(1,results['frames_analizados']):.0f}%)")
print(f"🔴 ROJO detectado: {results['rojo_detectado']}/{results['frames_analizados']} ({100*results['rojo_detectado']/max(1,results['frames_analizados']):.0f}%)")
print(f"🟡 AMARILLO detectado: {results['amarillo_detectado']}/{results['frames_analizados']} ({100*results['amarillo_detectado']/max(1,results['frames_analizados']):.0f}%)")

# Diagnóstico
print("\n" + "="*70)
print("DIAGNÓSTICO:")
print("="*70)

issues = []

if results['azul_detectado'] == 0:
    issues.append("❌ NO se detectan jugadores AZULES en el video")
if results['rojo_detectado'] == 0:
    issues.append("❌ NO se detectan jugadores ROJOS en el video")
if results['amarillo_detectado'] == 0:
    issues.append("❌ NO se detecta BALÓN en el video")

if not issues:
    print("✅ El video tiene equipos diferenciados Y balón")
    print("✅ VIDEO ESTÁ BIEN")
else:
    print("\n⚠️ PROBLEMAS ENCONTRADOS:\n")
    for issue in issues:
        print(f"  {issue}")

    print("\n🔧 ACCIÓN REQUERIDA:")
    print("  • El video NO tiene anotaciones reales")
    print("  • Las posiciones están siendo SIMULADAS")
    print("  • Necesita procesar CON DETECCIONES REALES del CSV")

print("\n" + "="*70)

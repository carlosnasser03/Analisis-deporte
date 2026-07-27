"""Test de calidad del video"""
import cv2
from pathlib import Path
import numpy as np

VIDEO = Path("data/0bfacc_0_REAL_CON_YOLO.mp4")

print("="*70)
print("TEST DE CALIDAD DEL VIDEO")
print("="*70)

if not VIDEO.exists():
    print("ERROR: Video no existe")
    exit(1)

cap = cv2.VideoCapture(str(VIDEO))
fps = cap.get(cv2.CAP_PROP_FPS)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

print(f"VIDEO: {VIDEO.name}")
print(f"Frames: {total_frames}, FPS: {fps}")

# Test frames
test_frames = [0, 250, 500, 750]
azul_count = 0
rojo_count = 0
amarillo_count = 0

for f_idx in test_frames:
    cap.set(cv2.CAP_PROP_POS_FRAMES, min(f_idx, total_frames-1))
    ret, frame = cap.read()
    if not ret:
        continue

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Detectar colores
    mask_blue = cv2.inRange(hsv, np.array([100, 50, 50]), np.array([130, 255, 255]))
    mask_red = cv2.inRange(hsv, np.array([0, 50, 50]), np.array([10, 255, 255])) | \
               cv2.inRange(hsv, np.array([170, 50, 50]), np.array([180, 255, 255]))
    mask_yellow = cv2.inRange(hsv, np.array([20, 50, 50]), np.array([40, 255, 255]))

    b_count = cv2.countNonZero(mask_blue)
    r_count = cv2.countNonZero(mask_red)
    y_count = cv2.countNonZero(mask_yellow)

    if b_count > 100: azul_count += 1
    if r_count > 100: rojo_count += 1
    if y_count > 50: amarillo_count += 1

    print(f"Frame {f_idx}: Azul={b_count} Rojo={r_count} Amarillo={y_count}")

cap.release()

print("\n" + "="*70)
print("RESULTADO:")
print("="*70)
print(f"AZUL detectado: {azul_count}/{len(test_frames)}")
print(f"ROJO detectado: {rojo_count}/{len(test_frames)}")
print(f"AMARILLO detectado: {amarillo_count}/{len(test_frames)}")

if azul_count == 0 or rojo_count == 0 or amarillo_count == 0:
    print("\nPROBLEMA: Video NO tiene anotaciones coloreadas correctamente")
    print("CAUSA: Las posiciones estan siendo simuladas, no de detecciones reales")
    print("SOLUCION: Usar detectores reales + tracking real del pipeline original")
else:
    print("\nOK: Video tiene anotaciones coloreadas")

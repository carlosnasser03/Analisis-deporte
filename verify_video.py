import cv2
from pathlib import Path

video_path = Path("data/videos/test_match_30s_ANALIZADO.mp4")

print(f"Archivo existe: {video_path.exists()}")
if video_path.exists():
    print(f"Tamaño: {video_path.stat().st_size / (1024*1024):.1f} MB")

    # Intentar abrir
    cap = cv2.VideoCapture(str(video_path))
    if cap.isOpened():
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"\nVideo ABIERTO correctamente:")
        print(f"  Frames: {frames}")
        print(f"  FPS: {fps}")
        print(f"  Resolucion: {width}x{height}")

        # Leer primer frame
        ret, frame = cap.read()
        if ret:
            print(f"  Primer frame: OK ({frame.shape})")
        else:
            print(f"  Primer frame: FALLO")

        cap.release()
    else:
        print("ERROR: No se puede abrir el video")
        print("El video esta corrupto")
else:
    print("ERROR: Archivo no existe")

"""Extract key frames from processed video"""
import cv2
import numpy as np
from pathlib import Path
import base64
import json

video_path = Path('data/videos/test_match_30s_ANALIZADO.mp4')

if not video_path.exists():
    print('Error: Video no encontrado')
    exit(1)

cap = cv2.VideoCapture(str(video_path))
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps = cap.get(cv2.CAP_PROP_FPS)

print(f'Video: {total_frames} frames @ {fps} FPS')

# Extraer frames clave
key_frames = [0, 150, 300, 450, 600, 700]
frames_data = []

for frame_num in key_frames:
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
    ret, frame = cap.read()

    if ret:
        # Convertir a JPEG base64
        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')

        time_sec = frame_num / fps

        frames_data.append({
            'frame_num': frame_num,
            'time': time_sec,
            'base64': frame_b64
        })

        print(f'Frame {frame_num} ({time_sec:.1f}s) extracted')

cap.release()

# Guardar datos para el HTML
output = {
    'total_frames': total_frames,
    'fps': fps,
    'frames': frames_data
}

import os
os.makedirs('scratchpad', exist_ok=True)

with open('scratchpad/frames_data.json', 'w') as f:
    json.dump(output, f)

print(f'Extracted {len(frames_data)} frames')
print('Saved to scratchpad/frames_data.json')

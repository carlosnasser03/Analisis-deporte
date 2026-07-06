"""
================================================================================
 0_validate.py   ·   FASE 1: DIAGNÓSTICO DE LÍNEA BASE
================================================================================
 Propósito: Validar modelos actuales en videos existentes y detectar:
  1. Confianza de detecciones
  2. Frecuencia de fallos
  3. Frames "difíciles" para anotación manual
  4. Cuellos de botella principales

 USO:
   python scripts/0_validate.py
   python scripts/0_validate.py --device intel:cpu --skip 2
   python scripts/0_validate.py --max-frames 500  # solo primeros 500 frames

 Output:
   - data/logs/frames_*.csv        (métricas por frame)
   - data/logs/summary_*.json      (resumen estadístico)
   - data/logs/difficult_frames.txt (frames para anotar)

================================================================================
"""
import os
import sys
import argparse
from pathlib import Path
from collections import defaultdict

import numpy as np
import cv2
import yaml

# Imports de nuestro proyecto
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.metrics import DetectionMetrics
from core.homography_validator import HomographyValidator

# Imports de librerías externas
import supervision as sv
from ultralytics import YOLO
from sports.common.view import ViewTransformer
from sports.configs.soccer import SoccerPitchConfiguration

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG_FILE = ROOT / "config" / "detection_config.yaml"

# Cargar configuración
with open(CONFIG_FILE) as f:
    CONFIG = yaml.safe_load(f)

# Argumentos
ap = argparse.ArgumentParser(
    description="Validación de línea base de modelos YOLO"
)
ap.add_argument(
    "--device",
    default=CONFIG['device']['primary'],
    help="intel:cpu | intel:gpu | intel:npu | cpu"
)
ap.add_argument(
    "--skip",
    type=int,
    default=CONFIG['processing']['frame_skip'],
    help="Procesar 1 de cada N frames"
)
ap.add_argument(
    "--max-frames",
    type=int,
    default=None,
    help="Límite de frames a procesar"
)
ap.add_argument(
    "--videos",
    type=str,
    default=None,
    help="Ruta específica de video (o dejar en blanco para usar todos)"
)

args = ap.parse_args()

DEVICE = args.device
FRAME_SKIP = max(1, args.skip)
MAX_FRAMES = args.max_frames

print("\n" + "="*70)
print("FASE 1: VALIDACIÓN DE LÍNEA BASE")
print("="*70)
print(f"Dispositivo: {DEVICE}")
print(f"Salteo de frames: 1/{FRAME_SKIP}")
if MAX_FRAMES:
    print(f"Máximo frames: {MAX_FRAMES}")
print("="*70 + "\n")

# ============================================================================
# CARGAR MODELOS
# ============================================================================

def cargar_modelo(nombre, task):
    """Carga modelo OpenVINO si existe, si no usa formato .pt"""
    ov = DATA / (Path(nombre).stem + "_openvino_model")
    pt = DATA / nombre

    if ov.exists():
        print(f"  ✓ Usando modelo OpenVINO: {ov.name}")
        return YOLO(str(ov), task=task)
    elif pt.exists():
        print(f"  ✓ Usando modelo .pt: {pt.name}")
        return YOLO(str(pt), task=task)
    else:
        sys.exit(f"ERROR: No encuentro modelo {nombre}. Ejecuta 1_preparar.py primero")


print(">> Cargando modelos YOLO...")
player_model = cargar_modelo("football-player-detection.pt", "detect")
pitch_model = cargar_modelo("football-pitch-detection.pt", "pose")
ball_model = cargar_modelo("football-ball-detection.pt", "detect")
print()

# ============================================================================
# OBTENER VIDEOS A VALIDAR
# ============================================================================

if args.videos:
    videos_to_validate = [Path(args.videos)]
else:
    # Usar videos de prueba default
    videos_to_validate = list((DATA).glob("*.mp4"))[:5]  # Primeros 5 videos

if not videos_to_validate:
    sys.exit("ERROR: No encuentro videos en data/")

print(f">> Validando {len(videos_to_validate)} video(s):\n")
for i, v in enumerate(videos_to_validate, 1):
    print(f"   {i}. {v.name}")
print()

# ============================================================================
# CONFIGURACIÓN DE CANCHA
# ============================================================================

CONFIG_PITCH = SoccerPitchConfiguration()
PITCH_V = np.array(CONFIG_PITCH.vertices, dtype=np.float32)

pnames = player_model.names
pids = [i for i, n in pnames.items() if n.lower() in ("player", "goalkeeper")]
if not pids:
    pids = [i for i, n in pnames.items()
            if "ball" not in n.lower() and "refer" not in n.lower()]

# ============================================================================
# PROCESAMIENTO
# ============================================================================

all_results = []

for video_path in videos_to_validate:
    print(f"\n{'='*70}")
    print(f"📹 Procesando: {video_path.name}")
    print(f"{'='*70}")

    if not video_path.exists():
        print(f"  ⚠ Video no encontrado, saltando...")
        continue

    video_stem = video_path.stem
    metrics = DetectionMetrics(output_dir=str(DATA / "logs"), video_name=video_stem)

    try:
        # Información del video
        info = sv.VideoInfo.from_video_path(str(video_path))
        fps = info.fps or 25
        total_frames = int(info.frame_count) if hasattr(info, 'frame_count') else 999999

        print(f"  Resolución: {info.width}x{info.height} | FPS: {fps} | Frames: ~{total_frames}")

    except Exception as e:
        print(f"  ERROR al leer video: {e}")
        continue

    # Procesar frames
    processed = 0
    T_last = None  # Última transformación válida

    try:
        for idx, frame in enumerate(sv.get_video_frames_generator(str(video_path))):
            # Controles de limite
            if MAX_FRAMES is not None and processed >= MAX_FRAMES:
                break
            if idx % FRAME_SKIP != 0:
                continue

            # ================================================================
            # DETECCIÓN DE CANCHA (Pitch)
            # ================================================================
            pitch_confidence = 0.0
            homography_valid = False
            homography_quality = 0.0
            valid_keypoints = 0
            T = None

            try:
                pres = pitch_model(frame, verbose=False, device=DEVICE)[0]
                kp = sv.KeyPoints.from_ultralytics(pres)
                kc = kp.keypoint_confidence

                if kc is not None and len(kc) > 0:
                    pitch_confidence = float(np.mean(kc[0]))
                    valid_mask = kc[0] > 0.5
                    valid_keypoints = int(np.sum(valid_mask))

                    if valid_keypoints >= 4:
                        # Validar homografía
                        validator = HomographyValidator(
                            kp.xy[0][valid_mask].astype(np.float32),
                            kc[0][valid_mask],
                            PITCH_V[:valid_keypoints]
                        )

                        homography_quality = validator.get_quality_score()
                        homography_valid = validator.is_valid()

                        if homography_valid:
                            T = ViewTransformer(
                                source=kp.xy[0][valid_mask].astype(np.float32),
                                target=PITCH_V[valid_mask]
                            )
                            T_last = T

            except Exception as e:
                # print(f"    ERROR detección cancha: {e}")
                pass

            # ================================================================
            # DETECCIÓN DE JUGADORES (Players)
            # ================================================================
            player_confidence = 0.0
            player_count = 0

            try:
                res = player_model(frame, classes=pids, device=DEVICE, verbose=False)[0]
                d = sv.Detections.from_ultralytics(res)

                if len(d) > 0:
                    player_confidence = float(np.mean(d.confidence))
                    player_count = len(d)

            except Exception as e:
                # print(f"    ERROR detección jugadores: {e}")
                pass

            # ================================================================
            # DETECCIÓN DE BALÓN (Ball)
            # ================================================================
            ball_confidence = 0.0

            try:
                bres = ball_model(frame, device=DEVICE, verbose=False)[0]
                db = sv.Detections.from_ultralytics(bres)

                if len(db) > 0:
                    ball_confidence = float(np.mean(db.confidence))

            except Exception as e:
                # print(f"    ERROR detección balón: {e}")
                pass

            # ================================================================
            # REGISTRAR MÉTRICAS
            # ================================================================
            metrics.log_frame(
                frame_idx=idx,
                data={
                    'player_confidence': player_confidence,
                    'player_count': player_count,
                    'ball_confidence': ball_confidence,
                    'pitch_confidence': pitch_confidence,
                    'pitch_keypoints_valid': valid_keypoints,
                    'homography_valid': homography_valid,
                    'homography_quality': homography_quality,
                    'team_accuracy': 0.0,  # No se calcula en validación
                }
            )

            processed += 1

            # Mostrar progreso
            if processed % 100 == 0:
                print(f"  ✓ {processed} frames procesados... "
                      f"(frame real: {idx}/{total_frames})")

    except KeyboardInterrupt:
        print("\n  ⚠ Validación interrumpida por usuario")
    except Exception as e:
        print(f"  ERROR: {e}")

    print(f"  ✓ Total: {processed} frames procesados")

    # ====================================================================
    # EXPORTAR RESULTADOS DEL VIDEO
    # ====================================================================
    metrics.print_summary()
    metrics.export_csv()
    metrics.export_summary()

    # Identificar frames difíciles
    difficult = metrics.identify_difficult_frames(threshold=0.5)
    if difficult:
        difficult_file = DATA / "logs" / f"difficult_frames_{video_stem}.txt"
        with open(difficult_file, 'w') as f:
            f.write(f"Frames difíciles para {video_stem}\n")
            f.write("="*50 + "\n\n")
            for item in difficult[:50]:  # Top 50
                f.write(f"Frame {item['frame']:5d} | "
                        f"Conf: {item['confidence_score']:.2f} | "
                        f"{item['reason']}\n")
        print(f"  📝 Frames difíciles guardados: {difficult_file.name}")

    all_results.append({
        'video': video_path.name,
        'metrics': metrics.get_summary(),
        'difficult_count': len(difficult),
    })

# ============================================================================
# RESUMEN FINAL
# ============================================================================

print("\n" + "="*70)
print("RESUMEN GENERAL")
print("="*70)

for result in all_results:
    print(f"\n📹 {result['video']}")
    metrics_dict = result['metrics']

    if 'player_confidence' in metrics_dict:
        pc = metrics_dict['player_confidence']
        print(f"  Player: {pc['mean']:.2f} (min: {pc['min']:.2f}, max: {pc['max']:.2f})")

    if 'ball_confidence' in metrics_dict:
        bc = metrics_dict['ball_confidence']
        print(f"  Ball:   {bc['mean']:.2f} (min: {bc['min']:.2f}, max: {bc['max']:.2f})")

    if 'pitch_confidence' in metrics_dict:
        pitchc = metrics_dict['pitch_confidence']
        print(f"  Pitch:  {pitchc['mean']:.2f} (min: {pitchc['min']:.2f}, max: {pitchc['max']:.2f})")

    if 'failure_rates' in metrics_dict:
        print(f"  Fallos: {metrics_dict['failure_rates']}")

print("\n" + "="*70)
print("✓ VALIDACIÓN COMPLETADA")
print(f"📊 Resultados guardados en: {DATA / 'logs'}")
print("="*70 + "\n")

"""
Procesa video real 0bfacc_0.mp4 usando TODA la arquitectura completa

Incluye:
- Detección YOLO (jugadores, balón, cancha)
- Validación homografía
- Tracking ByteTrack
- Clasificación de equipos
- Detección de árbitro y porteros
- Seguimiento de balón
- Cálculo distancia/velocidad
- Generación de video anotado
"""
import sys
from pathlib import Path

# Agregar rutas
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.video_processor import VideoProcessor
from core.metrics import FrameMetrics
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("="*70)
    logger.info("SCOUT AI - Procesamiento Completo de Video Real")
    logger.info("="*70)

    # Configuración
    video_path = Path("data/0bfacc_0.mp4")
    output_video = Path("data/0bfacc_0_COMPLETO.mp4")

    if not video_path.exists():
        logger.error(f"Video no encontrado: {video_path}")
        return False

    logger.info(f"\nVideo: {video_path}")
    logger.info(f"Output: {output_video}")

    # Usar el VideoProcessor completo
    try:
        logger.info("\nIniciando VideoProcessor...")

        processor = VideoProcessor(
            video_path=str(video_path),
            output_video_path=str(output_video),
            config_path="config/detection_config.yaml"
        )

        logger.info("VideoProcessor inicializado correctamente")
        logger.info("\nProcesando video...")

        # Procesar
        results = processor.process()

        if results:
            logger.info("\n" + "="*70)
            logger.info("✓ PROCESAMIENTO COMPLETADO EXITOSAMENTE")
            logger.info("="*70)

            logger.info(f"\nResultados:")
            logger.info(f"  Frames procesados: {results.get('frames_processed', 0)}")
            logger.info(f"  Duración: {results.get('duration', 0):.1f} segundos")
            logger.info(f"  FPS promedio: {results.get('fps', 0):.1f}")

            logger.info(f"\nVideo anotado guardado en:")
            logger.info(f"  {output_video}")

            if output_video.exists():
                size_mb = output_video.stat().st_size / (1024*1024)
                logger.info(f"  Tamaño: {size_mb:.1f} MB")

            logger.info("\nQué incluye el video:")
            logger.info("  ✓ Bounding boxes de jugadores (diferenciados por equipo)")
            logger.info("  ✓ IDs de tracking persistentes")
            logger.info("  ✓ Seguimiento de balón")
            logger.info("  ✓ Identificación de árbitro")
            logger.info("  ✓ Identificación de porteros")
            logger.info("  ✓ Líneas de movimiento")
            logger.info("  ✓ Estadísticas en tiempo real")
            logger.info("  ✓ Validación de jugadores dentro del campo")

            return True
        else:
            logger.error("El procesador devolvió resultados vacíos")
            return False

    except Exception as e:
        logger.error(f"Error durante procesamiento: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

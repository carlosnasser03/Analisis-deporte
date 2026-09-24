"""
Test específico para validar la inicialización del detector en integrated_pipeline.py

Este test reproduce el escenario del problema original:
- 750 frames procesados
- Validator que el detector.detect() NO lanza 'NoneType' object has no attribute 'detect'
"""

import pytest
import numpy as np
from pathlib import Path
from pipeline.integrated_pipeline import IntegratedAnalysisPipeline, ProcessingConfig


class TestDetectorNotNone:
    """Test que el detector NO es None y funciona correctamente."""

    def test_detector_initialized_on_creation(self):
        """
        VALIDACIÓN CRÍTICA: El detector debe estar inicializado en __init__
        No debe ser None cuando se crea el pipeline.
        """
        pipeline = IntegratedAnalysisPipeline()

        # Esto era el problema original - detector era None
        assert pipeline.detector is not None, (
            "❌ DETECTOR ES NONE - Problema no resuelto. "
            "El detector debe inicializarse en __init__() con UnifiedDetector"
        )

    def test_detector_has_required_methods(self):
        """El detector debe tener los métodos necesarios."""
        pipeline = IntegratedAnalysisPipeline()

        if pipeline.detector is None:
            pytest.skip("Detector no inicializado")

        # Verificar métodos existentes
        assert hasattr(pipeline.detector, 'detect_frame'), (
            "Detector debe tener método 'detect_frame'"
        )
        assert callable(pipeline.detector.detect_frame), (
            "detect_frame debe ser callable"
        )

    def test_process_750_frames_no_errors(self):
        """
        VALIDACIÓN DEL PROBLEMA ORIGINAL:
        Procesar 750 frames dummy sin que se lance 'NoneType' object has no attribute

        Problema original:
        - 750 frames → 750 errores: 'NoneType' object has no attribute 'detect'
        - 0 jugadores analizados

        Solución:
        - detector inicializado correctamente
        - detect_frame() llamado sin error
        """
        pipeline = IntegratedAnalysisPipeline()

        if pipeline.detector is None:
            pytest.skip("Detector no inicializado - modelos no disponibles")

        # Crear frames dummy (720x1280x3) como en el problema original
        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

        # Procesar 750 frames (cantidad del problema original)
        frame_count = 750
        error_count = 0
        success_count = 0

        for frame_idx in range(frame_count):
            try:
                # Esto es lo que ocurría antes (línea 341 de integrated_pipeline.py):
                # detections = self.detector.detect(frame)  # ← detector era None

                # Ahora se hace correctamente:
                result = pipeline._process_frame(dummy_frame, frame_idx)

                # Validar que result es válido
                assert result is not None
                assert result.frame_idx == frame_idx
                assert isinstance(result.players, list)

                success_count += 1

            except AttributeError as e:
                if "'NoneType' object has no attribute" in str(e):
                    # Este era el error original
                    error_count += 1
                    pytest.fail(
                        f"❌ ERROR CRÍTICO EN FRAME {frame_idx}: {str(e)}\n"
                        f"El detector es None - problema no resuelto"
                    )
                else:
                    raise
            except Exception as e:
                # Otros errores
                print(f"Advertencia en frame {frame_idx}: {str(e)}")

        # Validación final
        print(f"\n✓ Resultados después de {frame_count} frames:")
        print(f"  - Procesados correctamente: {success_count}")
        print(f"  - Errores de 'NoneType': {error_count}")

        # Verificación
        assert error_count == 0, (
            f"Se encontraron {error_count} errores de 'NoneType' object has no attribute"
        )
        assert success_count == frame_count, (
            f"Solo se procesaron {success_count}/{frame_count} frames"
        )

    def test_detector_detect_frame_returns_correct_structure(self):
        """
        El detector.detect_frame() debe retornar estructura con:
        - 'players': lista de dicts con bbox y confidence
        - 'ball': dict con detected, bbox, center, confidence
        - 'pitch': dict con corners, valid, quality_score
        - 'frame_shape': tupla (H, W)
        """
        pipeline = IntegratedAnalysisPipeline()

        if pipeline.detector is None:
            pytest.skip("Detector no inicializado")

        dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = pipeline.detector.detect_frame(dummy_frame)

        # Estructura esperada
        required_keys = ['players', 'ball', 'pitch', 'frame_shape']
        for key in required_keys:
            assert key in result, f"Falta clave requerida: {key}"

        # Tipos correctos
        assert isinstance(result['players'], list)
        assert isinstance(result['ball'], dict)
        assert isinstance(result['pitch'], dict)
        assert isinstance(result['frame_shape'], tuple)
        assert len(result['frame_shape']) == 2
        assert result['frame_shape'] == (720, 1280)

    def test_extract_ball_from_detection_result(self):
        """
        Test que _extract_ball_from_detection() trabaja correctamente
        con el formato nuevo de detection_result.
        """
        pipeline = IntegratedAnalysisPipeline()

        if pipeline.detector is None:
            pytest.skip("Detector no inicializado")

        # Crear mock detection_result
        detection_result = {
            'ball': {
                'detected': True,
                'center': [640.5, 360.2],
                'confidence': 0.85
            }
        }

        # Extraer balón
        ball_pos = pipeline._extract_ball_from_detection(detection_result)

        # Validar
        assert ball_pos is not None
        assert ball_pos[0] == 640.5
        assert ball_pos[1] == 360.2

    def test_detector_models_paths_correct(self):
        """Validar que las rutas de los modelos son correctas."""
        base_dir = Path(__file__).parent.parent / "data"

        player_model = base_dir / "football-player-detection.pt"
        ball_model = base_dir / "football-ball-detection.pt"
        pitch_model = base_dir / "football-pitch-detection.pt"

        # Mostrar estado
        print("\nRutas de modelos verificadas:")
        print(f"  - Player: {player_model} - {'✓ Existe' if player_model.exists() else '✗ NO EXISTE'}")
        print(f"  - Ball: {ball_model} - {'✓ Existe' if ball_model.exists() else '✗ NO EXISTE'}")
        print(f"  - Pitch: {pitch_model} - {'✓ Existe' if pitch_model.exists() else '✗ NO EXISTE'}")

        # Validar que existen
        assert player_model.exists(), f"Modelo de jugadores no encontrado: {player_model}"
        assert ball_model.exists(), f"Modelo de balón no encontrado: {ball_model}"
        assert pitch_model.exists(), f"Modelo de cancha no encontrado: {pitch_model}"


class TestProcessVideoWithDetector:
    """Test que process_video falla correctamente si detector es None."""

    def test_process_video_raises_if_detector_none(self, tmp_path):
        """
        Si el detector fuese None (problema original), process_video
        debe lanzar RuntimeError claro, no AttributeError.
        """
        # Crear video dummy mínimo
        import cv2

        video_path = tmp_path / "test.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(
            str(video_path), fourcc, 30.0, (1280, 720)
        )

        # Escribir 5 frames
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        for _ in range(5):
            out.write(frame)
        out.release()

        # Si el video existe, intentar procesarlo
        if video_path.exists():
            pipeline = IntegratedAnalysisPipeline()

            # El detector debe estar inicializado
            assert pipeline.detector is not None, (
                "Para este test, el detector debe estar inicializado"
            )

            # Intentar procesar (debería funcionar sin error de NoneType)
            try:
                result = pipeline.process_video(str(video_path))
                # Si llegamos aquí, el video se procesó sin el error crítico
                assert result.frames_processed > 0, "Al menos debe haber procesado un frame"
            except RuntimeError as e:
                # Es aceptable un RuntimeError si el detector no está disponible
                assert "DETECTOR NO INICIALIZADO" in str(e) or "Detector" in str(e)
            except AttributeError as e:
                if "'NoneType' object has no attribute" in str(e):
                    pytest.fail(
                        "❌ ERROR CRÍTICO: Se lanzó AttributeError de NoneType\n"
                        "El problema de detector=None NO fue resuelto"
                    )
                raise


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

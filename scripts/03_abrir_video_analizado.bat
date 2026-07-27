@echo off
REM Abre el video analizado con Scout AI

setlocal enabledelayedexpansion

set VIDEO_PATH=%~dp0..\data\videos\test_match_30s_ANALIZADO.mp4

echo.
echo ============================================================
echo Scout AI - Abriendo Video Analizado
echo ============================================================
echo.
echo Archivo: %VIDEO_PATH%
echo.
echo Mostrando:
echo   * Detecciones YOLO (bounding boxes)
echo   * Tracking ByteTrack (IDs persistentes)
echo   * Lineas de movimiento (trazas)
echo   * Clasificacion de equipos (azul/rojo)
echo   * Deteccion de balon
echo   * Estadisticas en tiempo real
echo.

if exist "%VIDEO_PATH%" (
    echo ✓ Archivo encontrado
    echo.
    start "" "%VIDEO_PATH%"
    echo ✓ Abriendo con reproductor default...
) else (
    echo ✗ Archivo NO encontrado: %VIDEO_PATH%
    echo.
    echo Asegurate de ejecutar primero:
    echo   python scripts/00_demo_completa.py
    pause
)

"""
01_generar_video_test.py - Genera un video de prueba con 22 jugadores en movimiento

Crea un video sintético de 30 segundos a 25 fps mostrando:
- 11 jugadores equipo local (azul)
- 11 jugadores equipo visitante (rojo)
- 1 balón en movimiento
- Campo de fútbol con líneas blancas
"""
import cv2
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("data/videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_FILE = OUTPUT_DIR / "test_match_30s.mp4"
DURATION_SECONDS = 30
FPS = 25
WIDTH, HEIGHT = 1280, 720

# Configuración de equipos
TEAMS = {
    'local': {'color': (255, 0, 0), 'name': 'Equipo Local', 'pos_offset': -200},  # Azul en BGR
    'away': {'color': (0, 0, 255), 'name': 'Equipo Visitante', 'pos_offset': 200}   # Rojo en BGR
}

class Player:
    def __init__(self, x, y, team_id, player_num, team_color):
        self.x = x
        self.y = y
        self.team_id = team_id
        self.player_num = player_num
        self.team_color = team_color
        self.vx = np.random.uniform(-3, 3)
        self.vy = np.random.uniform(-3, 3)

    def update(self, frame_num, total_frames):
        # Movimiento sinusoidal con cambios aleatorios
        self.x += self.vx
        self.y += self.vy

        # Cambiar dirección aleatoriamente
        if frame_num % 30 == 0:
            self.vx += np.random.uniform(-2, 2)
            self.vy += np.random.uniform(-2, 2)

        # Limites del campo
        margin = 60
        if self.x < margin or self.x > WIDTH - margin:
            self.vx *= -1
        if self.y < margin or self.y > HEIGHT - margin:
            self.vy *= -1

        self.x = np.clip(self.x, margin, WIDTH - margin)
        self.y = np.clip(self.y, margin, HEIGHT - margin)

    def draw(self, frame):
        # Dibujar jugador como círculo
        cv2.circle(frame, (int(self.x), int(self.y)), 12, self.team_color, -1)
        # Número de jersey
        cv2.putText(frame, str(self.player_num),
                   (int(self.x) - 5, int(self.y) + 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)


def draw_pitch(frame):
    """Dibuja el campo de fútbol"""
    h, w = frame.shape[:2]

    # Línea central vertical
    cv2.line(frame, (w // 2, 0), (w // 2, h), (255, 255, 255), 2)

    # Centro del campo
    cv2.circle(frame, (w // 2, h // 2), 50, (255, 255, 255), 2)
    cv2.circle(frame, (w // 2, h // 2), 3, (255, 255, 255), -1)

    # Área de penalti local
    cv2.rectangle(frame, (20, int(h * 0.25)), (150, int(h * 0.75)), (255, 255, 255), 2)
    # Área de meta local
    cv2.rectangle(frame, (20, int(h * 0.35)), (60, int(h * 0.65)), (255, 255, 255), 2)

    # Área de penalti visitante
    cv2.rectangle(frame, (w - 150, int(h * 0.25)), (w - 20, int(h * 0.75)), (255, 255, 255), 2)
    # Área de meta visitante
    cv2.rectangle(frame, (w - 60, int(h * 0.35)), (w - 20, int(h * 0.65)), (255, 255, 255), 2)

    # Líneas laterales
    cv2.rectangle(frame, (20, 20), (w - 20, h - 20), (255, 255, 255), 3)


def main():
    logger.info(f"Generando video de prueba: {VIDEO_FILE}")
    logger.info(f"Resolución: {WIDTH}x{HEIGHT}, FPS: {FPS}, Duración: {DURATION_SECONDS}s")

    # Crear escritor de video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(VIDEO_FILE), fourcc, FPS, (WIDTH, HEIGHT))

    if not out.isOpened():
        logger.error("No se pudo abrir VideoWriter")
        return False

    # Crear jugadores
    players = []

    # Equipo Local (azul) - formación 4-3-3
    local_positions = [
        (150, 360),   # Portero
        (300, 200), (300, 360), (300, 520),  # Defensa
        (450, 250), (450, 360), (450, 530),  # Mediocampo
        (650, 150), (650, 360), (650, 570),  # Ataque
        (800, 360)    # Extremo
    ]

    # Equipo Visitante (rojo) - formación 4-2-4
    away_positions = [
        (1130, 360),   # Portero
        (980, 200), (980, 360), (980, 520),  # Defensa
        (800, 280), (800, 440),  # Mediocampo
        (600, 150), (600, 300), (600, 420), (600, 570),  # Ataque
    ]

    local_team = TEAMS['local']
    away_team = TEAMS['away']

    for i, pos in enumerate(local_positions, 1):
        players.append(Player(pos[0], pos[1], 'local', i, local_team['color']))

    for i, pos in enumerate(away_positions, 1):
        players.append(Player(pos[0], pos[1], 'away', i, away_team['color']))

    # Balón
    ball_x, ball_y = WIDTH // 2, HEIGHT // 2
    ball_vx, ball_vy = 5, 3

    total_frames = FPS * DURATION_SECONDS

    for frame_num in range(total_frames):
        # Fondo verde (campo)
        frame = np.ones((HEIGHT, WIDTH, 3), dtype=np.uint8) * np.array([34, 139, 34], dtype=np.uint8)

        # Dibujar campo
        draw_pitch(frame)

        # Actualizar y dibujar jugadores
        for player in players:
            player.update(frame_num, total_frames)
            player.draw(frame)

        # Actualizar balón
        ball_x += ball_vx
        ball_y += ball_vy
        if ball_x < 50 or ball_x > WIDTH - 50:
            ball_vx *= -1
        if ball_y < 50 or ball_y > HEIGHT - 50:
            ball_vy *= -1

        # Dibujar balón
        cv2.circle(frame, (int(ball_x), int(ball_y)), 8, (0, 255, 255), -1)
        cv2.circle(frame, (int(ball_x), int(ball_y)), 8, (0, 200, 200), 2)

        # Información en pantalla
        cv2.putText(frame, f"Frame: {frame_num}/{total_frames}", (20, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, f"Tiempo: {frame_num / FPS:.1f}s", (20, 80),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, f"Equipo Local (Azul) vs Equipo Visitante (Rojo)", (20, HEIGHT - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        out.write(frame)

        if frame_num % 30 == 0:
            logger.info(f"Procesados {frame_num}/{total_frames} frames ({100 * frame_num / total_frames:.1f}%)")

    out.release()
    logger.info(f"✓ Video generado: {VIDEO_FILE}")
    logger.info(f"  Tamaño: {VIDEO_FILE.stat().st_size / (1024*1024):.1f} MB")

    return True


if __name__ == "__main__":
    main()

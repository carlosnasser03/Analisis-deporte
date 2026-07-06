"""
metrics.py - Logging y tracking de métricas de detección

Propósito: Rastrear confianzas y fallos en cada frame para diagnóstico
"""
import csv
import json
from pathlib import Path
from collections import defaultdict
import numpy as np


class DetectionMetrics:
    """Registra métricas de detección frame por frame"""

    def __init__(self, output_dir="data/logs", video_name="unknown"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        self.video_name = video_name
        self.frames_data = []
        self.summary_stats = defaultdict(list)

        # Contadores
        self.frame_count = 0
        self.detection_failures = {
            'player_low_confidence': 0,
            'pitch_low_confidence': 0,
            'ball_low_confidence': 0,
            'homography_invalid': 0,
            'team_classification_failed': 0,
        }

    def log_frame(self, frame_idx, data):
        """
        Registra métricas de un frame

        Args:
            frame_idx (int): Número de frame
            data (dict): Datos del frame:
                - player_confidence: float (0-1)
                - player_count: int
                - ball_confidence: float (0-1)
                - pitch_confidence: float (0-1)
                - pitch_keypoints_valid: int
                - homography_valid: bool
                - homography_quality: float (0-1)
                - team_accuracy: float (0-1)
        """
        self.frame_count += 1

        # Guardar datos brutos
        frame_record = {'frame': frame_idx}
        frame_record.update(data)
        self.frames_data.append(frame_record)

        # Actualizar estadísticas
        if data.get('player_confidence', 0) < 0.4:
            self.detection_failures['player_low_confidence'] += 1

        if data.get('pitch_confidence', 0) < 0.5:
            self.detection_failures['pitch_low_confidence'] += 1

        if data.get('ball_confidence', 0) < 0.3:
            self.detection_failures['ball_low_confidence'] += 1

        if not data.get('homography_valid', False):
            self.detection_failures['homography_invalid'] += 1

        if data.get('team_accuracy', 0) < 0.6:
            self.detection_failures['team_classification_failed'] += 1

        # Acumular para estadísticas
        for key, value in data.items():
            if isinstance(value, (int, float)):
                self.summary_stats[key].append(value)

    def get_summary(self):
        """Retorna resumen estadístico de todas las métricas"""
        summary = {}

        for metric_name, values in self.summary_stats.items():
            if values:
                summary[metric_name] = {
                    'mean': float(np.mean(values)),
                    'min': float(np.min(values)),
                    'max': float(np.max(values)),
                    'std': float(np.std(values)),
                }

        # Agregar contadores de fallos
        summary['failures'] = dict(self.detection_failures)
        summary['total_frames'] = self.frame_count

        # Calcular tasas de fallo
        if self.frame_count > 0:
            summary['failure_rates'] = {
                k: f"{v/self.frame_count*100:.1f}%"
                for k, v in self.detection_failures.items()
            }

        return summary

    def export_csv(self, filename=None):
        """Exporta datos frame-by-frame a CSV"""
        if filename is None:
            filename = self.output_dir / f"frames_{self.video_name}.csv"

        if not self.frames_data:
            print(f"⚠ No hay datos para exportar")
            return

        # Obtener todos los keys
        fieldnames = set()
        for record in self.frames_data:
            fieldnames.update(record.keys())
        fieldnames = sorted(list(fieldnames))

        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.frames_data)

        print(f"✓ CSV exportado: {filename}")
        return filename

    def export_summary(self, filename=None):
        """Exporta resumen estadístico a JSON"""
        if filename is None:
            filename = self.output_dir / f"summary_{self.video_name}.json"

        summary = self.get_summary()

        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)

        print(f"✓ Resumen exportado: {filename}")
        return filename

    def print_summary(self):
        """Imprime resumen en consola"""
        summary = self.get_summary()

        print("\n" + "="*60)
        print(f"MÉTRICAS DE VIDEO: {self.video_name}")
        print("="*60)

        print(f"\nFrames procesados: {summary.get('total_frames', 0)}")

        print("\n📊 CONFIANZAS (promedio):")
        for metric in ['player_confidence', 'ball_confidence', 'pitch_confidence',
                       'homography_quality', 'team_accuracy']:
            if metric in summary:
                stats = summary[metric]
                print(f"  {metric:30s}: {stats['mean']:.2f} "
                      f"(min: {stats['min']:.2f}, max: {stats['max']:.2f})")

        print("\n❌ TASAS DE FALLO:")
        for failure_type, rate in summary.get('failure_rates', {}).items():
            print(f"  {failure_type:30s}: {rate}")

        print("\n" + "="*60)

    def identify_difficult_frames(self, threshold=0.5):
        """
        Identifica frames "difíciles" (baja confianza)
        Útil para dataset de anotación manual
        """
        difficult = []

        for record in self.frames_data:
            confidence_score = (
                record.get('player_confidence', 0) +
                record.get('ball_confidence', 0) +
                record.get('pitch_confidence', 0)
            ) / 3

            if confidence_score < threshold:
                difficult.append({
                    'frame': record['frame'],
                    'confidence_score': confidence_score,
                    'reason': self._get_failure_reason(record)
                })

        return difficult

    def _get_failure_reason(self, record):
        """Determina por qué un frame es difícil"""
        reasons = []

        if record.get('player_confidence', 0) < 0.4:
            reasons.append('low_player_conf')
        if record.get('ball_confidence', 0) < 0.3:
            reasons.append('low_ball_conf')
        if record.get('pitch_confidence', 0) < 0.5:
            reasons.append('low_pitch_conf')
        if not record.get('homography_valid', False):
            reasons.append('invalid_homography')

        return '+'.join(reasons) if reasons else 'unknown'

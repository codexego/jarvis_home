"""Configuración del pipeline de voz."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class VoiceConfig:
    """Parámetros del módulo voice_listener."""

    sample_rate: int = 16_000
    channels: int = 1
    frame_ms: int = 30
    wake_word: str = "jarvis"
    # Modelo VOSK en español (descargar con scripts/download_vosk_model.py)
    model_path: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "models" / "vosk-model-small-es-0.42"
    )
    # Fallback al modelo inglés si el español no está disponible
    fallback_model_path: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "models" / "vosk-model-small-en-us-0.15"
    )
    language: str = "es"
    silence_timeout_s: float = 1.2
    # Sensibilidad VAD 0-3 (mayor = menos falsos positivos)
    vad_aggressiveness: int = 2
    # Umbral RMS manual (None = automático según aggressiveness)
    vad_energy_threshold: float | None = None
    input_device: int | None = None
    # Feedback inmediato al detectar wake (emitido como evento; response module habla)
    wake_ack_enabled: bool = True
    dry_run: bool = field(
        default_factory=lambda: os.getenv("JARVIS_VOICE_DRY_RUN", "").lower() in ("1", "true", "yes")
    )

    @property
    def frame_bytes(self) -> int:
        samples = self.sample_rate * self.frame_ms // 1000
        return samples * 2

    def resolved_model_path(self) -> Path:
        """Devuelve el modelo disponible (español preferido)."""
        if self.model_path.is_dir():
            return self.model_path
        if self.fallback_model_path.is_dir():
            return self.fallback_model_path
        return self.model_path

    def validate(self) -> list[str]:
        errors: list[str] = []
        resolved = self.resolved_model_path()
        if not self.dry_run and not resolved.is_dir():
            errors.append(
                f"Modelo VOSK no encontrado. Ejecuta: python scripts/download_vosk_model.py"
            )
        if self.vad_aggressiveness not in range(4):
            errors.append("vad_aggressiveness debe estar entre 0 y 3")
        return errors

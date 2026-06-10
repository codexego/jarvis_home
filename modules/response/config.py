"""Configuración del módulo de respuesta (TTS + UI)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class ResponseConfig:
    """Parámetros de voz y panel visual."""

    enabled: bool = True
    tts_enabled: bool = True
    ui_enabled: bool = True
    # Frase corta al detectar wake word
    wake_ack: str = "Sí, señor"
    # Velocidad y tono TTS
    tts_rate: int = 168
    tts_volume: float = 1.0
    voice_hint: str = "male"
    # Título del panel
    window_title: str = "Jarvis Home"
    dry_run: bool = field(
        default_factory=lambda: os.getenv("JARVIS_RESPONSE_DRY_RUN", "").lower()
        in ("1", "true", "yes")
    )

"""Configuración del módulo screen_monitor."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class ScreenConfig:
    """Parámetros de captura y análisis de pantalla."""

    analysis_scale: float = 0.6
    overlay_color: str = "#00ffff"
    overlay_width: int = 5
    overlay_enabled: bool = True
    ocr_min_confidence: int = 40
    # Idioma OCR Tesseract (spa+eng para YouTube en español)
    ocr_lang: str = "spa+eng"
    dry_run: bool = field(
        default_factory=lambda: os.getenv("JARVIS_SCREEN_DRY_RUN", "").lower()
        in ("1", "true", "yes")
    )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not 0.2 <= self.analysis_scale <= 1.0:
            errors.append("analysis_scale debe estar entre 0.2 y 1.0")
        return errors

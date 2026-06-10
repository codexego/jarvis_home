"""Configuraci?n del m?dulo de visi?n."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class VisionConfig:
    """Par?metros de captura y detecci?n."""

    camera_index: int = 0
    model_name: str = "yolov8n.pt"
    model_path: Path = field(
        default_factory=lambda: _PROJECT_ROOT / "models" / "yolov8n.pt"
    )
    confidence_threshold: float = 0.45
    inference_size: int = 320
    warmup_frames: int = 3
    capture_timeout_s: float = 5.0
    # Tracking corto bajo demanda (solo en consultas de mano/objeto)
    tracking_enabled: bool = True
    tracking_frames: int = 4
    tracking_interval_s: float = 0.35
    label_locale: str = "es"
    dry_run: bool = field(
        default_factory=lambda: os.getenv("JARVIS_VISION_DRY_RUN", "").lower()
        in ("1", "true", "yes")
    )

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.inference_size < 160:
            errors.append("inference_size debe ser >= 160")
        if not 0.0 < self.confidence_threshold < 1.0:
            errors.append("confidence_threshold debe estar entre 0 y 1")
        return errors

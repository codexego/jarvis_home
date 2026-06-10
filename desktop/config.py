"""Configuración persistente de la aplicación de escritorio."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SETTINGS_FILE = _PROJECT_ROOT / "data" / "desktop_settings.json"


@dataclass
class DesktopSettings:
    """Preferencias de la UI y módulos."""

    llm_model: str = "llama3.2"
    tts_volume: float = 1.0
    tts_rate: int = 168
    voice_enabled: bool = True
    vision_enabled: bool = True
    screen_enabled: bool = True
    startup_with_windows: bool = False
    window_width: int = 1100
    window_height: int = 780

    @classmethod
    def load(cls) -> DesktopSettings:
        if not _SETTINGS_FILE.is_file():
            return cls()
        try:
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except (json.JSONDecodeError, TypeError):
            return cls()

    def save(self) -> None:
        _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @property
    def db_path(self) -> Path:
        return _PROJECT_ROOT / "data" / "jarvis_memory.db"

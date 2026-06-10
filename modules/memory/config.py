"""Configuración del módulo memory."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class MemoryConfig:
    db_path: Path = field(default_factory=lambda: _PROJECT_ROOT / "data" / "jarvis_memory.db")
    session_id: str = "default"
    max_context_messages: int = 40
    habit_threshold: int = 3
    # Intervalo del bucle de aprendizaje en segundo plano
    learn_interval_s: float = 60.0
    # Retención de interacciones (días); 0 = sin límite
    retention_days: int = field(
        default_factory=lambda: int(os.getenv("JARVIS_MEMORY_RETENTION_DAYS", "90"))
    )

"""Configuración del módulo ai_brain."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(slots=True)
class AIConfig:
    """Parámetros del cerebro IA local."""

    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    model: str = field(default_factory=lambda: os.getenv("JARVIS_LLM_MODEL", "llama3.2"))
    fallback_model: str = field(
        default_factory=lambda: os.getenv("JARVIS_LLM_FALLBACK", "mistral")
    )
    # Modelos preferidos en orden (se usa el primero disponible en Ollama)
    model_priority: tuple[str, ...] = (
        "llama3.2",
        "qwen2.5",
        "mistral",
        "gemma2",
        "llama3.1",
    )
    request_timeout_s: float = 90.0
    max_context_messages: int = 10
    prefer_llm: bool = True
    session_id: str = "default"
    db_path: Path = field(default_factory=lambda: _PROJECT_ROOT / "data" / "jarvis_memory.db")
    dry_run: bool = field(
        default_factory=lambda: os.getenv("JARVIS_AI_DRY_RUN", "").lower() in ("1", "true", "yes")
    )

    def resolve_model(self, available: list[str]) -> str:
        """Elige el mejor modelo disponible en Ollama."""
        if not available:
            return self.model
        candidates = [self.model, self.fallback_model, *self.model_priority]
        seen: set[str] = set()
        for name in candidates:
            if name in seen:
                continue
            seen.add(name)
            for avail in available:
                if name == avail or avail.startswith(f"{name}:"):
                    return avail
        return available[0]

    def validate(self) -> list[str]:
        return []

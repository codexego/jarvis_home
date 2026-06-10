"""Configuración del módulo executor."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(slots=True)
class ExecutorConfig:
    """Parámetros de ejecución y seguridad."""

    # Pausa entre acciones pyautogui (segundos)
    action_pause_s: float = 0.04
    # Tiempo máximo esperando confirmación del usuario
    confirmation_timeout_s: float = 30.0
    # Si True, ejecuta acciones críticas sin pedir confirmación (solo desarrollo)
    auto_confirm: bool = field(
        default_factory=lambda: os.getenv("JARVIS_EXECUTOR_AUTO_CONFIRM", "").lower()
        in ("1", "true", "yes")
    )
    dry_run: bool = field(
        default_factory=lambda: os.getenv("JARVIS_EXECUTOR_DRY_RUN", "").lower()
        in ("1", "true", "yes")
    )
    # Navegador predeterminado para URLs
    browser_cmd: str | None = field(
        default_factory=lambda: os.getenv("JARVIS_BROWSER", None)
    )

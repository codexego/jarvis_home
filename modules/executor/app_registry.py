"""Registro dinámico de aplicaciones y URLs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from services.logging_service import get_logger

logger = get_logger("app_registry")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_APPS_FILE = _PROJECT_ROOT / "data" / "apps.json"

# Apps base conocidas
_BUILTIN: dict[str, dict[str, Any]] = {
    "youtube": {"kind": "url", "url": "https://www.youtube.com"},
    "youtu": {"kind": "url", "url": "https://www.youtube.com"},
    "vscode": {"kind": "app", "win": "code", "darwin": "code", "linux": "code"},
    "vs code": {"kind": "app", "win": "code", "darwin": "code", "linux": "code"},
    "visual studio code": {"kind": "app", "win": "code", "darwin": "code", "linux": "code"},
    "chrome": {"kind": "app", "win": "chrome", "darwin": "open -a 'Google Chrome'", "linux": "google-chrome"},
    "firefox": {"kind": "app", "win": "firefox", "darwin": "open -a Firefox", "linux": "firefox"},
    "edge": {"kind": "app", "win": "msedge", "darwin": "open -a 'Microsoft Edge'", "linux": "microsoft-edge"},
    "notepad": {"kind": "app", "win": "notepad", "darwin": "open -a TextEdit", "linux": "gedit"},
    "bloc de notas": {"kind": "app", "win": "notepad"},
    "calculadora": {"kind": "app", "win": "calc", "darwin": "open -a Calculator"},
    "calculator": {"kind": "app", "win": "calc", "darwin": "open -a Calculator"},
    "spotify": {"kind": "app", "win": "spotify", "darwin": "open -a Spotify"},
    "discord": {"kind": "app", "win": "discord", "darwin": "open -a Discord"},
}


class AppRegistry:
    """Registro de apps con persistencia JSON y aliases dinámicos."""

    def __init__(self, apps_file: Path | None = None) -> None:
        self.apps_file = apps_file or _DEFAULT_APPS_FILE
        self._registry: dict[str, dict[str, Any]] = dict(_BUILTIN)
        self._load()

    def _load(self) -> None:
        if not self.apps_file.is_file():
            return
        try:
            data = json.loads(self.apps_file.read_text(encoding="utf-8"))
            for name, spec in data.items():
                self._registry[name.lower().strip()] = spec
            logger.info("Apps cargadas desde %s: %d", self.apps_file, len(data))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo cargar apps.json: %s", exc)

    def save(self) -> None:
        custom = {k: v for k, v in self._registry.items() if k not in _BUILTIN}
        self.apps_file.parent.mkdir(parents=True, exist_ok=True)
        self.apps_file.write_text(
            json.dumps(custom, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def register(self, name: str, spec: dict[str, Any], *, persist: bool = True) -> None:
        key = name.lower().strip()
        self._registry[key] = spec
        if persist:
            self.save()
        logger.info("App registrada: %s", key)

    def resolve(self, name: str) -> dict[str, Any] | None:
        key = name.lower().strip()
        if key in self._registry:
            return self._registry[key]
        # Búsqueda parcial
        for reg_name, spec in self._registry.items():
            if key in reg_name or reg_name in key:
                return spec
        return None

    def all_names(self) -> list[str]:
        return sorted(self._registry.keys())

    def is_known(self, name: str) -> bool:
        return self.resolve(name) is not None


# Instancia global compartida
_registry = AppRegistry()


def get_registry() -> AppRegistry:
    return _registry


def resolve_app(name: str) -> dict[str, Any] | None:
    return _registry.resolve(name)


def register_app(name: str, spec: dict[str, Any], *, persist: bool = True) -> None:
    _registry.register(name, spec, persist=persist)


def build_open_action(name: str) -> dict[str, Any] | None:
    spec = resolve_app(name)
    if not spec:
        return None
    if spec["kind"] == "url":
        return {"type": "open_url", "url": spec["url"], "app": name}
    platform = sys.platform
    if platform == "win32":
        cmd = spec.get("win")
    elif platform == "darwin":
        cmd = spec.get("darwin")
    else:
        cmd = spec.get("linux")
    if not cmd:
        return None
    return {"type": "open_app", "app": name, "command": cmd}

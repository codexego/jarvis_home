"""Clasificación de riesgo y control de acciones críticas."""

from __future__ import annotations

from typing import Any

# Tipos que nunca se ejecutan sin confirmación explícita
_CRITICAL_TYPES = frozenset({"shell", "run", "delete_file", "shutdown", "kill"})

from modules.executor.app_registry import get_registry

# Dominios permitidos para open_url sin confirmación
_WHITELISTED_URL_PREFIXES = (
    "https://youtube.com",
    "https://www.youtube.com",
    "https://youtu.be",
    "https://github.com",
    "https://stackoverflow.com",
    "http://localhost",
    "https://localhost",
)


def classify_action(action: dict[str, Any]) -> str:
    """Devuelve 'low', 'medium' o 'high'."""
    kind = action.get("type", "")

    if kind in _CRITICAL_TYPES:
        return "high"

    if kind in ("click", "press", "hotkey", "type", "type_code", "wait", "paste"):
        return "low"

    if kind == "open_url":
        url = (action.get("url") or "").lower()
        if any(url.startswith(p) for p in _WHITELISTED_URL_PREFIXES):
            return "low"
        return "medium"

    if kind == "open_app":
        name = (action.get("app") or action.get("name") or "").lower().strip()
        if get_registry().is_known(name):
            return "low"
        return "medium"

    if kind in ("resume_video", "play_video"):
        return "low"

    return "medium"


def requires_confirmation(action: dict[str, Any], auto_confirm: bool = False) -> bool:
    if auto_confirm:
        return False
    risk = classify_action(action)
    return risk in ("medium", "high")


def partition_actions(
    actions: list[dict[str, Any]],
    auto_confirm: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separa acciones seguras de las que requieren confirmación."""
    safe: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for action in actions:
        if requires_confirmation(action, auto_confirm):
            pending.append(action)
        else:
            safe.append(action)
    return safe, pending

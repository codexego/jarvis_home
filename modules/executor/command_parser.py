"""Parser de comandos de voz para acciones del executor."""

from __future__ import annotations

import re
import sys
from typing import Any

from modules.executor.app_registry import build_open_action, get_registry, register_app

_OPEN_RE = re.compile(
    r"\b(abre|abrir|open|lanza|inicia|launch)\s+(?:la\s+|el\s+)?(.+?)\s*$",
    re.IGNORECASE,
)
_WRITE_CODE_RE = re.compile(
    r"\b(escribe|escribir|write|pega)\s+(?:el\s+)?(?:c[oó]digo|code)\s+"
    r"(?:en\s+)?(.+?)(?:\s*:\s*(.+))?\s*$",
    re.IGNORECASE,
)
_RESUME_VIDEO_RE = re.compile(
    r"\b(reanuda|resume|continua|continuar)\s+(?:el\s+)?video\b",
    re.IGNORECASE,
)
_LEARN_RE = re.compile(
    r"\b(?:cuando\s+diga|aprende\s+que|recuerda\s+que)\s+['\"]?(.+?)['\"]?\s*,?\s*"
    r"(?:abre|abrir|lanza|open)\s+['\"]?(.+?)['\"]?\s*$",
    re.IGNORECASE,
)
_REGISTER_APP_RE = re.compile(
    r"\b(?:registra|registrar)\s+(?:la\s+app|aplicaci[oó]n)\s+['\"]?(.+?)['\"]?\s+"
    r"(?:como|con\s+comando)\s+['\"]?(.+?)['\"]?\s*$",
    re.IGNORECASE,
)
_CONFIRM_RE = re.compile(r"\b(confirmar|confirm|s[ií]|adelante|ok)\b", re.IGNORECASE)
_CANCEL_RE = re.compile(r"\b(cancelar|cancel|no|detente|stop)\b", re.IGNORECASE)

_EXECUTOR_HINTS = (
    r"\b(abre|abrir|open|lanza)\s+",
    r"\b(escribe|write)\s+.*(c[oó]digo|code)",
    r"\b(reanuda|resume)\s+.*video",
    r"\b(cuando\s+diga|aprende\s+que|registra)\s+",
)


def is_executor_query(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    if parse_executor_command(normalized)["intent"] != "unknown":
        return True
    return any(re.search(p, normalized, re.IGNORECASE) for p in _EXECUTOR_HINTS)


def is_confirmation(text: str) -> bool:
    return bool(_CONFIRM_RE.search(text.strip()))


def is_cancellation(text: str) -> bool:
    return bool(_CANCEL_RE.search(text.strip()))


def parse_executor_command(text: str) -> dict[str, Any]:
    q = text.strip()

    m = _LEARN_RE.search(q)
    if m:
        return {
            "intent": "learn_command",
            "trigger": m.group(1).strip(),
            "target": m.group(2).strip(),
            "query": q,
        }

    m = _REGISTER_APP_RE.search(q)
    if m:
        return {
            "intent": "register_app",
            "app_name": m.group(1).strip(),
            "command": m.group(2).strip(),
            "query": q,
        }

    m = _OPEN_RE.search(q)
    if m:
        target = m.group(2).strip().rstrip(".")
        return {"intent": "open_app", "target": target, "query": q}

    m = _WRITE_CODE_RE.search(q)
    if m:
        app = m.group(2).strip()
        code = (m.group(3) or "").strip()
        return {"intent": "write_code", "app": app, "code": code, "query": q}

    if _RESUME_VIDEO_RE.search(q):
        return {"intent": "resume_video", "query": q}

    return {"intent": "unknown", "query": q}


def build_executor_actions(parsed: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    intent = parsed.get("intent", "unknown")
    actions: list[dict[str, Any]] = []

    if intent == "learn_command":
        return [], f"Aprendido: cuando digas '{parsed.get('trigger')}', abriré {parsed.get('target')}."

    if intent == "register_app":
        name = parsed.get("app_name", "")
        cmd = parsed.get("command", "")
        spec = {"kind": "app", "win": cmd, "darwin": cmd, "linux": cmd}
        register_app(name, spec)
        return [], f"Aplicación {name} registrada."

    if intent == "open_app":
        target = parsed.get("target", "")
        action = build_open_action(target)
        if action:
            actions.append(action)
            actions.append({"type": "wait", "seconds": 1.5})
            return actions, f"Abriendo {target}."
        # Registrar dinámicamente como comando genérico
        spec = {"kind": "app", "win": target, "darwin": target, "linux": target}
        register_app(target, spec, persist=True)
        actions.append({"type": "open_app", "app": target, "command": target})
        return actions, f"Intentando abrir {target}."

    if intent == "write_code":
        app = parsed.get("app", "vscode")
        code = parsed.get("code", "")
        open_action = build_open_action(app) or build_open_action("vscode")
        if open_action:
            actions.append(open_action)
        actions.append({"type": "wait", "seconds": 2.0})
        actions.append({"type": "hotkey", "keys": ["ctrl", "n"]})
        actions.append({"type": "wait", "seconds": 0.3})
        if code:
            actions.append({"type": "type_code", "text": code})
        return actions, f"Escribiendo código en {app}."

    if intent == "resume_video":
        actions.append({"type": "resume_video"})
        return actions, "Reanudando el video."

    return [], ""


def apply_custom_command(trigger: str, target: str) -> tuple[list[dict[str, Any]], str]:
    """Resuelve comando aprendido personalizado."""
    action = build_open_action(target)
    if action:
        return [action, {"type": "wait", "seconds": 1.5}], f"Abriendo {target}."
    return [{"type": "open_app", "app": target, "command": target}], f"Ejecutando {target}."

"""Detección de contexto de trabajo a partir de comandos."""

from __future__ import annotations

import re
from typing import Any

_CONTEXT_RULES: list[tuple[str, re.Pattern[str], list[str]]] = [
    (
        "programming",
        re.compile(
            r"\b(c[oó]digo|code|python|javascript|programa|debug|vs\s*code|terminal|git|api)\b",
            re.IGNORECASE,
        ),
        ["editor", "lenguaje", "framework"],
    ),
    (
        "media",
        re.compile(
            r"\b(video|youtube|m[uú]sica|spotify|reproduce|play|pausa|stream)\b",
            re.IGNORECASE,
        ),
        ["plataforma", "genero"],
    ),
    (
        "productivity",
        re.compile(
            r"\b(pantalla|screen|documento|email|reuni[oó]n|calendario|nota)\b",
            re.IGNORECASE,
        ),
        ["app", "tarea"],
    ),
    (
        "home_automation",
        re.compile(
            r"\b(luz|luces|temperatura|clima|casa|habitaci[oó]n|enciende|apaga)\b",
            re.IGNORECASE,
        ),
        ["dispositivo", "habitacion"],
    ),
]


def detect_work_context(text: str) -> str | None:
    for name, pattern, _ in _CONTEXT_RULES:
        if pattern.search(text):
            return name
    return None


def extract_context_metadata(text: str, work_context: str | None) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if not work_context:
        return meta

    for name, pattern, keys in _CONTEXT_RULES:
        if name != work_context:
            continue
        match = pattern.search(text)
        if match:
            meta["trigger_word"] = match.group(0).lower()
        break

    if work_context == "programming":
        for lang in ("python", "javascript", "typescript", "java", "rust", "go"):
            if lang in text.lower():
                meta["lenguaje"] = lang
                break
        if "vs code" in text.lower() or "vscode" in text.lower():
            meta["editor"] = "vscode"

    if work_context == "media" and "youtube" in text.lower():
        meta["plataforma"] = "youtube"

    return meta


def suggest_intent_from_habits(text: str, habits: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Sugiere intención si el texto coincide con un hábito aprendido."""
    normalized = " ".join(text.lower().split())
    if not normalized:
        return None

    best = None
    best_score = 0.0
    for habit in habits:
        pattern = habit.get("pattern", "")
        if not pattern:
            continue
        if pattern == normalized:
            return {"intent": habit.get("intent"), "pattern": pattern, "confidence": 0.95}
        if pattern in normalized or normalized in pattern:
            score = len(pattern) / max(len(normalized), 1)
            if score > best_score:
                best_score = score
                best = {
                    "intent": habit.get("intent"),
                    "pattern": pattern,
                    "confidence": round(min(0.85, score + 0.3), 2),
                }
    return best

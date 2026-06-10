"""Detección e interpretación de comandos de pantalla."""

from __future__ import annotations

import re
from typing import Any

_SCREEN_PATTERNS = (
    r"\b(reproduce|reproducir|play|pon|inicia|pausa|pause|reanuda|reanudar|continua|continuar)\s+(?:el\s+)?video\b",
    r"\b(busca|buscar|search)\s+(?:el\s+)?video\b",
    r"\b(video\s+que\s+(?:diga|tenga|con)|video\s+con)\b",
    r"\b(pantalla|en\s+pantalla|screen|lo\s+que\s+hay\s+en\s+pantalla)\b",
    r"\b(click|clic|pulsa|presiona|press)\b",
    r"\b(youtube|navegador|browser)\b",
)

_SEARCH_EXTRACTORS = (
    re.compile(
        r"(?:busca(?:r)?|search(?:\s+for)?)\s+(?:el\s+)?video\s+"
        r"(?:que\s+)?(?:diga|tenga|con|contenga|with|containing)\s+['\"]?(.+?)['\"]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"video\s+(?:que\s+)?(?:diga|tenga|con)\s+(?:la\s+)?(?:frase\s+)?['\"]?(.+?)['\"]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:busca(?:r)?)\s+(?:en\s+pantalla\s+)?(.+?)\s*$",
        re.IGNORECASE,
    ),
)

_PLAY_PATTERN = re.compile(
    r"\b(reproduce|reproducir|play|pon|inicia)\s+(?:el\s+)?video\b",
    re.IGNORECASE,
)
_RESUME_PATTERN = re.compile(
    r"\b(reanuda|reanudar|resume|continua|continuar)\s+(?:el\s+)?video\b",
    re.IGNORECASE,
)
_PAUSE_PATTERN = re.compile(r"\b(pausa|pause)\s+(?:el\s+)?video\b", re.IGNORECASE)

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _SCREEN_PATTERNS]


def is_screen_query(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    return any(p.search(normalized) for p in _COMPILED)


def parse_screen_command(query: str) -> dict[str, Any]:
    q = query.strip()
    intent = "describe_screen"
    phrase = None

    if _PLAY_PATTERN.search(q):
        intent = "play_video"
    elif _RESUME_PATTERN.search(q):
        intent = "resume_video"
    elif _PAUSE_PATTERN.search(q):
        intent = "pause_video"
    else:
        for pattern in _SEARCH_EXTRACTORS:
            match = pattern.search(q)
            if match:
                intent = "search_video"
                phrase = match.group(1).strip()
                break
        if intent != "search_video" and ("busca" in q.lower() or "search" in q.lower()):
            intent = "search_video"

    return {"intent": intent, "phrase": phrase, "query": q}


def build_screen_actions(
    parsed: dict[str, Any],
    analysis: dict[str, Any],
    monitor: dict[str, int],
) -> tuple[list[dict[str, Any]], str]:
    intent = parsed.get("intent", "describe_screen")
    context = analysis.get("context") or {}
    scale = context.get("scale") or 1.0
    elements = analysis.get("elements") or []
    text_lines = analysis.get("text_lines") or []
    actions: list[dict[str, Any]] = []
    answer = ""

    def to_abs(elem: dict) -> tuple[int, int]:
        center = elem.get("center") or [
            elem["bbox"][0] + elem["bbox"][2] // 2,
            elem["bbox"][1] + elem["bbox"][3] // 2,
        ]
        from modules.screen.analyzer import scale_point

        return scale_point(center[0], center[1], scale, monitor)

    if intent in ("play_video", "resume_video"):
        target = context.get("play_target")
        if target:
            x, y = to_abs(target)
            actions.append({"type": "click", "x": x, "y": y, "target": "play"})
            answer = "Reanudando el video." if intent == "resume_video" else "Reproduciendo el video."
        else:
            actions.append({"type": "press", "key": "space"})
            answer = "Reanudando el video." if intent == "resume_video" else "Intentando reproducir el video."
        return actions, answer

    if intent == "pause_video":
        actions.append({"type": "press", "key": "space"})
        answer = "Pausando el video."
        return actions, answer

    if intent == "search_video":
        phrase = parsed.get("phrase") or context.get("search_phrase") or ""
        match = context.get("phrase_match")
        yt_search = context.get("youtube_search_box")

        if match:
            answer = f"Encontré: {match.get('line', '')[:80]}"
            actions.append({"type": "hotkey", "keys": ["ctrl", "f"]})
            if phrase:
                actions.append({"type": "type", "text": phrase})
        else:
            search_box = next((e for e in elements if e["type"] == "search_box"), None)
            if search_box:
                x, y = to_abs(search_box)
                actions.append({"type": "click", "x": x, "y": y})
                actions.append({"type": "wait", "seconds": 0.3})
            elif yt_search:
                x, y = to_abs(yt_search)
                actions.append({"type": "click", "x": x, "y": y})
                actions.append({"type": "wait", "seconds": 0.3})
            else:
                actions.append({"type": "hotkey", "keys": ["ctrl", "f"]})
            if phrase:
                actions.append({"type": "type", "text": phrase})
                answer = f"Buscando el video que diga: {phrase}"
            else:
                answer = "Abriendo búsqueda en pantalla."
        return actions, answer

    summary = context.get("summary") or "Pantalla analizada."
    titles = context.get("video_titles") or []
    if titles:
        answer = f"En pantalla veo títulos como: {titles[0].get('line', '')[:60]}"
    elif text_lines:
        answer = f"En pantalla veo: {summary}"
    else:
        answer = f"Análisis de pantalla: {summary}"
    return actions, answer

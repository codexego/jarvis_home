"""Detección e interpretación de consultas de visión."""

from __future__ import annotations

import re

_VISION_PATTERNS = (
    r"\b(qué|que)\s+(tengo|ves|veo|hay|es\s+esto)\b",
    r"\b(en\s+la\s+mano|en\s+mi\s+mano|en\s+la\s+cámara|en\s+la\s+camara)\b",
    r"\b(mira|mirar|muéstrame|muestrame|reconoce|identifica|observa)\b",
    r"\b(what\s+(do\s+i\s+have|am\s+i\s+holding|is\s+this|do\s+you\s+see))\b",
    r"\b(in\s+my\s+hand|look\s+at|can\s+you\s+see|what's\s+this)\b",
    r"\b(cámara|camara|webcam|camera)\b",
)

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _VISION_PATTERNS]


def is_vision_query(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in _COMPILED)


def needs_tracking(text: str) -> bool:
    """True si conviene ráfaga corta (objeto en mano, seguimiento)."""
    lower = text.lower()
    return any(k in lower for k in ("mano", "hand", "tengo", "holding", "sostengo", "sujeto"))


def interpret_vision_answer(query: str, context: dict) -> str:
    labels = context.get("labels") or []
    primary = context.get("primary_object")
    hand_candidates = context.get("hand_candidates") or []
    summary = context.get("summary") or ""

    if not labels:
        return "No detecto ningún objeto con claridad en la cámara."

    query_lower = query.lower()
    hand_query = any(k in query_lower for k in ("mano", "hand", "holding", "tengo", "sostengo"))

    if hand_query and hand_candidates:
        obj = hand_candidates[0]
        return f"Parece que tienes {obj} en la mano."

    if primary:
        if len(labels) == 1:
            return f"Veo {primary}."
        return f"Veo {summary}. Lo más probable es {primary}."

    return f"Veo: {summary}."

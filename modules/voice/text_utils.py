"""Utilidades de limpieza de texto de voz."""

from __future__ import annotations

import re
import unicodedata


def clean_command_text(text: str, wake_word: str = "jarvis") -> str:
    """
    Devuelve texto listo para IA: sin wake word inicial y espacios normalizados.
    """
    if not text:
        return ""

    normalized = unicodedata.normalize("NFKC", text).strip()
    wake_pattern = re.compile(
        rf"^\s*{re.escape(wake_word)}\b\s*[,!.\-:]?\s*",
        re.IGNORECASE,
    )
    cleaned = wake_pattern.sub("", normalized).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned

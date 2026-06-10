"""Construcción de prompts con contexto de memoria."""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """Eres Jarvis Home, un asistente doméstico local que funciona sin internet.
Tu trabajo es interpretar comandos del usuario y decidir qué hacer.

Módulos disponibles para delegar:
- vision_module: cámara, objetos físicos, "qué tengo en la mano"
- screen_monitor: pantalla, videos YouTube, botones, texto en pantalla
- executor: clicks, teclado, acciones del sistema (solo si hay acciones concretas)
- chat: conversación general sin hardware

Responde SIEMPRE en JSON válido con esta estructura:
{
  "intent": "vision|screen|executor|chat|memory",
  "delegate": "vision_module|screen_monitor|executor|null",
  "answer": "respuesta natural en español para el usuario",
  "actions": [{"type": "click|press|type|hotkey|open_url|open_app|type_code|wait", ...}],
  "confidence": 0.0-1.0,
  "learn": {"clave_preferencia": "valor"} o null
}

Reglas:
- Si menciona mano, cámara u objeto físico -> vision
- Si menciona pantalla, video, YouTube, reproducir, buscar en pantalla -> screen
- Si pide abrir app (YouTube, VS Code), escribir codigo o reanudar video -> executor
- Si necesita VER la pantalla para actuar (reproducir video visible, buscar texto) -> screen
- Usa preferencias y hábitos del usuario cuando sean relevantes
- Sé breve y natural en "answer"
"""


def build_routing_messages(
    user_text: str,
    memory_summary: dict[str, Any],
    history: list[dict[str, str]],
) -> list[dict[str, str]]:
    memory_block = _format_memory(memory_summary)
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if memory_block:
        messages.append({"role": "system", "content": f"Memoria del usuario:\n{memory_block}"})
    messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages


def build_response_enhancement_messages(
    user_text: str,
    module_context: dict[str, Any],
    memory_summary: dict[str, Any],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Eres Jarvis Home. Genera una respuesta natural breve en español "
                "basada en los datos del módulo. Responde solo con el texto, sin JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Pregunta: {user_text}\n"
                f"Datos: {json.dumps(module_context, ensure_ascii=False)}\n"
                f"Preferencias: {json.dumps(memory_summary.get('preferences', {}), ensure_ascii=False)}"
            ),
        },
    ]


def _format_memory(summary: dict[str, Any]) -> str:
    parts: list[str] = []
    prefs = summary.get("preferences") or {}
    if prefs:
        parts.append("Preferencias: " + ", ".join(f"{k}={v}" for k, v in prefs.items()))

    habits = summary.get("habits") or []
    if habits:
        lines = [f"- {h.get('pattern')} ({h.get('intent')})" for h in habits[:5]]
        parts.append("Hábitos:\n" + "\n".join(lines))

    frequent = summary.get("frequent_commands") or []
    if frequent:
        lines = [f"- {c.get('phrase_normalized')} x{c.get('count')}" for c in frequent[:5]]
        parts.append("Comandos frecuentes:\n" + "\n".join(lines))

    return "\n\n".join(parts)

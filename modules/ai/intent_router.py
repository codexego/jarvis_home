"""Enrutamiento de intenciones: LLM local + reglas de respaldo."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from modules.ai.llm_client import OllamaClient
from modules.ai.prompt_builder import build_routing_messages
from modules.executor.command_parser import (
    apply_custom_command,
    build_executor_actions,
    is_executor_query,
    parse_executor_command,
)
from modules.screen.query_matcher import is_screen_query, parse_screen_command
from modules.vision.query_matcher import is_vision_query
from services.logging_service import get_logger

logger = get_logger("intent_router")

_VALID_INTENTS = {"vision", "screen", "executor", "chat", "memory", "learn_command"}
_VALID_DELEGATES = {"vision_module", "screen_monitor", "executor", None, "null"}


@dataclass(slots=True)
class RouteDecision:
    intent: str
    delegate: str | None
    answer: str | None
    actions: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    learn: dict[str, str] | None = None
    parsed_screen: dict[str, Any] | None = None
    source: str = "rules"


class IntentRouter:
    """Decide cómo procesar un comando de usuario."""

    def __init__(self, llm: OllamaClient, prefer_llm: bool = True) -> None:
        self.llm = llm
        self.prefer_llm = prefer_llm

    def route(
        self,
        text: str,
        memory_summary: dict[str, Any],
        history: list[dict[str, str]],
    ) -> RouteDecision:
        custom = self._match_custom_command(text, memory_summary)
        if custom:
            return custom

        if self.prefer_llm and self.llm.is_available():
            try:
                decision = self._route_llm(text, memory_summary, history)
                if decision.intent != "chat" or decision.confidence >= 0.6:
                    return decision
            except Exception:
                logger.exception("Fallo LLM, usando reglas locales")

        return self._route_rules(text, memory_summary)

    def _match_custom_command(
        self, text: str, memory_summary: dict[str, Any]
    ) -> RouteDecision | None:
        normalized = " ".join(text.lower().split())
        commands = memory_summary.get("custom_commands") or []
        best = None
        best_len = 0
        for cmd in commands:
            trigger = cmd.get("trigger_phrase", "")
            if trigger and trigger in normalized:
                if len(trigger) > best_len:
                    best_len = len(trigger)
                    best = cmd
        if not best:
            return None
        actions, answer = apply_custom_command(best["trigger_phrase"], best["target"])
        return RouteDecision(
            intent="executor",
            delegate="executor",
            answer=answer,
            actions=actions,
            confidence=0.92,
            source="memory",
        )

    def _route_llm(
        self,
        text: str,
        memory_summary: dict[str, Any],
        history: list[dict[str, str]],
    ) -> RouteDecision:
        messages = build_routing_messages(text, memory_summary, history)
        raw = self.llm.chat(messages, json_mode=True, model=self.llm.model)
        parsed = self._parse_llm_json(raw)

        intent = parsed.get("intent", "chat")
        if intent not in _VALID_INTENTS:
            intent = "chat"

        delegate = parsed.get("delegate")
        if delegate in ("null", ""):
            delegate = None

        learn = parsed.get("learn")
        if learn is not None and not isinstance(learn, dict):
            learn = None

        parsed_screen = None
        if intent == "screen" or delegate == "screen_monitor":
            parsed_screen = parse_screen_command(text)

        actions = parsed.get("actions") or []
        if intent == "executor" and not actions:
            ex = parse_executor_command(text)
            actions, answer = build_executor_actions(ex)
            parsed["answer"] = parsed.get("answer") or answer

        return RouteDecision(
            intent=intent,
            delegate=delegate,
            answer=parsed.get("answer"),
            actions=actions,
            confidence=float(parsed.get("confidence", 0.7)),
            learn=learn,
            parsed_screen=parsed_screen,
            source="llm",
        )

    def _route_rules(self, text: str, memory_summary: dict[str, Any] | None = None) -> RouteDecision:
        if is_vision_query(text):
            return RouteDecision(
                intent="vision",
                delegate="vision_module",
                answer=None,
                confidence=0.85,
                source="rules",
            )

        if is_executor_query(text):
            parsed = parse_executor_command(text)
            if parsed.get("intent") == "learn_command":
                trigger = parsed.get("trigger", "")
                target = parsed.get("target", "")
                return RouteDecision(
                    intent="learn_command",
                    delegate=None,
                    answer=f"Entendido. Cuando digas '{trigger}', abriré {target}.",
                    learn={"trigger": trigger, "target": target},
                    confidence=0.95,
                    source="rules",
                )
            actions, answer = build_executor_actions(parsed)
            return RouteDecision(
                intent="executor",
                delegate="executor",
                answer=answer or None,
                actions=actions,
                confidence=0.85,
                source="rules",
            )

        if is_screen_query(text):
            return RouteDecision(
                intent="screen",
                delegate="screen_monitor",
                answer=None,
                parsed_screen=parse_screen_command(text),
                confidence=0.85,
                source="rules",
            )

        return RouteDecision(
            intent="chat",
            delegate=None,
            answer=self._chat_fallback(text, memory_summary or {}),
            confidence=0.4,
            source="rules",
        )

    @staticmethod
    def _parse_llm_json(raw: str) -> dict[str, Any]:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise

    @staticmethod
    def _chat_fallback(text: str, memory_summary: dict[str, Any]) -> str:
        lower = text.lower()
        if any(w in lower for w in ("hola", "hello", "buenos", "hey", "jarvis")):
            name = memory_summary.get("preferences", {}).get("nombre", "")
            if name:
                return f"Hola, {name}. Estoy listo para ayudarte."
            return "Hola. Estoy listo para ayudarte."
        if any(w in lower for w in ("gracias", "thanks")):
            return "De nada, señor."
        top_apps = memory_summary.get("top_apps") or []
        if "abre" in lower and top_apps:
            return f"Puedo abrir {top_apps[0].get('app_name', 'aplicaciones')} u otras apps registradas."
        return (
            "Puedo ayudarte con la cámara, la pantalla, abrir apps o controlar videos. "
            "Di 'Jarvis' seguido de tu comando."
        )

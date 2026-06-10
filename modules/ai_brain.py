"""Módulo de procesamiento IA local con Ollama y memoria persistente."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from core.base_module import BaseModule
from core.event_bus import Event
from modules.ai.config import AIConfig
from modules.ai.intent_router import IntentRouter, RouteDecision
from modules.ai.llm_client import OllamaClient
from modules.ai.prompt_builder import build_response_enhancement_messages
from modules.screen.query_matcher import build_screen_actions, parse_screen_command
from modules.vision.query_matcher import interpret_vision_answer


class AIBrain(BaseModule):
    """
    Cerebro central: consulta memory antes de responder y delega a modulos.

    Flujo: voice.command -> memory.get_context -> enrutar -> ai.decision -> memory aprende
    """

    name = "ai_brain"

    def __init__(self, event_bus, config: AIConfig | None = None) -> None:
        super().__init__(event_bus)
        self.config = config or AIConfig()
        self._llm: OllamaClient | None = None
        self._router: IntentRouter | None = None
        self._pending_vision: dict[str, dict[str, Any]] = {}
        self._pending_screen: dict[str, dict[str, Any]] = {}
        self._memory_waiters: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._last_memory: dict[str, Any] = {}

    async def on_start(self) -> None:
        self.subscribe("voice.command", self._on_voice_command)
        self.subscribe("user.input", self._on_voice_command)
        self.subscribe("memory.context", self._on_memory_context)
        self.subscribe("vision.analysis", self._on_vision_analysis)
        self.subscribe("vision.error", self._on_vision_error)
        self.subscribe("screen.analysis", self._on_screen_analysis)
        self.subscribe("screen.error", self._on_screen_error)
        self.subscribe("config.update", self._on_config_update)
        self.subscribe("system.shutdown", self._on_shutdown)

        self._llm = OllamaClient(
            base_url=self.config.ollama_base_url,
            model=self.config.model,
            fallback_model=self.config.fallback_model,
            timeout_s=self.config.request_timeout_s,
        )
        if not self.config.dry_run and self._llm.is_available():
            resolved = self.config.resolve_model(self._llm.list_models())
            self._llm.model = resolved
            self.logger.info("Modelo LLM activo: %s", resolved)

        self._router = IntentRouter(self._llm, prefer_llm=self.config.prefer_llm and not self.config.dry_run)

        if self.config.dry_run:
            self.logger.info("AIBrain en modo dry_run (sin llamadas LLM)")
        elif self._llm.is_available():
            models = self._llm.list_models()
            self.logger.info("AIBrain listo | modelo=%s | ollama_models=%d", self.config.model, len(models))
        else:
            self.logger.info("AIBrain listo | modo reglas local (Ollama no detectado)")

    async def on_stop(self) -> None:
        self._pending_vision.clear()
        self._pending_screen.clear()
        for fut in self._memory_waiters.values():
            if not fut.done():
                fut.cancel()
        self._memory_waiters.clear()
        self.logger.info("AIBrain liberado")

    async def run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1)

    async def _on_voice_command(self, event: Event) -> None:
        text = event.payload.get("text", "").strip()
        if not text or not self._router:
            return
        # Tarea independiente: evita deadlock con memory.get_context en el mismo bus
        asyncio.create_task(self._process_voice_command(text), name="process_voice")

    async def _process_voice_command(self, text: str) -> None:
        if not self._router:
            return
        self.logger.info("Procesando comando: %s", text)

        memory_ctx = await self._fetch_memory_context(text)
        snapshot = memory_ctx.get("snapshot") or {}
        memory_summary = dict(snapshot.get("summary") or snapshot)
        if snapshot.get("custom_commands"):
            memory_summary["custom_commands"] = snapshot["custom_commands"]
        if snapshot.get("top_apps"):
            memory_summary["top_apps"] = snapshot["top_apps"]
        history = snapshot.get("history") or []
        intent_suggestion = memory_ctx.get("intent_suggestion")
        cached = snapshot.get("cached_response")

        route = await asyncio.to_thread(
            self._router.route,
            text,
            memory_summary,
            history[:-1] if history else [],
        )

        if intent_suggestion and route.source == "rules" and route.confidence < 0.7:
            suggested_intent = intent_suggestion.get("intent")
            if suggested_intent:
                route.confidence = intent_suggestion.get("confidence", route.confidence)
                self.logger.info("Intencion sugerida por memoria: %s", suggested_intent)

        if route.intent == "chat" and cached and route.source == "rules":
            await self._emit_decision(
                intent=cached.get("intent") or "chat",
                input_text=text,
                answer=cached.get("best_answer"),
                confidence=float(cached.get("avg_confidence", 0.6)),
                route=route,
                extra={"from_memory": True},
            )
            return

        self._apply_learning(route)
        await self._delegate(route, text, memory_summary)

    async def _fetch_memory_context(self, text: str) -> dict[str, Any]:
        request_id = str(uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._memory_waiters[request_id] = future

        await self.emit(
            "memory.get_context",
            {
                "request_id": request_id,
                "text": text,
                "session_id": self.config.session_id,
            },
        )

        try:
            ctx = await asyncio.wait_for(future, timeout=3.0)
            self._last_memory = ctx
            return ctx
        except asyncio.TimeoutError:
            self.logger.warning("Timeout consultando memoria, usando contexto vacio")
            self._memory_waiters.pop(request_id, None)
            return {"snapshot": {"summary": {}, "history": []}}
        except asyncio.CancelledError:
            self._memory_waiters.pop(request_id, None)
            raise

    async def _on_memory_context(self, event: Event) -> None:
        request_id = event.payload.get("request_id", "")
        future = self._memory_waiters.pop(request_id, None)
        if future and not future.done():
            future.set_result(event.payload)

    async def _delegate(
        self,
        route: RouteDecision,
        text: str,
        memory_summary: dict[str, Any] | None = None,
    ) -> None:
        self.logger.info(
            "Ruta: intent=%s delegate=%s source=%s conf=%.2f",
            route.intent,
            route.delegate,
            route.source,
            route.confidence,
        )

        if route.intent == "learn_command":
            learn = route.learn or {}
            await self.emit(
                "memory.learn_command",
                {"trigger": learn.get("trigger", ""), "target": learn.get("target", "")},
            )
            await self._emit_decision(
                intent="learn_command",
                input_text=text,
                answer=route.answer or "Comando aprendido.",
                confidence=route.confidence,
                route=route,
            )
            return

        if route.delegate == "vision_module" or route.intent == "vision":
            request_id = str(uuid4())
            self._pending_vision[request_id] = {"query": text, "route": route}
            await self.emit("vision.capture", {"query": text, "request_id": request_id})
            return

        if route.delegate == "screen_monitor" or route.intent == "screen":
            request_id = str(uuid4())
            parsed = route.parsed_screen or parse_screen_command(text)
            self._pending_screen[request_id] = {"query": text, "parsed": parsed, "route": route}
            await self.emit(
                "screen.capture",
                {"query": text, "request_id": request_id, "parsed": parsed},
            )
            return

        if route.delegate == "executor" or (route.intent == "executor" and route.actions):
            await self._emit_decision(
                intent="executor",
                input_text=text,
                answer=route.answer or "Ejecutando accion.",
                actions=route.actions,
                confidence=route.confidence,
                route=route,
            )
            return

        answer = route.answer or "No tengo una respuesta para eso ahora mismo."
        if route.source == "llm" and self._llm and self._llm.is_available() and not route.answer:
            answer = await asyncio.to_thread(
                self._generate_chat_reply,
                text,
                memory_summary or {},
            )

        await self._emit_decision(
            intent="chat",
            input_text=text,
            answer=answer,
            confidence=route.confidence,
            route=route,
        )

    async def _on_vision_analysis(self, event: Event) -> None:
        request_id = event.payload.get("request_id", "")
        pending = self._pending_vision.pop(request_id, {})
        query = event.payload.get("query") or pending.get("query", "")
        context = event.payload.get("context") or {}
        objects = event.payload.get("objects") or []

        answer = interpret_vision_answer(query, context)
        answer = await self._maybe_enhance_answer(query, {"vision": context, "objects": objects}, answer)

        await self._emit_decision(
            intent="vision_answer",
            input_text=query,
            answer=answer,
            confidence=context.get("primary_confidence", 0.0),
            extra={"vision": {"objects": objects, "context": context}},
        )

    async def _on_vision_error(self, event: Event) -> None:
        request_id = event.payload.get("request_id", "")
        pending = self._pending_vision.pop(request_id, {})
        query = pending.get("query", event.payload.get("query", ""))
        await self._emit_decision(
            intent="vision_error",
            input_text=query,
            answer="No pude acceder a la camara en este momento.",
            confidence=0.0,
        )

    async def _on_screen_analysis(self, event: Event) -> None:
        request_id = event.payload.get("request_id", "")
        pending = self._pending_screen.pop(request_id, {})
        query = event.payload.get("query") or pending.get("query", "")
        parsed = event.payload.get("parsed") or pending.get("parsed") or parse_screen_command(query)
        monitor = event.payload.get("monitor") or {"left": 0, "top": 0, "width": 1920, "height": 1080}

        analysis = {
            "elements": event.payload.get("elements") or [],
            "text_lines": event.payload.get("text_lines") or [],
            "context": event.payload.get("context") or {},
        }

        actions, answer = build_screen_actions(parsed, analysis, monitor)
        answer = await self._maybe_enhance_answer(query, analysis, answer)
        intent = f"screen_{parsed.get('intent', 'describe')}"

        await self._emit_decision(
            intent=intent,
            input_text=query,
            answer=answer,
            actions=actions,
            confidence=0.75 if actions else 0.5,
            extra={"screen": analysis},
        )

    async def _on_screen_error(self, event: Event) -> None:
        request_id = event.payload.get("request_id", "")
        pending = self._pending_screen.pop(request_id, {})
        query = pending.get("query", event.payload.get("query", ""))
        await self._emit_decision(
            intent="screen_error",
            input_text=query,
            answer="No pude analizar la pantalla en este momento.",
            confidence=0.0,
        )

    async def _emit_decision(
        self,
        intent: str,
        input_text: str,
        answer: str | None,
        confidence: float = 0.5,
        actions: list[dict[str, Any]] | None = None,
        extra: dict[str, Any] | None = None,
        route: RouteDecision | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "intent": intent,
            "input": input_text,
            "answer": answer,
            "confidence": confidence,
        }
        if actions:
            payload["actions"] = actions
        if extra:
            payload.update(extra)
        if route:
            payload["routing"] = {"source": route.source, "learn": route.learn}

        self.logger.info("Decision: %s | %s", intent, (answer or "")[:80])
        await self.emit("ai.decision", payload)

    def _apply_learning(self, route: RouteDecision) -> None:
        if not route.learn:
            return
        for key, value in route.learn.items():
            asyncio.create_task(
                self.emit(
                    "memory.preferences",
                    {"action": "set", "key": str(key), "value": str(value)},
                )
            )

    async def _maybe_enhance_answer(
        self,
        query: str,
        module_context: dict[str, Any],
        fallback: str,
    ) -> str:
        if self.config.dry_run or not self._llm or not self._llm.is_available():
            return fallback
        memory_summary = (self._last_memory.get("snapshot") or {}).get("summary") or {}
        try:
            return await asyncio.to_thread(
                self._generate_enhanced_answer,
                query,
                module_context,
                memory_summary,
                fallback,
            )
        except Exception:
            self.logger.debug("No se pudo mejorar respuesta con LLM")
            return fallback

    def _generate_enhanced_answer(
        self,
        query: str,
        module_context: dict[str, Any],
        memory_summary: dict[str, Any],
        fallback: str,
    ) -> str:
        assert self._llm is not None
        messages = build_response_enhancement_messages(query, module_context, memory_summary)
        reply = self._llm.chat(messages, temperature=0.5)
        return reply.strip() or fallback

    def _generate_chat_reply(self, text: str, memory_summary: dict[str, Any]) -> str:
        assert self._llm is not None
        history = memory_summary.get("recent_interactions") or []
        context_lines = [
            f"Usuario dijo: {h.get('input_text')} -> {h.get('answer')}"
            for h in history[:3]
            if h.get("input_text")
        ]
        prefs = memory_summary.get("preferences") or {}
        work = memory_summary.get("active_work_context") or {}
        system = (
            "Eres Jarvis Home, asistente local amable. Responde breve en espanol. "
            f"Preferencias: {prefs}. Contexto trabajo: {work.get('name', 'general')}."
        )
        if context_lines:
            system += " Reciente: " + " | ".join(context_lines)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ]
        return self._llm.chat(messages, temperature=0.6)

    async def _on_config_update(self, event: Event) -> None:
        model = event.payload.get("llm_model")
        if model and self._llm:
            self._llm.model = model
            self.config.model = model
            self.logger.info("Modelo LLM actualizado: %s", model)

    async def _on_shutdown(self, event: Event) -> None:
        self.logger.debug("Apagado del sistema recibido")

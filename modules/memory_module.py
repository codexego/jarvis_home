"""Módulo de memoria y aprendizaje continuo."""

from __future__ import annotations

import asyncio
from uuid import uuid4

from core.base_module import BaseModule
from core.event_bus import Event
from modules.memory.config import MemoryConfig
from modules.memory.context_detector import suggest_intent_from_habits
from modules.memory.pattern_learner import PatternLearner
from services.memory_store import MemoryStore


class Memory(BaseModule):
    """
    Aprendizaje continuo 24/7: persiste interacciones y refina patrones.

    ai_brain consulta via memory.get_context antes de responder.
    Se actualiza tras cada interaccion relevante.
    """

    name = "memory"

    def __init__(self, event_bus, config: MemoryConfig | None = None) -> None:
        super().__init__(event_bus)
        self.config = config or MemoryConfig()
        self._store: MemoryStore | None = None
        self._learner: PatternLearner | None = None

    async def on_start(self) -> None:
        self.subscribe("voice.command", self._on_voice_command)
        self.subscribe("user.input", self._on_voice_command)
        self.subscribe("ai.decision", self._on_ai_decision)
        self.subscribe("action.completed", self._on_action_completed)
        self.subscribe("vision.analysis", self._on_module_context)
        self.subscribe("screen.analysis", self._on_module_context)
        self.subscribe("memory.get_context", self._on_get_context)
        self.subscribe("memory.store", self._on_memory_store)
        self.subscribe("memory.query", self._on_query)
        self.subscribe("memory.search", self._on_search)
        self.subscribe("memory.preferences", self._on_preferences)
        self.subscribe("memory.learn_command", self._on_learn_command)
        self.subscribe("system.shutdown", self._on_shutdown)

        self._store = MemoryStore(self.config.db_path)
        self._store._retention_days = self.config.retention_days
        self._learner = PatternLearner(self._store, habit_threshold=self.config.habit_threshold)
        stats = self._store.stats()
        self.logger.info(
            "Memory listo | db=%s | interacciones=%d | habitos=%d | prefs=%d",
            self.config.db_path,
            stats["interactions"],
            stats["habits"],
            stats["preferences"],
        )

    async def on_stop(self) -> None:
        if self._store:
            self._store.close()
            self._store = None
        self._learner = None
        self.logger.info("Memory liberado")

    async def run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.config.learn_interval_s)
            if self._learner:
                await asyncio.to_thread(self._learner.run_maintenance)

    async def _on_voice_command(self, event: Event) -> None:
        if not self._store or not self._learner:
            return
        text = (event.payload.get("text") or "").strip()
        if not text:
            return
        await asyncio.to_thread(self._learner.learn_from_command, text)
        await asyncio.to_thread(
            self._store.record_interaction,
            "voice.command",
            text,
            None,
            None,
            event.payload,
        )

    async def _on_ai_decision(self, event: Event) -> None:
        if not self._store or not self._learner:
            return
        payload = event.payload
        await asyncio.to_thread(self._learner.learn_from_decision, payload)
        await asyncio.to_thread(
            self._store.record_interaction,
            "ai.decision",
            payload.get("input"),
            payload.get("intent"),
            payload.get("answer"),
            payload,
        )
        answer = payload.get("answer")
        if answer:
            await asyncio.to_thread(
                self._store.add_context_message,
                "assistant",
                answer,
                self.config.session_id,
            )

    async def _on_action_completed(self, event: Event) -> None:
        if not self._store:
            return
        payload = event.payload
        await asyncio.to_thread(
            self._store.record_interaction,
            "action.completed",
            None,
            payload.get("intent"),
            payload.get("answer"),
            payload,
        )
        if payload.get("status") == "ok" and payload.get("intent"):
            from datetime import datetime, timezone

            await asyncio.to_thread(
                self._store.set_preference,
                f"last_success_{payload['intent']}",
                datetime.now(timezone.utc).isoformat(),
            )
            # Registrar uso de app si aplica
            for result in payload.get("results") or []:
                app = result.get("app")
                if app and result.get("ok"):
                    await asyncio.to_thread(self._store.record_app_usage, app)

    async def _on_module_context(self, event: Event) -> None:
        if not self._store:
            return
        topic = event.topic
        ctx_name = "media" if "vision" in topic else "productivity"
        await asyncio.to_thread(
            self._store.update_work_context,
            ctx_name,
            {"source": event.source, "topic": topic},
        )

    async def _on_get_context(self, event: Event) -> None:
        if not self._store:
            return

        request_id = event.payload.get("request_id") or str(uuid4())
        user_text = (event.payload.get("text") or "").strip()
        session_id = event.payload.get("session_id") or self.config.session_id

        if user_text:
            await asyncio.to_thread(self._store.add_context_message, "user", user_text, session_id)
            if self._learner:
                await asyncio.to_thread(self._learner.learn_from_command, user_text)

        snapshot = await asyncio.to_thread(
            self._store.build_context_snapshot,
            session_id,
            self.config.max_context_messages,
        )

        suggestion = None
        if user_text:
            suggestion = suggest_intent_from_habits(user_text, snapshot.get("habits") or [])
            cached = await asyncio.to_thread(self._store.get_best_response, user_text)
            if cached:
                snapshot["cached_response"] = cached

        await self.emit(
            "memory.context",
            {
                "request_id": request_id,
                "snapshot": snapshot,
                "intent_suggestion": suggestion,
            },
        )

    async def _on_memory_store(self, event: Event) -> None:
        if not self._store:
            return
        p = event.payload
        await asyncio.to_thread(
            self._store.record_interaction,
            p.get("topic", "memory.store"),
            p.get("payload", {}).get("input"),
            p.get("payload", {}).get("intent"),
            p.get("payload", {}).get("answer"),
            p.get("payload"),
        )

    async def _on_query(self, event: Event) -> None:
        if not self._store:
            return
        limit = event.payload.get("limit", 10)
        results = await asyncio.to_thread(self._store.query_recent, limit)
        summary = await asyncio.to_thread(self._store.get_memory_summary)
        stats = await asyncio.to_thread(self._store.stats)
        await self.emit(
            "memory.response",
            {"results": results, "summary": summary, "stats": stats, "total": len(results)},
        )

    async def _on_search(self, event: Event) -> None:
        if not self._store:
            return
        query = event.payload.get("query", "")
        limit = event.payload.get("limit", 10)
        results = await asyncio.to_thread(self._store.search_interactions, query, limit)
        await self.emit("memory.search_results", {"query": query, "results": results})

    async def _on_learn_command(self, event: Event) -> None:
        if not self._store or not self._learner:
            return
        trigger = event.payload.get("trigger", "")
        target = event.payload.get("target", "")
        if trigger and target:
            await asyncio.to_thread(self._learner.learn_custom_command, trigger, target)

    async def _on_preferences(self, event: Event) -> None:
        if not self._store:
            return
        action = event.payload.get("action", "get")
        key = event.payload.get("key", "")
        if action == "set" and key:
            await asyncio.to_thread(
                self._store.set_preference,
                key,
                str(event.payload.get("value", "")),
            )
        value = await asyncio.to_thread(self._store.get_preference, key) if key else None
        prefs = await asyncio.to_thread(self._store.get_preferences)
        await self.emit("memory.preferences", {"key": key, "value": value, "all": prefs})

    async def _on_shutdown(self, event: Event) -> None:
        self.logger.debug("Apagado del sistema recibido")

"""Módulo ejecutor de acciones en el sistema."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from core.base_module import BaseModule
from core.event_bus import Event
from modules.executor.action_runner import ActionRunner
from modules.executor.command_parser import is_cancellation, is_confirmation
from modules.executor.config import ExecutorConfig
from modules.executor.security import partition_actions


@dataclass
class _PendingBatch:
    actions: list[dict[str, Any]]
    intent: str
    answer: str | None
    created_at: float = field(default_factory=time.time)
    request_id: str = ""


class Executor(BaseModule):
    """
    Ejecuta acciones de ratón, teclado, apps y navegador.

    Integra con screen_monitor via acciones contextuales (clicks, teclas).
    Las acciones de riesgo medio/alto requieren confirmación por voz.
    """

    name = "executor"

    def __init__(self, event_bus, config: ExecutorConfig | None = None) -> None:
        super().__init__(event_bus)
        self.config = config or ExecutorConfig()
        self._runner = ActionRunner(
            action_pause_s=self.config.action_pause_s,
            browser_cmd=self.config.browser_cmd,
        )
        self._pending: dict[str, _PendingBatch] = {}
        self._last_screen: dict[str, Any] | None = None

    async def on_start(self) -> None:
        self.subscribe("ai.decision", self._on_ai_decision)
        self.subscribe("executor.run", self._on_direct_action)
        self.subscribe("executor.confirm", self._on_confirm)
        self.subscribe("voice.command", self._on_voice_confirm)
        self.subscribe("screen.analysis", self._on_screen_analysis)
        self.subscribe("system.shutdown", self._on_shutdown)

        mode = "dry_run" if self.config.dry_run else "live"
        confirm = "auto" if self.config.auto_confirm else "voz requerida"
        self.logger.info("Executor listo | modo=%s | confirmacion=%s", mode, confirm)

    async def on_stop(self) -> None:
        self._pending.clear()
        self.logger.info("Executor liberado")

    async def run_loop(self) -> None:
        while self._running:
            await self._expire_pending()
            await asyncio.sleep(0.5)

    async def _on_screen_analysis(self, event: Event) -> None:
        self._last_screen = {
            "elements": event.payload.get("elements") or [],
            "context": event.payload.get("context") or {},
            "monitor": event.payload.get("monitor") or {},
        }
        self.logger.debug(
            "Contexto de pantalla actualizado | elementos=%d",
            len(self._last_screen["elements"]),
        )

    async def _on_ai_decision(self, event: Event) -> None:
        intent = event.payload.get("intent", "unknown")
        actions = list(event.payload.get("actions") or [])
        answer = event.payload.get("answer")

        if not actions:
            self.logger.debug("Sin acciones para intent: %s", intent)
            await self.emit(
                "action.completed",
                {"intent": intent, "status": "no_actions", "answer": answer},
            )
            return

        actions = self._enrich_with_screen_context(actions)
        await self._execute_batch(
            actions=actions,
            intent=intent,
            answer=answer,
            source="ai.decision",
        )

    async def _on_direct_action(self, event: Event) -> None:
        actions = event.payload.get("actions") or []
        if not actions:
            return
        await self._execute_batch(
            actions=actions,
            intent=event.payload.get("intent", "direct"),
            answer=event.payload.get("answer"),
            source="executor.run",
        )

    async def _execute_batch(
        self,
        actions: list[dict[str, Any]],
        intent: str,
        answer: str | None,
        source: str,
    ) -> None:
        safe, pending = partition_actions(actions, self.config.auto_confirm)

        results: list[dict[str, Any]] = []
        if safe:
            results = await asyncio.to_thread(
                self._runner.run,
                safe,
                self.config.dry_run,
            )
            self.logger.info("Acciones seguras ejecutadas: %d", len(results))

        if pending:
            batch_id = str(uuid4())
            self._pending[batch_id] = _PendingBatch(
                actions=pending,
                intent=intent,
                answer=answer,
                request_id=batch_id,
            )
            await self.emit(
                "executor.confirmation_required",
                {
                    "batch_id": batch_id,
                    "intent": intent,
                    "actions": pending,
                    "answer": answer,
                    "message": (
                        f"Tengo {len(pending)} accion(es) pendiente(s) de confirmacion. "
                        "Di 'confirmar' para ejecutar o 'cancelar' para abortar."
                    ),
                },
            )
            await self.emit(
                "action.completed",
                {
                    "intent": intent,
                    "status": "pending_confirmation",
                    "results": results,
                    "pending_batch_id": batch_id,
                    "answer": answer,
                },
            )
            return

        status = "ok" if all(r.get("ok") for r in results) else "partial"
        await self.emit(
            "action.completed",
            {
                "intent": intent,
                "status": status,
                "results": results,
                "answer": answer,
                "source": source,
            },
        )

    def _enrich_with_screen_context(self, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self._last_screen:
            return actions

        enriched: list[dict[str, Any]] = []
        context = self._last_screen.get("context") or {}
        monitor = self._last_screen.get("monitor") or {}

        for action in actions:
            target_name = action.get("target")
            play = context.get("play_target")
            if target_name in ("play", "play_button") and play:
                from modules.screen.analyzer import scale_point

                scale = context.get("scale") or 1.0
                center = play.get("center") or [
                    play["bbox"][0] + play["bbox"][2] // 2,
                    play["bbox"][1] + play["bbox"][3] // 2,
                ]
                x, y = scale_point(center[0], center[1], scale, monitor)
                enriched.append({**action, "type": "click", "x": x, "y": y})
                continue
            enriched.append(action)
        return enriched

    async def _on_confirm(self, event: Event) -> None:
        batch_id = event.payload.get("batch_id", "")
        if event.payload.get("confirmed", True):
            await self._run_pending(batch_id)
        else:
            await self._cancel_pending(batch_id)

    async def _on_voice_confirm(self, event: Event) -> None:
        if not self._pending:
            return
        text = event.payload.get("text", "")
        if is_confirmation(text):
            for batch_id in list(self._pending.keys()):
                await self._run_pending(batch_id)
        elif is_cancellation(text):
            for batch_id in list(self._pending.keys()):
                await self._cancel_pending(batch_id)

    async def _run_pending(self, batch_id: str) -> None:
        batch = self._pending.pop(batch_id, None)
        if not batch:
            return
        results = await asyncio.to_thread(
            self._runner.run,
            batch.actions,
            self.config.dry_run,
        )
        await self.emit(
            "action.completed",
            {
                "intent": batch.intent,
                "status": "ok",
                "results": results,
                "answer": batch.answer,
                "confirmed": True,
            },
        )

    async def _cancel_pending(self, batch_id: str) -> None:
        batch = self._pending.pop(batch_id, None)
        if not batch:
            return
        await self.emit(
            "action.completed",
            {
                "intent": batch.intent,
                "status": "cancelled",
                "answer": batch.answer,
            },
        )

    async def _expire_pending(self) -> None:
        if not self._pending:
            return
        now = time.time()
        expired = [
            bid
            for bid, batch in self._pending.items()
            if now - batch.created_at > self.config.confirmation_timeout_s
        ]
        for batch_id in expired:
            await self._cancel_pending(batch_id)
            await self.emit(
                "executor.confirmation_expired",
                {"batch_id": batch_id, "message": "Confirmacion expirada."},
            )

    async def _on_shutdown(self, event: Event) -> None:
        self._pending.clear()

"""Módulo de respuesta: TTS + panel visual para feedback al usuario."""

from __future__ import annotations

import asyncio
from typing import Any

from core.base_module import BaseModule
from core.event_bus import Event
from modules.response.config import ResponseConfig
from modules.response.ui_panel import ResponsePanel
from services.tts_engine import TTSEngine


class ResponseModule(BaseModule):
    """
    Responde SIEMPRE con texto en pantalla y voz simultánea.

    Suscrito a decisiones IA, confirmaciones, wake word y estado de escucha.
    """

    name = "response"

    def __init__(self, event_bus, config: ResponseConfig | None = None) -> None:
        super().__init__(event_bus)
        self.config = config or ResponseConfig()
        self._tts: TTSEngine | None = None
        self._ui: ResponsePanel | None = None
        self._tts_busy = asyncio.Event()
        self._tts_busy.set()

    async def on_start(self) -> None:
        self.subscribe("voice.wake", self._on_wake)
        self.subscribe("voice.listening", self._on_listening)
        self.subscribe("voice.command", self._on_voice_command)
        self.subscribe("ai.decision", self._on_ai_decision)
        self.subscribe("action.completed", self._on_action_completed)
        self.subscribe("executor.confirmation_required", self._on_confirmation_required)
        self.subscribe("system.ready", self._on_system_ready)
        self.subscribe("system.shutdown", self._on_shutdown)

        if self.config.dry_run:
            self.logger.info("ResponseModule en modo dry_run")
            return

        if self.config.ui_enabled:
            self._ui = ResponsePanel(title=self.config.window_title)
            await asyncio.to_thread(self._ui.start)

        if self.config.tts_enabled:
            loop = asyncio.get_running_loop()
            self._tts = TTSEngine(
                rate=self.config.tts_rate,
                volume=self.config.tts_volume,
                voice_hint=self.config.voice_hint,
                on_start=lambda: loop.call_soon_threadsafe(self._tts_busy.clear),
                on_finish=lambda: loop.call_soon_threadsafe(self._tts_busy.set),
            )
            await asyncio.to_thread(self._tts.start)

        self.logger.info("ResponseModule listo | TTS=%s | UI=%s", self.config.tts_enabled, self.config.ui_enabled)

    async def on_stop(self) -> None:
        if self._tts:
            await asyncio.to_thread(self._tts.stop)
            self._tts = None
        if self._ui:
            await asyncio.to_thread(self._ui.stop)
            self._ui = None

    async def run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1)

    async def _on_system_ready(self, event: Event) -> None:
        await self._respond("Jarvis Home listo.", intent="system.ready", speak=False)

    async def _on_wake(self, event: Event) -> None:
        if not event.payload.get("ack", True):
            return
        if self._ui:
            await asyncio.to_thread(self._ui.set_status, "Escuchando", "wake word detectada")
        await self.emit("ui.speaking", {"active": True, "text": self.config.wake_ack})
        await self._speak(self.config.wake_ack, interrupt=True)
        await self.emit("ui.speaking", {"active": False})

    async def _on_listening(self, event: Event) -> None:
        status = event.payload.get("status", "passive")
        if status == "active":
            detail = "di tu comando"
            label = "Escuchando comando"
        else:
            detail = "di 'Jarvis'"
            label = "Modo pasivo"
        if self._ui:
            await asyncio.to_thread(self._ui.set_status, label, detail)

    async def _on_voice_command(self, event: Event) -> None:
        text = event.payload.get("text", "")
        if text and self._ui:
            await asyncio.to_thread(self._ui.show_command, text)

    async def _on_ai_decision(self, event: Event) -> None:
        answer = event.payload.get("answer")
        if not answer:
            return
        intent = event.payload.get("intent", "")
        confidence = float(event.payload.get("confidence", 0))
        await self._respond(answer, intent=intent, confidence=confidence, speak=True)

    async def _on_action_completed(self, event: Event) -> None:
        status = event.payload.get("status", "")
        answer = event.payload.get("answer")
        if status == "pending_confirmation":
            return
        if status == "cancelled":
            await self._respond("Acción cancelada.", intent="executor", speak=True)
            return
        if answer and status in ("ok", "partial"):
            await self._respond(answer, intent=event.payload.get("intent", ""), speak=True)

    async def _on_confirmation_required(self, event: Event) -> None:
        message = event.payload.get("message") or "Necesito confirmación para continuar."
        await self._respond(message, intent="confirmation", speak=True)

    async def _respond(
        self,
        text: str,
        intent: str = "",
        confidence: float = 0.0,
        speak: bool = True,
    ) -> None:
        if self._ui:
            await asyncio.to_thread(self._ui.show_response, text, intent, confidence)
        if speak:
            await self.emit("ui.speaking", {"active": True, "text": text[:120]})
            await self._speak(text)
            await self.emit("ui.speaking", {"active": False})

    async def _speak(self, text: str, *, interrupt: bool = False) -> None:
        if not self._tts or not self.config.tts_enabled:
            return
        await asyncio.to_thread(self._tts.speak, text, interrupt=interrupt)
        if not interrupt:
            await self._tts_busy.wait()

    async def _on_shutdown(self, event: Event) -> None:
        pass

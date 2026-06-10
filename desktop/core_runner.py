"""Ejecuta el core Jarvis en un hilo con asyncio."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import Any

from core.app import JarvisApp
from core.bootstrap import build_registry
from core.event_bus import Event
from desktop.bridge import EventBridge
from services.logging_service import get_logger

logger = get_logger("desktop_core")

# Topics que la UI consume
_UI_TOPICS = frozenset({
    "voice.wake",
    "voice.listening",
    "voice.command",
    "user.input",
    "ai.decision",
    "action.completed",
    "executor.confirmation_required",
    "screen.capturing",
    "screen.analysis",
    "vision.capturing",
    "ui.speaking",
    "system.ready",
    "system.shutdown",
    "config.update",
})


class CoreRunner:
    """Arranca y detiene JarvisApp en hilo de fondo."""

    def __init__(self, bridge: EventBridge, log_file: Path | None = None) -> None:
        self.bridge = bridge
        self.log_file = log_file
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._app: JarvisApp | None = None
        self._ready = threading.Event()

    @property
    def loop(self) -> asyncio.AbstractEventLoop | None:
        return self._loop

    @property
    def event_bus(self):
        return self._app.event_bus if self._app else None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._thread = threading.Thread(target=self._run_loop, name="jarvis_core", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=30.0)

    def stop(self) -> None:
        if self._loop and self._app:
            fut = asyncio.run_coroutine_threadsafe(self._app.stop(), self._loop)
            try:
                fut.result(timeout=15.0)
            except Exception:
                logger.exception("Error deteniendo core")
        if self._thread:
            self._thread.join(timeout=5.0)

    def submit(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        if not self._loop or not self._app:
            return
        asyncio.run_coroutine_threadsafe(
            self._app.event_bus.emit(topic=topic, payload=payload or {}, source="desktop"),
            self._loop,
        )

    def send_text(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.bridge.enqueue("user.input", {"text": text, "source": "desktop"}, source="desktop")
        self.submit("user.input", {"text": text, "source": "desktop"})

    def _run_loop(self) -> None:
        if __import__("sys").platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_main())

    async def _async_main(self) -> None:
        self._app = JarvisApp(
            registry=build_registry(desktop_mode=True),
            log_file=self.log_file,
        )
        await self._app.start()
        self._wire_bridge()
        self._ready.set()
        logger.info("Core Jarvis listo en hilo de fondo")
        await self._app._shutdown_event.wait()

    def _wire_bridge(self) -> None:
        assert self._app is not None
        bus = self._app.event_bus

        async def forward(event: Event) -> None:
            if event.topic in _UI_TOPICS:
                await self.bridge.on_event(event)

        for topic in _UI_TOPICS:
            bus.subscribe(topic, forward)

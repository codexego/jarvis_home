"""Módulo de monitorización de pantalla bajo demanda."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

from core.base_module import BaseModule
from core.event_bus import Event
from modules.screen.analyzer import ScreenAnalyzer
from modules.screen.capture import ScreenCapture
from modules.screen.config import ScreenConfig
from modules.screen.overlay import NeonOverlay
from modules.screen.query_matcher import parse_screen_command


class ScreenMonitor(BaseModule):
    """
    Captura y analiza la pantalla solo cuando se solicita.

    Muestra overlay neón durante el análisis. No hay captura continua.
    """

    name = "screen_monitor"

    def __init__(self, event_bus, config: ScreenConfig | None = None) -> None:
        super().__init__(event_bus)
        self.config = config or ScreenConfig()
        self._capture: ScreenCapture | None = None
        self._analyzer: ScreenAnalyzer | None = None
        self._overlay: NeonOverlay | None = None
        self._capture_lock = asyncio.Lock()
        self._busy = False

    async def on_start(self) -> None:
        self.subscribe("screen.capture", self._on_capture_request)
        self.subscribe("system.shutdown", self._on_shutdown)

        for err in self.config.validate():
            self.logger.error(err)

        if self.config.dry_run:
            self.logger.info("ScreenMonitor en modo dry_run")
            return

        self._capture = ScreenCapture()
        self._analyzer = ScreenAnalyzer(
            analysis_scale=self.config.analysis_scale,
            ocr_min_confidence=self.config.ocr_min_confidence,
            ocr_lang=self.config.ocr_lang,
        )
        if self.config.overlay_enabled:
            self._overlay = NeonOverlay(
                color=self.config.overlay_color,
                border_width=self.config.overlay_width,
            )
        self.logger.info("ScreenMonitor listo | captura bajo demanda")

    async def on_stop(self) -> None:
        if self._overlay and self._overlay.is_visible:
            await asyncio.to_thread(self._overlay.hide)
        self.logger.info("ScreenMonitor liberado")

    async def run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1)

    async def _on_capture_request(self, event: Event) -> None:
        request_id = event.payload.get("request_id") or str(uuid4())
        query = event.payload.get("query", "")
        parsed = event.payload.get("parsed") or parse_screen_command(query)
        search_phrase = parsed.get("phrase")

        if self.config.dry_run:
            await self._emit_stub(request_id, query, parsed)
            return

        if self._busy:
            self.logger.warning("Captura de pantalla en curso")
            await self.emit("screen.busy", {"request_id": request_id})
            return

        async with self._capture_lock:
            self._busy = True
            await self.emit("screen.capturing", {"request_id": request_id, "query": query})
            started = time.perf_counter()

            try:
                if self._overlay and self.config.overlay_enabled:
                    await asyncio.to_thread(self._overlay.show)

                result = await asyncio.to_thread(
                    self._capture_and_analyze,
                    search_phrase,
                )
            except Exception:
                self.logger.exception("Error en captura de pantalla")
                await self.emit(
                    "screen.error",
                    {"request_id": request_id, "query": query, "error": "capture_failed"},
                )
                return
            finally:
                if self._overlay and self._overlay.is_visible:
                    await asyncio.to_thread(self._overlay.hide)
                self._busy = False

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            payload = {
                "request_id": request_id,
                "query": query,
                "parsed": parsed,
                "monitor": result["monitor"],
                "elements": result["analysis"]["elements"],
                "text_lines": result["analysis"]["text_lines"],
                "context": result["analysis"]["context"],
                "elapsed_ms": elapsed_ms,
            }

            await self.emit("screen.analysis", payload)
            self.logger.info(
                "Pantalla analizada | elementos=%d | %dms",
                len(payload["elements"]),
                elapsed_ms,
            )

    def _capture_and_analyze(self, search_phrase: str | None) -> dict[str, Any]:
        assert self._capture is not None
        assert self._analyzer is not None

        frame, monitor = self._capture.grab()
        analysis = self._analyzer.analyze(frame, search_phrase=search_phrase)
        return {"monitor": monitor, "analysis": analysis}

    async def _emit_stub(
        self,
        request_id: str,
        query: str,
        parsed: dict[str, Any],
    ) -> None:
        payload = {
            "request_id": request_id,
            "query": query,
            "parsed": parsed,
            "monitor": {"left": 0, "top": 0, "width": 1920, "height": 1080},
            "elements": [
                {
                    "type": "video",
                    "label": "YouTube",
                    "bbox": [0, 0, 1920, 1080],
                    "confidence": 0.8,
                    "center": [960, 540],
                },
                {
                    "type": "button",
                    "label": "Play",
                    "bbox": [900, 500, 80, 80],
                    "confidence": 0.7,
                    "center": [940, 540],
                },
                {
                    "type": "text",
                    "label": "Sample video title about python tutorial",
                    "bbox": [100, 200, 400, 30],
                    "confidence": 0.85,
                    "center": [300, 215],
                },
            ],
            "text_lines": ["Sample video title about python tutorial", "YouTube"],
            "context": {
                "summary": "video detectado, 1 botones, texto: Sample video",
                "has_youtube": True,
                "text_line_count": 2,
                "button_count": 1,
                "search_phrase": parsed.get("phrase"),
                "phrase_match": (
                    {"line_index": 0, "line": "Sample video title about python tutorial", "matched": parsed.get("phrase")}
                    if parsed.get("phrase") and "python" in (parsed.get("phrase") or "").lower()
                    else None
                ),
                "play_target": {
                    "type": "button",
                    "label": "Play",
                    "bbox": [900, 500, 80, 80],
                    "center": [940, 540],
                },
                "scale": 1.0,
            },
            "elapsed_ms": 0,
            "dry_run": True,
        }
        await self.emit("screen.analysis", payload)

    async def _on_shutdown(self, event: Event) -> None:
        if self._overlay and self._overlay.is_visible:
            await asyncio.to_thread(self._overlay.hide)
        self.logger.debug("Apagado del sistema recibido")

"""Módulo de visión por cámara bajo demanda."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

from core.base_module import BaseModule
from core.event_bus import Event
from modules.vision.camera import Camera
from modules.vision.config import VisionConfig
from modules.vision.object_detector import ObjectDetector
from modules.vision.query_matcher import needs_tracking
from modules.vision.tracker import ShortBurstTracker


class VisionModule(BaseModule):
    """
    Captura y analiza frames solo cuando se solicita.

    La cámara permanece apagada hasta recibir vision.capture.
    La inferencia YOLO corre en un hilo para no bloquear el event loop.
    """

    name = "vision_module"

    def __init__(self, event_bus, config: VisionConfig | None = None) -> None:
        super().__init__(event_bus)
        self.config = config or VisionConfig()
        self._camera: Camera | None = None
        self._detector: ObjectDetector | None = None
        self._capture_lock = asyncio.Lock()
        self._busy = False

    async def on_start(self) -> None:
        self.subscribe("vision.capture", self._on_capture_request)
        self.subscribe("system.shutdown", self._on_shutdown)

        errors = self.config.validate()
        for err in errors:
            self.logger.error(err)

        if self.config.dry_run:
            self.logger.info("VisionModule en modo dry_run (sin cámara)")
            return

        self._camera = Camera(
            device_index=self.config.camera_index,
            warmup_frames=self.config.warmup_frames,
            capture_timeout_s=self.config.capture_timeout_s,
        )
        self._detector = ObjectDetector(
            model_path=self.config.model_path,
            model_name=self.config.model_name,
            confidence=self.config.confidence_threshold,
            inference_size=self.config.inference_size,
        )
        self.logger.info(
            "VisionModule listo | cámara bajo demanda | modelo=%s",
            self.config.model_name,
        )

    async def on_stop(self) -> None:
        if self._camera and self._camera.is_open:
            await asyncio.to_thread(self._camera.close)
        self.logger.info("VisionModule liberado")

    async def run_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1)

    async def _on_capture_request(self, event: Event) -> None:
        request_id = event.payload.get("request_id") or str(uuid4())
        query = event.payload.get("query", "")

        if self.config.dry_run:
            await self._emit_stub_analysis(request_id, query)
            return

        if self._busy:
            self.logger.warning("Captura en curso, ignorando solicitud duplicada")
            await self.emit(
                "vision.busy",
                {"request_id": request_id, "query": query},
            )
            return

        async with self._capture_lock:
            self._busy = True
            await self.emit("vision.capturing", {"request_id": request_id, "query": query})
            started = time.perf_counter()

            try:
                result = await asyncio.to_thread(self._capture_and_detect, query)
            except Exception:
                self.logger.exception("Error en captura/análisis")
                await self.emit(
                    "vision.error",
                    {"request_id": request_id, "query": query, "error": "capture_failed"},
                )
                return
            finally:
                self._busy = False

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            result["request_id"] = request_id
            result["query"] = query
            result["elapsed_ms"] = elapsed_ms

            await self.emit("vision.analysis", result)
            await self.emit(
                "vision.frame",
                {
                    "request_id": request_id,
                    "objects": result["objects"],
                    "context": result["context"],
                },
            )
            self.logger.info(
                "Análisis enviado | objetos=%d | %dms",
                result["context"]["count"],
                elapsed_ms,
            )

    def _capture_and_detect(self, query: str = "") -> dict[str, Any]:
        assert self._camera is not None
        assert self._detector is not None

        use_tracking = self.config.tracking_enabled and needs_tracking(query)

        if use_tracking and query:
            tracker = ShortBurstTracker(
                self._detector,
                self._camera,
                frames=self.config.tracking_frames,
                interval_s=self.config.tracking_interval_s,
            )
            return tracker.capture_and_track()

        frame = self._camera.capture_on_demand()
        if frame is None:
            return {
                "objects": [],
                "context": ObjectDetector.build_context([]),
                "frame_shape": None,
            }

        detections = self._detector.detect(frame)
        objects = [d.to_dict() for d in detections]
        context = ObjectDetector.build_context(detections, frame.shape)

        return {
            "objects": objects,
            "context": context,
            "frame_shape": list(frame.shape),
        }

    async def _emit_stub_analysis(self, request_id: str, query: str) -> None:
        payload = {
            "request_id": request_id,
            "query": query,
            "objects": [
                {"label": "cup", "confidence": 0.71, "bbox": [120, 80, 280, 320]},
            ],
            "context": {
                "summary": "cup",
                "labels": ["cup"],
                "count": 1,
                "primary_object": "cup",
                "primary_confidence": 0.71,
                "hand_candidates": ["cup"],
            },
            "frame_shape": [480, 640, 3],
            "elapsed_ms": 0,
            "dry_run": True,
        }
        await self.emit("vision.analysis", payload)
        await self.emit(
            "vision.frame",
            {
                "request_id": request_id,
                "objects": payload["objects"],
                "context": payload["context"],
            },
        )

    async def _on_shutdown(self, event: Event) -> None:
        self.logger.debug("Apagado del sistema recibido")

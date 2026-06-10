"""Captura de micrófono en hilo separado con cola asyncio."""

from __future__ import annotations

import asyncio
from typing import Any

from services.logging_service import get_logger

logger = get_logger("audio_capture")


class AudioCapture:
    """Captura PCM int16 mono sin bloquear el event loop."""

    def __init__(
        self,
        sample_rate: int = 16_000,
        channels: int = 1,
        blocksize: int = 480,
        device: int | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.device = device
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)
        self._stream: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        import sounddevice as sd

        if self._running:
            return

        self._loop = loop
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.blocksize,
            device=self.device,
            callback=self._audio_callback,
        )
        self._stream.start()
        self._running = True
        logger.info(
            "Captura de audio iniciada | rate=%d | blocksize=%d | device=%s",
            self.sample_rate,
            self.blocksize,
            self.device if self.device is not None else "default",
        )

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("Captura de audio detenida")

    def _audio_callback(
        self,
        indata: bytes,
        frames: int,
        time_info: object,
        status: Any,
    ) -> None:
        if status:
            logger.warning("Estado de audio: %s", status)
        if not self._running or self._loop is None:
            return

        data = bytes(indata)
        try:
            self._loop.call_soon_threadsafe(self._enqueue, data)
        except RuntimeError:
            pass

    def _enqueue(self, data: bytes) -> None:
        try:
            self.queue.put_nowait(data)
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.queue.put_nowait(data)

"""Motor TTS offline (pyttsx3) con voz estilo asistente."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from services.logging_service import get_logger

logger = get_logger("tts_engine")


class TTSEngine:
    """
    Cola de síntesis de voz en hilo dedicado.

    Evita bloquear el event loop y serializa frases para naturalidad.
    """

    def __init__(
        self,
        rate: int = 165,
        volume: float = 1.0,
        voice_hint: str = "male",
        on_start: Callable[[], None] | None = None,
        on_finish: Callable[[], None] | None = None,
    ) -> None:
        self.rate = rate
        self.volume = volume
        self.voice_hint = voice_hint
        self._on_start = on_start
        self._on_finish = on_finish
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._engine = None
        self._running = False
        self._speaking = False

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker, name="tts_worker", daemon=True)
        self._thread.start()
        logger.info("TTSEngine iniciado")

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._engine = None
        logger.info("TTSEngine detenido")

    def speak(self, text: str, *, interrupt: bool = False) -> None:
        """Encola texto para síntesis."""
        text = (text or "").strip()
        if not text:
            return
        if interrupt:
            self._drain_queue()
        self._queue.put(text)

    def _drain_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _init_engine(self) -> None:
        if self._engine is not None:
            return
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)
        self._select_voice(engine)
        self._engine = engine
        logger.info("Voz TTS seleccionada | rate=%d", self.rate)

    def _select_voice(self, engine) -> None:
        voices = engine.getProperty("voices") or []
        if not voices:
            return

        preferred_ids = (
            "david",
            "helena",
            "pablo",
            "jorge",
            "male",
            "spanish",
            "es-",
            "es_",
        )
        chosen = None
        for hint in preferred_ids:
            for voice in voices:
                vid = (voice.id or "").lower()
                vname = (voice.name or "").lower()
                if hint in vid or hint in vname:
                    chosen = voice
                    break
            if chosen:
                break

        if not chosen and self.voice_hint == "male":
            for voice in voices:
                vname = (voice.name or "").lower()
                if "female" not in vname and "zira" not in vname:
                    chosen = voice
                    break

        if chosen:
            engine.setProperty("voice", chosen.id)
            logger.debug("Voz TTS: %s", chosen.name)

    def _worker(self) -> None:
        while self._running:
            try:
                text = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if text is None:
                break
            try:
                self._init_engine()
                assert self._engine is not None
                self._speaking = True
                if self._on_start:
                    self._on_start()
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:
                logger.exception("Error en TTS")
            finally:
                self._speaking = False
                if self._on_finish:
                    self._on_finish()

"""Módulo de entrada de voz con wake word y STT offline."""

from __future__ import annotations

import asyncio
import enum
import time
from typing import TYPE_CHECKING

from core.base_module import BaseModule
from core.event_bus import Event
from modules.voice.config import VoiceConfig
from modules.voice.speech_recognizer import SpeechRecognizer
from modules.voice.text_utils import clean_command_text
from modules.voice.vad_segmenter import VadSegmenter
from modules.voice.vosk_engine import VoskEngine
from modules.voice.wake_word_detector import WakeWordDetector
from services.audio_capture import AudioCapture

if TYPE_CHECKING:
    pass


class _ListenMode(enum.Enum):
    PASSIVE = "passive"
    ACTIVE = "active"


class VoiceListener(BaseModule):
    """
    Escucha pasiva 24/7 con bajo consumo.

    Pipeline:
      1. VAD filtra silencio (modo pasivo)
      2. WakeWordDetector busca "Jarvis"
      3. SpeechRecognizer transcribe el comando completo
      4. Emite voice.command con texto limpio al core
    """

    name = "voice_listener"

    def __init__(self, event_bus, config: VoiceConfig | None = None) -> None:
        super().__init__(event_bus)
        self.config = config or VoiceConfig()
        self._audio: AudioCapture | None = None
        self._vad: VadSegmenter | None = None
        self._wake: WakeWordDetector | None = None
        self._stt: SpeechRecognizer | None = None
        self._mode = _ListenMode.PASSIVE
        self._in_speech = False
        self._silence_frames = 0
        self._heard_command_audio = False
        self._last_transcript = ""
        self._passive_silence_limit = 15  # ~450 ms sin voz para resetear wake detector
        self._active_silence_limit = 0
        self._speech_buffer: list[bytes] = []

    async def on_start(self) -> None:
        self.subscribe("system.shutdown", self._on_shutdown)

        errors = self.config.validate()
        if errors:
            for err in errors:
                self.logger.error(err)
            if not self.config.dry_run:
                self.logger.warning("VoiceListener en espera (configuración incompleta)")
                return

        if self.config.dry_run:
            self.logger.info("VoiceListener en modo dry_run (sin micrófono)")
            return

        self._active_silence_limit = max(
            1,
            int(self.config.silence_timeout_s * 1000 / self.config.frame_ms),
        )

        model_path = self.config.resolved_model_path()
        engine = VoskEngine(model_path)
        self._vad = VadSegmenter(
            sample_rate=self.config.sample_rate,
            frame_ms=self.config.frame_ms,
            aggressiveness=self.config.vad_aggressiveness,
            energy_threshold=self.config.vad_energy_threshold,
        )
        self._wake = WakeWordDetector(
            engine=engine,
            wake_word=self.config.wake_word,
            sample_rate=self.config.sample_rate,
        )
        self._stt = SpeechRecognizer(engine=engine, sample_rate=self.config.sample_rate)

        self._audio = AudioCapture(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            blocksize=self.config.sample_rate * self.config.frame_ms // 1000,
            device=self.config.input_device,
        )
        self._audio.start(asyncio.get_running_loop())
        self.logger.info(
            "VoiceListener activo | wake='%s' | modelo=%s | VAD=%d",
            self.config.wake_word,
            model_path.name,
            self.config.vad_aggressiveness,
        )

    async def on_stop(self) -> None:
        if self._audio:
            self._audio.stop()
            self._audio = None
        self.logger.info("VoiceListener liberado")

    async def run_loop(self) -> None:
        if self.config.dry_run or self._audio is None:
            while self._running:
                await asyncio.sleep(1)
            return

        while self._running:
            try:
                chunk = await asyncio.wait_for(self._audio.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            frames = self._vad.feed(chunk)
            for frame in frames:
                await self._process_frame(frame)

    async def _process_frame(self, frame: bytes) -> None:
        if not self._vad or not self._wake or not self._stt:
            return

        is_speech = self._vad.is_speech(frame)

        if self._mode == _ListenMode.PASSIVE:
            await self._process_passive(frame, is_speech)
        else:
            await self._process_active(frame, is_speech)

    async def _process_passive(self, frame: bytes, is_speech: bool) -> None:
        assert self._wake is not None

        if is_speech:
            self._in_speech = True
            self._silence_frames = 0
            self._speech_buffer.append(frame)
            if self._wake.feed(frame):
                await self._enter_active_mode(replay=self._speech_buffer)
        elif self._in_speech:
            self._silence_frames += 1
            if self._silence_frames >= self._passive_silence_limit:
                self._wake.reset()
                self._in_speech = False
                self._speech_buffer.clear()

    async def _process_active(self, frame: bytes, is_speech: bool) -> None:
        assert self._stt is not None

        final = self._stt.feed(frame)
        if final:
            self._last_transcript = final
            self._heard_command_audio = True

        partial = self._stt.partial()
        if partial:
            self._last_transcript = partial

        if is_speech:
            self._silence_frames = 0
            self._heard_command_audio = True
            self._speech_buffer.append(frame)
        elif self._heard_command_audio:
            self._silence_frames += 1
            if self._silence_frames >= self._active_silence_limit:
                await self._finalize_command()

    async def _enter_active_mode(self, replay: list[bytes] | None = None) -> None:
        assert self._stt is not None

        self._mode = _ListenMode.ACTIVE
        self._silence_frames = 0
        self._heard_command_audio = False
        self._last_transcript = ""
        self._speech_buffer.clear()
        self._stt.reset()

        for buffered_frame in replay or []:
            final = self._stt.feed(buffered_frame)
            if final:
                self._last_transcript = final
                self._heard_command_audio = True

        self.logger.info("Wake word detectada → modo escucha activa")
        await self.emit(
            "voice.wake",
            {
                "wake_word": self.config.wake_word,
                "ack": self.config.wake_ack_enabled,
            },
        )
        await self.emit("voice.listening", {"status": "active"})

    async def _finalize_command(self) -> None:
        assert self._stt is not None
        assert self._wake is not None

        raw = self._stt.finalize() or self._last_transcript
        cleaned = clean_command_text(raw, self.config.wake_word)

        if cleaned:
            self.logger.info("Comando de voz: '%s'", cleaned)
            await self.emit(
                "voice.command",
                {
                    "text": cleaned,
                    "raw": raw,
                    "timestamp": time.time(),
                },
            )
        else:
            self.logger.info("Wake word sin comando adicional")

        self._mode = _ListenMode.PASSIVE
        self._in_speech = False
        self._silence_frames = 0
        self._heard_command_audio = False
        self._last_transcript = ""
        self._wake.reset()
        self._stt.reset()
        await self.emit("voice.listening", {"status": "passive"})

    async def _on_shutdown(self, event: Event) -> None:
        self.logger.debug("Apagado del sistema recibido")

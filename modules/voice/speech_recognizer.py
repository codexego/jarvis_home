"""Reconocimiento de voz completo offline con VOSK."""

from __future__ import annotations

import json

from services.logging_service import get_logger

logger = get_logger("stt")


class SpeechRecognizer:
    """STT de comando completo sin gramática restringida."""

    def __init__(self, engine: object, sample_rate: int = 16_000) -> None:
        self.sample_rate = sample_rate
        self._engine = engine
        self._recognizer = self._create_recognizer()
        logger.info("SpeechRecognizer listo")

    def _create_recognizer(self):
        return self._engine.create_recognizer(self.sample_rate)

    def reset(self) -> None:
        self._recognizer = self._create_recognizer()

    def feed(self, audio: bytes) -> str | None:
        """Alimenta audio. Devuelve texto final si hay frase completa."""
        if not audio:
            return None

        if self._recognizer.AcceptWaveform(audio):
            return self._extract_text(self._recognizer.Result())
        return None

    def partial(self) -> str:
        try:
            data = json.loads(self._recognizer.PartialResult())
        except json.JSONDecodeError:
            return ""
        return (data.get("partial") or "").strip()

    def finalize(self) -> str:
        """Fuerza el resultado final del buffer actual."""
        return self._extract_text(self._recognizer.FinalResult())

    @staticmethod
    def _extract_text(result_json: str) -> str:
        try:
            data = json.loads(result_json)
        except json.JSONDecodeError:
            return ""
        return (data.get("text") or "").strip()

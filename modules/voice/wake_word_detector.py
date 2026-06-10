"""Detección offline de palabra clave con VOSK (gramática restringida)."""

from __future__ import annotations

import json

from services.logging_service import get_logger

logger = get_logger("wake_word")


class WakeWordDetector:
    """
    Detector de wake word de bajo coste.

    Usa un reconocedor VOSK con gramática limitada a la palabra clave,
    separado del reconocedor de comando completo.
    """

    def __init__(
        self,
        engine: object,
        wake_word: str = "jarvis",
        sample_rate: int = 16_000,
    ) -> None:
        self.wake_word = wake_word.lower().strip()
        self.sample_rate = sample_rate
        self._engine = engine
        self._recognizer = self._create_recognizer()
        logger.info("WakeWordDetector listo | wake_word='%s'", self.wake_word)

    def _create_recognizer(self):
        variants = list(dict.fromkeys([self.wake_word, "harris", "yarvis", "[unk]"]))
        return self._engine.create_recognizer(
            self.sample_rate,
            grammar=variants,
        )

    def reset(self) -> None:
        self._recognizer = self._create_recognizer()

    def feed(self, audio: bytes) -> bool:
        """
        Procesa audio y devuelve True si se detecta la palabra clave.

        Revisa resultados parciales para minimizar latencia.
        """
        if not audio:
            return False

        detected = False

        if self._recognizer.AcceptWaveform(audio):
            detected = self._contains_wake_word(self._recognizer.Result())
            self.reset()
        else:
            detected = self._contains_wake_word(self._recognizer.PartialResult())
            if detected:
                self.reset()

        if detected:
            logger.info("Wake word detectada: '%s'", self.wake_word)

        return detected

    def _contains_wake_word(self, result_json: str) -> bool:
        try:
            data = json.loads(result_json)
        except json.JSONDecodeError:
            return False

        text = (data.get("text") or data.get("partial") or "").lower().strip()
        if not text:
            return False

        tokens = text.split()
        wake_variants = {self.wake_word, "harris", "yarvis", "jarvis"}
        return any(t in wake_variants for t in tokens)

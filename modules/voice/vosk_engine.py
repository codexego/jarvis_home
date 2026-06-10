"""Motor VOSK compartido entre wake word y STT."""

from __future__ import annotations

from pathlib import Path

from services.logging_service import get_logger

logger = get_logger("vosk_engine")


class VoskEngine:
    """Carga el modelo VOSK una sola vez para todos los reconocedores."""

    def __init__(self, model_path: Path) -> None:
        from vosk import Model, SetLogLevel

        SetLogLevel(-1)
        self.model_path = model_path
        self._model = Model(str(model_path))
        logger.info("Modelo VOSK cargado: %s", model_path)

    def create_recognizer(self, sample_rate: int = 16_000, grammar: list[str] | None = None):
        from vosk import KaldiRecognizer

        recognizer = KaldiRecognizer(self._model, sample_rate)
        if grammar is not None:
            import json

            recognizer.SetGrammar(json.dumps(grammar))
        else:
            recognizer.SetWords(True)
        return recognizer

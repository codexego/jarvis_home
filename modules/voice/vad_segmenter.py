"""Detección de actividad de voz por energía RMS ajustable."""

from __future__ import annotations

import struct

from services.logging_service import get_logger

logger = get_logger("vad")

# Umbrales RMS por nivel de agresividad (0=sensible, 3=estricto)
_DEFAULT_THRESHOLDS = (280.0, 420.0, 600.0, 850.0)


class VadSegmenter:
    """Clasifica frames como voz o silencio según energía RMS adaptativa."""

    def __init__(
        self,
        sample_rate: int = 16_000,
        frame_ms: int = 30,
        aggressiveness: int = 2,
        energy_threshold: float | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.aggressiveness = max(0, min(3, aggressiveness))
        self.frame_bytes = sample_rate * frame_ms // 1000 * 2
        self._buffer = bytearray()
        self._threshold = energy_threshold or _DEFAULT_THRESHOLDS[self.aggressiveness]
        self._noise_floor = self._threshold * 0.45
        self._speech_frames = 0
        logger.debug("VAD | threshold=%.0f | aggressiveness=%d", self._threshold, self.aggressiveness)

    def set_aggressiveness(self, level: int) -> None:
        """Ajusta sensibilidad en caliente (0=más sensible, 3=más estricto)."""
        self.aggressiveness = max(0, min(3, level))
        self._threshold = _DEFAULT_THRESHOLDS[self.aggressiveness]

    def feed(self, chunk: bytes) -> list[bytes]:
        """Acumula audio y devuelve frames completos listos."""
        self._buffer.extend(chunk)
        frames: list[bytes] = []
        while len(self._buffer) >= self.frame_bytes:
            frame = bytes(self._buffer[: self.frame_bytes])
            del self._buffer[: self.frame_bytes]
            frames.append(frame)
        return frames

    def is_speech(self, frame: bytes) -> bool:
        rms = self._rms(frame)
        # Histéresis: requiere varios frames de voz para activar
        if rms >= self._threshold:
            self._speech_frames = min(self._speech_frames + 1, 5)
            self._adapt_noise_floor(rms, is_speech=True)
            return True
        if self._speech_frames > 0 and rms >= self._noise_floor * 1.4:
            self._speech_frames -= 1
            return True
        self._speech_frames = 0
        self._adapt_noise_floor(rms, is_speech=False)
        return False

    def _adapt_noise_floor(self, rms: float, is_speech: bool) -> None:
        if not is_speech:
            self._noise_floor = 0.92 * self._noise_floor + 0.08 * rms

    @staticmethod
    def _rms(frame: bytes) -> float:
        if len(frame) < 2:
            return 0.0
        count = len(frame) // 2
        samples = struct.unpack(f"<{count}h", frame[: count * 2])
        if not samples:
            return 0.0
        return (sum(s * s for s in samples) / len(samples)) ** 0.5

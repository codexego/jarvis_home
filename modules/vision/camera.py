"""Acceso a webcam bajo demanda (abre y cierra por captura)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from services.logging_service import get_logger

if TYPE_CHECKING:
    import numpy as np

logger = get_logger("camera")


class Camera:
    """Webcam que solo se activa durante una captura."""

    def __init__(
        self,
        device_index: int = 0,
        warmup_frames: int = 3,
        capture_timeout_s: float = 5.0,
    ) -> None:
        self.device_index = device_index
        self.warmup_frames = warmup_frames
        self.capture_timeout_s = capture_timeout_s
        self._cap = None

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def open(self) -> None:
        import cv2

        if self.is_open:
            return

        if sys.platform == "win32":
            self._cap = cv2.VideoCapture(self.device_index, cv2.CAP_DSHOW)
        else:
            self._cap = cv2.VideoCapture(self.device_index)

        if not self._cap.isOpened():
            if self._cap is not None:
                self._cap.release()
            self._cap = cv2.VideoCapture(self.device_index)

        if not self._cap.isOpened():
            raise RuntimeError(f"No se pudo abrir la cámara (índice {self.device_index})")

        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        logger.info("Cámara abierta | device=%d", self.device_index)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Cámara cerrada")

    def capture_frame(self) -> np.ndarray | None:
        """Captura un frame tras descartar warmup_frames."""
        import cv2

        if not self.is_open:
            self.open()

        assert self._cap is not None

        for _ in range(self.warmup_frames):
            self._cap.grab()

        ok, frame = self._cap.read()
        if not ok or frame is None:
            logger.warning("No se pudo leer frame de la cámara")
            return None

        logger.debug("Frame capturado | shape=%s", frame.shape)
        return frame

    def grab_frame(self) -> np.ndarray | None:
        """Lee un frame con la cámara ya abierta."""
        if not self.is_open:
            self.open()
        assert self._cap is not None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        return frame

    def capture_burst(self, count: int, interval_s: float = 0.35) -> list[np.ndarray]:
        """Abre cámara, captura varios frames y cierra (tracking corto)."""
        import time

        frames: list[np.ndarray] = []
        try:
            self.open()
            for i in range(count):
                frame = self.capture_frame() if i == 0 else self.grab_frame()
                if frame is not None:
                    frames.append(frame)
                if i < count - 1:
                    time.sleep(interval_s)
        finally:
            self.close()
        return frames

    def capture_on_demand(self) -> np.ndarray | None:
        """Abre cámara, captura un frame y cierra."""
        try:
            self.open()
            return self.capture_frame()
        finally:
            self.close()

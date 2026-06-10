"""Captura de pantalla bajo demanda con mss."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.logging_service import get_logger

if TYPE_CHECKING:
    import numpy as np

logger = get_logger("screen_capture")


class ScreenCapture:
    """Captura rápida de pantalla principal."""

    def __init__(self, monitor_index: int = 1) -> None:
        # mss: 0 = todas, 1 = pantalla principal
        self.monitor_index = monitor_index

    def grab(self) -> tuple[np.ndarray, dict[str, int]]:
        """
        Captura la pantalla y devuelve frame BGR + metadatos del monitor.

        La captura es instantánea; no mantiene sesión abierta.
        """
        import mss
        import numpy as np

        with mss.mss() as sct:
            monitors = sct.monitors
            idx = min(self.monitor_index, len(monitors) - 1)
            monitor = monitors[idx]
            shot = sct.grab(monitor)

            frame = np.array(shot, dtype=np.uint8)
            frame = frame[:, :, :3]  # BGRA -> BGR

            meta = {
                "left": monitor["left"],
                "top": monitor["top"],
                "width": monitor["width"],
                "height": monitor["height"],
            }
            logger.debug(
                "Pantalla capturada | %dx%d @ (%d,%d)",
                meta["width"],
                meta["height"],
                meta["left"],
                meta["top"],
            )
            return frame, meta

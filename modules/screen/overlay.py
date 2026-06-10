"""Overlay visual con borde neón cuando screen_monitor está activo."""

from __future__ import annotations

import threading

from services.logging_service import get_logger

logger = get_logger("screen_overlay")


class NeonOverlay:
    """Ventana fullscreen topmost con borde neón (tkinter en hilo separado)."""

    def __init__(self, color: str = "#00ffff", border_width: int = 5) -> None:
        self.color = color
        self.border_width = border_width
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._visible = False

    @property
    def is_visible(self) -> bool:
        return self._visible

    def show(self) -> None:
        if self._visible and self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="neon_overlay", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3.0)
        self._visible = True
        logger.info("Overlay neón activado")

    def hide(self) -> None:
        if not self._visible:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self._visible = False
        logger.info("Overlay neón desactivado")

    def _run(self) -> None:
        import tkinter as tk

        root = tk.Tk()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.geometry(f"{sw}x{sh}+0+0")
        root.configure(bg="black")

        try:
            root.attributes("-transparentcolor", "black")
        except tk.TclError:
            root.attributes("-alpha", 0.15)

        canvas = tk.Canvas(root, bg="black", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        pad = self.border_width + 2
        canvas.create_rectangle(
            pad,
            pad,
            sw - pad,
            sh - pad,
            outline=self.color,
            width=self.border_width,
        )

        def poll() -> None:
            if self._stop_event.is_set():
                root.quit()
                root.destroy()
            else:
                root.after(80, poll)

        self._ready.set()
        root.after(80, poll)
        root.mainloop()

"""Panel visual de respuestas Jarvis (tkinter)."""

from __future__ import annotations

import threading
from typing import Any

from services.logging_service import get_logger

logger = get_logger("response_ui")


class ResponsePanel:
    """Ventana flotante con estado y última respuesta del asistente."""

    def __init__(self, title: str = "Jarvis Home") -> None:
        self.title = title
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._commands: list[tuple[str, Any]] = []
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._ready.clear()
        self._thread = threading.Thread(target=self._run, name="response_ui", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5.0)
        logger.info("ResponsePanel iniciado")

    def stop(self) -> None:
        if not self._running:
            return
        self._post("quit", None)
        if self._thread:
            self._thread.join(timeout=3.0)
        self._running = False

    def set_status(self, status: str, detail: str = "") -> None:
        self._post("status", (status, detail))

    def show_response(self, text: str, intent: str = "", confidence: float = 0.0) -> None:
        self._post("response", (text, intent, confidence))

    def show_command(self, text: str) -> None:
        self._post("command", text)

    def _post(self, cmd: str, payload: Any) -> None:
        with self._lock:
            self._commands.append((cmd, payload))

    def _drain_commands(self) -> list[tuple[str, Any]]:
        with self._lock:
            cmds = list(self._commands)
            self._commands.clear()
        return cmds

    def _run(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        root = tk.Tk()
        root.title(self.title)
        root.geometry("420x220+20+20")
        root.attributes("-topmost", True)
        root.configure(bg="#0a0e17")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Jarvis.TLabel", background="#0a0e17", foreground="#00e5ff", font=("Segoe UI", 10))
        style.configure("Jarvis.Title.TLabel", background="#0a0e17", foreground="#7df9ff", font=("Segoe UI", 11, "bold"))
        style.configure("Jarvis.Body.TLabel", background="#0a0e17", foreground="#e0f7fa", font=("Segoe UI", 10), wraplength=380)

        frame = ttk.Frame(root, padding=12)
        frame.pack(fill="both", expand=True)

        title_lbl = ttk.Label(frame, text="JARVIS", style="Jarvis.Title.TLabel")
        title_lbl.pack(anchor="w")

        status_var = tk.StringVar(value="En espera")
        status_lbl = ttk.Label(frame, textvariable=status_var, style="Jarvis.TLabel")
        status_lbl.pack(anchor="w", pady=(4, 8))

        response_var = tk.StringVar(value="Listo para ayudarte.")
        response_lbl = ttk.Label(frame, textvariable=response_var, style="Jarvis.Body.TLabel", justify="left")
        response_lbl.pack(anchor="w", fill="x")

        meta_var = tk.StringVar(value="")
        meta_lbl = ttk.Label(frame, textvariable=meta_var, style="Jarvis.TLabel")
        meta_lbl.pack(anchor="w", pady=(8, 0))

        def poll() -> None:
            for cmd, payload in self._drain_commands():
                if cmd == "quit":
                    root.quit()
                    root.destroy()
                    return
                if cmd == "status":
                    status, detail = payload
                    status_var.set(f"● {status}" + (f" — {detail}" if detail else ""))
                elif cmd == "response":
                    text, intent, conf = payload
                    response_var.set(text)
                    meta = []
                    if intent:
                        meta.append(intent)
                    if conf:
                        meta.append(f"conf {conf:.0%}")
                    meta_var.set(" | ".join(meta))
                elif cmd == "command":
                    status_var.set(f"● Comando: {payload[:60]}")
            root.after(80, poll)

        self._ready.set()
        root.after(80, poll)
        root.mainloop()

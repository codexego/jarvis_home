"""Punto de entrada de la aplicación de escritorio."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from desktop.bridge import EventBridge
from desktop.config import DesktopSettings
from desktop.core_runner import CoreRunner
from desktop.main_window import MainWindow


def run_desktop() -> None:
    """Inicia Qt + core Jarvis en hilo de fondo."""
    settings = DesktopSettings.load()
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis Home")
    app.setOrganizationName("JarvisHome")

    bridge = EventBridge()
    log_file = Path(__file__).resolve().parents[1] / "logs" / "jarvis.log"
    runner = CoreRunner(bridge=bridge, log_file=log_file)
    runner.start()

    window = MainWindow(settings)
    window.attach_core(runner)
    window.show()

    exit_code = app.exec()
    runner.stop()
    sys.exit(exit_code)

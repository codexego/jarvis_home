"""Ventana principal de Jarvis Home Desktop."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QPushButton, QVBoxLayout, QWidget

from desktop.bridge import BridgeMessage
from desktop.chat_panel import ChatPanel
from desktop.config import DesktopSettings
from desktop.core_runner import CoreRunner
from desktop.neural_view import NeuralCanvas, NeuralState
from desktop.settings_dialog import SettingsDialog
from desktop.styles import DARK_THEME_QSS
from services.memory_store import MemoryStore


class MainWindow(QMainWindow):
    def __init__(self, settings: DesktopSettings) -> None:
        super().__init__()
        self._settings = settings
        self._runner: CoreRunner | None = None
        self._state = NeuralState.IDLE
        self._screen_scan_active = False

        self.setWindowTitle("Jarvis Home")
        self.resize(settings.window_width, settings.window_height)
        self.setStyleSheet(DARK_THEME_QSS)

        self._build_ui()
        self._poll = QTimer(self)
        self._poll.timeout.connect(self._process_bridge)
        self._poll.start(50)

    def attach_core(self, runner: CoreRunner) -> None:
        self._runner = runner

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Barra superior
        top = QHBoxLayout()
        top.setContentsMargins(16, 12, 16, 4)
        title = QLabel("JARVIS HOME")
        title.setObjectName("titleLabel")
        self._status = QLabel("● Iniciando...")
        self._status.setObjectName("statusBadge")
        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setObjectName("settingsBtn")
        self._settings_btn.setFixedSize(36, 36)
        self._settings_btn.clicked.connect(self._open_settings)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self._status)
        top.addWidget(self._settings_btn)
        layout.addLayout(top)

        # Visualización neural
        self._neural = NeuralCanvas()
        layout.addWidget(self._neural, stretch=2)

        # Chat
        self._chat = ChatPanel()
        self._chat.send_requested.connect(self._on_user_send)
        self._chat.mic_requested.connect(self._on_mic_hint)
        layout.addWidget(self._chat, stretch=3)

        self._load_chat_history()

    def _load_chat_history(self) -> None:
        db = self._settings.db_path
        if not db.is_file():
            return
        try:
            store = MemoryStore(db)
            history = store.get_context_for_llm(limit=80)
            store.close()
            if history:
                self._chat.load_history(history)
        except Exception:
            pass

    def _on_user_send(self, text: str) -> None:
        if not self._runner:
            return
        self._set_state(NeuralState.THINKING, "Procesando...")
        self._runner.send_text(text)

    def _on_mic_hint(self) -> None:
        self._chat.add_jarvis_message(
            "Di 'Jarvis' seguido de tu comando. El micrófono está activo en segundo plano.",
            animate=False,
        )

    def _open_settings(self) -> None:
        models = self._fetch_ollama_models()
        dlg = SettingsDialog(self._settings, models, self)
        if dlg.exec():
            self._settings = dlg.apply_to(self._settings)
            self._settings.save()
            self._apply_startup_registry()
            self._runner.submit("config.update", {"llm_model": self._settings.llm_model})

    def _fetch_ollama_models(self) -> list[str]:
        try:
            from modules.ai.llm_client import OllamaClient

            client = OllamaClient()
            if client.is_available():
                return client.list_models() or [self._settings.llm_model]
        except Exception:
            pass
        return [self._settings.llm_model]

    def _apply_startup_registry(self) -> None:
        try:
            from scripts.windows_startup import set_startup_enabled

            set_startup_enabled(self._settings.startup_with_windows)
        except Exception:
            pass

    def _set_state(self, state: NeuralState, label: str) -> None:
        self._state = state
        self._neural.set_state(state)
        self._status.setText(f"● {label}")

    def _process_bridge(self) -> None:
        if not self._runner:
            return
        for msg in self._runner.bridge.drain():
            self._handle_message(msg)

    def _handle_message(self, msg: BridgeMessage) -> None:
        topic, payload = msg.topic, msg.payload

        if topic == "system.ready":
            self._set_state(NeuralState.IDLE, "Listo")
            self._chat.add_jarvis_message("Jarvis Home operativo. ¿En qué puedo ayudarte?", animate=True)

        elif topic == "voice.wake":
            self._set_state(NeuralState.LISTENING, "Escuchando")

        elif topic == "voice.listening":
            st = payload.get("status", "passive")
            if st == "active":
                self._set_state(NeuralState.LISTENING, "Escuchando comando")
            elif self._state != NeuralState.THINKING:
                self._set_state(NeuralState.IDLE, "En espera — di 'Jarvis'")

        elif topic == "voice.command":
            text = payload.get("text", "")
            if text:
                self._chat.add_user_message(text)
                self._set_state(NeuralState.THINKING, "Procesando...")

        elif topic in ("screen.capturing", "vision.capturing"):
            self._screen_scan_active = topic == "screen.capturing"
            self._set_state(NeuralState.SCANNING, "Analizando pantalla" if self._screen_scan_active else "Analizando cámara")

        elif topic in ("screen.analysis", "vision.analysis"):
            self._screen_scan_active = False
            self._set_state(NeuralState.THINKING, "Generando respuesta...")

        elif topic == "ai.decision":
            answer = payload.get("answer")
            if answer:
                self._chat.add_jarvis_message(answer, animate=True)
            intent = payload.get("intent", "")
            if payload.get("actions"):
                self._set_state(NeuralState.EXECUTING, "Ejecutando...")
            elif self._state != NeuralState.SPEAKING:
                self._set_state(NeuralState.IDLE, "Listo")

        elif topic == "ui.speaking":
            if payload.get("active"):
                self._set_state(NeuralState.SPEAKING, "Hablando...")
            else:
                self._set_state(NeuralState.IDLE, "Listo")

        elif topic == "executor.confirmation_required":
            message = payload.get("message", "Necesito confirmación.")
            self._chat.add_jarvis_message(message, animate=True)

        elif topic == "action.completed":
            status = payload.get("status", "")
            if status == "cancelled":
                self._chat.add_jarvis_message("Acción cancelada.", animate=True)
            self._set_state(NeuralState.IDLE, "Listo")

        elif topic == "system.shutdown":
            self._set_state(NeuralState.IDLE, "Detenido")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._runner:
            self._runner.stop()
        self._settings.window_width = self.width()
        self._settings.window_height = self.height()
        self._settings.save()
        super().closeEvent(event)

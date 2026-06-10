"""Panel de configuración de la aplicación."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
)

from desktop.config import DesktopSettings


class SettingsDialog(QDialog):
    def __init__(self, settings: DesktopSettings, ollama_models: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración — Jarvis Home")
        self.setMinimumWidth(420)
        self._settings = settings
        self._models = ollama_models or [settings.llm_model]
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._model = QComboBox()
        self._model.addItems(self._models)
        idx = self._model.findText(self._settings.llm_model)
        if idx >= 0:
            self._model.setCurrentIndex(idx)
        form.addRow("Modelo IA (Ollama):", self._model)

        vol_row = QHBoxLayout()
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(int(self._settings.tts_volume * 100))
        self._vol_lbl = QLabel(f"{int(self._settings.tts_volume * 100)}%")
        self._volume.valueChanged.connect(lambda v: self._vol_lbl.setText(f"{v}%"))
        vol_row.addWidget(self._volume)
        vol_row.addWidget(self._vol_lbl)
        form.addRow("Volumen voz:", vol_row)

        self._voice = QCheckBox("Módulo de voz activo")
        self._voice.setChecked(self._settings.voice_enabled)
        form.addRow(self._voice)

        self._vision = QCheckBox("Visión (cámara)")
        self._vision.setChecked(self._settings.vision_enabled)
        form.addRow(self._vision)

        self._screen = QCheckBox("Monitor de pantalla")
        self._screen.setChecked(self._settings.screen_enabled)
        form.addRow(self._screen)

        self._startup = QCheckBox("Iniciar con Windows")
        self._startup.setChecked(self._settings.startup_with_windows)
        form.addRow(self._startup)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_to(self, settings: DesktopSettings) -> DesktopSettings:
        settings.llm_model = self._model.currentText()
        settings.tts_volume = self._volume.value() / 100.0
        settings.voice_enabled = self._voice.isChecked()
        settings.vision_enabled = self._vision.isChecked()
        settings.screen_enabled = self._screen.isChecked()
        settings.startup_with_windows = self._startup.isChecked()
        return settings

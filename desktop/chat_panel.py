"""Panel de chat persistente con efecto de escritura progresiva."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class _TypewriterLabel(QLabel):
    """Label que revela texto progresivamente."""

    finished = Signal()

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = text
        self._index = 0
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)
        if text:
            self._timer.start(18)
        else:
            self.setText("")

    def _step(self) -> None:
        self._index += 2
        self.setText(self._full[: self._index])
        if self._index >= len(self._full):
            self._timer.stop()
            self.finished.emit()


class ChatPanel(QWidget):
    """Chat único persistente: usuario derecha, Jarvis izquierda."""

    send_requested = Signal(str)
    mic_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 12)
        root.setSpacing(8)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._messages_host = QWidget()
        self._messages_layout = QVBoxLayout(self._messages_host)
        self._messages_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._messages_layout.setSpacing(10)
        self._scroll.setWidget(self._messages_host)
        root.addWidget(self._scroll, stretch=1)

        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setObjectName("chatInput")
        self._input.setPlaceholderText("Escribe a Jarvis...")
        self._input.returnPressed.connect(self._on_send)

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setObjectName("micBtn")
        self._mic_btn.setFixedSize(40, 40)
        self._mic_btn.setToolTip("Di 'Jarvis' o usa el micrófono del sistema")
        self._mic_btn.clicked.connect(self.mic_requested.emit)

        self._send_btn = QPushButton("Enviar")
        self._send_btn.setObjectName("sendBtn")
        self._send_btn.clicked.connect(self._on_send)

        input_row.addWidget(self._input, stretch=1)
        input_row.addWidget(self._mic_btn)
        input_row.addWidget(self._send_btn)
        root.addLayout(input_row)

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.add_user_message(text)
        self.send_requested.emit(text)

    def add_user_message(self, text: str) -> None:
        self._add_bubble(text, is_user=True, animate=False)

    def add_jarvis_message(self, text: str, *, animate: bool = True) -> None:
        self._add_bubble(text, is_user=False, animate=animate)

    def load_history(self, messages: list[dict[str, str]]) -> None:
        """Carga historial desde memoria (sin animación)."""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content:
                continue
            if role == "user":
                self.add_user_message(content)
            elif role == "assistant":
                self.add_jarvis_message(content, animate=False)

    def _add_bubble(self, text: str, *, is_user: bool, animate: bool) -> None:
        row = QHBoxLayout()
        bubble = QFrame()
        bubble.setObjectName("chatBubbleUser" if is_user else "chatBubbleJarvis")
        bubble.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Minimum)
        bubble.setMaximumWidth(520)

        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(0, 0, 0, 0)
        if animate and not is_user:
            lbl = _TypewriterLabel(text, bubble)
        else:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
        bl.addWidget(lbl)

        if is_user:
            row.addStretch()
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch()

        wrap = QWidget()
        wrap.setLayout(row)
        self._messages_layout.addWidget(wrap)
        QTimer.singleShot(50, self._scroll_to_bottom)

    def _scroll_to_bottom(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

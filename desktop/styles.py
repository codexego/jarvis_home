"""Tema visual oscuro estilo Jarvis."""

DARK_THEME_QSS = """
QMainWindow, QWidget#centralRoot {
    background-color: #050a12;
    color: #c8e8ff;
    font-family: "Segoe UI", "Inter", sans-serif;
}

QLabel#titleLabel {
    color: #00e5ff;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 3px;
}

QLabel#statusBadge {
    color: #7df9ff;
    background: rgba(0, 229, 255, 0.08);
    border: 1px solid rgba(0, 229, 255, 0.35);
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 11px;
}

QScrollArea {
    background: transparent;
    border: none;
}

QFrame#chatBubbleUser {
    background: rgba(0, 120, 180, 0.35);
    border: 1px solid rgba(0, 200, 255, 0.4);
    border-radius: 14px;
    padding: 10px 14px;
    color: #e8f7ff;
}

QFrame#chatBubbleJarvis {
    background: rgba(0, 229, 255, 0.07);
    border: 1px solid rgba(0, 229, 255, 0.25);
    border-radius: 14px;
    padding: 10px 14px;
    color: #b8ecff;
}

QLineEdit#chatInput {
    background: rgba(10, 20, 35, 0.95);
    border: 1px solid rgba(0, 229, 255, 0.35);
    border-radius: 20px;
    padding: 10px 16px;
    color: #e0f7fa;
    font-size: 13px;
}

QLineEdit#chatInput:focus {
    border: 1px solid #00e5ff;
}

QPushButton#sendBtn, QPushButton#micBtn, QPushButton#settingsBtn {
    background: rgba(0, 229, 255, 0.12);
    border: 1px solid rgba(0, 229, 255, 0.45);
    border-radius: 18px;
    color: #00e5ff;
    padding: 8px 14px;
    font-weight: 600;
}

QPushButton#sendBtn:hover, QPushButton#micBtn:hover, QPushButton#settingsBtn:hover {
    background: rgba(0, 229, 255, 0.22);
}

QPushButton#sendBtn:pressed, QPushButton#micBtn:pressed {
    background: rgba(0, 229, 255, 0.35);
}

QDialog {
    background-color: #0a1220;
    color: #c8e8ff;
}

QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox {
    background: #0f1a2a;
    border: 1px solid rgba(0, 229, 255, 0.3);
    border-radius: 6px;
    padding: 4px 8px;
    color: #c8e8ff;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #1a2a3a;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 14px;
    margin: -4px 0;
    background: #00e5ff;
    border-radius: 7px;
}
"""

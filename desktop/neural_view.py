"""Visualización central: red neuronal animada."""

from __future__ import annotations

import math
import random
from enum import Enum

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class NeuralState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    EXECUTING = "executing"
    SCANNING = "scanning"


class _Node:
    __slots__ = ("x", "y", "vx", "vy", "phase")

    def __init__(self, w: float, h: float) -> None:
        self.x = random.uniform(0.15, 0.85) * w
        self.y = random.uniform(0.15, 0.85) * h
        self.vx = random.uniform(-0.4, 0.4)
        self.vy = random.uniform(-0.4, 0.4)
        self.phase = random.uniform(0, math.tau)


class NeuralCanvas(QWidget):
    """Red de nodos conectados con animación fluida."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(280)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self._state = NeuralState.IDLE
        self._nodes: list[_Node] = []
        self._pulse = 0.0
        self._wave = 0.0
        self._node_count = 42
        self._link_dist = 120.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)  # ~30 FPS

    def set_state(self, state: NeuralState) -> None:
        self._state = state

    def _ensure_nodes(self) -> None:
        if self._nodes and len(self._nodes) == self._node_count:
            return
        w, h = max(self.width(), 100), max(self.height(), 100)
        self._nodes = [_Node(w, h) for _ in range(self._node_count)]

    def _activity(self) -> float:
        return {
            NeuralState.IDLE: 0.35,
            NeuralState.LISTENING: 0.85,
            NeuralState.THINKING: 1.0,
            NeuralState.SPEAKING: 0.75,
            NeuralState.EXECUTING: 0.9,
            NeuralState.SCANNING: 0.95,
        }[self._state]

    def _tick(self) -> None:
        act = self._activity()
        self._pulse = (self._pulse + 0.04 * act) % math.tau
        self._wave = (self._wave + 0.06 * act) % math.tau
        w, h = self.width(), self.height()
        self._ensure_nodes()

        for n in self._nodes:
            speed = 0.35 + act * 0.9
            n.x += n.vx * speed
            n.y += n.vy * speed
            n.phase += 0.02 * act
            if n.x < 20 or n.x > w - 20:
                n.vx *= -1
            if n.y < 20 or n.y > h - 20:
                n.vy *= -1
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Fondo degradado
        painter.fillRect(self.rect(), QColor(5, 10, 18))

        act = self._activity()
        self._ensure_nodes()
        link_dist = self._link_dist + act * 30
        pulse = (math.sin(self._pulse) + 1) * 0.5

        # Conexiones
        for i, a in enumerate(self._nodes):
            for b in self._nodes[i + 1 :]:
                dx, dy = a.x - b.x, a.y - b.y
                dist = math.hypot(dx, dy)
                if dist > link_dist:
                    continue
                alpha = int(40 + (1 - dist / link_dist) * 90 * act)
                pen = QPen(QColor(0, 229, 255, alpha), 1.0)
                painter.setPen(pen)
                painter.drawLine(QPointF(a.x, a.y), QPointF(b.x, b.y))

        # Nodos
        for n in self._nodes:
            glow = 2.5 + pulse * 2 * act
            core = QColor(0, 229, 255, int(180 + 60 * act))
            painter.setBrush(core)
            painter.setPen(Qt.PenStyle.NoPen)
            r = 2.0 + math.sin(n.phase) * 0.8
            painter.drawEllipse(QPointF(n.x, n.y), r + glow * 0.3, r + glow * 0.3)
            painter.setBrush(QColor(180, 250, 255, 230))
            painter.drawEllipse(QPointF(n.x, n.y), r, r)

        # Ondas al escuchar/hablar
        if self._state in (NeuralState.LISTENING, NeuralState.SPEAKING):
            cx, cy = w / 2, h / 2
            for ring in range(3):
                radius = 30 + ring * 28 + math.sin(self._wave + ring) * 12
                alpha = int(80 - ring * 20)
                pen = QPen(QColor(0, 229, 255, alpha), 1.5)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), radius, radius)

        # Borde neón cuando escanea pantalla
        if self._state == NeuralState.SCANNING:
            pen = QPen(QColor(0, 255, 255, 200), 3)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(4, 4, w - 8, h - 8, 8, 8)

        painter.end()

"""Registro compartido de módulos para CLI y escritorio."""

from __future__ import annotations

from core.module_registry import ModuleRegistry
from modules import (
    AIBrain,
    Executor,
    Memory,
    ResponseModule,
    ScreenMonitor,
    VisionModule,
    VoiceListener,
)
from modules.response.config import ResponseConfig


class DesktopResponseModule(ResponseModule):
    """ResponseModule sin panel tkinter (la UI de escritorio lo sustituye)."""

    name = "response"

    def __init__(self, event_bus) -> None:
        super().__init__(
            event_bus,
            config=ResponseConfig(ui_enabled=False, tts_enabled=True),
        )


def build_registry(*, desktop_mode: bool = False) -> ModuleRegistry:
    registry = ModuleRegistry()
    registry.register(VoiceListener)
    registry.register(VisionModule)
    registry.register(ScreenMonitor)
    registry.register(AIBrain)
    registry.register(Executor)
    registry.register(Memory)
    registry.register(DesktopResponseModule if desktop_mode else ResponseModule)
    return registry

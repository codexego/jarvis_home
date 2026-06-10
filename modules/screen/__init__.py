"""Componentes del pipeline de pantalla."""

from modules.screen.analyzer import ScreenAnalyzer, UIElement
from modules.screen.capture import ScreenCapture
from modules.screen.config import ScreenConfig
from modules.screen.overlay import NeonOverlay
from modules.screen.query_matcher import (
    build_screen_actions,
    is_screen_query,
    parse_screen_command,
)

__all__ = [
    "ScreenConfig",
    "ScreenCapture",
    "ScreenAnalyzer",
    "UIElement",
    "NeonOverlay",
    "is_screen_query",
    "parse_screen_command",
    "build_screen_actions",
]

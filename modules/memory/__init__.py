"""Componentes del módulo memory."""

from modules.memory.config import MemoryConfig
from modules.memory.context_detector import detect_work_context, suggest_intent_from_habits
from modules.memory.pattern_learner import PatternLearner

__all__ = [
    "MemoryConfig",
    "PatternLearner",
    "detect_work_context",
    "suggest_intent_from_habits",
]

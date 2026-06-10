"""Tests del modulo memory."""

import tempfile
from pathlib import Path

from modules.memory.context_detector import detect_work_context, suggest_intent_from_habits
from modules.memory.pattern_learner import PatternLearner
from services.memory_store import MemoryStore


def test_work_context_programming():
    assert detect_work_context("escribe codigo python en vs code") == "programming"


def test_work_context_media():
    assert detect_work_context("reproduce el video de youtube") == "media"


def test_habit_suggestion_exact():
    habits = [{"pattern": "abre youtube", "intent": "executor", "count": 5}]
    s = suggest_intent_from_habits("abre youtube", habits)
    assert s and s["intent"] == "executor"


def test_learning_habits_and_context():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(Path(tmp) / "mem.db")
        learner = PatternLearner(store, habit_threshold=3)

        for _ in range(3):
            learner.learn_from_command("abre youtube", intent="executor")

        summary = store.get_memory_summary()
        assert len(summary["habits"]) >= 1

        learner.learn_from_command("escribe codigo python", intent="executor")
        contexts = store.get_work_contexts()
        assert any(c["name"] == "programming" for c in contexts)
        store.close()


def test_response_cache():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(Path(tmp) / "mem.db")
        store.record_response_quality("hola jarvis", "chat", "Hola, como estas?", 0.8)
        store.record_response_quality("hola jarvis", "chat", "Hola de nuevo!", 0.9)
        cached = store.get_best_response("hola jarvis")
        assert cached and cached["use_count"] >= 2
        store.close()


def test_search_interactions():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(Path(tmp) / "mem.db")
        store.record_interaction("test", "abre youtube", "executor", "Abriendo", {})
        results = store.search_interactions("youtube")
        assert len(results) == 1
        store.close()

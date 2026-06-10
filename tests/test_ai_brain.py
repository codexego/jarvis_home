"""Tests del cerebro IA y memoria."""

import tempfile
from pathlib import Path

from modules.ai.intent_router import IntentRouter
from modules.ai.llm_client import OllamaClient
from services.memory_store import MemoryStore


class _FakeLLM(OllamaClient):
    def __init__(self) -> None:
        super().__init__()
        self._available = False

    def is_available(self) -> bool:
        return False


def test_memory_store_preferences_and_habits():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(Path(tmp) / "test.db")
        store.set_preference("idioma", "español")
        assert store.get_preference("idioma") == "español"

        for _ in range(3):
            store.record_command("reproduce el video", intent="screen")
        summary = store.get_memory_summary()
        assert len(summary["habits"]) >= 1
        store.close()


def test_intent_router_rules_vision():
    router = IntentRouter(_FakeLLM(), prefer_llm=False)
    route = router.route("que tengo en la mano", {}, [])
    assert route.intent == "vision"
    assert route.delegate == "vision_module"


def test_intent_router_rules_screen():
    router = IntentRouter(_FakeLLM(), prefer_llm=False)
    route = router.route("reproduce el video", {}, [])
    assert route.intent == "screen"
    assert route.delegate == "screen_monitor"


def test_intent_router_chat_fallback():
    router = IntentRouter(_FakeLLM(), prefer_llm=False)
    route = router.route("hola jarvis", {}, [])
    assert route.intent == "chat"
    assert route.answer

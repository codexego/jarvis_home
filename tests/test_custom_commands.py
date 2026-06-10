"""Tests de comandos personalizados en memoria."""

import tempfile
from pathlib import Path

from modules.ai.intent_router import IntentRouter
from modules.ai.llm_client import OllamaClient
from services.memory_store import MemoryStore


class _FakeLLM(OllamaClient):
    def is_available(self) -> bool:
        return False


def test_custom_command_storage_and_routing():
    with tempfile.TemporaryDirectory() as tmp:
        store = MemoryStore(Path(tmp) / "test.db")
        store.save_custom_command("modo trabajo", "vscode")

        router = IntentRouter(_FakeLLM(), prefer_llm=False)
        summary = {"custom_commands": store.get_custom_commands()}
        route = router.route("activar modo trabajo", summary, [])

        assert route.intent == "executor"
        assert route.source == "memory"
        assert route.actions
        store.close()

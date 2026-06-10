"""Cliente LLM local compatible con Ollama (y APIs OpenAI-like)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from services.logging_service import get_logger

logger = get_logger("llm_client")


class OllamaClient:
    """Cliente HTTP para Ollama sin dependencias externas."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.2",
        fallback_model: str = "mistral",
        timeout_s: float = 90.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.fallback_model = fallback_model
        self.timeout_s = timeout_s
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            self._request("GET", "/api/tags")
            self._available = True
            logger.info("Ollama disponible en %s", self.base_url)
        except Exception:
            self._available = False
            logger.warning("Ollama no disponible en %s (modo reglas local)", self.base_url)
        return self._available

    def list_models(self) -> list[str]:
        try:
            data = self._request("GET", "/api/tags")
            models = data.get("models") or []
            return [m.get("name", "") for m in models if m.get("name")]
        except Exception:
            return []

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.3,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            data = self._request("POST", "/api/chat", payload)
            return (data.get("message") or {}).get("content", "").strip()
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and model != self.fallback_model:
                logger.warning("Modelo %s no encontrado, probando %s", model, self.fallback_model)
                return self.chat(messages, model=self.fallback_model, json_mode=json_mode)
            raise

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}

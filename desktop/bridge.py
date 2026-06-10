"""Puente thread-safe entre EventBus asyncio y Qt."""

from __future__ import annotations

import queue
from dataclasses import dataclass
from typing import Any

from core.event_bus import Event


@dataclass(slots=True)
class BridgeMessage:
  topic: str
  payload: dict[str, Any]
  source: str = "system"


class EventBridge:
    """Cola de eventos del core hacia el hilo UI."""

    def __init__(self) -> None:
        self._queue: queue.Queue[BridgeMessage] = queue.Queue()

    def enqueue(self, topic: str, payload: dict[str, Any] | None = None, source: str = "system") -> None:
        self._queue.put(BridgeMessage(topic=topic, payload=payload or {}, source=source))

    async def on_event(self, event: Event) -> None:
        self.enqueue(event.topic, event.payload, event.source)

    def drain(self) -> list[BridgeMessage]:
        items: list[BridgeMessage] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items

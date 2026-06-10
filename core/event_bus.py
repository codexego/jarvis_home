"""Bus de eventos pub/sub asíncrono para comunicación entre módulos."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from services.logging_service import get_logger

logger = get_logger("event_bus")

EventHandler = Callable[["Event"], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class Event:
    """Mensaje interno entre módulos."""

    topic: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EventBus:
    """Cola pub/sub asíncrona para mensajería interna."""

    def __init__(self, queue_maxsize: int = 0) -> None:
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_subscribers: list[EventHandler] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=queue_maxsize)
        self._running = False
        self._dispatcher_task: asyncio.Task[None] | None = None

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Registra un handler para un topic específico."""
        self._subscribers[topic].append(handler)
        logger.debug("Suscriptor añadido al topic '%s'", topic)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Registra un handler que recibe todos los eventos."""
        self._wildcard_subscribers.append(handler)
        logger.debug("Suscriptor global añadido")

    def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """Elimina un handler de un topic."""
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        """Encola un evento para despacho asíncrono."""
        await self._queue.put(event)
        logger.debug(
            "Evento encolado | topic=%s | source=%s | id=%s",
            event.topic,
            event.source,
            event.event_id,
        )

    async def emit(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
        source: str = "system",
    ) -> None:
        """Atajo para publicar un evento."""
        await self.publish(
            Event(topic=topic, payload=payload or {}, source=source)
        )

    async def start(self) -> None:
        """Inicia el despachador de eventos en segundo plano."""
        if self._running:
            return
        self._running = True
        self._dispatcher_task = asyncio.create_task(
            self._dispatch_loop(),
            name="event_bus_dispatcher",
        )
        logger.info("EventBus iniciado")

    async def stop(self) -> None:
        """Detiene el despachador y espera a que termine."""
        if not self._running:
            return
        self._running = False
        await self._queue.put(
            Event(topic="__shutdown__", source="event_bus")
        )
        if self._dispatcher_task:
            await self._dispatcher_task
            self._dispatcher_task = None
        logger.info("EventBus detenido")

    async def _dispatch_loop(self) -> None:
        while self._running:
            event = await self._queue.get()
            if event.topic == "__shutdown__":
                break
            await self._dispatch(event)
            self._queue.task_done()

    async def _dispatch(self, event: Event) -> None:
        handlers = list(self._subscribers.get(event.topic, []))
        handlers.extend(self._wildcard_subscribers)

        if not handlers:
            logger.debug("Sin suscriptores para topic '%s'", event.topic)
            return

        logger.info(
            "Despachando evento | topic=%s | source=%s | handlers=%d",
            event.topic,
            event.source,
            len(handlers),
        )

        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(
                    "Error en handler del topic '%s' (event_id=%s)",
                    event.topic,
                    event.event_id,
                )

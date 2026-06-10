"""Clase base abstracta para todos los módulos de Jarvis Home."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from core.event_bus import Event, EventBus
from services.logging_service import get_logger


class BaseModule(ABC):
    """
    Interfaz común para módulos del sistema.

    Cada módulo corre en su propia tarea asyncio sin bloquear el core.
    """

    name: str = "base_module"

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.logger = get_logger(self.name)
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @abstractmethod
    async def on_start(self) -> None:
        """Inicialización del módulo. Suscribirse a eventos aquí."""

    @abstractmethod
    async def on_stop(self) -> None:
        """Limpieza al detener el módulo."""

    @abstractmethod
    async def run_loop(self) -> None:
        """Bucle principal del módulo. Debe respetar self._running."""

    async def start(self) -> None:
        """Arranca el módulo en una tarea asyncio independiente."""
        if self._running:
            self.logger.warning("Módulo ya en ejecución")
            return

        self.logger.info("Iniciando módulo")
        self._running = True
        await self.on_start()
        self._task = asyncio.create_task(self._run_wrapper(), name=f"module_{self.name}")
        self.logger.info("Módulo activo")

    async def stop(self) -> None:
        """Detiene el módulo de forma ordenada."""
        if not self._running:
            return

        self.logger.info("Deteniendo módulo")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        await self.on_stop()
        self.logger.info("Módulo detenido")

    async def emit(self, topic: str, payload: dict[str, Any] | None = None) -> None:
        """Publica un evento al bus desde este módulo."""
        await self.event_bus.emit(topic=topic, payload=payload or {}, source=self.name)

    def subscribe(self, topic: str, handler) -> None:
        """Suscribe un handler a un topic del bus."""
        self.event_bus.subscribe(topic, handler)

    async def _run_wrapper(self) -> None:
        try:
            await self.run_loop()
        except asyncio.CancelledError:
            self.logger.debug("Bucle cancelado")
            raise
        except Exception:
            self.logger.exception("Error fatal en bucle del módulo")
            self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

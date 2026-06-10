"""Aplicación principal que coordina el sistema Jarvis Home."""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

from core.event_bus import EventBus
from core.module_registry import ModuleRegistry
from services.logging_service import get_logger, setup_logging

logger = get_logger("core")


class JarvisApp:
    """Core principal: arranca, coordina y detiene todos los módulos."""

    def __init__(
        self,
        registry: ModuleRegistry,
        log_file: Path | None = None,
    ) -> None:
        self.registry = registry
        self.event_bus = EventBus()
        self._modules: dict[str, object] = {}
        self._shutdown_event = asyncio.Event()
        self._log_file = log_file

    async def start(self) -> None:
        """Inicia el bus de eventos y todos los módulos registrados."""
        setup_logging(log_file=self._log_file)
        logger.info("=== Jarvis Home iniciando ===")

        await self.event_bus.start()

        self._modules = self.registry.create_all(self.event_bus)

        for module in self.registry.all_modules():
            await module.start()

        await self.event_bus.emit(
            topic="system.ready",
            payload={"modules": self.registry.registered_names},
            source="core",
        )
        logger.info(
            "Sistema listo | módulos activos: %s",
            ", ".join(self.registry.registered_names),
        )

    async def stop(self) -> None:
        """Detiene todos los módulos y el bus de eventos."""
        logger.info("=== Jarvis Home deteniendo ===")

        await self.event_bus.emit(topic="system.shutdown", source="core")

        for module in reversed(self.registry.all_modules()):
            await module.stop()

        await self.event_bus.stop()
        self._shutdown_event.set()
        logger.info("=== Jarvis Home detenido ===")

    async def run_forever(self) -> None:
        """Ejecución continua 24/7 hasta señal de parada."""
        await self.start()
        self._register_signal_handlers()
        logger.info("Ejecutando en modo continuo (Ctrl+C para detener)")
        await self._shutdown_event.wait()

    def _register_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig,
                    lambda: asyncio.create_task(self._handle_shutdown()),
                )
            except NotImplementedError:
                # Windows no soporta add_signal_handler para SIGTERM en todos los casos
                pass

    async def _handle_shutdown(self) -> None:
        logger.info("Señal de apagado recibida")
        await self.stop()

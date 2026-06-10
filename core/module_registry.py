"""Registro y descubrimiento de módulos."""

from __future__ import annotations

from typing import Type

from core.base_module import BaseModule
from core.event_bus import EventBus
from services.logging_service import get_logger

logger = get_logger("registry")


class ModuleRegistry:
    """Gestiona el registro e instanciación de módulos."""

    def __init__(self) -> None:
        self._module_types: dict[str, Type[BaseModule]] = {}
        self._instances: dict[str, BaseModule] = {}

    def register(self, module_cls: Type[BaseModule]) -> Type[BaseModule]:
        """Registra una clase de módulo. Puede usarse como decorador."""
        name = module_cls.name
        if name in self._module_types:
            raise ValueError(f"Módulo '{name}' ya registrado")

        self._module_types[name] = module_cls
        logger.info("Módulo registrado: %s", name)
        return module_cls

    def create_all(self, event_bus: EventBus) -> dict[str, BaseModule]:
        """Instancia todos los módulos registrados."""
        self._instances = {
            name: cls(event_bus) for name, cls in self._module_types.items()
        }
        logger.info("Instancias creadas: %d módulo(s)", len(self._instances))
        return self._instances

    def get(self, name: str) -> BaseModule | None:
        return self._instances.get(name)

    def all_modules(self) -> list[BaseModule]:
        return list(self._instances.values())

    @property
    def registered_names(self) -> list[str]:
        return list(self._module_types.keys())

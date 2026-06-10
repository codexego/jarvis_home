"""Análisis periódico de patrones para aprendizaje continuo."""

from __future__ import annotations

from typing import Any

from modules.memory.context_detector import detect_work_context, extract_context_metadata
from services.logging_service import get_logger

logger = get_logger("pattern_learner")


class PatternLearner:
    """Refina hábitos, contexto de trabajo y calidad de respuestas."""

    def __init__(self, store: Any, habit_threshold: int = 3) -> None:
        self._store = store
        self.habit_threshold = habit_threshold

    def learn_from_command(self, text: str, intent: str | None = None) -> dict[str, Any]:
        """Aprende de un comando de voz individual."""
        self._store.record_command(text, intent=intent)
        ctx = detect_work_context(text)
        updates: dict[str, Any] = {"work_context": ctx}
        if ctx:
            meta = extract_context_metadata(text, ctx)
            self._store.update_work_context(ctx, meta)
            updates["context_metadata"] = meta
        return updates

    def learn_from_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Aprende de una decisión de la IA."""
        intent = payload.get("intent")
        input_text = payload.get("input", "")
        answer = payload.get("answer")
        routing = payload.get("routing") or {}
        learn = routing.get("learn") or {}

        if input_text and intent:
            self._store.record_command(input_text, intent=intent)

        for key, value in learn.items():
            self._store.set_preference(str(key), str(value))

        if input_text:
            ctx = detect_work_context(input_text)
            if ctx:
                self._store.update_work_context(ctx, extract_context_metadata(input_text, ctx))

        if input_text and answer:
            self._store.record_response_quality(input_text, intent, answer, payload.get("confidence"))

        return {"preferences_learned": list(learn.keys()), "intent": intent}

    def run_maintenance(self) -> dict[str, int]:
        """Tareas periódicas: limpieza, reindexación, consolidación."""
        retention = getattr(self._store, "_retention_days", 90)
        pruned = self._store.prune_old_interactions(retention)
        habits_synced = self._store.sync_habits_from_frequency(self.habit_threshold)
        if pruned or habits_synced:
            logger.info("Mantenimiento memoria | podadas=%d | habitos_sync=%d", pruned, habits_synced)
        return {"pruned": pruned, "habits_synced": habits_synced}

    def learn_custom_command(self, trigger: str, target: str) -> None:
        self._store.save_custom_command(trigger, target)

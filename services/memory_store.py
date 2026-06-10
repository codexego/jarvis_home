"""Almacenamiento persistente SQLite para contexto y aprendizaje."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from services.logging_service import get_logger

logger = get_logger("memory_store")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    topic TEXT NOT NULL,
    input_text TEXT,
    intent TEXT,
    answer TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS command_frequency (
    phrase_normalized TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 1,
    last_used TEXT NOT NULL,
    intent TEXT
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL UNIQUE,
    intent TEXT,
    metadata_json TEXT,
    count INTEGER NOT NULL DEFAULT 1,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS context_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_contexts (
    name TEXT PRIMARY KEY,
    score INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT,
    last_active TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS response_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_pattern TEXT NOT NULL,
    intent TEXT,
    best_answer TEXT,
    use_count INTEGER NOT NULL DEFAULT 1,
    avg_confidence REAL DEFAULT 0.5,
    last_used TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_interactions_ts ON interactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_interactions_intent ON interactions(intent);
CREATE INDEX IF NOT EXISTS idx_interactions_input ON interactions(input_text);
CREATE INDEX IF NOT EXISTS idx_context_session ON context_messages(session_id, id);
CREATE INDEX IF NOT EXISTS idx_habits_pattern ON habits(pattern);
CREATE INDEX IF NOT EXISTS idx_response_input ON response_patterns(input_pattern);
CREATE INDEX IF NOT EXISTS idx_command_count ON command_frequency(count DESC);

CREATE TABLE IF NOT EXISTS custom_commands (
    trigger_phrase TEXT PRIMARY KEY,
    target TEXT NOT NULL,
    action_type TEXT NOT NULL DEFAULT 'open_app',
    use_count INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_used TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_usage (
    app_name TEXT PRIMARY KEY,
    use_count INTEGER NOT NULL DEFAULT 1,
    last_used TEXT NOT NULL
);
"""


class MemoryStore:
    """Base de datos local para hábitos, preferencias y contexto conversacional."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()
        logger.info("MemoryStore listo: %s", db_path)

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def record_interaction(
        self,
        topic: str,
        input_text: str | None = None,
        intent: str | None = None,
        answer: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        now = self._now()
        cur = self._conn.execute(
            """
            INSERT INTO interactions (timestamp, topic, input_text, intent, answer, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (now, topic, input_text, intent, answer, json.dumps(payload or {}, ensure_ascii=False)),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def record_command(self, phrase: str, intent: str | None = None) -> None:
        normalized = " ".join(phrase.lower().split())
        if not normalized:
            return
        now = self._now()
        row = self._conn.execute(
            "SELECT count FROM command_frequency WHERE phrase_normalized = ?",
            (normalized,),
        ).fetchone()
        if row:
            self._conn.execute(
                """
                UPDATE command_frequency
                SET count = count + 1, last_used = ?, intent = COALESCE(?, intent)
                WHERE phrase_normalized = ?
                """,
                (now, intent, normalized),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO command_frequency (phrase_normalized, count, last_used, intent)
                VALUES (?, 1, ?, ?)
                """,
                (normalized, now, intent),
            )
        self._maybe_create_habit(normalized, intent, now)
        self._conn.commit()

    def _maybe_create_habit(self, pattern: str, intent: str | None, now: str) -> None:
        row = self._conn.execute(
            "SELECT count FROM command_frequency WHERE phrase_normalized = ?",
            (pattern,),
        ).fetchone()
        if not row or row["count"] < 3:
            return
        existing = self._conn.execute(
            "SELECT id FROM habits WHERE pattern = ?", (pattern,)
        ).fetchone()
        if existing:
            self._conn.execute(
                "UPDATE habits SET count = ?, last_seen = ?, intent = COALESCE(?, intent) WHERE pattern = ?",
                (row["count"], now, intent, pattern),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO habits (pattern, intent, metadata_json, count, last_seen)
                VALUES (?, ?, '{}', ?, ?)
                """,
                (pattern, intent, row["count"], now),
            )
            logger.info("Habito aprendido: '%s' (%s)", pattern[:50], intent)

    def sync_habits_from_frequency(self, threshold: int = 3) -> int:
        rows = self._conn.execute(
            "SELECT phrase_normalized, count, intent, last_used FROM command_frequency WHERE count >= ?",
            (threshold,),
        ).fetchall()
        synced = 0
        for row in rows:
            self._maybe_create_habit(row["phrase_normalized"], row["intent"], row["last_used"])
            synced += 1
        self._conn.commit()
        return synced

    def set_preference(self, key: str, value: str) -> None:
        now = self._now()
        self._conn.execute(
            """
            INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, value, now),
        )
        self._conn.commit()

    def get_preference(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def get_preferences(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT key, value FROM preferences").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def update_work_context(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        now = self._now()
        row = self._conn.execute(
            "SELECT score, metadata_json FROM work_contexts WHERE name = ?", (name,)
        ).fetchone()
        if row:
            existing = {}
            try:
                existing = json.loads(row["metadata_json"] or "{}")
            except json.JSONDecodeError:
                pass
            if metadata:
                existing.update(metadata)
            self._conn.execute(
                """
                UPDATE work_contexts SET score = score + 1, metadata_json = ?, last_active = ?
                WHERE name = ?
                """,
                (json.dumps(existing, ensure_ascii=False), now, name),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO work_contexts (name, score, metadata_json, last_active)
                VALUES (?, 1, ?, ?)
                """,
                (name, json.dumps(metadata or {}, ensure_ascii=False), now),
            )
            logger.info("Contexto de trabajo detectado: %s", name)
        self._conn.commit()

    def get_work_contexts(self, limit: int = 5) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT name, score, metadata_json, last_active FROM work_contexts ORDER BY score DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            item = dict(r)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            except json.JSONDecodeError:
                item["metadata"] = {}
            result.append(item)
        return result

    def get_active_work_context(self) -> dict[str, Any] | None:
        contexts = self.get_work_contexts(limit=1)
        return contexts[0] if contexts else None

    def record_response_quality(
        self,
        input_text: str,
        intent: str | None,
        answer: str,
        confidence: float | None,
    ) -> None:
        pattern = " ".join(input_text.lower().split())[:200]
        if not pattern or not answer:
            return
        now = self._now()
        conf = float(confidence or 0.5)
        row = self._conn.execute(
            "SELECT id, use_count, avg_confidence, best_answer FROM response_patterns WHERE input_pattern = ?",
            (pattern,),
        ).fetchone()
        if row:
            new_count = row["use_count"] + 1
            new_avg = ((row["avg_confidence"] or 0.5) * row["use_count"] + conf) / new_count
            best = row["best_answer"]
            if conf >= (row["avg_confidence"] or 0):
                best = answer
            self._conn.execute(
                """
                UPDATE response_patterns
                SET use_count = ?, avg_confidence = ?, best_answer = ?, intent = COALESCE(?, intent), last_used = ?
                WHERE id = ?
                """,
                (new_count, new_avg, best, intent, now, row["id"]),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO response_patterns (input_pattern, intent, best_answer, use_count, avg_confidence, last_used)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (pattern, intent, answer, conf, now),
            )
        self._conn.commit()

    def get_best_response(self, input_text: str) -> dict[str, Any] | None:
        pattern = " ".join(input_text.lower().split())[:200]
        row = self._conn.execute(
            """
            SELECT best_answer, intent, avg_confidence, use_count
            FROM response_patterns WHERE input_pattern = ? AND use_count >= 2
            """,
            (pattern,),
        ).fetchone()
        return dict(row) if row else None

    def add_context_message(self, role: str, content: str, session_id: str = "default") -> None:
        now = self._now()
        self._conn.execute(
            """
            INSERT INTO context_messages (session_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, now),
        )
        self._conn.commit()
        self._trim_context(session_id)

    def _trim_context(self, session_id: str, max_messages: int = 40) -> None:
        rows = self._conn.execute(
            "SELECT COUNT(*) AS c FROM context_messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if rows and rows["c"] > max_messages:
            excess = rows["c"] - max_messages
            self._conn.execute(
                """
                DELETE FROM context_messages
                WHERE id IN (
                    SELECT id FROM context_messages
                    WHERE session_id = ?
                    ORDER BY id ASC LIMIT ?
                )
                """,
                (session_id, excess),
            )
            self._conn.commit()

    def get_context_for_llm(self, session_id: str = "default", limit: int = 10) -> list[dict[str, str]]:
        rows = self._conn.execute(
            """
            SELECT role, content FROM context_messages
            WHERE session_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def get_memory_summary(self, command_limit: int = 5, habit_limit: int = 5) -> dict[str, Any]:
        commands = self._conn.execute(
            """
            SELECT phrase_normalized, count, intent, last_used
            FROM command_frequency ORDER BY count DESC LIMIT ?
            """,
            (command_limit,),
        ).fetchall()
        habits = self._conn.execute(
            """
            SELECT pattern, intent, count, last_seen
            FROM habits ORDER BY count DESC LIMIT ?
            """,
            (habit_limit,),
        ).fetchall()
        prefs = self.get_preferences()
        recent = self._conn.execute(
            """
            SELECT input_text, intent, answer, timestamp
            FROM interactions
            WHERE input_text IS NOT NULL
            ORDER BY id DESC LIMIT 5
            """
        ).fetchall()
        return {
            "frequent_commands": [dict(r) for r in commands],
            "habits": [dict(r) for r in habits],
            "preferences": prefs,
            "recent_interactions": [dict(r) for r in recent],
            "work_contexts": self.get_work_contexts(),
            "active_work_context": self.get_active_work_context(),
            "custom_commands": self.get_custom_commands(),
            "top_apps": self.get_top_apps(),
        }

    def build_context_snapshot(self, session_id: str = "default", limit: int = 10) -> dict[str, Any]:
        """Paquete completo para que ai_brain consulte antes de responder."""
        summary = self.get_memory_summary()
        return {
            "summary": summary,
            "history": self.get_context_for_llm(session_id, limit),
            "preferences": summary["preferences"],
            "habits": summary["habits"],
            "frequent_commands": summary["frequent_commands"],
            "custom_commands": summary.get("custom_commands", []),
            "top_apps": summary.get("top_apps", []),
            "work_context": summary.get("active_work_context"),
            "work_contexts": summary.get("work_contexts", []),
        }

    def search_interactions(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Búsqueda simple por texto en interacciones."""
        pattern = f"%{query.lower()}%"
        rows = self._conn.execute(
            """
            SELECT id, timestamp, topic, input_text, intent, answer
            FROM interactions
            WHERE LOWER(COALESCE(input_text,'')) LIKE ?
               OR LOWER(COALESCE(answer,'')) LIKE ?
               OR LOWER(COALESCE(intent,'')) LIKE ?
            ORDER BY id DESC LIMIT ?
            """,
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def query_recent(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM interactions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        results = []
        for r in rows:
            item = dict(r)
            if item.get("payload_json"):
                try:
                    item["payload"] = json.loads(item["payload_json"])
                except json.JSONDecodeError:
                    item["payload"] = {}
            results.append(item)
        return results

    def prune_old_interactions(self, retention_days: int = 90) -> int:
        if retention_days <= 0:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        cur = self._conn.execute(
            "DELETE FROM interactions WHERE timestamp < ?", (cutoff,)
        )
        self._conn.commit()
        return cur.rowcount

    def stats(self) -> dict[str, int]:
        return {
            "interactions": self._conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0],
            "habits": self._conn.execute("SELECT COUNT(*) FROM habits").fetchone()[0],
            "preferences": self._conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0],
            "commands": self._conn.execute("SELECT COUNT(*) FROM command_frequency").fetchone()[0],
            "custom_commands": self._conn.execute("SELECT COUNT(*) FROM custom_commands").fetchone()[0],
        }

    def save_custom_command(self, trigger: str, target: str, action_type: str = "open_app") -> None:
        key = " ".join(trigger.lower().split())
        now = self._now()
        row = self._conn.execute(
            "SELECT use_count FROM custom_commands WHERE trigger_phrase = ?", (key,)
        ).fetchone()
        if row:
            self._conn.execute(
                """
                UPDATE custom_commands SET target = ?, action_type = ?,
                use_count = use_count + 1, last_used = ? WHERE trigger_phrase = ?
                """,
                (target, action_type, now, key),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO custom_commands (trigger_phrase, target, action_type, use_count, created_at, last_used)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (key, target, action_type, now, now),
            )
        self._conn.commit()
        logger.info("Comando personalizado guardado: '%s' -> %s", key, target)

    def get_custom_commands(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT trigger_phrase, target, action_type, use_count, last_used FROM custom_commands ORDER BY use_count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def match_custom_command(self, text: str) -> dict[str, Any] | None:
        normalized = " ".join(text.lower().split())
        rows = self._conn.execute(
            "SELECT trigger_phrase, target, action_type FROM custom_commands"
        ).fetchall()
        best = None
        best_len = 0
        for row in rows:
            trigger = row["trigger_phrase"]
            if trigger in normalized or normalized in trigger:
                if len(trigger) > best_len:
                    best_len = len(trigger)
                    best = dict(row)
        return best

    def record_app_usage(self, app_name: str) -> None:
        key = app_name.lower().strip()
        now = self._now()
        row = self._conn.execute("SELECT use_count FROM app_usage WHERE app_name = ?", (key,)).fetchone()
        if row:
            self._conn.execute(
                "UPDATE app_usage SET use_count = use_count + 1, last_used = ? WHERE app_name = ?",
                (now, key),
            )
        else:
            self._conn.execute(
                "INSERT INTO app_usage (app_name, use_count, last_used) VALUES (?, 1, ?)",
                (key, now),
            )
        self._conn.commit()

    def get_top_apps(self, limit: int = 5) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT app_name, use_count, last_used FROM app_usage ORDER BY use_count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

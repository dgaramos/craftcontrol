from __future__ import annotations

from pathlib import Path
import sqlite3
import time
from typing import Any
import json


class StateRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS state (kind TEXT, key TEXT, value TEXT, updated_at REAL, "
                "source TEXT, PRIMARY KEY(kind,key))"
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(state)")}
            if "changed_at" not in columns:
                connection.execute("ALTER TABLE state ADD COLUMN changed_at REAL")
                connection.execute("UPDATE state SET changed_at = updated_at WHERE changed_at IS NULL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, "
                "created_at REAL NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute("PRAGMA journal_mode=WAL")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def store(self, kind: str, values: dict[str, str], source: str) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO state(kind,key,value,updated_at,source,changed_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(kind,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at,"
                "source=excluded.source,changed_at=CASE WHEN state.value != excluded.value THEN excluded.changed_at ELSE state.changed_at END",
                [(kind, key, value, now, source, now) for key, value in values.items()],
            )

    def replace(self, kind: str, values: dict[str, str], source: str) -> None:
        with self._connect() as connection:
            if values:
                placeholders = ",".join("?" for _ in values)
                connection.execute(
                    f"DELETE FROM state WHERE kind = ? AND key NOT IN ({placeholders})",
                    (kind, *values.keys()),
                )
            else:
                connection.execute("DELETE FROM state WHERE kind = ?", (kind,))
        self.store(kind, values, source)

    def snapshot(self, refreshing: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "settings": {}, "gamerules": {}, "players": [], "online": 0,
            "max_players": 0, "updated_at": 0, "refreshing": refreshing,
        }
        with self._connect() as connection:
            rows = connection.execute("SELECT kind,key,value,updated_at,changed_at,source FROM state").fetchall()
        domains: dict[str, dict[str, Any]] = {}
        for kind, key, value, updated_at, changed_at, source in rows:
            if kind == "players":
                result["players"].append(key)
            elif kind == "server" and key in {"online", "max_players"}:
                result[key] = int(value)
            else:
                result.setdefault(kind, {})[key] = value
            result["updated_at"] = max(result["updated_at"], updated_at)
            domain = domains.setdefault(kind, {"observed_at": 0, "changed_at": 0, "source": source})
            domain["observed_at"] = max(domain["observed_at"], updated_at)
            domain["changed_at"] = max(domain["changed_at"], changed_at or updated_at)
            domain["source"] = source
        now = time.time()
        for domain in domains.values():
            domain["freshness"] = "fresh" if now - domain["observed_at"] < 1200 else "stale"
        result["domains"] = domains
        return result

    def record_event(self, topic: str, source: str, payload: dict[str, Any]) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO events(topic,created_at,source,payload) VALUES(?,?,?,?)",
                (topic, time.time(), source, json.dumps(payload, ensure_ascii=False)),
            )
            connection.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 2000)")
            return int(cursor.lastrowid)

    def events_after(self, event_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id,topic,created_at,source,payload FROM events WHERE id > ? ORDER BY id LIMIT ?",
                (event_id, limit),
            ).fetchall()
        return [{"id": row[0], "topic": row[1], "timestamp": row[2], "source": row[3], "payload": json.loads(row[4])} for row in rows]

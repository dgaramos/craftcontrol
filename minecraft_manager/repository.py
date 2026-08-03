from __future__ import annotations

from pathlib import Path
import sqlite3
import time
from typing import Any


class StateRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS state (kind TEXT, key TEXT, value TEXT, updated_at REAL, "
                "source TEXT, PRIMARY KEY(kind,key))"
            )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.path)

    def store(self, kind: str, values: dict[str, str], source: str) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO state(kind,key,value,updated_at,source) VALUES(?,?,?,?,?) "
                "ON CONFLICT(kind,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at,source=excluded.source",
                [(kind, key, value, now, source) for key, value in values.items()],
            )

    def replace(self, kind: str, values: dict[str, str], source: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM state WHERE kind = ?", (kind,))
        self.store(kind, values, source)

    def snapshot(self, refreshing: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "settings": {}, "gamerules": {}, "players": [], "online": 0,
            "max_players": 0, "updated_at": 0, "refreshing": refreshing,
        }
        with self._connect() as connection:
            rows = connection.execute("SELECT kind,key,value,updated_at FROM state").fetchall()
        for kind, key, value, updated_at in rows:
            if kind == "players":
                result["players"].append(key)
            elif kind == "server" and key in {"online", "max_players"}:
                result[key] = int(value)
            else:
                result.setdefault(kind, {})[key] = value
            result["updated_at"] = max(result["updated_at"], updated_at)
        return result

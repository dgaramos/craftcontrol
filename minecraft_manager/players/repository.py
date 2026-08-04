"""Player persistence adapter over the shared SQLite database."""

from __future__ import annotations

from typing import Any

from ..repository import StateRepository


class SQLitePlayerRepository:
    def __init__(self, database: StateRepository) -> None:
        self.database = database

    def snapshot(self, refreshing: bool = False) -> dict[str, Any]:
        return self.database.snapshot(refreshing)

    def store(self, kind: str, values: dict[str, str], source: str) -> None:
        self.database.store(kind, values, source)

    def replace(self, kind: str, values: dict[str, str], source: str) -> None:
        self.database.replace(kind, values, source)

    def observe_player(self, name: str, connected: bool, xuid: str = "", source: str = "bedrock-log", occurred_at: float | None = None) -> dict[str, Any]:
        return self.database.observe_player(name, connected, xuid, source, occurred_at)

    def close_online_sessions(self, reason: str, source: str = "docker-events") -> list[str]:
        return self.database.close_online_sessions(reason, source)

    def record_player_death(self, name: str, cause: str, raw: str, source: str, event_key: str) -> bool:
        return self.database.record_player_death(name, cause, raw, source, event_key)

    def set_player_permission(self, name: str, permission: str, source: str = "manager") -> None:
        self.database.set_player_permission(name, permission, source)

    def player_profiles(self) -> list[dict[str, Any]]:
        return self.database.player_profiles()

    def player_profile(self, public_id: str, history_limit: int = 100, session_limit: int = 50) -> dict[str, Any] | None:
        return self.database.player_profile(public_id, history_limit, session_limit)

    def player_activity(self, kind: str, player: str, source: str, search: str, days: int, page: int, page_size: int) -> dict[str, Any]:
        return self.database.player_activity(kind, player, source, search, days, page, page_size)

    def player_rankings(self, limit: int = 10) -> dict[str, Any]:
        return self.database.player_rankings(limit)

    def block_analytics(self, limit: int = 10) -> dict[str, Any]:
        return self.database.block_analytics(limit)

    def combat_analytics(self, limit: int = 10) -> dict[str, Any]:
        return self.database.combat_analytics(limit)

    def exploration_analytics(self, limit: int = 10) -> dict[str, Any]:
        return self.database.exploration_analytics(limit)

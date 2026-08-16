"""Tests for SQLitePlayerRepository — delegation to StateRepository."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from minecraft_manager.players.repository import SQLitePlayerRepository


@pytest.fixture
def db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def repo(db: MagicMock) -> SQLitePlayerRepository:
    return SQLitePlayerRepository(db)


def test_snapshot_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.snapshot.return_value = {"players": {}}
    result = repo.snapshot()
    db.snapshot.assert_called_once_with(False)
    assert result == {"players": {}}


def test_snapshot_refreshing_flag_forwarded(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    repo.snapshot(refreshing=True)
    db.snapshot.assert_called_once_with(True)


def test_store_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    repo.store("players", {"VonCrush": "online"}, "bedrock-log")
    db.store.assert_called_once_with("players", {"VonCrush": "online"}, "bedrock-log")


def test_replace_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    repo.replace("permissions", {"voncrush": "member"}, "permissions.json")
    db.replace.assert_called_once_with("permissions", {"voncrush": "member"}, "permissions.json")


def test_observe_player_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    repo.observe_player("VonCrush", True, "999", "bedrock-log", 1000.0)
    db.observe_player.assert_called_once_with("VonCrush", True, "999", "bedrock-log", 1000.0)


def test_observe_player_default_args(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    repo.observe_player("VonCrush", False)
    db.observe_player.assert_called_once_with("VonCrush", False, "", "bedrock-log", None)


def test_close_online_sessions_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.close_online_sessions.return_value = ["VonCrush"]
    result = repo.close_online_sessions("shutdown", "docker-events")
    db.close_online_sessions.assert_called_once_with("shutdown", "docker-events")
    assert result == ["VonCrush"]


def test_record_player_death_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.record_player_death.return_value = True
    result = repo.record_player_death("VonCrush", "creeper", "VonCrush was blown up", "bedrock-log", "abc123")
    db.record_player_death.assert_called_once_with("VonCrush", "creeper", "VonCrush was blown up", "bedrock-log", "abc123")
    assert result is True


def test_set_player_permission_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    repo.set_player_permission("VonCrush", "operator", "manager")
    db.set_player_permission.assert_called_once_with("VonCrush", "operator", "manager")


def test_player_profiles_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.player_profiles.return_value = [{"name": "VonCrush"}]
    result = repo.player_profiles()
    db.player_profiles.assert_called_once()
    assert result[0]["name"] == "VonCrush"


def test_player_profile_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.player_profile.return_value = {"name": "VonCrush"}
    result = repo.player_profile("some-uuid")
    db.player_profile.assert_called_once_with("some-uuid", 100, 50)
    assert result is not None


def test_player_activity_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.player_activity.return_value = {"events": []}
    result = repo.player_activity("all", "VonCrush", "all", "", 0, 1, 10)
    db.player_activity.assert_called_once_with("all", "VonCrush", "all", "", 0, 1, 10)
    assert result == {"events": []}


def test_player_rankings_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.player_rankings.return_value = {"top": ["VonCrush"]}
    result = repo.player_rankings(5)
    db.player_rankings.assert_called_once_with(5)
    assert result == {"top": ["VonCrush"]}


def test_block_analytics_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.block_analytics.return_value = {"mined": 42}
    result = repo.block_analytics(5)
    db.block_analytics.assert_called_once_with(5)
    assert result == {"mined": 42}


def test_combat_analytics_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.combat_analytics.return_value = {"kills": 7}
    result = repo.combat_analytics(5)
    db.combat_analytics.assert_called_once_with(5)
    assert result == {"kills": 7}


def test_exploration_analytics_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.exploration_analytics.return_value = {"biomes": 3}
    result = repo.exploration_analytics(5)
    db.exploration_analytics.assert_called_once_with(5)
    assert result == {"biomes": 3}


def test_period_analytics_delegates(repo: SQLitePlayerRepository, db: MagicMock) -> None:
    db.period_analytics.return_value = {"sessions": 12}
    result = repo.period_analytics(30, 5)
    db.period_analytics.assert_called_once_with(30, 5)
    assert result == {"sessions": 12}

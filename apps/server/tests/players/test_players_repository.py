"""Tests for SQLitePlayerRepository — autonomous SQL adapter."""
from __future__ import annotations

import pytest

from minecraft_manager.players.repository import SQLitePlayerRepository


def test_observe_player_creates_profile(player_repo: SQLitePlayerRepository) -> None:
    result = player_repo.observe_player("VonCrush", True, "999", "bedrock-log", 1000.0)
    assert result["changed"] is True
    profiles = player_repo.player_profiles()
    assert len(profiles) == 1
    assert profiles[0]["name"] == "VonCrush"
    assert profiles[0]["online"] is True


def test_observe_player_disconnect_closes_session(player_repo: SQLitePlayerRepository) -> None:
    player_repo.observe_player("VonCrush", True, "999", occurred_at=100.0)
    player_repo.observe_player("VonCrush", False, "999", occurred_at=160.0)
    profile = player_repo.player_profiles()[0]
    assert profile["online"] is False
    assert profile["sessions_count"] == 1
    assert profile["total_play_seconds"] == 60


def test_store_and_snapshot(player_repo: SQLitePlayerRepository) -> None:
    player_repo.store("players", {"VonCrush": "online"}, "bedrock-log")
    snapshot = player_repo.snapshot()
    assert "VonCrush" in snapshot["players"]


def test_replace_updates_state(player_repo: SQLitePlayerRepository) -> None:
    player_repo.replace("permissions", {"voncrush": "member"}, "permissions.json")
    snapshot = player_repo.snapshot()
    assert snapshot.get("permissions", {}).get("voncrush") == "member"


def test_close_online_sessions(player_repo: SQLitePlayerRepository) -> None:
    player_repo.observe_player("VonCrush", True, "999", occurred_at=100.0)
    names = player_repo.close_online_sessions("shutdown")
    assert "VonCrush" in names
    assert player_repo.player_profiles()[0]["online"] is False


def test_record_player_death(player_repo: SQLitePlayerRepository) -> None:
    player_repo.observe_player("VonCrush", True, "999")
    inserted = player_repo.record_player_death("VonCrush", "creeper", "VonCrush was blown up", "bedrock-log", "abc123")
    assert inserted is True
    profile = player_repo.player_profiles()[0]
    assert profile["deaths_count"] == 1


def test_record_player_death_idempotent(player_repo: SQLitePlayerRepository) -> None:
    player_repo.observe_player("VonCrush", True, "999")
    assert player_repo.record_player_death("VonCrush", "creeper", "raw", "bedrock-log", "key1") is True
    assert player_repo.record_player_death("VonCrush", "creeper", "raw", "bedrock-log", "key1") is False


def test_set_player_permission(player_repo: SQLitePlayerRepository) -> None:
    player_repo.observe_player("VonCrush", True, "999")
    player_repo.set_player_permission("VonCrush", "operator", "manager")
    profile = player_repo.player_profiles()[0]
    assert profile["permission"] == "operator"
    assert profile["operator"] is True


def test_player_profiles_returns_list(player_repo: SQLitePlayerRepository) -> None:
    assert player_repo.player_profiles() == []
    player_repo.observe_player("VonCrush", True)
    assert len(player_repo.player_profiles()) == 1


def test_player_profile_returns_detail(player_repo: SQLitePlayerRepository) -> None:
    player_repo.observe_player("VonCrush", True, "999", occurred_at=100.0)
    player_repo.observe_player("VonCrush", False, "999", occurred_at=160.0)
    profiles = player_repo.player_profiles()
    detail = player_repo.player_profile(profiles[0]["id"])
    assert detail is not None
    assert detail["name"] == "VonCrush"
    assert len(detail["history"]) == 2
    assert len(detail["sessions"]) == 1


def test_player_profile_without_telemetry_has_no_observed_game_mode(
    player_repo: SQLitePlayerRepository,
) -> None:
    """The optional Telemetry Pack never fabricates an observed game mode."""
    player_repo.observe_player("VonCrush", True, "999", occurred_at=100.0)

    detail = player_repo.player_profile(player_repo.player_profiles()[0]["id"])

    assert detail is not None
    assert detail["observed_game_mode"] is None


def test_player_profile_unknown_returns_none(player_repo: SQLitePlayerRepository) -> None:
    assert player_repo.player_profile("nonexistent-id") is None


def test_player_activity_returns_paginated(player_repo: SQLitePlayerRepository) -> None:
    player_repo.observe_player("VonCrush", True, "999")
    player_repo.observe_player("VonCrush", False, "999")
    result = player_repo.player_activity("all", "VonCrush", "all", "", 0, 1, 10)
    assert result["total"] == 2
    assert len(result["events"]) == 2
    assert isinstance(result["first_event_at"], float)


def test_player_activity_first_event_at_is_none_when_empty(player_repo: SQLitePlayerRepository) -> None:
    result = player_repo.player_activity("all", "", "all", "", 0, 1, 10)
    assert result["first_event_at"] is None


def test_player_rankings_is_shaped(player_repo: SQLitePlayerRepository) -> None:
    result = player_repo.player_rankings(5)
    assert result["period"] == "lifetime"
    assert "play_time" in result["metrics"]


def test_block_analytics_returns_structure(player_repo: SQLitePlayerRepository) -> None:
    result = player_repo.block_analytics(5)
    assert "totals" in result
    assert "ores" in result


def test_combat_analytics_zero_state(player_repo: SQLitePlayerRepository) -> None:
    result = player_repo.combat_analytics(5)
    assert result["totals"]["deaths"] == 0
    assert result["pvp"] == []


def test_exploration_analytics_zero_state(player_repo: SQLitePlayerRepository) -> None:
    result = player_repo.exploration_analytics(5)
    assert result["totals"]["distance"] == 0
    assert result["players"] == []


def test_period_analytics_returns_calendar(player_repo: SQLitePlayerRepository) -> None:
    result = player_repo.period_analytics(7, 5)
    assert result["period_days"] == 7
    assert len(result["calendar"]) == 7
    assert len(result["heatmap"]) == 168


def test_reconcile_online_marks_absent_players_offline(player_repo: SQLitePlayerRepository) -> None:
    player_repo.observe_player("VonCrush", True, "111")
    player_repo.observe_player("Nicole", True, "222")
    player_repo.reconcile_online_players(["Nicole"], {"Nicole": "222"}, "reconcile")
    profiles = {p["name"]: p for p in player_repo.player_profiles()}
    assert profiles["VonCrush"]["online"] is False
    assert profiles["Nicole"]["online"] is True

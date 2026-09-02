"""TDD tests for per-player preferred_game_mode — issue #408."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from minecraft_manager.players.repository import SQLitePlayerRepository
from minecraft_manager.players.service import PlayerService
from minecraft_manager.core.migrations import run_migrations
from minecraft_manager.runtime import ManagerService

import sqlite3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def console() -> MagicMock:
    return MagicMock()


@pytest.fixture
def events() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(player_repo: SQLitePlayerRepository, console: MagicMock, events: MagicMock) -> PlayerService:
    return PlayerService(player_repo, MagicMock(), console, events)


# ---------------------------------------------------------------------------
# test_set_game_mode_persists_preference
# ---------------------------------------------------------------------------


def test_set_game_mode_persists_preference(
    service: PlayerService, player_repo: SQLitePlayerRepository, console: MagicMock
) -> None:
    """Online player: preference persisted in the repository and command sent to console."""
    player_repo.observe_player("VonCrush", True, "999")
    # Populate the state table so the service sees VonCrush as online.
    player_repo.store("players", {"VonCrush": "online"}, "bedrock-log")
    service.set_game_mode("VonCrush", "creative")

    console.set_game_mode.assert_called_once_with("VonCrush", "creative")
    profiles = player_repo.player_profiles()
    assert profiles[0]["preferred_game_mode"] == "creative"


# ---------------------------------------------------------------------------
# test_player_profile_exposes_preferred_game_mode
# ---------------------------------------------------------------------------


def test_player_profile_exposes_preferred_game_mode(
    player_repo: SQLitePlayerRepository, tmp_path: Path
) -> None:
    """Row with preferred_game_mode = 'creative' exposes the field on the profile detail."""
    player_repo.observe_player("VonCrush", True, "999")
    profiles = player_repo.player_profiles()
    public_id = profiles[0]["id"]

    # Directly set the column to simulate a pre-existing preference.
    with sqlite3.connect(tmp_path / "state.db") as conn:
        conn.execute(
            "UPDATE player_profiles SET preferred_game_mode = 'creative' WHERE current_name = 'VonCrush'"
        )

    detail = player_repo.player_profile(public_id)
    assert detail is not None
    assert detail["preferred_game_mode"] == "creative"


# ---------------------------------------------------------------------------
# test_set_game_mode_invalid_mode_rejected
# ---------------------------------------------------------------------------


def test_set_game_mode_invalid_mode_rejected(service: PlayerService) -> None:
    """'spectator' is not a valid mode and must raise ValueError."""
    with pytest.raises(ValueError):
        service.set_game_mode("VonCrush", "spectator")


# ---------------------------------------------------------------------------
# test_set_game_mode_offline_still_persists
# ---------------------------------------------------------------------------


def test_set_game_mode_offline_still_persists(
    service: PlayerService, player_repo: SQLitePlayerRepository, console: MagicMock
) -> None:
    """Offline player: preference is persisted but no console command is sent."""
    player_repo.observe_player("VonCrush", True, "999")
    # Disconnect so they are offline.
    player_repo.observe_player("VonCrush", False, "999")

    service.set_game_mode("VonCrush", "creative")

    console.set_game_mode.assert_not_called()
    profiles = player_repo.player_profiles()
    assert profiles[0]["preferred_game_mode"] == "creative"


# ---------------------------------------------------------------------------
# test_migration_idempotent
# ---------------------------------------------------------------------------


def test_migration_idempotent(tmp_path: Path) -> None:
    """Applying the migration twice must not raise any exception."""
    path = tmp_path / "idem.db"
    with sqlite3.connect(path) as conn:
        run_migrations(conn)
        # Running again — idempotent.
        run_migrations(conn)


# ---------------------------------------------------------------------------
# test_preferred_game_mode_null_by_default
# ---------------------------------------------------------------------------


def test_preferred_game_mode_null_by_default(player_repo: SQLitePlayerRepository) -> None:
    """Freshly created profile has preferred_game_mode: None."""
    player_repo.observe_player("VonCrush", True, "999")
    profiles = player_repo.player_profiles()
    assert profiles[0]["preferred_game_mode"] is None


# ---------------------------------------------------------------------------
# test_observed_game_mode_unchanged
# ---------------------------------------------------------------------------


def test_observed_game_mode_unchanged(
    service: PlayerService, player_repo: SQLitePlayerRepository
) -> None:
    """After setting preference, observed_game_mode still reflects only telemetry."""
    player_repo.observe_player("VonCrush", True, "999")
    player_repo.store("players", {"VonCrush": "online"}, "bedrock-log")
    profiles = player_repo.player_profiles()
    public_id = profiles[0]["id"]

    service.set_game_mode("VonCrush", "creative")

    detail = player_repo.player_profile(public_id)
    assert detail is not None
    # No telemetry was pushed, so observed_game_mode must remain None.
    assert detail["observed_game_mode"] is None
    # But preferred_game_mode must reflect what was set.
    assert detail["preferred_game_mode"] == "creative"


# ---------------------------------------------------------------------------
# test_manager_service_set_player_game_mode_returns_value
# ---------------------------------------------------------------------------


def test_manager_service_set_player_game_mode_returns_value() -> None:
    """ManagerService.set_player_game_mode forwards the return value from PlayerService."""
    player_service = MagicMock()
    player_service.set_game_mode.return_value = "survival"

    manager = ManagerService.__new__(ManagerService)
    manager.player_service = player_service

    result = manager.set_player_game_mode("VonCrush", "survival")

    player_service.set_game_mode.assert_called_once_with("VonCrush", "survival")
    assert result == "survival"

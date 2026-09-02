"""TDD tests for per-player preferred_game_mode — issue #408."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from minecraft_manager.players.repository import SQLitePlayerRepository
from minecraft_manager.players.service import PlayerService
from minecraft_manager.core.migrations import run_migrations
from minecraft_manager.core.repository import StateRepository
from minecraft_manager.runtime import ManagerService

import sqlite3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "state.db"
    StateRepository(path).initialize()
    return path


@pytest.fixture
def repo(db_path: Path) -> SQLitePlayerRepository:
    return SQLitePlayerRepository(db_path)


@pytest.fixture
def console() -> MagicMock:
    return MagicMock()


@pytest.fixture
def events() -> MagicMock:
    return MagicMock()


@pytest.fixture
def service(repo, console, events) -> PlayerService:
    return PlayerService(repo, MagicMock(), console, events)


# ---------------------------------------------------------------------------
# test_set_game_mode_persists_preference
# ---------------------------------------------------------------------------


def test_set_game_mode_persists_preference(
    service: PlayerService, repo: SQLitePlayerRepository, console: MagicMock
) -> None:
    """Online player: preference persisted in the repository and command sent to console."""
    repo.observe_player("VonCrush", True, "999")
    # Populate the state table so the service sees VonCrush as online.
    repo.store("players", {"VonCrush": "online"}, "bedrock-log")
    service.set_game_mode("VonCrush", "creative")

    console.set_game_mode.assert_called_once_with("VonCrush", "creative")
    profiles = repo.player_profiles()
    assert profiles[0]["preferred_game_mode"] == "creative"


# ---------------------------------------------------------------------------
# test_player_profile_exposes_preferred_game_mode
# ---------------------------------------------------------------------------


def test_player_profile_exposes_preferred_game_mode(
    repo: SQLitePlayerRepository, db_path: Path
) -> None:
    """Row with preferred_game_mode = 'creative' exposes the field on the profile detail."""
    repo.observe_player("VonCrush", True, "999")
    profiles = repo.player_profiles()
    public_id = profiles[0]["id"]

    # Directly set the column to simulate a pre-existing preference.
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE player_profiles SET preferred_game_mode = 'creative' WHERE current_name = 'VonCrush'"
        )

    detail = repo.player_profile(public_id)
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
    service: PlayerService, repo: SQLitePlayerRepository, console: MagicMock
) -> None:
    """Offline player: preference is persisted but no console command is sent."""
    repo.observe_player("VonCrush", True, "999")
    # Disconnect so they are offline.
    repo.observe_player("VonCrush", False, "999")

    service.set_game_mode("VonCrush", "creative")

    console.set_game_mode.assert_not_called()
    profiles = repo.player_profiles()
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


def test_preferred_game_mode_null_by_default(repo: SQLitePlayerRepository) -> None:
    """Freshly created profile has preferred_game_mode: None."""
    repo.observe_player("VonCrush", True, "999")
    profiles = repo.player_profiles()
    assert profiles[0]["preferred_game_mode"] is None


# ---------------------------------------------------------------------------
# test_observed_game_mode_unchanged
# ---------------------------------------------------------------------------


def test_observed_game_mode_unchanged(
    service: PlayerService, repo: SQLitePlayerRepository
) -> None:
    """After setting preference, observed_game_mode still reflects only telemetry."""
    repo.observe_player("VonCrush", True, "999")
    repo.store("players", {"VonCrush": "online"}, "bedrock-log")
    profiles = repo.player_profiles()
    public_id = profiles[0]["id"]

    service.set_game_mode("VonCrush", "creative")

    detail = repo.player_profile(public_id)
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

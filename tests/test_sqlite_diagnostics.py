"""Verify that sqlite_diagnostics covers all manager persistence paths.

Each test checks that a real database operation on a specific path (auth,
operations, core state, players, telemetry) increments the shared connection
counter so diagnostics describe the full contention picture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from minecraft_manager._db import sqlite_diagnostics
from minecraft_manager.auth.service import AuthService
from minecraft_manager.core.repository import StateRepository
from minecraft_manager.operations.repository import SQLiteOperationRepository
from minecraft_manager.players.repository import SQLitePlayerRepository
from minecraft_manager.telemetry_repository import SQLiteTelemetryRepository
from minecraft_manager.migrations import run_migrations
import sqlite3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _initialized_db(tmp_path: Path, name: str = "manager.db") -> Path:
    """Return a path to a freshly migrated database."""
    path = tmp_path / name
    StateRepository(path).initialize()
    return path


def _baseline() -> int:
    """Return the current connection count before a test touches the database."""
    return int(sqlite_diagnostics()["connections"])


# ---------------------------------------------------------------------------
# Auth path
# ---------------------------------------------------------------------------


def test_auth_connect_increments_diagnostics(tmp_path: Path) -> None:
    """AuthService._connect must record its connection wait in shared diagnostics."""
    path = _initialized_db(tmp_path)
    auth = AuthService(path)
    before = _baseline()

    # Any auth operation that opens a connection is sufficient.
    auth.access_list()

    after = int(sqlite_diagnostics()["connections"])
    assert after > before, "auth path did not increment diagnostics connection counter"


# ---------------------------------------------------------------------------
# Core state path
# ---------------------------------------------------------------------------


def test_core_state_connect_increments_diagnostics(tmp_path: Path) -> None:
    """StateRepository._connect must record its connection wait in shared diagnostics."""
    path = _initialized_db(tmp_path)
    repo = StateRepository(path)
    before = _baseline()

    repo.database_schema_version()

    after = int(sqlite_diagnostics()["connections"])
    assert after > before, "core state path did not increment diagnostics connection counter"


# ---------------------------------------------------------------------------
# Operations path
# ---------------------------------------------------------------------------


def test_operations_connect_increments_diagnostics(tmp_path: Path) -> None:
    """SQLiteOperationRepository reads/writes must record connection waits in diagnostics."""
    path = _initialized_db(tmp_path)
    repo = SQLiteOperationRepository(path)
    before = _baseline()

    # get_active uses the read-path _connect; no operations exist yet so this is
    # a lightweight but real database round-trip.
    repo.get_active("test-server")

    after = int(sqlite_diagnostics()["connections"])
    assert after > before, "operations path did not increment diagnostics connection counter"


# ---------------------------------------------------------------------------
# Players path
# ---------------------------------------------------------------------------


def test_players_connect_increments_diagnostics(tmp_path: Path) -> None:
    """SQLitePlayerRepository operations must record connection waits in diagnostics."""
    path = _initialized_db(tmp_path)
    repo = SQLitePlayerRepository(path)
    before = _baseline()

    repo.player_profiles()

    after = int(sqlite_diagnostics()["connections"])
    assert after > before, "players path did not increment diagnostics connection counter"


# ---------------------------------------------------------------------------
# Telemetry path
# ---------------------------------------------------------------------------


def test_telemetry_connect_increments_diagnostics(tmp_path: Path) -> None:
    """SQLiteTelemetryRepository operations must record connection waits in diagnostics."""
    path = _initialized_db(tmp_path)
    repo = SQLiteTelemetryRepository(path)
    before = _baseline()

    repo.snapshot()

    after = int(sqlite_diagnostics()["connections"])
    assert after > before, "telemetry path did not increment diagnostics connection counter"


# ---------------------------------------------------------------------------
# Diagnostics shape
# ---------------------------------------------------------------------------


def test_diagnostics_keys_are_complete(tmp_path: Path) -> None:
    """sqlite_diagnostics must always return the four expected keys."""
    path = _initialized_db(tmp_path)
    StateRepository(path).database_schema_version()

    result = sqlite_diagnostics()
    assert set(result.keys()) == {"connections", "wait_ms_average", "wait_ms_max", "contention_failures"}


def test_diagnostics_values_are_non_negative(tmp_path: Path) -> None:
    """All diagnostic values must be zero or positive."""
    path = _initialized_db(tmp_path)
    StateRepository(path).database_schema_version()

    result = sqlite_diagnostics()
    for key, value in result.items():
        assert value >= 0, f"diagnostic {key!r} has unexpected negative value {value!r}"

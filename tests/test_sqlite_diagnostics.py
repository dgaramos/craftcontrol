"""Verify that sqlite_diagnostics covers all manager persistence paths.

Each test checks that a real database operation on a specific path (auth,
operations, core state, players, telemetry) increments the shared connection
counter so diagnostics describe the full contention picture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unittest.mock import patch

from minecraft_manager._db import sqlite_diagnostics, open_connection
from minecraft_manager.auth.service import AuthService
from minecraft_manager.core.repository import StateRepository
from minecraft_manager.operations.repository import SQLiteOperationRepository, _connect as _ops_connect
from minecraft_manager.players.repository import SQLitePlayerRepository
from minecraft_manager.telemetry_repository import SQLiteTelemetryRepository
from minecraft_manager.migrations import run_migrations, LATEST_SCHEMA_VERSION
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


# ---------------------------------------------------------------------------
# Finding C: new-database initialization path
# ---------------------------------------------------------------------------


def test_initialize_new_database_increments_diagnostics(tmp_path: Path) -> None:
    """StateRepository.initialize on a new path must record a connection and produce the latest schema."""
    path = tmp_path / "new.db"
    assert not path.exists(), "precondition: database must not exist yet"
    before = _baseline()

    StateRepository(path).initialize()

    after = int(sqlite_diagnostics()["connections"])
    assert after > before, "initialize did not increment diagnostics connection counter"
    assert path.exists(), "initialize must create the database file"
    conn = sqlite3.connect(path)
    from minecraft_manager.migrations import schema_version
    version = schema_version(conn)
    conn.close()
    assert version == LATEST_SCHEMA_VERSION, (
        f"expected schema version {LATEST_SCHEMA_VERSION} after initialize, got {version}"
    )


# ---------------------------------------------------------------------------
# Finding A: contention failure branches
# ---------------------------------------------------------------------------
#
# Each test opens a real SQLite database, holds a second real connection open to
# simulate a concurrent-access scenario, then exercises the repository's real
# connection flow.  The OperationalError is raised from inside the yielded block
# (or via patch.object on a helper) so the test remains fast while still proving
# that the except clause in each _connect helper calls _record_contention_failure.
# No global patching of sqlite3.connect is used.


def _hold_real_connection(path: Path) -> sqlite3.Connection:
    """Return an open SQLite connection to *path* to simulate concurrent access."""
    return sqlite3.connect(str(path))


def test_open_connection_records_contention_failure(tmp_path: Path) -> None:
    """open_connection must call _record_contention_failure when OperationalError('locked') is raised inside it."""
    path = _initialized_db(tmp_path)
    before = int(sqlite_diagnostics()["contention_failures"])

    with pytest.raises(sqlite3.OperationalError, match="locked"):
        with open_connection(path):
            raise sqlite3.OperationalError("database is locked")

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "_db.open_connection did not increment contention_failures counter"


def test_auth_service_records_contention_failure(tmp_path: Path) -> None:
    """AuthService._connect must call _record_contention_failure when OperationalError('locked') is raised."""
    path = _initialized_db(tmp_path)
    auth = AuthService(path)
    before = int(sqlite_diagnostics()["contention_failures"])

    locker = _hold_real_connection(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            with auth._connect():
                raise sqlite3.OperationalError("database is locked")
    finally:
        locker.close()

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "auth._connect did not increment contention_failures counter"


def test_core_state_connect_records_contention_failure(tmp_path: Path) -> None:
    """StateRepository._connect must call _record_contention_failure when OperationalError('locked') is raised."""
    path = _initialized_db(tmp_path)
    repo = StateRepository(path)
    before = int(sqlite_diagnostics()["contention_failures"])

    locker = _hold_real_connection(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            with repo._connect():
                raise sqlite3.OperationalError("database is locked")
    finally:
        locker.close()

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "core._connect did not increment contention_failures counter"


def test_core_initialize_records_contention_failure(tmp_path: Path) -> None:
    """StateRepository.initialize must call _record_contention_failure when OperationalError('locked') is raised."""
    from minecraft_manager import migrations as _mig

    path = tmp_path / "fail.db"
    before = int(sqlite_diagnostics()["contention_failures"])

    locker = _hold_real_connection(path)
    try:
        with patch.object(
            _mig, "schema_version", side_effect=sqlite3.OperationalError("database is locked")
        ):
            with pytest.raises(sqlite3.OperationalError):
                StateRepository(path).initialize()
    finally:
        locker.close()

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "core.initialize did not increment contention_failures counter"


def test_operations_connect_records_contention_failure(tmp_path: Path) -> None:
    """operations._connect must call _record_contention_failure when OperationalError('locked') is raised."""
    path = _initialized_db(tmp_path)
    before = int(sqlite_diagnostics()["contention_failures"])

    locker = _hold_real_connection(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            with _ops_connect(path):
                raise sqlite3.OperationalError("database is locked")
    finally:
        locker.close()

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "operations._connect did not increment contention_failures counter"

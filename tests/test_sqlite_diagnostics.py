"""Verify that sqlite_diagnostics covers all manager persistence paths.

Each test checks that a real database operation on a specific path (auth,
operations, core state, players, telemetry) increments the shared connection
counter so diagnostics describe the full contention picture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from unittest.mock import patch, MagicMock

from minecraft_manager._db import sqlite_diagnostics, open_connection
from minecraft_manager.auth.service import AuthService
from minecraft_manager.core.repository import StateRepository
from minecraft_manager.operations.repository import SQLiteOperationRepository
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


def _make_mock_conn_raising_after(n_pragma_calls: int) -> MagicMock:
    """Return a MagicMock connection whose execute raises OperationalError('locked')
    after *n_pragma_calls* setup calls succeed.  Setting the counter lets PRAGMA
    lines pass so the error is raised inside the try/yield block of each _connect
    helper, where the instrumented except clause lives."""
    call_count = 0

    def _execute(sql, *args, **kw):
        nonlocal call_count
        call_count += 1
        if call_count > n_pragma_calls:
            raise sqlite3.OperationalError("database is locked")
        return MagicMock()

    mock_conn = MagicMock()
    mock_conn.execute = MagicMock(side_effect=_execute)
    mock_conn.executemany = MagicMock(side_effect=sqlite3.OperationalError("database is locked"))
    # Behave as a context manager that simply enters/exits without swallowing errors
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.commit = MagicMock()
    mock_conn.rollback = MagicMock()
    mock_conn.close = MagicMock()
    mock_conn.in_transaction = False
    return mock_conn


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

    # auth._connect executes two PRAGMAs before yielding, so allow 2 setup calls.
    mock_conn = _make_mock_conn_raising_after(2)
    with patch("minecraft_manager.auth.service.sqlite3.connect", return_value=mock_conn):
        with pytest.raises(sqlite3.OperationalError):
            auth.access_list()

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "auth._connect did not increment contention_failures counter"


def test_core_state_connect_records_contention_failure(tmp_path: Path) -> None:
    """StateRepository._connect must call _record_contention_failure when OperationalError('locked') is raised."""
    path = _initialized_db(tmp_path)
    repo = StateRepository(path)
    before = int(sqlite_diagnostics()["contention_failures"])

    # core._connect executes one PRAGMA before yielding, so allow 1 setup call.
    mock_conn = _make_mock_conn_raising_after(1)
    with patch("minecraft_manager.core.repository.sqlite3.connect", return_value=mock_conn):
        with pytest.raises(sqlite3.OperationalError):
            repo.database_schema_version()

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "core._connect did not increment contention_failures counter"


def test_core_initialize_records_contention_failure(tmp_path: Path) -> None:
    """StateRepository.initialize must call _record_contention_failure when OperationalError('locked') is raised."""
    import tempfile as _tempfile
    import pathlib as _pathlib
    from minecraft_manager import migrations as _mig

    before = int(sqlite_diagnostics()["contention_failures"])

    with _tempfile.TemporaryDirectory() as d:
        fail_path = _pathlib.Path(d) / "fail.db"
        mock_conn = MagicMock()
        mock_conn.close = MagicMock()
        with patch("minecraft_manager.core.repository.sqlite3.connect", return_value=mock_conn):
            with patch.object(
                _mig, "schema_version", side_effect=sqlite3.OperationalError("database is locked")
            ):
                with pytest.raises(sqlite3.OperationalError):
                    StateRepository(fail_path).initialize()

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "core.initialize did not increment contention_failures counter"


def test_operations_connect_records_contention_failure(tmp_path: Path) -> None:
    """operations._connect must call _record_contention_failure when OperationalError('locked') is raised."""
    path = _initialized_db(tmp_path)
    repo = SQLiteOperationRepository(path)
    before = int(sqlite_diagnostics()["contention_failures"])

    # operations._connect executes two PRAGMAs (busy_timeout and foreign_keys)
    # plus sets row_factory before entering the context; allow 2 setup calls.
    mock_conn = _make_mock_conn_raising_after(2)
    mock_conn.row_factory = None
    with patch("minecraft_manager.operations.repository.sqlite3.connect", return_value=mock_conn):
        with pytest.raises(sqlite3.OperationalError):
            repo.get_active("test-server")

    after = int(sqlite_diagnostics()["contention_failures"])
    assert after > before, "operations._connect did not increment contention_failures counter"

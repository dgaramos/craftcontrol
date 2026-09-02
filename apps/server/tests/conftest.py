"""Shared pytest fixtures for the craftcontrol backend test suite."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# tests-root path bootstrap (allows subpackages to import fakes / conftest)
# ---------------------------------------------------------------------------
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.append(_TESTS_DIR)

# ---------------------------------------------------------------------------
# host-agent path bootstrap (shared by test_host_agent_* modules)
# ---------------------------------------------------------------------------
_HOST_AGENT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "services", "host-agent")
)
if _HOST_AGENT_DIR not in sys.path:
    sys.path.insert(0, _HOST_AGENT_DIR)

import pytest
from flask import Flask

from controlplane.auth.http import install_auth
from controlplane.auth.service import AuthService
from controlplane.core.events import EventBroker
from controlplane.core.migrations import run_migrations
from controlplane.server.files import ServerFiles
from controlplane.players import PlayerService, SQLitePlayerRepository
from controlplane.runtime import ReconciliationService
from controlplane.core.repository import StateRepository
from controlplane.server import WorldService
from controlplane.runtime import ManagerService
from controlplane.operations.repository import SQLiteOperationRepository
from controlplane.operations.service import ServerOperationService
from controlplane.telemetry.repository import SQLiteTelemetryRepository
from controlplane.telemetry.service import TelemetryService
from fakes import FakeBedrock, FakeConsole, FakeDocker, FakeRuntime  # noqa: E402

__all__ = ["FakeBedrock", "FakeConsole", "FakeDocker", "FakeRuntime"]


def make_auth_mock(**overrides) -> MagicMock:
    auth = MagicMock(spec=AuthService)
    auth.authenticate.return_value = {"id": "1", "name": "Steve", "role": "owner", "capabilities": ["*"]}
    auth.verify_csrf.return_value = True
    auth.csrf_token.return_value = "tok"
    auth.require_capability.return_value = None
    for attr, value in overrides.items():
        setattr(auth, attr, value)
    return auth


def wire_auth(app: Flask, auth: MagicMock, *, mode: str = "local", secure_cookie: bool = True) -> None:
    app.extensions["auth_service"] = auth
    install_auth(app, auth, mode=mode, secure_cookie=secure_cookie)


def make_manager_service(
    directory: Path,
    bedrock: FakeBedrock | None = None,
    docker: FakeDocker | None = None,
    operation_service=None,
    manager_broker=None,
) -> ManagerService:
    db_path = directory / "state.db"
    repo = StateRepository(db_path)
    repo.initialize()
    files = ServerFiles(directory / ".env", directory / "server.properties")
    bedrock = bedrock or FakeBedrock()  # type: ignore[assignment]
    docker = docker or FakeDocker()  # type: ignore[assignment]
    broker = EventBroker(repo)
    player_repo = SQLitePlayerRepository(db_path)
    player_service = PlayerService(player_repo, files, bedrock, broker)  # type: ignore[arg-type]
    telemetry_service = TelemetryService(SQLiteTelemetryRepository(db_path), broker)
    world_service = WorldService(bedrock, broker)  # type: ignore[arg-type]
    reconciliation_service = ReconciliationService(
        repository=repo,
        files=files,
        bedrock=bedrock,  # type: ignore[arg-type]
        broker=broker,
        player_service=player_service,
        telemetry_service=telemetry_service,
    )
    return ManagerService(
        repo,
        files,
        bedrock,  # type: ignore[arg-type]
        docker,  # type: ignore[arg-type]
        broker=broker if manager_broker is None else manager_broker,
        player_service=player_service,
        telemetry_service=telemetry_service,
        world_service=world_service,
        reconciliation_service=reconciliation_service,
        operation_service=operation_service,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_bedrock() -> FakeBedrock:
    return FakeBedrock()


@pytest.fixture
def fake_docker() -> FakeDocker:
    return FakeDocker()


@pytest.fixture
def fake_runtime() -> FakeRuntime:
    return FakeRuntime()


@pytest.fixture
def fake_console() -> FakeConsole:
    return FakeConsole()


@pytest.fixture
def tmp_db(tmp_path: Path) -> StateRepository:
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    return repository


@pytest.fixture
def manager_service(tmp_path: Path, fake_bedrock: FakeBedrock, fake_docker: FakeDocker) -> ManagerService:
    return make_manager_service(tmp_path, fake_bedrock, fake_docker)


# ---------------------------------------------------------------------------
# Repository fixtures
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path) -> Path:
    """Create and migrate a fresh SQLite database; return its path."""
    import sqlite3
    db = tmp_path / "state.db"
    with sqlite3.connect(db) as conn:
        run_migrations(conn)
    return db


def make_operation_db(tmp_path: Path, filename: str = "state.db") -> Path:
    """Public factory: create and migrate a fresh SQLite database.

    Suitable for tests that need direct access to the database path (e.g.
    startup-orphan tests that pre-populate operations before creating the
    service).
    """
    import sqlite3
    db = tmp_path / filename
    with sqlite3.connect(db) as conn:
        run_migrations(conn)
    return db


def make_operation_service(
    tmp_path: Path,
    docker: MagicMock | None = None,
    broker: MagicMock | None = None,
    configuration: MagicMock | None = None,
    health_timeout: int = 1,
    restart_timeout: int = 180,
    thread_factory=None,
    refresh_observed_settings=None,
) -> "ServerOperationService":
    """Public factory: assemble a ServerOperationService with sensible mocks.

    This is the shared replacement for the per-file ``make_service`` helpers.
    Pass only the parameters you want to override; everything else uses safe
    defaults.
    """
    import threading as _threading
    if thread_factory is None:
        thread_factory = _threading.Thread
    if docker is None:
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.return_value = None
    if broker is None:
        broker = MagicMock()
    if configuration is None:
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "1"}
    return ServerOperationService(
        operation_repository=SQLiteOperationRepository(make_operation_db(tmp_path)),
        docker=docker,
        broker=broker,
        configuration=configuration,
        thread_factory=thread_factory,
        server_id="test-server",
        health_timeout=health_timeout,
        restart_timeout=restart_timeout,
        refresh_observed_settings=refresh_observed_settings,
    )


@pytest.fixture
def operation_repo(tmp_path: Path) -> SQLiteOperationRepository:
    """Initialized SQLiteOperationRepository backed by a temp database."""
    return SQLiteOperationRepository(_make_db(tmp_path))


@pytest.fixture
def player_repo(tmp_path: Path) -> SQLitePlayerRepository:
    """Initialized SQLitePlayerRepository backed by a temp database."""
    db = _make_db(tmp_path)
    return SQLitePlayerRepository(db)


@pytest.fixture
def telemetry_repo(tmp_path: Path) -> SQLiteTelemetryRepository:
    """Initialized SQLiteTelemetryRepository backed by a temp database."""
    db = _make_db(tmp_path)
    return SQLiteTelemetryRepository(db)


@pytest.fixture
def broker(tmp_db: StateRepository) -> EventBroker:
    """EventBroker composed over an initialized StateRepository."""
    return EventBroker(tmp_db)


# ---------------------------------------------------------------------------
# Service fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def operation_service(tmp_path: Path) -> ServerOperationService:
    """ServerOperationService assembled with sensible mocks for unit tests.

    Mirrors the local ``make_service`` helper in
    ``tests/operations/test_operations.py`` so that file can delegate to this
    fixture instead of duplicating the wiring.
    """
    docker = MagicMock()
    docker.status.return_value = {"state": "running", "online": True}
    docker.execute.return_value = None
    broker_mock = MagicMock()
    configuration = MagicMock()
    configuration.read_properties.return_value = {"max-players": "1"}
    return ServerOperationService(
        operation_repository=SQLiteOperationRepository(_make_db(tmp_path)),
        docker=docker,
        broker=broker_mock,
        configuration=configuration,
        thread_factory=__import__("threading").Thread,
        server_id="test-server",
        health_timeout=1,
        restart_timeout=180,
        refresh_observed_settings=None,
    )


def wait_for_terminal(
    service: "ServerOperationService",
    operation_id: str,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
) -> None:
    """Poll until the operation reaches a terminal state or the timeout expires."""
    import time as _time
    deadline = _time.monotonic() + timeout
    last_state = None
    while True:
        op = service.get_operation(operation_id)
        if op is not None:
            last_state = op.state
            if op.state.is_terminal:
                return
        remaining = deadline - _time.monotonic()
        if remaining <= 0:
            raise AssertionError(
                f"Operation {operation_id} timed out; last_state={last_state!r}"
            )
        _time.sleep(min(poll_interval, remaining))


@pytest.fixture
def reconciliation_service(tmp_path: Path, fake_bedrock: FakeBedrock) -> ReconciliationService:
    """ReconciliationService with injected fakes, ready for isolation tests."""
    db_path = _make_db(tmp_path)
    repo = StateRepository(db_path)
    repo.initialize()
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties")
    brk = EventBroker(repo)
    player_repo = SQLitePlayerRepository(db_path)
    player_svc = PlayerService(player_repo, files, fake_bedrock, brk)  # type: ignore[arg-type]
    telemetry_svc = TelemetryService(SQLiteTelemetryRepository(db_path), brk)
    return ReconciliationService(
        repository=repo,
        files=files,
        bedrock=fake_bedrock,  # type: ignore[arg-type]
        broker=brk,
        player_service=player_svc,
        telemetry_service=telemetry_svc,
    )

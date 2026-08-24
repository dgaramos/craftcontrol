"""Shared pytest fixtures for the craftcontrol backend test suite."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask

from minecraft_manager.auth.http import install_auth
from minecraft_manager.auth.service import AuthService
from minecraft_manager.events import EventBroker
from minecraft_manager.files import ServerFiles
from minecraft_manager.players import PlayerService, SQLitePlayerRepository
from minecraft_manager.reconciliation import ReconciliationService
from minecraft_manager.repository import StateRepository
from minecraft_manager.server import WorldService
from minecraft_manager.services import ManagerService
from minecraft_manager.telemetry_repository import SQLiteTelemetryRepository
from minecraft_manager.telemetry_service import TelemetryService
from tests.fakes import FakeBedrock, FakeConsole, FakeDocker, FakeRuntime

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

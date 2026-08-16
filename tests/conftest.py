"""Shared pytest fixtures for the craftcontrol backend test suite."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask

from minecraft_manager.auth.http import install_auth
from minecraft_manager.auth.service import AuthService
from minecraft_manager.files import ServerFiles
from minecraft_manager.repository import StateRepository
from minecraft_manager.services import ManagerService
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
) -> ManagerService:
    repo = StateRepository(directory / "state.db")
    repo.initialize()
    return ManagerService(
        repo,
        ServerFiles(directory / ".env", directory / "server.properties"),
        bedrock or FakeBedrock(),  # type: ignore[arg-type]
        docker or FakeDocker(),  # type: ignore[arg-type]
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

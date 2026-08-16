"""Shared pytest fixtures for the craftcontrol backend test suite."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from minecraft_manager.files import ServerFiles
from minecraft_manager.repository import StateRepository
from minecraft_manager.services import ManagerService
from tests.fakes import FakeBedrock, FakeConsole, FakeDocker, FakeRuntime

__all__ = ["FakeBedrock", "FakeConsole", "FakeDocker", "FakeRuntime"]


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
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    return ManagerService(
        repository,
        ServerFiles(tmp_path / ".env", tmp_path / "server.properties"),
        fake_bedrock,  # type: ignore[arg-type]
        fake_docker,  # type: ignore[arg-type]
    )

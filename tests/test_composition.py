"""Tests for the production composition root (composition.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minecraft_manager.config import Settings


def _minimal_settings(root: Path, bootstrap_operator: str = "") -> Settings:
    return Settings(
        container="bedrock",
        project=root,
        database=root / "manager.db",
        auth_cookie_secure=False,
        bootstrap_operator=bootstrap_operator,
    )


@patch("minecraft_manager.composition.EventRuntime")
@patch("minecraft_manager.composition.DockerOperations")
@patch("minecraft_manager.composition.BedrockClient")
def test_compose_manager_returns_manager_service(MockBedrock, MockDocker, MockRuntime, tmp_path: Path) -> None:
    from minecraft_manager.composition import compose_manager
    from minecraft_manager.services import ManagerService

    settings = _minimal_settings(tmp_path)
    manager = compose_manager(settings)

    assert isinstance(manager, ManagerService)


@patch("minecraft_manager.composition.EventRuntime")
@patch("minecraft_manager.composition.DockerOperations")
@patch("minecraft_manager.composition.BedrockClient")
def test_compose_manager_attaches_runtime(MockBedrock, MockDocker, MockRuntime, tmp_path: Path) -> None:
    from minecraft_manager.composition import compose_manager

    fake_runtime = MagicMock()
    MockRuntime.return_value = fake_runtime

    settings = _minimal_settings(tmp_path)
    manager = compose_manager(settings)

    MockRuntime.assert_called_once()
    assert manager.runtime is fake_runtime


@patch("minecraft_manager.composition.EventRuntime")
@patch("minecraft_manager.composition.DockerOperations")
@patch("minecraft_manager.composition.BedrockClient")
def test_compose_manager_uses_bootstrap_operator(MockBedrock, MockDocker, MockRuntime, tmp_path: Path) -> None:
    from minecraft_manager.composition import compose_manager

    settings = _minimal_settings(tmp_path, bootstrap_operator="Steve")
    manager = compose_manager(settings)

    assert manager.bootstrap_operator == "Steve"

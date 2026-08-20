"""Tests for the production composition root (composition.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minecraft_manager.config import Settings
from minecraft_manager.composition import _docker_factory, compose_manager
from minecraft_manager.services import ManagerService


def _minimal_settings(
    root: Path, bootstrap_operator: str = "", compose_project: str = "minecraft-bedrock"
) -> Settings:
    return Settings(
        container="bedrock",
        project=root,
        database=root / "manager.db",
        compose_project=compose_project,
        auth_cookie_secure=False,
        bootstrap_operator=bootstrap_operator,
    )


def _fake_deps():
    return dict(
        bedrock=MagicMock(),
        docker=MagicMock(),
        runtime=MagicMock(),
    )


def test_compose_manager_returns_manager_service(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path)
    manager = compose_manager(settings, **_fake_deps())
    assert isinstance(manager, ManagerService)


def test_compose_manager_attaches_runtime(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path)
    fake_runtime = MagicMock()
    manager = compose_manager(settings, bedrock=MagicMock(), docker=MagicMock(), runtime=fake_runtime)
    assert manager.runtime is fake_runtime


def test_compose_manager_uses_bootstrap_operator(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path, bootstrap_operator="Steve")
    manager = compose_manager(settings, **_fake_deps())
    assert manager.bootstrap_operator == "Steve"


def test_compose_manager_preserves_falsy_injected_runtime(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path)
    fake_runtime = MagicMock()
    fake_runtime.__bool__ = lambda self: False
    manager = compose_manager(settings, bedrock=MagicMock(), docker=MagicMock(), runtime=fake_runtime)
    assert manager.runtime is fake_runtime


def test_docker_factory_calls_docker_from_env() -> None:
    fake_client = MagicMock()
    with patch("docker.from_env", return_value=fake_client) as mock_from_env:
        result = _docker_factory()
    mock_from_env.assert_called_once()
    assert result is fake_client


def test_compose_manager_builds_bedrock_when_none(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path)
    fake_bedrock = MagicMock()
    with patch("minecraft_manager.composition.BedrockClient", return_value=fake_bedrock) as mock_cls:
        manager = compose_manager(settings, docker=MagicMock(), runtime=MagicMock())
    mock_cls.assert_called_once_with(settings.container, list(mock_cls.call_args[0][1]), settings.console_wait_seconds)
    assert manager.bedrock is fake_bedrock


def test_compose_manager_builds_docker_when_none(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path)
    fake_docker = MagicMock()
    with patch("minecraft_manager.composition.DockerOperations", return_value=fake_docker) as mock_cls:
        manager = compose_manager(settings, bedrock=MagicMock(), runtime=MagicMock())
    mock_cls.assert_called_once_with(
        settings.container, settings.project, compose_project=settings.compose_project
    )


def test_compose_manager_passes_custom_compose_project(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path, compose_project="family-bedrock")
    with patch("minecraft_manager.composition.DockerOperations") as mock_cls:
        compose_manager(settings, bedrock=MagicMock(), runtime=MagicMock())
    mock_cls.assert_called_once_with(
        settings.container, settings.project, compose_project="family-bedrock"
    )


def test_compose_manager_builds_runtime_when_none(tmp_path: Path) -> None:
    settings = _minimal_settings(tmp_path)
    fake_runtime = MagicMock()
    with patch("minecraft_manager.composition.EventRuntime", return_value=fake_runtime) as mock_cls:
        manager = compose_manager(settings, bedrock=MagicMock(), docker=MagicMock())
    mock_cls.assert_called_once()
    assert manager.runtime is fake_runtime

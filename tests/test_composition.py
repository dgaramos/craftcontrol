"""Tests for the production composition root (composition.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minecraft_manager.config import Settings
from minecraft_manager.composition import _docker_factory, compose_manager
from minecraft_manager.host_agent import HostAgentContainerOperations
from minecraft_manager.server.console import BedrockClient
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
    fake_docker_client = MagicMock()
    manager = compose_manager(
        settings,
        docker=MagicMock(),
        runtime=MagicMock(),
        bedrock_docker_factory=lambda: fake_docker_client,
    )
    assert isinstance(manager.bedrock, BedrockClient)
    assert manager.bedrock.container_name == settings.container
    assert manager.bedrock.console_wait_seconds == settings.console_wait_seconds


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


def _split_settings(root: Path) -> Settings:
    """Settings mimicking a split-mode deployment with HOST_AGENT_URL configured."""
    return Settings(
        container="bedrock",
        project=root,
        database=root / "manager.db",
        compose_project="minecraft-bedrock",
        auth_cookie_secure=False,
        host_agent_url="http://host-gateway:7890",
        host_agent_token_file=str(root / "token"),
    )


def test_compose_manager_split_mode_builds_host_agent_container_ops(tmp_path: Path) -> None:
    """When HOST_AGENT_URL is configured, ContainerOperations must use HostAgentContainerOperations."""
    token_file = tmp_path / "token"
    token_file.write_text("test-token")
    settings = _split_settings(tmp_path)
    fake_runtime = MagicMock()
    manager = compose_manager(settings, bedrock=MagicMock(), runtime=fake_runtime)
    assert isinstance(manager.docker, HostAgentContainerOperations)


def test_compose_manager_split_mode_still_builds_bedrock_client(tmp_path: Path) -> None:
    """In split-mode, both transports are selected: HostAgentContainerOperations for docker
    and BedrockClient (with Docker SDK) for console operations."""
    token_file = tmp_path / "token"
    token_file.write_text("test-token")
    settings = _split_settings(tmp_path)
    fake_docker_client = MagicMock()
    manager = compose_manager(
        settings,
        runtime=MagicMock(),
        bedrock_docker_factory=lambda: fake_docker_client,
    )
    assert isinstance(manager.docker, HostAgentContainerOperations)
    assert isinstance(manager.bedrock, BedrockClient)
    assert manager.bedrock.container_name == settings.container
    assert manager.bedrock.console_wait_seconds == settings.console_wait_seconds

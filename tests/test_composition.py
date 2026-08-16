"""Tests for the production composition root (composition.py)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from minecraft_manager.config import Settings
from minecraft_manager.composition import compose_manager
from minecraft_manager.services import ManagerService


def _minimal_settings(root: Path, bootstrap_operator: str = "") -> Settings:
    return Settings(
        container="bedrock",
        project=root,
        database=root / "manager.db",
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

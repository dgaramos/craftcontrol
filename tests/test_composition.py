"""Tests for the production composition root (composition.py)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from minecraft_manager.config import Settings


def _minimal_settings(directory: str, bootstrap_operator: str = "") -> Settings:
    root = Path(directory)
    return Settings(
        container="bedrock",
        project=root,
        database=root / "manager.db",
        auth_cookie_secure=False,
        bootstrap_operator=bootstrap_operator,
    )


class ComposeManagerTest(unittest.TestCase):
    @patch("minecraft_manager.composition.EventRuntime")
    @patch("minecraft_manager.composition.DockerOperations")
    @patch("minecraft_manager.composition.BedrockClient")
    def test_compose_manager_returns_manager_service(self, MockBedrock, MockDocker, MockRuntime) -> None:
        from minecraft_manager.composition import compose_manager
        from minecraft_manager.services import ManagerService

        with tempfile.TemporaryDirectory() as d:
            settings = _minimal_settings(d)
            manager = compose_manager(settings)

        self.assertIsInstance(manager, ManagerService)

    @patch("minecraft_manager.composition.EventRuntime")
    @patch("minecraft_manager.composition.DockerOperations")
    @patch("minecraft_manager.composition.BedrockClient")
    def test_compose_manager_attaches_runtime(self, MockBedrock, MockDocker, MockRuntime) -> None:
        from minecraft_manager.composition import compose_manager

        fake_runtime = MagicMock()
        MockRuntime.return_value = fake_runtime

        with tempfile.TemporaryDirectory() as d:
            settings = _minimal_settings(d)
            manager = compose_manager(settings)

        MockRuntime.assert_called_once()
        self.assertIs(manager.runtime, fake_runtime)

    @patch("minecraft_manager.composition.EventRuntime")
    @patch("minecraft_manager.composition.DockerOperations")
    @patch("minecraft_manager.composition.BedrockClient")
    def test_compose_manager_uses_bootstrap_operator(self, MockBedrock, MockDocker, MockRuntime) -> None:
        from minecraft_manager.composition import compose_manager

        with tempfile.TemporaryDirectory() as d:
            settings = _minimal_settings(d, bootstrap_operator="Steve")
            manager = compose_manager(settings)

        self.assertEqual(manager.bootstrap_operator, "Steve")


if __name__ == "__main__":
    unittest.main()

"""Tests for DockerOperations (docker_ops.py)."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from minecraft_manager.docker_ops import DockerOperations


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


class DockerOperationsStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ops = DockerOperations("bedrock", Path("/srv/project"))

    @patch("minecraft_manager.docker_ops.subprocess.run")
    def test_status_running(self, mock_run) -> None:
        mock_run.return_value = _completed(stdout="running\n")
        result = self.ops.status()
        self.assertEqual(result["state"], "running")
        self.assertTrue(result["online"])
        self.assertEqual(result["container"], "bedrock")

    @patch("minecraft_manager.docker_ops.subprocess.run")
    def test_status_exited(self, mock_run) -> None:
        mock_run.return_value = _completed(stdout="exited\n")
        result = self.ops.status()
        self.assertEqual(result["state"], "exited")
        self.assertFalse(result["online"])

    @patch("minecraft_manager.docker_ops.subprocess.run")
    def test_status_docker_error_returns_stopped(self, mock_run) -> None:
        mock_run.return_value = _completed(returncode=1, stdout="", stderr="No such container")
        result = self.ops.status()
        self.assertEqual(result["state"], "stopped")
        self.assertFalse(result["online"])


class DockerOperationsExecuteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.ops = DockerOperations("bedrock", Path("/srv/project"))

    @patch("minecraft_manager.docker_ops.subprocess.run")
    def test_start_calls_compose_up(self, mock_run) -> None:
        mock_run.return_value = _completed()
        self.ops.execute("start")
        cmd = mock_run.call_args[0][0]
        self.assertIn("compose", cmd)
        self.assertIn("up", cmd)

    @patch("minecraft_manager.docker_ops.subprocess.run")
    def test_apply_calls_force_recreate(self, mock_run) -> None:
        mock_run.return_value = _completed()
        self.ops.execute("apply")
        cmd = mock_run.call_args[0][0]
        self.assertIn("--force-recreate", cmd)

    @patch("minecraft_manager.docker_ops.subprocess.run")
    def test_stop_calls_docker_stop(self, mock_run) -> None:
        mock_run.return_value = _completed()
        self.ops.execute("stop")
        cmd = mock_run.call_args[0][0]
        self.assertIn("stop", cmd)
        self.assertIn("bedrock", cmd)

    @patch("minecraft_manager.docker_ops.subprocess.run")
    def test_restart_calls_docker_restart(self, mock_run) -> None:
        mock_run.return_value = _completed()
        self.ops.execute("restart")
        cmd = mock_run.call_args[0][0]
        self.assertIn("restart", cmd)

    @patch("minecraft_manager.docker_ops.subprocess.run")
    def test_execute_nonzero_raises_runtime_error(self, mock_run) -> None:
        mock_run.return_value = _completed(returncode=1, stderr="permission denied")
        with self.assertRaises(RuntimeError) as ctx:
            self.ops.execute("stop")
        self.assertIn("permission denied", str(ctx.exception))

    def test_unknown_action_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            self.ops.execute("unknown")


if __name__ == "__main__":
    unittest.main()

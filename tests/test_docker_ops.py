"""Tests for DockerOperations (docker_ops.py)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from minecraft_manager.docker_ops import DockerOperations


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    cp = MagicMock(spec=subprocess.CompletedProcess)
    cp.returncode = returncode
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


def _ops(result: subprocess.CompletedProcess | None = None) -> tuple[DockerOperations, MagicMock]:
    executor = MagicMock(return_value=result or _completed())
    return DockerOperations("bedrock", Path("/srv/project"), executor=executor), executor


# ---------------------------------------------------------------------------
# Status tests
# ---------------------------------------------------------------------------

def test_status_running() -> None:
    ops, _ = _ops(_completed(stdout="running\n"))
    result = ops.status()
    assert result["state"] == "running"
    assert result["online"]
    assert result["container"] == "bedrock"


def test_status_exited() -> None:
    ops, _ = _ops(_completed(stdout="exited\n"))
    result = ops.status()
    assert result["state"] == "exited"
    assert not result["online"]


def test_status_docker_error_returns_stopped() -> None:
    ops, _ = _ops(_completed(returncode=1, stdout="", stderr="No such container"))
    result = ops.status()
    assert result["state"] == "stopped"
    assert not result["online"]


# ---------------------------------------------------------------------------
# Execute tests
# ---------------------------------------------------------------------------

def test_start_calls_compose_up() -> None:
    ops, executor = _ops()
    ops.execute("start")
    executor.assert_called_once_with(
        ["docker", "compose", "--project-directory", "/srv/project", "up", "-d", "minecraft-bedrock"],
        capture_output=True, text=True, timeout=120, check=False,
    )


def test_apply_calls_force_recreate() -> None:
    ops, executor = _ops()
    ops.execute("apply")
    executor.assert_called_once_with(
        ["docker", "compose", "--project-directory", "/srv/project", "up", "-d", "--force-recreate", "minecraft-bedrock"],
        capture_output=True, text=True, timeout=120, check=False,
    )


def test_stop_calls_docker_stop() -> None:
    ops, executor = _ops()
    ops.execute("stop")
    executor.assert_called_once_with(
        ["docker", "stop", "bedrock"],
        capture_output=True, text=True, timeout=120, check=False,
    )


def test_restart_calls_docker_restart() -> None:
    ops, executor = _ops()
    ops.execute("restart")
    executor.assert_called_once_with(
        ["docker", "restart", "bedrock"],
        capture_output=True, text=True, timeout=120, check=False,
    )


def test_execute_nonzero_raises_runtime_error() -> None:
    ops, _ = _ops(_completed(returncode=1, stderr="permission denied"))
    with pytest.raises(RuntimeError) as exc_info:
        ops.execute("stop")
    assert "permission denied" in str(exc_info.value)


def test_unknown_action_raises_key_error() -> None:
    ops, _ = _ops()
    with pytest.raises(KeyError):
        ops.execute("unknown")

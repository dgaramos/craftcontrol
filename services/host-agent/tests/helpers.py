"""Shared helpers for host-agent tests."""
from __future__ import annotations

import tempfile
from typing import Any
import uuid
from unittest.mock import MagicMock

from host_agent.adapters.docker import DockerComposeRunner
from host_agent.adapters.filesystem import BedrockFileSystem
from host_agent.runtime.operations import OperationExecutor


def fake_run(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    return MagicMock(return_value=MagicMock(returncode=returncode, stdout=stdout, stderr=stderr))


def operation_id() -> str:
    """Return a unique operation identifier for a test request or record."""
    return str(uuid.uuid4())


def execute_request(
    intended_state: dict[str, Any] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Build a valid Host Agent execute request with optional overrides."""
    request = {"operation_id": operation_id(), "intended_state": intended_state or {}}
    request.update(overrides)
    return request


def agent_config(**overrides: Any) -> dict[str, Any]:
    """Build the minimal Host Agent runtime configuration used by adapters."""
    config = {
        "compose_project": "mc",
        "compose_file": "/tmp/docker-compose.yml",
        "bedrock_data": tempfile.mkdtemp(),
    }
    config.update(overrides)
    return config


class FakeProbe:
    """Fake HealthProbe that returns a fixed result without opening sockets."""

    def __init__(self, result: bool = True) -> None:
        self._result = result

    def wait(self, host: str, port: int, timeout_seconds: int) -> bool:
        return self._result


def make_executor(
    subprocess_run: Any = None,
    probe_result: bool = True,
    bedrock_data: str | None = None,
) -> OperationExecutor:
    """Build an OperationExecutor with injected fakes.

    When *bedrock_data* is ``None`` a fresh temporary directory is created for
    each call so tests never share filesystem state.
    """
    if bedrock_data is None:
        bedrock_data = tempfile.mkdtemp()
    config = agent_config(bedrock_data=bedrock_data)
    runner = DockerComposeRunner(config, subprocess_run=subprocess_run)
    fs = BedrockFileSystem(bedrock_data)
    probe = FakeProbe(probe_result)
    return OperationExecutor(runner, fs, probe)

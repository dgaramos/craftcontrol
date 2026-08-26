"""Shared helpers for host-agent tests."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(_AGENT_DIR) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(_AGENT_DIR))

from adapters.docker import DockerComposeRunner
from adapters.filesystem import BedrockFileSystem
from operations import OperationExecutor


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
    config = {
        "compose_project": "mc",
        "compose_file": "/tmp/docker-compose.yml",
        "bedrock_data": bedrock_data,
    }
    runner = DockerComposeRunner(config, subprocess_run=subprocess_run)
    fs = BedrockFileSystem(bedrock_data)
    probe = FakeProbe(probe_result)
    return OperationExecutor(runner, fs, probe)



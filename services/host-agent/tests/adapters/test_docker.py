"""Tests for Docker adapters."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from host_agent.adapters.docker import DockerComposeRunner, DockerContainerStatus
from helpers import agent_config, fake_run
from host_agent.ports import RestartTimeoutError


class TestDockerComposeRunner:
    _CONFIG = agent_config(compose_file="/tmp/dc.yml", bedrock_data="/tmp/bd")

    def test_restart_runs_configured_service_and_returns_reference(self) -> None:
        run = fake_run()
        reference = DockerComposeRunner({**self._CONFIG, "compose_service": "bedrock"}, subprocess_run=run).restart(60)
        assert run.call_args.args[0][-1] == "bedrock"
        assert "bedrock_restart_" in reference

    def test_restart_error_is_exposed(self) -> None:
        with pytest.raises(RuntimeError, match="compose error"):
            DockerComposeRunner(self._CONFIG, subprocess_run=fake_run(returncode=1, stderr="compose error")).restart(60)

    def test_restart_timeout_uses_domain_error(self) -> None:
        run = MagicMock(side_effect=subprocess.TimeoutExpired(["docker"], 60))
        with pytest.raises(RestartTimeoutError):
            DockerComposeRunner(self._CONFIG, subprocess_run=run).restart(60)


class TestDockerContainerStatus:
    @pytest.mark.parametrize(("result", "expected"), [("true\n", True), ("false\n", False)])
    def test_reads_container_running_state(self, result: str, expected: bool) -> None:
        assert DockerContainerStatus(subprocess_run=fake_run(stdout=result)).is_running("bedrock") is expected

    def test_failures_are_not_reported_as_running(self) -> None:
        run = MagicMock(side_effect=OSError("docker unavailable"))
        assert DockerContainerStatus(subprocess_run=run).is_running("bedrock") is False

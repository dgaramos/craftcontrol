"""Tests for Docker adapters."""
from __future__ import annotations

import subprocess
from unittest.mock import MagicMock

import pytest

from src.adapters.docker import DockerComposeRunner, DockerContainerLogs, DockerContainerStatus
from helpers import agent_config, fake_run
from src.ports import RestartTimeoutError


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


class TestDockerContainerLogs:
    def test_started_at_reads_the_current_boot_timestamp(self) -> None:
        run = fake_run(stdout="2026-09-17T17:29:10.123456789Z\n")
        assert DockerContainerLogs(subprocess_run=run).started_at("bedrock") == "2026-09-17T17:29:10.123456789Z"
        assert run.call_args.args[0][:2] == ["docker", "inspect"]
        assert "bedrock" in run.call_args.args[0]

    def test_started_at_is_none_when_inspect_fails(self) -> None:
        assert DockerContainerLogs(subprocess_run=fake_run(returncode=1, stderr="no such container")).started_at("bedrock") is None
        run = MagicMock(side_effect=subprocess.TimeoutExpired(["docker"], 10))
        assert DockerContainerLogs(subprocess_run=run).started_at("bedrock") is None

    def test_logs_since_scopes_the_read_to_the_boot_and_merges_stderr(self) -> None:
        run = fake_run(stdout="[INFO] Starting Server\n", stderr="[INFO] Server started.\n")
        text = DockerContainerLogs(subprocess_run=run).logs_since("bedrock", "2026-09-17T17:29:10Z")
        assert "Starting Server" in text and "Server started." in text
        cmd = run.call_args.args[0]
        assert cmd[:2] == ["docker", "logs"]
        assert cmd[cmd.index("--since") + 1] == "2026-09-17T17:29:10Z"
        assert cmd[-1] == "bedrock"

    def test_docker_calls_use_their_own_limits_without_a_budget(self) -> None:
        run = fake_run(stdout="2026-09-17T17:29:10Z\n")
        logs = DockerContainerLogs(subprocess_run=run)
        logs.started_at("bedrock")
        assert run.call_args.kwargs["timeout"] == 10
        logs.logs_since("bedrock", "2026-09-17T17:29:10Z")
        assert run.call_args.kwargs["timeout"] == 30

    @pytest.mark.parametrize(("budget", "inspect_timeout", "logs_timeout"), [(4.5, 4.5, 4.5), (15, 10, 15), (60, 10, 30), (-1, 0, 0)])
    def test_docker_calls_never_exceed_the_caller_budget(self, budget: float, inspect_timeout: float, logs_timeout: float) -> None:
        run = fake_run(stdout="2026-09-17T17:29:10Z\n")
        logs = DockerContainerLogs(subprocess_run=run)
        logs.started_at("bedrock", timeout_seconds=budget)
        assert run.call_args.kwargs["timeout"] == inspect_timeout
        logs.logs_since("bedrock", "2026-09-17T17:29:10Z", timeout_seconds=budget)
        assert run.call_args.kwargs["timeout"] == logs_timeout

    def test_logs_since_raises_a_domain_error_on_failure(self) -> None:
        with pytest.raises(OSError, match="docker logs failed"):
            DockerContainerLogs(subprocess_run=fake_run(returncode=1, stderr="daemon down")).logs_since("bedrock", "2026-09-17T17:29:10Z")
        run = MagicMock(side_effect=subprocess.TimeoutExpired(["docker"], 10))
        with pytest.raises(OSError):
            DockerContainerLogs(subprocess_run=run).logs_since("bedrock", "2026-09-17T17:29:10Z")

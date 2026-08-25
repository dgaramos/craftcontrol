from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol


class DockerExecutor(Protocol):
    def __call__(self, cmd: list[str], *, capture_output: bool, text: bool, timeout: int, check: bool) -> subprocess.CompletedProcess[str]: ...


class DockerOperations:
    def __init__(
        self,
        container: str,
        project: Path,
        executor: DockerExecutor | None = None,
        *,
        compose_project: str = "minecraft-bedrock",
    ) -> None:
        self.container = container
        self.project = project
        self.compose_project = compose_project
        self._executor: DockerExecutor = executor if executor is not None else subprocess.run

    def _run(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return self._executor(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)

    def status(self) -> dict[str, object]:
        result = self._run("inspect", "-f", "{{.State.Status}}", self.container)
        state = result.stdout.strip() if result.returncode == 0 else "stopped"
        return {"container": self.container, "state": state, "online": state == "running"}

    def execute(
        self,
        action: str,
        *,
        operation_id: str | None = None,
        intended_state: dict | None = None,
        health_timeout_seconds: int = 120,
        restart_timeout_seconds: int = 60,
    ) -> None:
        if action == "start":
            result = self._run("compose", "--project-name", self.compose_project, "--project-directory", str(self.project), "up", "-d", "minecraft-bedrock", timeout=120)
        elif action == "apply":
            result = self._run("compose", "--project-name", self.compose_project, "--project-directory", str(self.project), "up", "-d", "--force-recreate", "minecraft-bedrock", timeout=120)
        elif action in {"stop", "restart"}:
            result = self._run(action, self.container, timeout=120)
        else:
            raise KeyError(action)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout).strip())

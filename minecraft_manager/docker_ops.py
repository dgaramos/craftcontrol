from __future__ import annotations

from pathlib import Path
import subprocess


class DockerOperations:
    def __init__(self, container: str, project: Path) -> None:
        self.container = container
        self.project = project

    @staticmethod
    def _run(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)

    def status(self) -> dict[str, object]:
        result = self._run("inspect", "-f", "{{.State.Status}}", self.container)
        state = result.stdout.strip() if result.returncode == 0 else "stopped"
        return {"container": self.container, "state": state, "online": state == "running"}

    def execute(self, action: str) -> None:
        if action == "start":
            result = self._run("compose", "--project-directory", str(self.project), "up", "-d", "minecraft-bedrock", timeout=120)
        elif action == "apply":
            result = self._run("compose", "--project-directory", str(self.project), "up", "-d", "--force-recreate", "minecraft-bedrock", timeout=120)
        elif action in {"stop", "restart"}:
            result = self._run(action, self.container, timeout=120)
        else:
            raise KeyError(action)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout).strip())

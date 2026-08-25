"""DockerComposeRunner — concrete ContainerRunner adapter."""
from __future__ import annotations

import logging
import subprocess
import time
from typing import Any, Callable

from ports import ContainerRunner, RestartTimeoutError

logger = logging.getLogger("host-agent")


class DockerComposeRunner:
    """ContainerRunner adapter: restarts the Bedrock container via docker compose."""

    def __init__(
        self,
        config: dict[str, str],
        subprocess_run: Callable[..., Any] | None = None,
    ) -> None:
        self._config = config
        self._subprocess_run = subprocess_run or subprocess.run

    def restart(self, timeout: int) -> str:
        """Run ``docker compose restart`` and return an executor reference string."""
        project = self._config["compose_project"]
        compose_file = self._config["compose_file"]
        cmd = [
            "docker", "compose",
            "--project-name", project,
            "--file", compose_file,
            "restart", "minecraft-server",
        ]
        logger.info("Running: %s (timeout=%ds)", " ".join(cmd), timeout)
        try:
            result = self._subprocess_run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RestartTimeoutError(str(exc)) from exc

        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"docker compose restart failed (exit {result.returncode}): {stderr}")

        ts = int(time.time())
        return f"{project}_minecraft-server_restart_{ts}"


# Satisfy the structural Protocol check at import time.
_: ContainerRunner = DockerComposeRunner.__new__(DockerComposeRunner)

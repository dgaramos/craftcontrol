"""Ports (typing.Protocol) and shared exceptions for the host-agent use-case layer.

Each protocol defines the boundary between ``operations.py`` and its concrete
adapters.  ``operations.py`` only imports from this module — it must never
import subprocess, socket, or pathlib directly.
"""
from __future__ import annotations

from typing import Protocol


class RestartTimeoutError(Exception):
    """Raised by ContainerRunner.restart() when the operation exceeds its deadline."""


class ContainerRunner(Protocol):
    """Restart the Bedrock container and return a stable executor reference."""

    def restart(self, timeout: int) -> str:
        ...


class FileSystem(Protocol):
    """Merge-write server.properties from a pre-rendered key→value map."""

    def write_server_properties(self, updates: dict[str, str]) -> None:
        ...


class HealthProbe(Protocol):
    """Poll the Bedrock server until healthy or until the deadline expires."""

    def wait(self, host: str, port: int, timeout_seconds: int) -> bool:
        ...


class ContainerStatusChecker(Protocol):
    """Check whether the Bedrock container is currently running."""

    def is_running(self, container_name: str) -> bool:  # pragma: no cover
        ...


class ContainerLogReader(Protocol):
    """Read the Bedrock container's current boot timestamp and its log output.

    ``timeout_seconds`` is the caller's remaining budget: an implementation
    must not block longer than that (it may use a shorter internal limit).
    ``None`` means the implementation's own default limit applies.
    """

    def started_at(
        self, container_name: str, *, timeout_seconds: float | None = None,
    ) -> str | None:  # pragma: no cover
        """Return the container's last start timestamp, or None when unknown."""
        ...

    def logs_since(
        self, container_name: str, since: str, *, timeout_seconds: float | None = None,
    ) -> str:  # pragma: no cover
        """Return log text emitted at or after *since*; raise OSError on failure."""
        ...

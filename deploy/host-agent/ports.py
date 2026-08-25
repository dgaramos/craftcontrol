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

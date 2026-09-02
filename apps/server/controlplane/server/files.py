from __future__ import annotations

import os
from pathlib import Path
import tempfile
import json


class ServerFiles:
    def __init__(self, env_file: Path, properties_file: Path, permissions_file: Path | None = None) -> None:
        self.env_file = env_file
        self.properties_file = properties_file
        self.permissions_file = permissions_file or properties_file.parent / "permissions.json"

    @staticmethod
    def _parse(lines: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        for line in lines:
            if line and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
        return values

    def read_env(self) -> tuple[list[str], dict[str, str]]:
        lines = self.env_file.read_text(encoding="utf-8").splitlines() if self.env_file.exists() else []
        return lines, self._parse(lines)

    def read_properties(self) -> dict[str, str]:
        if not self.properties_file.exists():
            return {}
        return self._parse(self.properties_file.read_text(encoding="utf-8").splitlines())

    def write_env(self, changes: dict[str, str]) -> None:
        lines, _ = self.read_env()
        found: set[str] = set()
        output: list[str] = []
        for line in lines:
            if line and not line.lstrip().startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                if key in changes:
                    output.append(f"{key}={changes[key]}")
                    found.add(key)
                    continue
            output.append(line)
        output.extend(f"{key}={value}" for key, value in changes.items() if key not in found)
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".env.", dir=self.env_file.parent, text=True)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write("\n".join(output).rstrip() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.env_file)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def write_properties(self, changes: dict[str, str]) -> None:
        """Atomically merge canonical Bedrock property updates.

        The Bedrock project ``.env`` is deployment-only. Server settings are
        persisted in ``server.properties`` so they are not overwritten by a
        stale Compose environment on the next boot.
        """
        lines = self.properties_file.read_text(encoding="utf-8").splitlines() if self.properties_file.exists() else []
        found: set[str] = set()
        output: list[str] = []
        for line in lines:
            if line and not line.lstrip().startswith("#") and "=" in line:
                key = line.split("=", 1)[0].strip()
                if key in changes:
                    output.append(f"{key}={changes[key]}")
                    found.add(key)
                    continue
            output.append(line)
        output.extend(f"{key}={value}" for key, value in changes.items() if key not in found)
        self.properties_file.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".server.properties.", dir=self.properties_file.parent, text=True)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write("\n".join(output).rstrip() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.properties_file)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def read_permissions(self) -> list[dict[str, str]]:
        if not self.permissions_file.exists():
            return []
        data = json.loads(self.permissions_file.read_text(encoding="utf-8"))
        return [item for item in data if isinstance(item, dict) and "xuid" in item and "permission" in item]

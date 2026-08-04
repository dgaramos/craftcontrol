from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    container: str
    project: Path
    database: Path
    console_wait_seconds: float = 1.0
    bootstrap_operator: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            container=os.getenv("MINECRAFT_CONTAINER", "minecraft-bedrock"),
            project=Path(os.getenv("MINECRAFT_PROJECT", "/minecraft-project")),
            database=Path(os.getenv("DATABASE_PATH", "/data/manager.db")),
            console_wait_seconds=float(os.getenv("CONSOLE_WAIT_SECONDS", "1")),
            bootstrap_operator=os.getenv("BOOTSTRAP_OPERATOR", ""),
        )

    @property
    def env_file(self) -> Path:
        return self.project / ".env"

    @property
    def properties_file(self) -> Path:
        return self.project / "data" / "server.properties"

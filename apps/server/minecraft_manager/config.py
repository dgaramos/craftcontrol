from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re


COMPOSE_PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
HOST_AGENT_URL_PATTERN = re.compile(r"^https?://[^\s/]+(/.*)?$")


@dataclass(frozen=True)
class Settings:
    container: str
    project: Path
    database: Path
    compose_project: str = "minecraft-bedrock"
    console_wait_seconds: float = 1.0
    bootstrap_operator: str = ""
    reconcile_seconds: int = 900
    backup_root: Path = Path("/data/backups/coordinated")
    auth_mode: str = "local"
    auth_cookie_secure: bool = True
    host_agent_url: str = ""
    host_agent_token_file: str = "/run/secrets/host_agent_token"  # noqa: S105

    @classmethod
    def from_env(cls) -> "Settings":
        compose_project = os.getenv("MINECRAFT_COMPOSE_PROJECT", "minecraft-bedrock")
        if not COMPOSE_PROJECT_NAME.fullmatch(compose_project):
            raise ValueError("MINECRAFT_COMPOSE_PROJECT must be a valid Docker Compose project name")
        host_agent_url = os.getenv("HOST_AGENT_URL", "")
        if host_agent_url and not HOST_AGENT_URL_PATTERN.fullmatch(host_agent_url):
            raise ValueError("HOST_AGENT_URL must be an http:// or https:// URL")
        return cls(
            container=os.getenv("MINECRAFT_CONTAINER", "minecraft-bedrock"),
            project=Path(os.getenv("MINECRAFT_PROJECT", "/minecraft-project")),
            compose_project=compose_project,
            database=Path(os.getenv("DATABASE_PATH", "/data/manager.db")),
            console_wait_seconds=float(os.getenv("CONSOLE_WAIT_SECONDS", "1")),
            bootstrap_operator=os.getenv("BOOTSTRAP_OPERATOR", ""),
            reconcile_seconds=int(os.getenv("RECONCILE_SECONDS", "900")),
            backup_root=Path(os.getenv("BACKUP_ROOT", "/data/backups/coordinated")),
            auth_mode=os.getenv("AUTH_MODE", "local").lower(),
            auth_cookie_secure=os.getenv("AUTH_COOKIE_SECURE", "true").lower() == "true",
            host_agent_url=host_agent_url,
            host_agent_token_file=os.getenv("HOST_AGENT_TOKEN_FILE", "/run/secrets/host_agent_token"),
        )

    @property
    def env_file(self) -> Path:
        return self.project / ".env"

    @property
    def properties_file(self) -> Path:
        return self.project / "data" / "server.properties"

    @property
    def permissions_file(self) -> Path:
        return self.project / "data" / "permissions.json"

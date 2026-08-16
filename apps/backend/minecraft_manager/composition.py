"""Production dependency composition for CraftControl."""

from __future__ import annotations

from typing import Any

from .bedrock import BedrockClient
from .config import Settings
from .docker_ops import DockerOperations
from .events import EventBroker
from .files import ServerFiles
from .repository import StateRepository
from .runtime import EventRuntime
from .schema import GAMERULES
from .services import ManagerService
from .players import PlayerService, SQLitePlayerRepository
from .telemetry_service import TelemetryService
from .telemetry_repository import SQLiteTelemetryRepository


def _docker_factory() -> object:
    import docker as docker_sdk
    return docker_sdk.from_env()


def compose_manager(
    settings: Settings,
    *,
    bedrock: Any = None,
    docker: Any = None,
    runtime: Any = None,
) -> ManagerService:
    """Build the production object graph in one explicit composition root."""
    repository = StateRepository(settings.database)
    files = ServerFiles(settings.env_file, settings.properties_file, settings.permissions_file)
    bedrock = bedrock or BedrockClient(settings.container, list(GAMERULES), settings.console_wait_seconds)
    containers = docker or DockerOperations(settings.container, settings.project)
    broker = EventBroker(repository)
    players = PlayerService(SQLitePlayerRepository(repository), files, bedrock, broker, settings.bootstrap_operator)
    telemetry = TelemetryService(SQLiteTelemetryRepository(repository), broker)
    manager = ManagerService(
        repository=repository,
        files=files,
        bedrock=bedrock,
        docker=containers,
        bootstrap_operator=settings.bootstrap_operator,
        broker=broker,
        player_service=players,
        telemetry_service=telemetry,
    )
    manager.attach_runtime(
        runtime or EventRuntime(manager, broker, settings.container, settings.reconcile_seconds, docker_factory=_docker_factory)
    )
    return manager

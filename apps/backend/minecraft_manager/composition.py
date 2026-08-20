"""Production dependency composition for CraftControl."""

from __future__ import annotations

from .bedrock import BedrockClient
from .config import Settings
from .docker_ops import DockerOperations
from .events import EventBroker
from .files import ServerFiles
from .ports import ContainerOperations, RuntimeSupervisor, ServerConsole
from .repository import StateRepository
from .runtime import EventRuntime
from .schema import GAMERULES
from .services import ManagerService
from .players import PlayerService, SQLitePlayerRepository
from .telemetry_service import TelemetryService
from .telemetry_repository import SQLiteTelemetryRepository
from .server import WorldService
from .reconciliation import ReconciliationService


def _docker_factory() -> object:
    import docker as docker_sdk
    return docker_sdk.from_env()


def compose_manager(
    settings: Settings,
    *,
    bedrock: ServerConsole | None = None,
    docker: ContainerOperations | None = None,
    runtime: RuntimeSupervisor | None = None,
) -> ManagerService:
    """Build the production object graph in one explicit composition root."""
    repository = StateRepository(settings.database)
    files = ServerFiles(settings.env_file, settings.properties_file, settings.permissions_file)
    if bedrock is None:
        bedrock = BedrockClient(settings.container, list(GAMERULES), settings.console_wait_seconds)
    if docker is None:
        docker = DockerOperations(settings.container, settings.project, compose_project=settings.compose_project)
    broker = EventBroker(repository)
    players = PlayerService(
        SQLitePlayerRepository(settings.database), files, bedrock, broker, settings.bootstrap_operator
    )
    telemetry = TelemetryService(SQLiteTelemetryRepository(settings.database), broker)
    world = WorldService(bedrock, broker)
    reconciliation = ReconciliationService(
        repository=repository,
        files=files,
        bedrock=bedrock,
        broker=broker,
        player_service=players,
        telemetry_service=telemetry,
    )
    manager = ManagerService(
        repository=repository,
        files=files,
        bedrock=bedrock,
        docker=docker,
        bootstrap_operator=settings.bootstrap_operator,
        broker=broker,
        player_service=players,
        telemetry_service=telemetry,
        world_service=world,
        reconciliation_service=reconciliation,
    )
    if runtime is None:
        runtime = EventRuntime(
            manager, broker, settings.container, settings.reconcile_seconds, docker_factory=_docker_factory
        )
    manager.attach_runtime(runtime)
    return manager

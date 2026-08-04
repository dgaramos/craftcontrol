"""Production dependency composition for CraftControl."""

from __future__ import annotations

from .bedrock import BedrockClient
from .config import Settings
from .docker_ops import DockerOperations
from .events import EventBroker
from .files import ServerFiles
from .repository import StateRepository
from .runtime import EventRuntime
from .schema import GAMERULES
from .services import ManagerService
from .players import PlayerService
from .telemetry_service import TelemetryService


def compose_manager(settings: Settings) -> ManagerService:
    """Build the production object graph in one explicit composition root."""
    repository = StateRepository(settings.database)
    files = ServerFiles(settings.env_file, settings.properties_file, settings.permissions_file)
    bedrock = BedrockClient(settings.container, list(GAMERULES), settings.console_wait_seconds)
    containers = DockerOperations(settings.container, settings.project)
    broker = EventBroker(repository)
    players = PlayerService(repository, files, bedrock, broker, settings.bootstrap_operator)
    telemetry = TelemetryService(repository, broker)
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
    manager.attach_runtime(EventRuntime(manager, broker, settings.container, settings.reconcile_seconds))
    return manager

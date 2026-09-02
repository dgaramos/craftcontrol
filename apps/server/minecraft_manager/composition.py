"""Production dependency composition for CraftControl."""

from __future__ import annotations

import threading

from .server.console import BedrockClient
from .server.docker import DockerOperations
from .server.host_agent import HostAgentContainerOperations, _UrllibClient, _load_token
from .core.config import Settings
from .core.events import EventBroker
from .server.files import ServerFiles
from .ports import ContainerOperations, RuntimeSupervisor, ServerConsole
from .core.repository import StateRepository
from .runtime import EventRuntime
from .core.schema import GAMERULES
from .runtime import ManagerService
from .players import PlayerService, SQLitePlayerRepository
from .telemetry.service import TelemetryService
from .telemetry.repository import SQLiteTelemetryRepository
from .server import WorldService
from .runtime import ReconciliationService
from .operations import ServerOperationService, SQLiteOperationRepository
from .audit import SQLiteAuditRepository, AuditService


def _docker_factory() -> object:
    import docker as docker_sdk
    return docker_sdk.from_env()


def compose_manager(
    settings: Settings,
    *,
    bedrock: ServerConsole | None = None,
    docker: ContainerOperations | None = None,
    runtime: RuntimeSupervisor | None = None,
    bedrock_docker_factory: object = None,
) -> ManagerService:
    """Build the production object graph in one explicit composition root."""
    repository = StateRepository(settings.database)
    files = ServerFiles(settings.env_file, settings.properties_file, settings.permissions_file)
    if bedrock is None:
        # BedrockClient uses the Docker SDK directly (attach socket, exec, logs)
        # for console operations and log streaming.  It requires a Docker socket
        # mount in all topologies, including split-mode with HOST_AGENT_URL set.
        # The host-agent contract covers ContainerOperations only (PREPARATION,
        # RESTART, HEALTH_WAIT); console and log-stream operations are not
        # delegated to the agent — see docs/host-agent-contract.md.
        bedrock = BedrockClient(
            settings.container,
            list(GAMERULES),
            settings.console_wait_seconds,
            docker_factory=bedrock_docker_factory,
        )
    if docker is None:
        if settings.host_agent_url:
            token = _load_token(settings.host_agent_token_file)
            docker = HostAgentContainerOperations(
                settings.host_agent_url,
                token,
                http_client=_UrllibClient(),
                server_name=settings.container,
            )
        else:
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
    operation_repo = SQLiteOperationRepository(settings.database)
    operation_service = ServerOperationService(
        operation_repository=operation_repo,
        docker=docker,
        broker=broker,
        configuration=files,
        thread_factory=threading.Thread,
        server_id=settings.container,
        refresh_observed_settings=reconciliation.refresh_settings_from_properties,
        health_timeout=settings.host_agent_health_timeout_seconds,
        restart_timeout=settings.host_agent_restart_timeout_seconds,
    )
    audit_repo = SQLiteAuditRepository(settings.database)
    audit = AuditService(audit_repo)
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
        operation_service=operation_service,
        audit_service=audit,
    )
    if runtime is None:
        runtime = EventRuntime(
            manager, broker, settings.container, settings.reconcile_seconds, docker_factory=_docker_factory
        )
    manager.attach_runtime(runtime)
    return manager

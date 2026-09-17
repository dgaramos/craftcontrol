#!/usr/bin/env python3
"""CraftControl host agent — bootstrap entry point.

Runs on the Docker host (outside all containers). Accepts authenticated
HTTP requests from the CraftControl backend and executes exactly the permitted
host-level operations defined in docs/bedrock-proxy-contract.md.

Environment variables:
  BEDROCK_PROXY_BIND          Bind address for the HTTP server. Default: 0.0.0.0:7890
  BEDROCK_PROXY_SECRET_FILE   Path to the shared-secret token file.
                           Default: /etc/craftcontrol/bedrock-proxy-token
  BEDROCK_PROXY_COMPOSE_PROJECT  Docker Compose project name. Default: minecraft-bedrock
  BEDROCK_PROXY_COMPOSE_FILE     Path to the docker-compose.yml file.
                              Default: /opt/craftcontrol/docker-compose.yml
  BEDROCK_PROXY_BEDROCK_DATA     Path to the Bedrock data directory.
                              Default: /opt/craftcontrol/data/bedrock
  BEDROCK_PROXY_COMPOSE_SERVICE   Docker Compose service name for the Bedrock server.
                               Default: minecraft-server
  BEDROCK_PROXY_BEDROCK_CONTAINER  Docker container name for the Bedrock server.
                                Default: minecraft-server
  BEDROCK_PROXY_DB            Path to the SQLite database for operation persistence.
                           Default: /var/lib/craftcontrol/bedrock-proxy.db
  BEDROCK_PROXY_WORKERS       Number of worker threads in the operation pool.
                           Default: 1 (sequential execution, no concurrent restarts).
  BEDROCK_PROXY_QUEUE_SIZE    Maximum pending operations before rejecting with 503.
                           Default: 8.

The HOST_AGENT_* forms remain accepted for one release and log a deprecation
warning. BEDROCK_PROXY_* takes precedence when both are present.
"""
from __future__ import annotations

import logging
import os
from http.server import HTTPServer
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Re-exports — keep every public name accessible as ``agent.<name>`` so that
# callers that do ``import agent as ha`` continue to work.
# ---------------------------------------------------------------------------

from src.store.store import (  # noqa: F401
    OperationRecord,
    OperationStore,
    RESULT_RETENTION_SECONDS,
)
from src.runtime.operations import (  # noqa: F401
    OperationExecutor,
    _validate_intended_state_values,
    _render_field_value,
    _ENUM_ALLOWED,
    _INT_FIELDS,
    _PORT_FIELDS,
    _BOOL_FIELDS,
    _FLOAT_FIELDS,
    _INTENDED_STATE_FIELDS,
    BEDROCK_DEFAULT_PORT,
)
from src.adapters.raknet import (  # noqa: F401
    RAKNET_MAGIC,
    PROBE_INITIAL_INTERVAL_SECONDS,
    PROBE_MAX_INTERVAL_SECONDS,
    PROBE_READ_TIMEOUT_SECONDS,
    _build_unconnected_ping,
    _validate_pong,
    _probe_bedrock,
    _wait_for_health,
)
from src.adapters.readiness import (  # noqa: F401
    SERVER_STARTED_MARKER,
    TRANSPORT_NETHERNET,
    TRANSPORT_RAKNET,
    TransportAwareHealthProbe,
    read_transport,
)
from src.http.router import AgentHandler, build_handler_class  # noqa: F401
from src.runtime.queue_worker import OperationQueue  # noqa: F401
from src.http.handler import (  # noqa: F401
    MAX_BODY_BYTES,
    VERSION,
    HEALTH_TIMEOUT_MIN,
    HEALTH_TIMEOUT_MAX,
    HEALTH_TIMEOUT_DEFAULT,
    RESTART_TIMEOUT_MIN,
    RESTART_TIMEOUT_MAX,
    RESTART_TIMEOUT_DEFAULT,
)
from src.adapters.docker import DockerContainerLogs, DockerContainerStatus  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("bedrock-proxy")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BIND_DEFAULT = "0.0.0.0:7890"
SECRET_FILE_DEFAULT = "/etc/craftcontrol/bedrock-proxy-token"
COMPOSE_PROJECT_DEFAULT = "minecraft-bedrock"
COMPOSE_FILE_DEFAULT = "/opt/craftcontrol/docker-compose.yml"
COMPOSE_SERVICE_DEFAULT = "minecraft-server"
BEDROCK_DATA_DEFAULT = "/opt/craftcontrol/data/bedrock"
BEDROCK_CONTAINER_DEFAULT = "minecraft-server"
DB_DEFAULT = "/var/lib/craftcontrol/bedrock-proxy.db"

CANONICAL_ENVIRONMENT_VARIABLES = frozenset({
    "BEDROCK_PROXY_BIND", "BEDROCK_PROXY_SECRET_FILE", "BEDROCK_PROXY_COMPOSE_PROJECT",
    "BEDROCK_PROXY_COMPOSE_FILE", "BEDROCK_PROXY_COMPOSE_SERVICE",
    "BEDROCK_PROXY_BEDROCK_DATA", "BEDROCK_PROXY_BEDROCK_CONTAINER",
    "BEDROCK_PROXY_DB", "BEDROCK_PROXY_WORKERS", "BEDROCK_PROXY_QUEUE_SIZE",
})
LEGACY_ENVIRONMENT_VARIABLES = frozenset(
    variable.replace("BEDROCK_PROXY_", "HOST_AGENT_")
    for variable in CANONICAL_ENVIRONMENT_VARIABLES
)


def _load_token(path: str) -> str:
    p = Path(path)
    try:
        token = p.read_text().strip()
    except OSError as exc:
        raise RuntimeError(f"Cannot read secret file {path}: {exc}") from exc
    if not token:
        raise RuntimeError(f"Secret file {path} is empty")
    return token


def _environment_value(name: str, default: str) -> str:
    canonical = f"BEDROCK_PROXY_{name}"
    legacy = f"HOST_AGENT_{name}"
    if canonical in os.environ:
        return os.environ[canonical]
    if legacy in os.environ:
        logger.warning("%s is deprecated; use %s", legacy, canonical)
        return os.environ[legacy]
    return default


def _load_config() -> dict[str, str]:
    return {
        "bind": _environment_value("BIND", BIND_DEFAULT),
        "secret_file": _environment_value("SECRET_FILE", SECRET_FILE_DEFAULT),
        "compose_project": _environment_value("COMPOSE_PROJECT", COMPOSE_PROJECT_DEFAULT),
        "compose_file": _environment_value("COMPOSE_FILE", COMPOSE_FILE_DEFAULT),
        "compose_service": _environment_value("COMPOSE_SERVICE", COMPOSE_SERVICE_DEFAULT) or COMPOSE_SERVICE_DEFAULT,
        "bedrock_data": _environment_value("BEDROCK_DATA", BEDROCK_DATA_DEFAULT),
        "bedrock_container": _environment_value("BEDROCK_CONTAINER", BEDROCK_CONTAINER_DEFAULT),
        "db": _environment_value("DB", DB_DEFAULT),
        "workers": _environment_value("WORKERS", "1"),
        "queue_size": _environment_value("QUEUE_SIZE", "8"),
    }


# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

def run(*, bind: str, token: str, config: dict[str, str], subprocess_run: Any = None) -> None:
    from src.adapters.docker import DockerComposeRunner, DockerContainerLogs, DockerContainerStatus
    from src.adapters.filesystem import BedrockFileSystem
    from src.adapters.readiness import TransportAwareHealthProbe

    host, _, port_str = bind.rpartition(":")
    host = host or "0.0.0.0"
    port = int(port_str)

    store = OperationStore(db_path=config.get("db"))
    runner = DockerComposeRunner(config, subprocess_run=subprocess_run)
    filesystem = BedrockFileSystem(config["bedrock_data"])
    bedrock_container = config.get("bedrock_container", BEDROCK_CONTAINER_DEFAULT)
    # Readiness follows the transport declared in server.properties: RakNet
    # ping for transport=raknet, console-log evidence for transport=nethernet.
    probe = TransportAwareHealthProbe(
        config["bedrock_data"],
        bedrock_container,
        DockerContainerLogs(subprocess_run=subprocess_run),
    )
    executor = OperationExecutor(runner, filesystem, probe)
    status_checker = DockerContainerStatus(subprocess_run=subprocess_run)

    from src.runtime.queue_worker import OperationQueue
    op_queue = OperationQueue(
        executor,
        workers=int(config.get("workers", "1")),
        queue_size=int(config.get("queue_size", "8")),
    )
    op_queue.start()

    handler_class = build_handler_class(
        token, store, executor, status_checker, bedrock_container, op_queue
    )

    server = HTTPServer((host, port), handler_class)
    logger.info("Host agent v%s listening on %s:%d", VERSION, host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")


def main() -> None:
    config = _load_config()
    token = _load_token(config["secret_file"])
    run(bind=config["bind"], token=token, config=config)


if __name__ == "__main__":
    main()

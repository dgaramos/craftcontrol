#!/usr/bin/env python3
"""CraftControl host agent — bootstrap entry point.

Runs on the Docker host (outside all containers). Accepts authenticated
HTTP requests from the CraftControl backend and executes exactly the permitted
host-level operations defined in docs/host-agent-contract.md.

Environment variables:
  HOST_AGENT_BIND          Bind address for the HTTP server. Default: 0.0.0.0:7890
  HOST_AGENT_SECRET_FILE   Path to the shared-secret token file.
                           Default: /etc/craftcontrol/host-agent-token
  HOST_AGENT_COMPOSE_PROJECT  Docker Compose project name. Default: minecraft-bedrock
  HOST_AGENT_COMPOSE_FILE     Path to the docker-compose.yml file.
                              Default: /opt/craftcontrol/docker-compose.yml
  HOST_AGENT_BEDROCK_DATA     Path to the Bedrock data directory.
                              Default: /opt/craftcontrol/data/bedrock
  HOST_AGENT_COMPOSE_SERVICE   Docker Compose service name for the Bedrock server.
                               Default: minecraft-server
  HOST_AGENT_BEDROCK_CONTAINER  Docker container name for the Bedrock server.
                                Default: minecraft-server
  HOST_AGENT_DB            Path to the SQLite database for operation persistence.
                           Default: /var/lib/craftcontrol/host-agent.db
  HOST_AGENT_WORKERS       Number of worker threads in the operation pool.
                           Default: 1 (sequential execution, no concurrent restarts).
  HOST_AGENT_QUEUE_SIZE    Maximum pending operations before rejecting with 503.
                           Default: 8.
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

from store import (  # noqa: F401
    OperationRecord,
    OperationStore,
    RESULT_RETENTION_SECONDS,
)
from operations import (  # noqa: F401
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
from adapters.raknet import (  # noqa: F401
    RAKNET_MAGIC,
    PROBE_INITIAL_INTERVAL_SECONDS,
    PROBE_MAX_INTERVAL_SECONDS,
    PROBE_READ_TIMEOUT_SECONDS,
    _build_unconnected_ping,
    _validate_pong,
    _probe_bedrock,
    _wait_for_health,
)
from router import AgentHandler, build_handler_class  # noqa: F401
from queue_worker import OperationQueue  # noqa: F401
from handler import (  # noqa: F401
    MAX_BODY_BYTES,
    VERSION,
    HEALTH_TIMEOUT_MIN,
    HEALTH_TIMEOUT_MAX,
    HEALTH_TIMEOUT_DEFAULT,
    RESTART_TIMEOUT_MIN,
    RESTART_TIMEOUT_MAX,
    RESTART_TIMEOUT_DEFAULT,
)
from adapters.docker import DockerContainerStatus  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("host-agent")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BIND_DEFAULT = "0.0.0.0:7890"
SECRET_FILE_DEFAULT = "/etc/craftcontrol/host-agent-token"
COMPOSE_PROJECT_DEFAULT = "minecraft-bedrock"
COMPOSE_FILE_DEFAULT = "/opt/craftcontrol/docker-compose.yml"
COMPOSE_SERVICE_DEFAULT = "minecraft-server"
BEDROCK_DATA_DEFAULT = "/opt/craftcontrol/data/bedrock"
BEDROCK_CONTAINER_DEFAULT = "minecraft-server"
DB_DEFAULT = "/var/lib/craftcontrol/host-agent.db"


def _load_token(path: str) -> str:
    p = Path(path)
    try:
        token = p.read_text().strip()
    except OSError as exc:
        raise RuntimeError(f"Cannot read secret file {path}: {exc}") from exc
    if not token:
        raise RuntimeError(f"Secret file {path} is empty")
    return token


def _load_config() -> dict[str, str]:
    return {
        "bind": os.environ.get("HOST_AGENT_BIND", BIND_DEFAULT),
        "secret_file": os.environ.get("HOST_AGENT_SECRET_FILE", SECRET_FILE_DEFAULT),
        "compose_project": os.environ.get("HOST_AGENT_COMPOSE_PROJECT", COMPOSE_PROJECT_DEFAULT),
        "compose_file": os.environ.get("HOST_AGENT_COMPOSE_FILE", COMPOSE_FILE_DEFAULT),
        "compose_service": os.environ.get("HOST_AGENT_COMPOSE_SERVICE") or COMPOSE_SERVICE_DEFAULT,
        "bedrock_data": os.environ.get("HOST_AGENT_BEDROCK_DATA", BEDROCK_DATA_DEFAULT),
        "bedrock_container": os.environ.get("HOST_AGENT_BEDROCK_CONTAINER", BEDROCK_CONTAINER_DEFAULT),
        "db": os.environ.get("HOST_AGENT_DB", DB_DEFAULT),
        "workers": os.environ.get("HOST_AGENT_WORKERS", "1"),
        "queue_size": os.environ.get("HOST_AGENT_QUEUE_SIZE", "8"),
    }


# ---------------------------------------------------------------------------
# Server bootstrap
# ---------------------------------------------------------------------------

def run(*, bind: str, token: str, config: dict[str, str], subprocess_run: Any = None) -> None:
    from adapters.docker import DockerComposeRunner, DockerContainerStatus
    from adapters.filesystem import BedrockFileSystem
    from adapters.raknet import RakNetHealthProbe

    host, _, port_str = bind.rpartition(":")
    host = host or "0.0.0.0"
    port = int(port_str)

    store = OperationStore(db_path=config.get("db"))
    runner = DockerComposeRunner(config, subprocess_run=subprocess_run)
    filesystem = BedrockFileSystem(config["bedrock_data"])
    probe = RakNetHealthProbe()
    executor = OperationExecutor(runner, filesystem, probe)
    status_checker = DockerContainerStatus(subprocess_run=subprocess_run)
    bedrock_container = config.get("bedrock_container", "minecraft-server")

    from queue_worker import OperationQueue
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

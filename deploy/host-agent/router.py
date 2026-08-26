"""HTTP routing and authentication composition for the host agent.

``AgentHandler`` dispatches incoming requests by method and path, enforces
Bearer token authentication via ``auth.verify_bearer_token``, and delegates
endpoint logic to ``EndpointMixin`` (from ``handler.py``).  It contains no
business logic of its own.

``build_handler_class`` is the public factory used by ``agent.py`` to inject
dependencies at server startup.
"""
from __future__ import annotations

import logging
from http.server import BaseHTTPRequestHandler
from typing import Any, Protocol, TYPE_CHECKING

from auth import verify_bearer_token
from handler import EndpointMixin
from ports import ContainerStatusChecker

if TYPE_CHECKING:
    from store import OperationRecord

logger = logging.getLogger("host-agent")


class OperationStorePort(Protocol):
    """Minimal port for the operation store used by ``AgentHandler``."""

    def evict_expired(self) -> None: ...

    def get(self, operation_id: str) -> OperationRecord | None: ...

    def create(self, operation_id: str) -> OperationRecord | None: ...


class OperationExecutorPort(Protocol):
    """Minimal port for the operation executor used by ``AgentHandler``."""

    def run(
        self,
        record: OperationRecord,
        store: OperationStorePort,
        intended_state: dict[str, Any],
        health_timeout: int,
        restart_timeout: int,
    ) -> None: ...


class AgentHandler(EndpointMixin, BaseHTTPRequestHandler):
    """HTTP request handler for the host agent.

    Routing and auth live here; per-endpoint logic lives in ``EndpointMixin``.
    """

    # Set by build_handler_class before accepting connections
    token: str = ""
    store: OperationStorePort
    executor: OperationExecutorPort
    status_checker: ContainerStatusChecker
    bedrock_container_name: str = "minecraft-server"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Strip query strings from requestline args to avoid logging sensitive params.
        sanitized = tuple(
            a.split("?")[0] if isinstance(a, str) and "?" in a else a for a in args
        )
        logger.info(format, *sanitized)

    def _require_auth(self) -> bool:
        """Return True if the request carries a valid Bearer token; send 401 and return False otherwise."""
        auth = self.headers.get("Authorization", "")
        if not verify_bearer_token(auth, self.token):
            safe_path = self.path.split("?")[0]
            logger.warning(
                "Unauthorized request from %s: %s %s",
                self.client_address,
                self.command,
                safe_path,
            )
            self._send_json(401, {"error": "unauthorized", "message": "Invalid or missing token"})
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/v1/health":
            self._handle_health()
        elif path == "/v1/bedrock/status":
            if not self._require_auth():
                return
            self._handle_bedrock_status()
        elif path.startswith("/v1/status/"):
            if not self._require_auth():
                return
            operation_id = path[len("/v1/status/"):]
            self._handle_status(operation_id)
        else:
            self._send_json(404, {"error": "not_found", "message": "Unknown path"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/v1/execute":
            if not self._require_auth():
                return
            body = self._read_json_body()
            if body is None:
                return
            self._handle_execute(body)
        else:
            self._send_json(404, {"error": "not_found", "message": "Unknown path"})


def build_handler_class(
    token: str,
    store: OperationStorePort,
    executor: OperationExecutorPort,
    status_checker: ContainerStatusChecker,
    bedrock_container_name: str = "minecraft-server",
) -> type:
    """Return an AgentHandler subclass with dependencies injected as class attributes."""

    class BoundHandler(AgentHandler):
        pass

    BoundHandler.token = token
    BoundHandler.store = store
    BoundHandler.executor = executor
    BoundHandler.status_checker = status_checker  # type: ignore[assignment]
    BoundHandler.bedrock_container_name = bedrock_container_name
    return BoundHandler

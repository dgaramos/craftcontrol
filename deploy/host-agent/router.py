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
from typing import Any

from auth import verify_bearer_token
from handler import EndpointMixin
from operations import OperationExecutor
from ports import ContainerStatusChecker
from store import OperationStore

logger = logging.getLogger("host-agent")


class AgentHandler(EndpointMixin, BaseHTTPRequestHandler):
    """HTTP request handler for the host agent.

    Routing and auth live here; per-endpoint logic lives in ``EndpointMixin``.
    """

    # Set by build_handler_class before accepting connections
    token: str = ""
    store: OperationStore
    executor: OperationExecutor
    status_checker: ContainerStatusChecker
    bedrock_container_name: str = "minecraft-server"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.info(format, *args)

    def _require_auth(self) -> bool:
        """Return True if the request carries a valid Bearer token; send 401 and return False otherwise."""
        auth = self.headers.get("Authorization", "")
        if not verify_bearer_token(auth, self.token):
            logger.warning(
                "Unauthorized request from %s: %s %s",
                self.client_address,
                self.command,
                self.path,
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
    store: OperationStore,
    executor: OperationExecutor,
    status_checker: ContainerStatusChecker,
    bedrock_container_name: str = "minecraft-server",
) -> type:
    """Return an AgentHandler subclass with dependencies injected as class attributes."""

    class BoundHandler(AgentHandler):
        pass

    BoundHandler.token = token
    BoundHandler.store = store  # type: ignore[assignment]
    BoundHandler.executor = executor  # type: ignore[assignment]
    BoundHandler.status_checker = status_checker  # type: ignore[assignment]
    BoundHandler.bedrock_container_name = bedrock_container_name
    return BoundHandler

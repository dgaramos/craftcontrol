"""AgentHandler and build_handler_class: HTTP routing and Bearer auth."""
from __future__ import annotations

import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler
from typing import Any

from operations import (
    OperationExecutor,
    _INTENDED_STATE_FIELDS,
    _validate_intended_state_values,
)
from ports import ContainerStatusChecker
from store import OperationStore

logger = logging.getLogger("host-agent")

VERSION = "0.1.0"

MAX_BODY_BYTES = 64 * 1024

HEALTH_TIMEOUT_MIN = 10
HEALTH_TIMEOUT_MAX = 600
HEALTH_TIMEOUT_DEFAULT = 120
RESTART_TIMEOUT_MIN = 10
RESTART_TIMEOUT_MAX = 300
RESTART_TIMEOUT_DEFAULT = 60


class AgentHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the host agent."""

    # Set by the server before accepting connections
    token: str = ""
    store: OperationStore
    executor: OperationExecutor
    status_checker: ContainerStatusChecker
    bedrock_container_name: str = "minecraft-server"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.info(format, *args)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authenticate(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        received = auth[len("Bearer "):]
        return hmac.compare_digest(received.encode(), self.token.encode())

    def _require_auth(self) -> bool:
        if not self._authenticate():
            logger.warning("Unauthorized request from %s: %s %s", self.client_address, self.command, self.path)
            self._send_json(401, {"error": "unauthorized", "message": "Invalid or missing token"})
            return False
        return True

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send_json(400, {"error": "bad_request", "message": "Invalid Content-Length"})
            return None
        if length < 0 or length > MAX_BODY_BYTES:
            self._send_json(400, {"error": "bad_request", "message": "Request body too large or invalid"})
            return None
        if length == 0:
            return {}
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": "bad_request", "message": f"Invalid JSON: {exc}"})
            return None
        if not isinstance(body, dict):
            self._send_json(400, {"error": "bad_request", "message": "Request body must be a JSON object"})
            return None
        return body

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

    def _handle_health(self) -> None:
        self._send_json(200, {"status": "ok", "version": VERSION})

    def _handle_bedrock_status(self) -> None:
        running = self.status_checker.is_running(self.bedrock_container_name)
        self._send_json(200, {"bedrock_running": running})

    def _handle_status(self, operation_id: str) -> None:
        # Evict expired records opportunistically
        self.store.evict_expired()

        rec = self.store.get(operation_id)
        if rec is None:
            self._send_json(404, {
                "error": "not_found",
                "operation_id": operation_id,
                "message": "Unknown operation",
            })
            return

        if rec.status == "running":
            self._send_json(200, rec.to_running_dict())
        else:
            self._send_json(200, rec.to_done_dict())

    def _handle_execute(self, body: dict[str, Any]) -> None:
        # Validate required fields
        operation_id = body.get("operation_id")
        if not operation_id or not isinstance(operation_id, str):
            self._send_json(400, {"error": "bad_request", "message": "'operation_id' is required and must be a string"})
            return

        intended_state = body.get("intended_state")
        if not isinstance(intended_state, dict):
            self._send_json(400, {"error": "bad_request", "message": "'intended_state' is required and must be an object"})
            return

        # Reject unknown fields in intended_state
        unknown = set(intended_state) - _INTENDED_STATE_FIELDS
        if unknown:
            self._send_json(400, {
                "error": "bad_request",
                "message": f"Unrecognised fields in intended_state: {', '.join(sorted(unknown))}",
            })
            return

        # Validate field values (type, domain, and injection safety)
        value_error = _validate_intended_state_values(intended_state)
        if value_error is not None:
            self._send_json(400, {"error": "bad_request", "message": value_error})
            return

        # Validate optional timeouts
        health_timeout = body.get("health_timeout_seconds", HEALTH_TIMEOUT_DEFAULT)
        restart_timeout = body.get("restart_timeout_seconds", RESTART_TIMEOUT_DEFAULT)

        if not isinstance(health_timeout, int) or not (HEALTH_TIMEOUT_MIN <= health_timeout <= HEALTH_TIMEOUT_MAX):
            self._send_json(400, {
                "error": "bad_request",
                "message": f"'health_timeout_seconds' must be an integer between {HEALTH_TIMEOUT_MIN} and {HEALTH_TIMEOUT_MAX}",
            })
            return

        if not isinstance(restart_timeout, int) or not (RESTART_TIMEOUT_MIN <= restart_timeout <= RESTART_TIMEOUT_MAX):
            self._send_json(400, {
                "error": "bad_request",
                "message": f"'restart_timeout_seconds' must be an integer between {RESTART_TIMEOUT_MIN} and {RESTART_TIMEOUT_MAX}",
            })
            return

        # Check for duplicate / replay
        existing = self.store.get(operation_id)
        if existing is not None:
            if existing.status == "running":
                self._send_json(409, {
                    "error": "conflict",
                    "operation_id": operation_id,
                    "message": "Operation already in progress",
                })
                return
            # Done — idempotent replay
            self._send_json(202, {"operation_id": operation_id, "status": "accepted"})
            return

        record = self.store.create(operation_id)
        if record is None:
            # Race: another thread created it between our get() and create()
            self._send_json(409, {
                "error": "conflict",
                "operation_id": operation_id,
                "message": "Operation already in progress",
            })
            return

        logger.info("Accepted operation %s", operation_id)

        thread = threading.Thread(
            target=self.executor.run,
            args=(record, self.store, intended_state, health_timeout, restart_timeout),
            daemon=True,
            name=f"op-{operation_id[:8]}",
        )
        thread.start()

        self._send_json(202, {"operation_id": operation_id, "status": "accepted"})


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

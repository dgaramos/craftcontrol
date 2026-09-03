"""Per-endpoint request/response handlers for the host agent.

Each method in ``EndpointMixin`` owns exactly one endpoint: JSON parsing,
field validation, delegation to ``operations.py``, and response serialisation.
Routing and authentication live in ``router.py``.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from host_agent.runtime.operations import (
    OperationExecutor,
    _INTENDED_STATE_FIELDS,
    _validate_intended_state_values,
)
from host_agent.store.store import OperationStore

logger = logging.getLogger("host-agent")

VERSION = "0.1.0"

MAX_BODY_BYTES = 64 * 1024

HEALTH_TIMEOUT_MIN = 10
HEALTH_TIMEOUT_MAX = 600
HEALTH_TIMEOUT_DEFAULT = 300
RESTART_TIMEOUT_MIN = 10
RESTART_TIMEOUT_MAX = 300
RESTART_TIMEOUT_DEFAULT = 60


class EndpointMixin:
    """Mixin that provides I/O helpers and one method per endpoint.

    Relies on ``self.wfile``, ``self.rfile``, ``self.headers``,
    ``self.send_response``, ``self.send_header``, and ``self.end_headers``
    being supplied by ``http.server.BaseHTTPRequestHandler`` (via the concrete
    class in ``router.py``).  Also relies on ``self.store``,
    ``self.executor``, ``self.status_checker``, and
    ``self.bedrock_container_name`` being injected by ``build_handler_class``.
    """

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)  # type: ignore[attr-defined]
        self.send_header("Content-Type", "application/json")  # type: ignore[attr-defined]
        self.send_header("Content-Length", str(len(data)))  # type: ignore[attr-defined]
        self.end_headers()  # type: ignore[attr-defined]
        self.wfile.write(data)  # type: ignore[attr-defined]

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", 0))  # type: ignore[attr-defined]
        except ValueError:
            self._send_json(400, {"error": "bad_request", "message": "Invalid Content-Length"})
            return None
        if length < 0 or length > MAX_BODY_BYTES:
            self._send_json(400, {"error": "bad_request", "message": "Request body too large or invalid"})
            return None
        if length == 0:
            return {}
        try:
            body = json.loads(self.rfile.read(length))  # type: ignore[attr-defined]
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": "bad_request", "message": f"Invalid JSON: {exc}"})
            return None
        if not isinstance(body, dict):
            self._send_json(400, {"error": "bad_request", "message": "Request body must be a JSON object"})
            return None
        return body

    def _handle_health(self) -> None:
        body: dict[str, Any] = {"status": "ok", "version": VERSION}
        op_queue = getattr(self, "operation_queue", None)  # type: ignore[attr-defined]
        if op_queue is not None:
            body["queue_depth"] = op_queue.queue_depth
            body["worker_count"] = op_queue.worker_count
        self._send_json(200, body)

    def _handle_bedrock_status(self) -> None:
        running = self.status_checker.is_running(self.bedrock_container_name)  # type: ignore[attr-defined]
        self._send_json(200, {"bedrock_running": running})

    def _handle_status(self, operation_id: str) -> None:
        self.store.evict_expired()  # type: ignore[attr-defined]

        rec = self.store.get(operation_id)  # type: ignore[attr-defined]
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
        operation_id = body.get("operation_id")
        if not operation_id or not isinstance(operation_id, str):
            self._send_json(400, {"error": "bad_request", "message": "'operation_id' is required and must be a string"})
            return

        intended_state = body.get("intended_state")
        if not isinstance(intended_state, dict):
            self._send_json(400, {"error": "bad_request", "message": "'intended_state' is required and must be an object"})
            return

        unknown = set(intended_state) - _INTENDED_STATE_FIELDS
        if unknown:
            self._send_json(400, {
                "error": "bad_request",
                "message": f"Unrecognised fields in intended_state: {', '.join(sorted(unknown))}",
            })
            return

        value_error = _validate_intended_state_values(intended_state)
        if value_error is not None:
            self._send_json(400, {"error": "bad_request", "message": value_error})
            return

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

        existing = self.store.get(operation_id)  # type: ignore[attr-defined]
        if existing is not None:
            if existing.status == "running":
                self._send_json(409, {
                    "error": "conflict",
                    "operation_id": operation_id,
                    "message": "Operation already in progress",
                })
                return
            self._send_json(202, {"operation_id": operation_id, "status": "accepted"})
            return

        record = self.store.create(operation_id)  # type: ignore[attr-defined]
        if record is None:
            self._send_json(409, {
                "error": "conflict",
                "operation_id": operation_id,
                "message": "Operation already in progress",
            })
            return

        logger.info("Accepted operation %s", operation_id)

        op_queue = getattr(self, "operation_queue", None)  # type: ignore[attr-defined]
        if op_queue is not None:
            accepted = op_queue.enqueue(
                record,
                self.store,  # type: ignore[attr-defined]
                intended_state,
                health_timeout,
                restart_timeout,
            )
            if not accepted:
                import time as _time
                self.store.update(  # type: ignore[attr-defined]
                    operation_id,
                    status="done",
                    outcome="error",
                    failed_stage=None,
                    detail="Operation rejected: queue at capacity",
                    error_code="queue_full",
                    completed_at=_time.time(),
                )
                self._send_json(503, {
                    "error": "queue_full",
                    "message": "Operation queue is at capacity; try again later",
                })
                return
        else:
            import threading
            thread = threading.Thread(
                target=self.executor.run,  # type: ignore[attr-defined]
                args=(record, self.store, intended_state, health_timeout, restart_timeout),  # type: ignore[attr-defined]
                daemon=True,
                name=f"op-{operation_id[:8]}",
            )
            thread.start()

        self._send_json(202, {"operation_id": operation_id, "status": "accepted"})

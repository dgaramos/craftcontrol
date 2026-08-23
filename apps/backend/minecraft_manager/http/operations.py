"""HTTP routes for server-operation lifecycle (issue #191).

Provides:
- GET  /api/operations/latest   — most-recent operation for the default server
- GET  /api/operations/active   — the current non-terminal operation, if any
- GET  /api/operations/<id>     — a specific operation by its UUID
- GET  /api/operations          — recent operation list
- GET  /api/operations/stream   — SSE stream of operation.updated lifecycle events
- POST /api/operations/<id>/reconcile — re-observe and refresh terminal outcome
"""

from __future__ import annotations

import json

from flask import Blueprint, Response, jsonify, request, stream_with_context

from .dependencies import manager
from ..auth.http import require

operations_api = Blueprint("operations_api", __name__)


def _op_service():
    return manager().operation_service


@operations_api.get("/api/operations/latest")
@require("server.configure")
def get_latest_operation():
    op = _op_service().get_latest()
    if op is None:
        return jsonify(operation=None), 200
    return jsonify(operation=op.as_dict()), 200


@operations_api.get("/api/operations/active")
@require("server.configure")
def get_active_operation():
    op = _op_service().get_active()
    if op is None:
        return jsonify(operation=None), 200
    return jsonify(operation=op.as_dict()), 200


@operations_api.get("/api/operations/<operation_id>")
@require("server.configure")
def get_operation(operation_id: str):
    op = _op_service().get_operation(operation_id)
    if op is None:
        return jsonify(error="operation not found"), 404
    return jsonify(operation=op.as_dict()), 200


@operations_api.get("/api/operations")
@require("server.configure")
def list_operations():
    ops = _op_service().list_recent()
    return jsonify(operations=[op.as_dict() for op in ops]), 200


@operations_api.get("/api/operations/stream")
@require("server.configure")
def stream_operations():
    """SSE stream of operation lifecycle changes (issue #191).

    Emits an ``operation`` event for every ``operation.updated`` broker event.
    Clients should pass the ``Last-Event-ID`` header on reconnect so no
    terminal outcome is missed.  A keepalive comment is emitted on broker
    heartbeat ticks so the connection stays alive through idle periods.
    """
    try:
        after_id = int(request.headers.get("Last-Event-ID", "0") or 0)
    except ValueError:
        after_id = 0

    @stream_with_context
    def generate():
        for event in manager().broker.stream(after_id):
            if event is None:
                yield ": keepalive\n\n"
                continue
            if event.topic != "operation.updated":
                yield f"id: {event.id}\n: skip\n\n"
                continue
            payload = json.dumps(event.payload, ensure_ascii=False)
            yield f"id: {event.id}\nevent: operation\ndata: {payload}\n\n"

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


@operations_api.post("/api/operations/<operation_id>/reconcile")
@require("server.configure")
def reconcile_operation(operation_id: str):
    """Re-observe Bedrock and refresh a terminal operation's outcome (issue #194)."""
    op = _op_service().request_reconciliation(operation_id)
    if op is None:
        return jsonify(error="operation not found"), 404
    return jsonify(operation=op.as_dict()), 200

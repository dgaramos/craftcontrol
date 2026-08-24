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
from ..operations.service import ConflictingOperationError

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
    try:
        page = int(request.args.get("page", "1"))
        limit = int(request.args.get("limit", "10"))
        if page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        result = _op_service().list_recent(page=page, limit=limit)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(
        operations=[op.as_dict() for op in result["operations"]],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
        pages=result["pages"],
    ), 200


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


@operations_api.post("/api/operations/<operation_id>/retry")
@require("server.configure")
def retry_operation(operation_id: str):
    """Create a new linked operation as a retry of a failed or divergent one (issue #194).

    The original operation is preserved unchanged.  The new operation carries
    ``parent_operation_id`` pointing to the origin so the audit trail is intact.
    """
    try:
        new_operation_id = manager().retry_settings_operation(operation_id)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except ConflictingOperationError as exc:
        return jsonify(error=str(exc)), 409
    op = _op_service().get_operation(new_operation_id)
    if op is None:
        return jsonify(error="retry operation not found after creation"), 500
    return jsonify(operation=op.as_dict()), 202

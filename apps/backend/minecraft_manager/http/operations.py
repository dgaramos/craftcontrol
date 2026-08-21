"""HTTP routes for server-operation lifecycle (issue #191).

Provides:
- GET  /api/operations/latest   — most-recent operation for the default server
- GET  /api/operations/active   — the current non-terminal operation, if any
- GET  /api/operations/<id>     — a specific operation by its UUID
- GET  /api/operations          — recent operation list
- POST /api/operations/<id>/reconcile — re-observe and refresh terminal outcome
"""

from __future__ import annotations

from flask import Blueprint, jsonify

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


@operations_api.post("/api/operations/<operation_id>/reconcile")
@require("server.configure")
def reconcile_operation(operation_id: str):
    """Re-observe Bedrock and refresh a terminal operation's outcome (issue #194)."""
    op = _op_service().request_reconciliation(operation_id)
    if op is None:
        return jsonify(error="operation not found"), 404
    return jsonify(operation=op.as_dict()), 200

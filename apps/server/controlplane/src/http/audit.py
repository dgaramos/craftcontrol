"""HTTP routes for the owner audit history panel (issue #268).

Provides:
- GET /api/audit — paginated, filtered audit records (owner-only)
"""

from __future__ import annotations

from dataclasses import asdict

from flask import Blueprint, jsonify, request

from .dependencies import manager
from ..auth.http import require

audit_api = Blueprint("audit_api", __name__)


@audit_api.get("/api/audit")
@require("audit.view")
def list_audit_records():
    """Return a paginated page of sanitized audit records.

    Query parameters
    ----------------
    page : int, default 1
        One-based page number.
    page_size : int, default 25, max 100
        Records per page.
    actor : str, optional
        Filter to records from this actor identity.
    action : str, optional
        Filter to records with this action name.
    """
    try:
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "25"))
        if page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    actor: str | None = request.args.get("actor") or None
    action: str | None = request.args.get("action") or None

    svc = manager().audit_service
    result = svc.query(page=page, page_size=page_size, actor=actor, action=action)

    records = [
        {
            "id": rec.id,
            "occurred_at": rec.occurred_at,
            "actor": rec.actor,
            "action": rec.action,
            "target": rec.target,
            "result": rec.result,
            "metadata": dict(rec.metadata),
        }
        for rec in result["records"]
    ]

    return jsonify(
        records=records,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    ), 200

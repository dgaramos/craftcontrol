"""HTTP routes for player data exports (issue #270).

Provides:
- GET /api/exports/players/<resource> — bounded JSON or CSV export (owner-only)

Authorization is checked here rather than through the shared ``require``
decorator: that decorator answers 403 before any handler runs and never reaches
the audit boundary, so an export route relying on it would leave no trace of who
tried. See ``docs/exports.md``.
"""

from __future__ import annotations

import json
import time
from typing import Any

from flask import Blueprint, Response, g, jsonify, request

from .dependencies import manager, player_exports
from ..auth.http import auth_service
from ..core.exports import (
    FORMATS,
    ExportTooLarge,
    Manifest,
    file_name,
    rfc3339,
    serialize_csv,
    serialize_json,
)
from ..players.exports import RESOURCES, UnknownExportResource

EXPORT_CAPABILITY = "data.export"
EXPORT_ACTION = "data.export"
MANIFEST_HEADER = "X-CraftControl-Export-Manifest"
# Instants are epoch numbers in JSON and RFC 3339 in CSV, because a spreadsheet
# cannot be trusted to interpret an epoch number.
CSV_INSTANTS = ("timestamp", "connected_at", "disconnected_at")

exports_api = Blueprint("exports_api", __name__)


def _actor() -> str | None:
    user = getattr(g, "user", None)
    return user.get("id") if user else None


def _audit(target: str, result: str, metadata: dict[str, Any]) -> None:
    service = manager().audit_service
    if service is not None:
        service.write(
            actor=_actor(), action=EXPORT_ACTION, target=target, result=result, metadata=metadata
        )


def _refuse(target: str, status: int, metadata: dict[str, Any], **body: Any):
    _audit(target, "failed", metadata)
    return jsonify(**body), status


@exports_api.get("/api/exports/players/<resource>")
def export_players(resource: str):
    """Export one player resource as JSON or CSV, bounded and audited.

    Every attempt writes exactly one audit record, including an unexpected
    failure: the contract promises a trace of who tried, and a handler that only
    caught the errors it predicted would silently lose the rest.
    """
    try:
        return _export_players(resource)
    except Exception:
        _audit(
            f"players.{resource}:{request.args.get('format', 'json')}",
            "failed",
            {"reason": "unexpected failure"},
        )
        raise


def _export_players(resource: str):
    export_format = request.args.get("format", "json")
    target = f"players.{resource}:{export_format}"

    # An unauthenticated request never reaches this route: the auth boundary
    # refuses it first, and it has no actor to record. Auditing it there would
    # let unauthenticated traffic write to the audit log; failed authentication
    # is already recorded in `auth_attempts`.
    user = g.user

    try:
        auth_service().require_capability(user, EXPORT_CAPABILITY)
    except PermissionError:
        return _refuse(
            target,
            403,
            {"reason": "insufficient permission"},
            error="insufficient permission",
            capability=EXPORT_CAPABILITY,
        )

    if export_format not in FORMATS:
        return _refuse(
            target, 400, {"reason": "invalid format"}, error="invalid export format"
        )
    if resource not in RESOURCES:
        return _refuse(
            target, 404, {"reason": "unknown resource"}, error="unknown export resource"
        )

    service = player_exports()
    try:
        days = int(request.args.get("days", 0))
    except ValueError:
        return _refuse(target, 400, {"reason": "invalid period"}, error="invalid export period")

    try:
        records, filters = service.records(
            resource,
            player=request.args.get("player", ""),
            days=days,
            source=request.args.get("source", "all"),
        )
    except UnknownExportResource:
        return _refuse(
            target, 404, {"reason": "unknown resource"}, error="unknown export resource"
        )
    except ValueError as error:
        return _refuse(target, 400, {"reason": str(error)}, error=str(error))
    except ExportTooLarge as error:
        return _refuse(
            target,
            422,
            {"limit": error.limit, "measured": error.measured, "allowed": error.allowed},
            error=str(error),
            limit=error.limit,
            measured=error.measured,
            allowed=error.allowed,
            hint="narrow the export with a player, period or category filter",
        )

    manifest = Manifest(
        resource=f"players.{resource}",
        format=export_format,
        filters=filters,
        row_count=len(records),
        generated_at=time.time(),
    )
    try:
        if export_format == "csv":
            body = serialize_csv(
                [_csv_record(record) for record in records], service.columns(resource)
            )
        else:
            body = serialize_json(manifest, records)
    except ExportTooLarge as error:
        return _refuse(
            target,
            422,
            {"limit": error.limit, "measured": error.measured, "allowed": error.allowed},
            error=str(error),
            limit=error.limit,
            measured=error.measured,
            allowed=error.allowed,
            hint="narrow the export with a player, period or category filter",
        )

    _audit(target, "ok", {"filters": filters, "row_count": len(records)})
    return _download(body, manifest, export_format)


def _csv_record(record: dict[str, Any]) -> dict[str, Any]:
    """Render instants as RFC 3339 for the CSV representation."""
    rendered = dict(record)
    for column in CSV_INSTANTS:
        if column in rendered:
            rendered[column] = rfc3339(rendered[column])
    return rendered


def _download(body: str, manifest: Manifest, export_format: str) -> Response:
    extension = "csv" if export_format == "csv" else "json"
    mimetype = "text/csv" if export_format == "csv" else "application/json"
    response = Response(body, mimetype=mimetype)
    # docker-compose also publishes the backend port directly, so the export
    # cannot rely on the proxy to keep an authenticated payload out of caches.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{file_name(manifest.resource, extension, manifest.generated_at)}"'
    )
    if export_format == "csv":
        response.headers[MANIFEST_HEADER] = json.dumps(
            manifest.as_dict(), ensure_ascii=False, separators=(",", ":")
        )
    return response

from __future__ import annotations

import json

from flask import Blueprint, jsonify

from .dependencies import manager, telemetry_installer
from ..auth.http import require
from ..version import STARTED_AT, VERSION

telemetry_api = Blueprint("telemetry_api", __name__)


@telemetry_api.get("/api/diagnostics")
@require("telemetry.manage")
def diagnostics():
    return jsonify(manager().diagnostics())


@telemetry_api.get("/api/telemetry-pack")
def telemetry_pack_status():
    try:
        pack = telemetry_installer().status().to_dict()
        snapshot = manager().state()
        domain = snapshot.get("domains", {}).get("telemetry", {})
        values = snapshot.get("telemetry", {})
        pack["health"] = values.get("status", "waiting")
        pack["last_topic"] = values.get("last_topic")
        pack["last_response_at"] = float(values["last_event_at"]) if values.get("last_event_at") else domain.get("observed_at")
        pack["sequence"] = values.get("sequence")
        pack["expected_sequence"] = values.get("expected_sequence")
        pack["gap_count"] = int(values.get("gap_count", 0))
        pack["missing_events"] = int(values.get("missing_events", 0))
        pack["last_gap"] = values.get("last_gap")
        pack["last_snapshot_at"] = float(values["last_snapshot_at"]) if values.get("last_snapshot_at") else None
        pack["last_error"] = values.get("last_error") or None
        pack["runtime_version"] = values.get("pack_version")
        pack["application"] = {"version": VERSION, "started_at": STARTED_AT}
        pack["storage_version"] = values.get("storage_version")
        pack["storage_status"] = values.get("storage_status")
        pack["storage_migrated_from"] = values.get("storage_migrated_from")
        pack["persistence_blocked"] = values.get("persistence_blocked") == "true"
        try:
            pack["capabilities"] = json.loads(values.get("capabilities", "{}"))
        except (TypeError, ValueError):
            pack["capabilities"] = {}
        pack["capability_status"] = values.get("capability_status")
        pack["capabilities_supported"] = int(values.get("capabilities_supported", 0))
        pack["capabilities_total"] = int(values.get("capabilities_total", 0))
        return jsonify(pack)
    except (FileNotFoundError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400


@telemetry_api.post("/api/telemetry-pack/<action>")
@require("telemetry.manage")
def telemetry_pack_action(action: str):
    try:
        installer = telemetry_installer()
        if action in {"install", "upgrade"}:
            result = installer.install()
            result["action"] = action
        elif action == "disable":
            result = installer.disable()
        elif action == "rollback":
            result = installer.rollback()
        else:
            return jsonify(error="Ação de telemetria não permitida"), 404
        return jsonify(result)
    except (FileNotFoundError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400

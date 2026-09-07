"""Handler-level tests for GET /api/exports/players/<resource> (issue #270).

TDD criteria:
  A — authorization: unauthenticated is 401; a role without `data.export` is 403
      and leaves exactly one audited refusal, since the shared `require`
      decorator would return 403 without reaching the audit boundary.
  B — payloads: JSON carries the manifest, CSV carries the header and the
      manifest header, both as downloads.
  C — filters: an unsupported format, period or resource is refused.
  D — ceilings: an oversized export answers 422 and is audited as failed.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from flask import Flask

from src.audit.service import AuditService
from src.core.exports import ExportTooLarge
from conftest import make_auth_mock, wire_auth
from fakes import FakeAuditPort


def _profile(name: str = "Steve") -> dict:
    return {
        "id": f"pub-{name}", "name": name, "online": True, "sessions_count": 1,
        "total_play_seconds": 60, "deaths_count": 0, "permission": "member",
        "operator": False, "xuid": "2535428139999999",
        "sessions": [{
            "id": 7, "connected_at": 1788806153.0, "disconnected_at": None,
            "duration_seconds": 60, "close_reason": None, "inferred": False, "active": True,
        }],
    }


class _FakePlayerService:
    def __init__(self, profiles=None, events=None) -> None:
        self._profiles = profiles if profiles is not None else [_profile()]
        self._events = events or []

    def list_profiles(self):
        return list(self._profiles)

    def profile(self, identity):
        return self._profiles[0] if self._profiles else None

    def activity(self, kind, player, source, search, days, page, page_size):
        return {"events": list(self._events), "total": len(self._events),
                "page": page, "page_size": page_size, "pages": 1}


def _app(port: FakeAuditPort, *, capabilities=("*",), players=None) -> Flask:
    from src.http.exports import exports_api

    app = Flask(__name__)
    manager = MagicMock()
    manager.audit_service = AuditService(port)
    manager.player_service = players or _FakePlayerService()
    app.extensions["manager_service"] = manager

    auth = make_auth_mock()
    auth.authenticate.return_value = {
        "id": "1", "name": "Steve", "role": "owner", "capabilities": list(capabilities),
    }

    def require_capability(user, capability):
        if "*" not in user.get("capabilities", []) and capability not in user["capabilities"]:
            raise PermissionError(capability)

    auth.require_capability.side_effect = require_capability
    wire_auth(app, auth, mode="local")
    app.register_blueprint(exports_api)
    return app


# -- criterion A — authorization --------------------------------------------

def test_unauthenticated_export_is_refused() -> None:
    port = FakeAuditPort()
    app = _app(port)
    app.extensions["auth_service"].authenticate.return_value = None
    assert app.test_client().get("/api/exports/players/profiles").status_code == 401


def test_missing_capability_is_refused_and_audited_exactly_once() -> None:
    port = FakeAuditPort()
    app = _app(port, capabilities=("server.read",))
    response = app.test_client().get("/api/exports/players/profiles")
    assert response.status_code == 403
    assert response.get_json()["capability"] == "data.export"
    assert len(port.records) == 1
    record = port.records[0]
    assert record["action"] == "data.export"
    assert record["result"] == "failed"
    assert record["target"] == "players.profiles:json"


def test_successful_export_is_audited_with_its_filters_and_row_count() -> None:
    port = FakeAuditPort()
    app = _app(port)
    response = app.test_client().get("/api/exports/players/profiles?player=Steve")
    assert response.status_code == 200
    assert len(port.records) == 1
    assert port.records[0]["result"] == "ok"
    assert port.records[0]["metadata"] == {"filters": {"player": "Steve"}, "row_count": 1}


def test_audit_metadata_never_carries_exported_rows() -> None:
    port = FakeAuditPort()
    app = _app(port)
    app.test_client().get("/api/exports/players/profiles")
    assert "pub-Steve" not in json.dumps(port.records[0]["metadata"])


# -- criterion B — payloads --------------------------------------------------

def test_json_export_carries_the_manifest_and_public_records() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/players/profiles")
    payload = response.get_json()
    assert payload["manifest"]["resource"] == "players.profiles"
    assert payload["manifest"]["format"] == "json"
    assert payload["manifest"]["row_count"] == 1
    assert payload["manifest"]["truncated"] is False
    assert payload["records"][0]["name"] == "Steve"
    assert "xuid" not in response.get_data(as_text=True)


def test_json_export_is_served_as_a_download() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/players/profiles")
    disposition = response.headers["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert "craftcontrol-players.profiles-" in disposition
    assert disposition.endswith('.json"')


def test_csv_export_carries_the_header_row_and_the_manifest_header() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/players/profiles?format=csv")
    assert response.mimetype == "text/csv"
    body = response.get_data(as_text=True)
    assert body.splitlines()[0] == (
        "id,name,online,sessions_count,total_play_seconds,deaths_count,permission,operator"
    )
    assert body.splitlines()[1].startswith("pub-Steve,Steve,true,")
    manifest = json.loads(response.headers["X-CraftControl-Export-Manifest"])
    assert manifest["format"] == "csv"
    assert manifest["timezone"]


def test_csv_export_renders_instants_as_rfc3339() -> None:
    """An epoch number in a spreadsheet is unreadable; CSV carries RFC 3339."""
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/players/sessions?player=Steve&format=csv")
    assert "2026-09-07T18:35:53Z" in response.get_data(as_text=True)


def test_json_export_keeps_epoch_instants() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/players/sessions?player=Steve")
    assert response.get_json()["records"][0]["connected_at"] == 1788806153.0


# -- criterion C — filters ---------------------------------------------------

def test_unknown_resource_answers_404() -> None:
    port = FakeAuditPort()
    app = _app(port)
    assert app.test_client().get("/api/exports/players/passwords").status_code == 404
    assert port.records[0]["result"] == "failed"


def test_unsupported_format_answers_400() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/players/profiles?format=xlsx")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid export format"


def test_non_numeric_period_answers_400() -> None:
    app = _app(FakeAuditPort())
    assert app.test_client().get(
        "/api/exports/players/activity?days=soon"
    ).status_code == 400


def test_unsupported_period_answers_400() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/players/activity?days=1")
    assert response.status_code == 400
    assert "period" in response.get_json()["error"]


def test_sessions_without_a_player_answers_400() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/players/sessions")
    assert response.status_code == 400
    assert "player filter" in response.get_json()["error"]


# -- criterion D — ceilings --------------------------------------------------

def test_oversized_export_answers_422_and_is_audited(monkeypatch) -> None:
    port = FakeAuditPort()
    app = _app(port)

    def refuse(*args, **kwargs):
        raise ExportTooLarge("record", 20_000, 10_000)

    monkeypatch.setattr("src.players.exports.enforce_row_limit", refuse)
    response = app.test_client().get("/api/exports/players/profiles")
    assert response.status_code == 422
    payload = response.get_json()
    assert payload["limit"] == "record"
    assert payload["measured"] == 20_000
    assert payload["allowed"] == 10_000
    assert "narrow" in payload["hint"]
    assert port.records[0]["result"] == "failed"
    assert port.records[0]["metadata"]["limit"] == "record"


def test_refusal_returns_no_payload_at_all(monkeypatch) -> None:
    """A refused export is never a partial file."""
    app = _app(FakeAuditPort())

    def refuse(*args, **kwargs):
        raise ExportTooLarge("byte", 6_000_000, 5_242_880)

    monkeypatch.setattr("src.http.exports.serialize_json", refuse)
    response = app.test_client().get("/api/exports/players/profiles")
    assert response.status_code == 422
    assert "records" not in response.get_json()

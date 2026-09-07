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

    def profile_count(self):
        return len(self._profiles)

    def profile(self, identity):
        return self._profiles[0] if self._profiles else None

    def activity(self, kind, player, source, search, days, page, page_size):
        return {"events": list(self._events), "total": len(self._events),
                "page": page, "page_size": page_size, "pages": 1}

    def rankings(self, limit):
        return {"metrics": {"play_time": [
            {"player": {"id": "pub-Steve", "name": "Steve"}, "value": 30, "source": "manager"}
        ]}}

    def periods(self, days, limit):
        return {"totals": {"sessions": 2}, "rankings": {}, "timezone": "America/Sao_Paulo",
                "calendar": [{"day": "2026-09-07", "play_seconds": 90.0}], "heatmap": []}

    def blocks(self, limit):
        return {"totals": {"broken": 1}, "rankings": {}}

    def combat(self, limit):
        return {"totals": {"deaths": 1}, "rankings": {}}

    def exploration(self, limit):
        return {"totals": {"distance": 1.0}, "rankings": {}}


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


# -- review findings ---------------------------------------------------------

@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_csv_neutralizes_formula_prefixes_in_player_supplied_text(prefix) -> None:
    """A Gamertag is player input; a spreadsheet must read it as text."""
    players = _FakePlayerService(profiles=[_profile(f"{prefix}cmd|calc")])
    app = _app(FakeAuditPort(), players=players)
    response = app.test_client().get("/api/exports/players/profiles?format=csv")
    row = response.get_data(as_text=True).splitlines()[1]
    assert f",'{prefix}cmd|calc," in row or row.endswith(f"'{prefix}cmd|calc")
    assert f",{prefix}cmd|calc," not in row


def test_numbers_keep_their_sign_and_are_not_neutralized() -> None:
    """Only text is neutralized, so a negative number stays a number."""
    profile = _profile()
    profile["total_play_seconds"] = -5
    app = _app(FakeAuditPort(), players=_FakePlayerService(profiles=[profile]))
    response = app.test_client().get("/api/exports/players/profiles?format=csv")
    assert ",-5," in response.get_data(as_text=True).splitlines()[1]


def test_unauthenticated_request_never_reaches_the_export_audit() -> None:
    """The auth boundary refuses first, and there is no actor to record.

    Auditing it here would let unauthenticated traffic write to the audit log;
    failed authentication is recorded by the auth layer instead.
    """
    port = FakeAuditPort()
    app = _app(port)
    app.extensions["auth_service"].authenticate.return_value = None
    response = app.test_client().get("/api/exports/players/profiles")
    assert response.status_code == 401
    assert port.records == []


def test_unexpected_failure_is_audited_once_and_not_swallowed(monkeypatch) -> None:
    port = FakeAuditPort()
    app = _app(port)

    def explode(*args, **kwargs):
        raise RuntimeError("repository unavailable")

    monkeypatch.setattr(_FakePlayerService, "list_profiles", explode)
    response = app.test_client().get("/api/exports/players/profiles")
    assert response.status_code == 500
    assert len(port.records) == 1
    assert port.records[0]["result"] == "failed"
    assert port.records[0]["metadata"]["reason"] == "unexpected failure"


def test_download_is_never_cached() -> None:
    """The backend port is published directly, so it cannot rely on the proxy."""
    app = _app(FakeAuditPort())
    for query in ("", "?format=csv"):
        response = app.test_client().get(f"/api/exports/players/profiles{query}")
        assert response.headers["Cache-Control"] == "no-store"


# -- analytics resources (issue #271) ----------------------------------------

def test_analytics_export_carries_measure_rows_and_its_manifest() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/analytics/rankings")
    payload = response.get_json()
    assert payload["manifest"]["resource"] == "analytics.rankings"
    assert payload["records"][0] == {
        "section": "rankings", "metric": "play_time", "key": "", "rank": 1,
        "player": {"id": "pub-Steve", "name": "Steve"}, "value": 30, "source": "manager",
    }


def test_analytics_csv_uses_the_same_columns_for_every_resource() -> None:
    """One column set means a spreadsheet template survives the resource switch."""
    app = _app(FakeAuditPort())
    header = "section,metric,key,rank,player.id,player.name,value,source"
    for resource in ("rankings", "periods", "blocks", "combat", "exploration"):
        response = app.test_client().get(f"/api/exports/analytics/{resource}?format=csv")
        assert response.status_code == 200
        assert response.get_data(as_text=True).splitlines()[0] == header


def test_analytics_export_is_audited_with_its_effective_filters() -> None:
    port = FakeAuditPort()
    app = _app(port)
    app.test_client().get("/api/exports/analytics/periods?days=7&limit=5")
    assert port.records[0]["result"] == "ok"
    assert port.records[0]["target"] == "analytics.periods:json"
    assert port.records[0]["metadata"]["filters"]["days"] == 7
    assert port.records[0]["metadata"]["filters"]["timezone"] == "America/Sao_Paulo"


def test_analytics_export_requires_the_capability() -> None:
    port = FakeAuditPort()
    app = _app(port, capabilities=("server.read",))
    response = app.test_client().get("/api/exports/analytics/rankings")
    assert response.status_code == 403
    assert port.records[0]["result"] == "failed"


def test_analytics_unknown_resource_answers_404() -> None:
    app = _app(FakeAuditPort())
    assert app.test_client().get("/api/exports/analytics/salaries").status_code == 404


def test_analytics_rejects_an_out_of_range_limit() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/analytics/rankings?limit=99")
    assert response.status_code == 400
    assert "limit" in response.get_json()["error"]


def test_analytics_rejects_a_non_numeric_filter() -> None:
    app = _app(FakeAuditPort())
    assert app.test_client().get(
        "/api/exports/analytics/periods?days=soon"
    ).status_code == 400


def test_analytics_download_is_never_cached() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/analytics/rankings")
    assert response.headers["Cache-Control"] == "no-store"


def test_analytics_unexpected_failure_is_audited_once(monkeypatch) -> None:
    port = FakeAuditPort()
    app = _app(port)

    def explode(*args, **kwargs):
        raise RuntimeError("repository unavailable")

    monkeypatch.setattr(_FakePlayerService, "rankings", explode)
    response = app.test_client().get("/api/exports/analytics/rankings")
    assert response.status_code == 500
    assert len(port.records) == 1
    assert port.records[0]["metadata"]["reason"] == "unexpected failure"


def test_analytics_ceiling_refusal_answers_422(monkeypatch) -> None:
    port = FakeAuditPort()
    app = _app(port)

    def refuse(*args, **kwargs):
        raise ExportTooLarge("record", 20_000, 10_000)

    monkeypatch.setattr("src.players.analytics_exports.enforce_row_limit", refuse)
    response = app.test_client().get("/api/exports/analytics/rankings")
    assert response.status_code == 422
    assert response.get_json()["limit"] == "record"
    assert port.records[0]["result"] == "failed"


def test_analytics_rejects_an_unsupported_format() -> None:
    app = _app(FakeAuditPort())
    response = app.test_client().get("/api/exports/analytics/rankings?format=xlsx")
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid export format"


def test_analytics_byte_ceiling_refuses_during_serialization(monkeypatch) -> None:
    """The byte ceiling is measured on the payload, after the rows are known."""
    port = FakeAuditPort()
    app = _app(port)

    def refuse(*args, **kwargs):
        raise ExportTooLarge("byte", 6_000_000, 5_242_880)

    monkeypatch.setattr("src.http.exports.serialize_json", refuse)
    response = app.test_client().get("/api/exports/analytics/rankings")
    assert response.status_code == 422
    assert response.get_json()["limit"] == "byte"
    assert port.records[0]["metadata"]["limit"] == "byte"

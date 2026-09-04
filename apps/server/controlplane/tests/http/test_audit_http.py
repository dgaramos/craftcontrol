"""Handler-level tests for GET /api/audit (issue #268).

TDD criteria:
  A — authorization: viewer/operator receive 401/403; owner receives 200.
  B — happy path: paginated records are returned in the expected envelope.
  C — empty state: zero records return records=[], total=0, pages=0.
  D — bad params: invalid page/page_size returns 400.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask

from src.audit.service import AuditService
from src.audit.model import AuditRecord
from conftest import make_auth_mock, wire_auth
from fakes import FakeAuditPort

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_audit_app(audit_service, *, auth_mode: str = "disabled") -> Flask:
    """Build a minimal Flask app that only mounts the audit blueprint."""
    from src.http.audit import audit_api

    app = Flask(__name__)
    manager = MagicMock()
    manager.audit_service = audit_service
    app.extensions["manager_service"] = manager
    auth = make_auth_mock()
    wire_auth(app, auth, mode=auth_mode)
    app.register_blueprint(audit_api)
    return app


def _owner_app(audit_service) -> Flask:
    return _make_audit_app(audit_service, auth_mode="local")


# ---------------------------------------------------------------------------
# Criterion A — authorization
# ---------------------------------------------------------------------------


def test_audit_requires_authentication():
    """Unauthenticated request must return 401."""
    port = FakeAuditPort()
    app = _owner_app(AuditService(port))
    auth = app.extensions["auth_service"]
    auth.authenticate.return_value = None
    resp = app.test_client().get("/api/audit")
    assert resp.status_code == 401


def test_audit_denies_viewer():
    """A viewer (no audit.view capability) must receive 403."""
    port = FakeAuditPort()
    app = _owner_app(AuditService(port))
    auth = app.extensions["auth_service"]
    auth.authenticate.return_value = {
        "id": "v1",
        "name": "Viewer",
        "role": "viewer",
        "capabilities": ["server.read"],
    }

    def _deny(user, cap):
        if "*" not in user.get("capabilities", []) and cap not in user.get("capabilities", []):
            raise PermissionError(cap)

    auth.require_capability.side_effect = _deny
    resp = app.test_client().get("/api/audit")
    assert resp.status_code == 403
    assert auth.require_capability.called
    called_cap = auth.require_capability.call_args[0][1]
    assert called_cap == "audit.view"


# ---------------------------------------------------------------------------
# Criterion B — happy path
# ---------------------------------------------------------------------------


def test_audit_returns_paginated_records():
    """Owner request returns 200 with the expected envelope keys."""
    port = FakeAuditPort()
    # Pre-populate two records
    port.records = [
        AuditRecord(id=2, occurred_at=1000.0, actor="alice", action="auth.login", target="alice", result="success", metadata={}),
        AuditRecord(id=1, occurred_at=900.0, actor="bob", action="auth.login", target="bob", result="denied", metadata={}),
    ]
    service = AuditService(port)
    app = _make_audit_app(service)
    client = app.test_client()
    resp = client.get("/api/audit")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "records" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "pages" in data
    assert data["total"] == 2
    assert len(data["records"]) == 2
    first = data["records"][0]
    assert first["id"] == 2
    assert first["actor"] == "alice"
    assert first["action"] == "auth.login"
    assert first["result"] == "success"
    assert "occurred_at" in first


def test_audit_passes_filters_to_service():
    """Query params actor and action are forwarded to the port."""
    port = FakeAuditPort()
    calls = []
    original_query = port.query

    def capturing_query(**kwargs):
        calls.append(kwargs)
        return original_query(**kwargs)

    port.query = capturing_query
    app = _make_audit_app(AuditService(port))
    app.test_client().get("/api/audit?actor=alice&action=auth.login&page=2&page_size=10")
    assert calls, "port.query was not called"
    kw = calls[0]
    assert kw["actor"] == "alice"
    assert kw["action"] == "auth.login"
    assert kw["page"] == 2
    assert kw["page_size"] == 10


# ---------------------------------------------------------------------------
# Criterion C — empty state
# ---------------------------------------------------------------------------


def test_audit_empty_state():
    """Zero records returns records=[], total=0, pages=0."""
    port = FakeAuditPort()
    port.query = lambda **kw: {"records": [], "total": 0, "page": kw["page"], "page_size": kw["page_size"], "pages": 0}
    app = _make_audit_app(AuditService(port))
    resp = app.test_client().get("/api/audit")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["records"] == []
    assert data["total"] == 0
    assert data["pages"] == 0


# ---------------------------------------------------------------------------
# Criterion D — bad params
# ---------------------------------------------------------------------------


def test_audit_bad_page_returns_400():
    """Non-integer page param returns 400."""
    port = FakeAuditPort()
    app = _make_audit_app(AuditService(port))
    resp = app.test_client().get("/api/audit?page=abc")
    assert resp.status_code == 400


def test_audit_bad_page_size_returns_400():
    """page_size=0 returns 400."""
    port = FakeAuditPort()
    app = _make_audit_app(AuditService(port))
    resp = app.test_client().get("/api/audit?page_size=0")
    assert resp.status_code == 400


def test_audit_page_size_too_large_returns_400():
    """page_size > 100 returns 400."""
    port = FakeAuditPort()
    app = _make_audit_app(AuditService(port))
    resp = app.test_client().get("/api/audit?page_size=200")
    assert resp.status_code == 400

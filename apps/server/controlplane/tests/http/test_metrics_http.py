"""Handler-level tests for GET /metrics (issue #531).

TDD criteria:
  A — open endpoint: no SCRAPE_SECRET → 200, correct Content-Type, Prometheus body.
  B — bearer auth: SCRAPE_SECRET set, correct token → 200.
  C — bearer auth: SCRAPE_SECRET set, missing Authorization → 401 + WWW-Authenticate.
  D — bearer auth: SCRAPE_SECRET set, wrong token → 401.
  E — bearer auth: SCRAPE_SECRET set, correct secret but wrong scheme → 401.
  F — edge: SCRAPE_SECRET absent, Authorization header present but ignored → 200.
  G — content: all expected metric families present with correct TYPE comments.
  H — content: no PII, XUIDs, or player names in output.
  I — content: labeled metrics per-topic and per-domain.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIAGNOSTICS_STUB = {
    "persistence": {
        "connections": 5,
        "wait_ms_average": 1.2,
        "wait_ms_max": 8.5,
        "contention_failures": 0,
        "retries": 2,
        "database_size_bytes": 102400,
    },
    "runtime": {
        "reconciliation": {
            "count": 10,
            "duration_ms_total": 500.0,
            "duration_ms_max": 75.0,
        }
    },
    "telemetry": {
        "snapshots": {
            "count": 3,
            "duration_ms_total": 120.0,
            "duration_ms_max": 50.0,
        },
        "by_topic": {
            "player.joined": {"accepted": 7, "rejected": 1},
            "player.left": {"accepted": 4, "rejected": 0},
        },
    },
    "telemetry_state": {
        "sequence": 42,
        "expected_sequence": 43,
    },
    "domains": {
        "telemetry": {"age_seconds": 12.3, "stale": False},
        "players": {"age_seconds": None, "stale": True},
    },
}


def _make_metrics_app(*, secret: str | None = None) -> Flask:
    """Build a minimal Flask app that only mounts the metrics blueprint."""
    from src.http.metrics import metrics_api, _SCRAPE_SECRET_ENV

    app = Flask(__name__)
    mgr = MagicMock()
    mgr.diagnostics.return_value = dict(_DIAGNOSTICS_STUB)
    app.extensions["manager_service"] = mgr
    app.config["TESTING"] = True
    if secret is not None:
        app.config[_SCRAPE_SECRET_ENV] = secret
    else:
        # Ensure a SCRAPE_SECRET in the process environment doesn't leak into
        # tests that expect the endpoint to be open.
        app.config.pop(_SCRAPE_SECRET_ENV, None)
    app.register_blueprint(metrics_api)
    return app


@pytest.fixture(autouse=True)
def _isolate_scrape_secret(monkeypatch):
    """Remove SCRAPE_SECRET from os.environ for every test in this module."""
    monkeypatch.delenv("SCRAPE_SECRET", raising=False)


def _get(app: Flask, headers: dict | None = None) -> object:
    return app.test_client().get("/metrics", headers=headers or {})


# ---------------------------------------------------------------------------
# Criterion A — open endpoint, no secret
# ---------------------------------------------------------------------------


def test_metrics_open_returns_200():
    """Without SCRAPE_SECRET the endpoint is open."""
    app = _make_metrics_app(secret=None)
    resp = _get(app)
    assert resp.status_code == 200


def test_metrics_open_content_type():
    """Content-Type must be text/plain; version=0.0.4."""
    app = _make_metrics_app(secret=None)
    resp = _get(app)
    assert "text/plain" in resp.content_type
    assert "version=0.0.4" in resp.content_type


# ---------------------------------------------------------------------------
# Criterion B — bearer auth, correct token
# ---------------------------------------------------------------------------


def test_metrics_bearer_correct_returns_200():
    """Correct Bearer token returns 200 when SCRAPE_SECRET is set."""
    app = _make_metrics_app(secret="s3cret")
    resp = _get(app, headers={"Authorization": "Bearer s3cret"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Criterion C — bearer auth, missing Authorization
# ---------------------------------------------------------------------------


def test_metrics_bearer_missing_returns_401():
    """Missing Authorization header returns 401 when SCRAPE_SECRET is set."""
    app = _make_metrics_app(secret="s3cret")
    resp = _get(app)
    assert resp.status_code == 401


def test_metrics_bearer_missing_www_authenticate_header():
    """401 response must include WWW-Authenticate: Bearer."""
    app = _make_metrics_app(secret="s3cret")
    resp = _get(app)
    assert "Bearer" in resp.headers.get("WWW-Authenticate", "")


# ---------------------------------------------------------------------------
# Criterion D — bearer auth, wrong token
# ---------------------------------------------------------------------------


def test_metrics_bearer_wrong_token_returns_401():
    """Wrong token returns 401."""
    app = _make_metrics_app(secret="s3cret")
    resp = _get(app, headers={"Authorization": "Bearer wrongtoken"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Criterion E — correct secret, wrong scheme
# ---------------------------------------------------------------------------


def test_metrics_bearer_wrong_scheme_returns_401():
    """Basic auth with correct secret is rejected (wrong scheme)."""
    app = _make_metrics_app(secret="s3cret")
    resp = _get(app, headers={"Authorization": "Basic s3cret"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Criterion F — SCRAPE_SECRET absent, Authorization ignored
# ---------------------------------------------------------------------------


def test_metrics_open_ignores_authorization_header():
    """When SCRAPE_SECRET is absent, any Authorization header is ignored → 200."""
    app = _make_metrics_app(secret=None)
    resp = _get(app, headers={"Authorization": "Bearer whatever"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Criterion G — content correctness: TYPE comments
# ---------------------------------------------------------------------------


def _body(app: Flask, headers: dict | None = None) -> str:
    return _get(app, headers).data.decode()


def test_metrics_contains_sqlite_connections():
    body = _body(_make_metrics_app())
    assert "# TYPE craftcontrol_sqlite_connections_total gauge" in body
    assert "craftcontrol_sqlite_connections_total 5" in body


def test_metrics_contains_sqlite_wait_avg():
    body = _body(_make_metrics_app())
    assert "# TYPE craftcontrol_sqlite_wait_ms_average gauge" in body


def test_metrics_contains_sqlite_database_size():
    body = _body(_make_metrics_app())
    assert "# TYPE craftcontrol_sqlite_database_size_bytes gauge" in body
    assert "craftcontrol_sqlite_database_size_bytes 102400" in body


def test_metrics_contains_reconciliation():
    body = _body(_make_metrics_app())
    assert "# TYPE craftcontrol_reconciliation_total counter" in body
    assert "craftcontrol_reconciliation_total 10" in body


def test_metrics_contains_snapshot():
    body = _body(_make_metrics_app())
    assert "# TYPE craftcontrol_snapshot_total counter" in body
    assert "craftcontrol_snapshot_total 3" in body


def test_metrics_contains_telemetry_sequence():
    body = _body(_make_metrics_app())
    assert "# TYPE craftcontrol_telemetry_sequence gauge" in body
    assert "craftcontrol_telemetry_sequence 42" in body


def test_metrics_contains_expected_sequence():
    body = _body(_make_metrics_app())
    assert "# TYPE craftcontrol_telemetry_expected_sequence gauge" in body
    assert "craftcontrol_telemetry_expected_sequence 43" in body


# ---------------------------------------------------------------------------
# Criterion I — labeled metrics per-topic and per-domain
# ---------------------------------------------------------------------------


def test_metrics_contains_ingestion_by_topic():
    body = _body(_make_metrics_app())
    assert 'craftcontrol_ingestion_accepted_total{topic="player.joined"} 7' in body
    assert 'craftcontrol_ingestion_rejected_total{topic="player.joined"} 1' in body
    assert 'craftcontrol_ingestion_accepted_total{topic="player.left"} 4' in body


def test_metrics_contains_domain_age():
    body = _body(_make_metrics_app())
    assert 'craftcontrol_domain_age_seconds{domain="telemetry"}' in body


def test_metrics_contains_domain_fresh():
    body = _body(_make_metrics_app())
    assert 'craftcontrol_domain_fresh{domain="telemetry"} 1' in body
    assert 'craftcontrol_domain_fresh{domain="players"} 0' in body


# ---------------------------------------------------------------------------
# Criterion H — no PII in output
# ---------------------------------------------------------------------------


def test_metrics_no_player_names_in_body():
    """Metric output must not contain player names or XUIDs."""
    body = _body(_make_metrics_app())
    # Topic labels are allowed (they are event type names, not player identifiers)
    # Ensure no raw player-identity-shaped strings appear
    assert "xuid" not in body.lower()
    assert "player_name" not in body.lower()

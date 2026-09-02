"""Tests for routes.py — blueprint registration and HTTP method bindings."""
from __future__ import annotations

import pytest
from flask import Flask

from minecraft_manager.http import api


def _collect_routes(app: Flask) -> dict[str, set[str]]:
    routes: dict[str, set[str]] = {}
    for rule in app.url_map.iter_rules():
        methods = routes.setdefault(rule.rule, set())
        methods.update(rule.methods - {"HEAD", "OPTIONS"})
    return routes


@pytest.fixture
def routes() -> dict[str, set[str]]:
    app = Flask(__name__)
    app.register_blueprint(api)
    return _collect_routes(app)


@pytest.fixture
def routes_client():
    app = Flask(__name__)
    app.register_blueprint(api)
    return app.test_client()


def test_health_endpoint_registered(routes) -> None:
    assert "/api/health" in routes


def test_health_responds_to_get(routes) -> None:
    assert "GET" in routes["/api/health"]


def test_state_endpoint_registered(routes) -> None:
    assert "/api/state" in routes


def test_events_sse_endpoint_registered(routes) -> None:
    assert "/api/events" in routes


def test_server_action_endpoint_registered(routes) -> None:
    matching = [p for p in routes if "server" in p or "action" in p]
    assert len(matching) > 0, "Expected at least one server action route"


def test_players_endpoint_registered(routes) -> None:
    matching = [p for p in routes if "player" in p]
    assert len(matching) > 0, "Expected at least one players route"


def test_analytics_endpoint_registered(routes) -> None:
    matching = [p for p in routes if "analytic" in p or "metric" in p or "history" in p]
    assert len(matching) > 0, "Expected at least one analytics route"


def test_docs_endpoint_registered(routes) -> None:
    matching = [p for p in routes if "doc" in p or "openapi" in p or "swagger" in p]
    assert len(matching) > 0, "Expected at least one docs route"


def test_all_routes_are_under_api_prefix_or_root(routes) -> None:
    for path in routes:
        assert (
            path.startswith("/api/") or path == "/" or path.startswith("/static/")
        ), f"Unexpected route outside /api/ prefix: {path}"


def test_health_returns_200(routes_client) -> None:
    response = routes_client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["ok"]

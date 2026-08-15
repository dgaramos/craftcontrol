"""Tests for routes.py — blueprint registration and HTTP method bindings."""
from __future__ import annotations

import unittest

from flask import Flask

from minecraft_manager.routes import api


def _collect_routes(app: Flask) -> dict[str, set[str]]:
    routes: dict[str, set[str]] = {}
    for rule in app.url_map.iter_rules():
        methods = routes.setdefault(rule.rule, set())
        methods.update(rule.methods - {"HEAD", "OPTIONS"})
    return routes


class RoutesRegistrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Flask(__name__)
        self.app.register_blueprint(api)
        self.routes = _collect_routes(self.app)

    def test_health_endpoint_registered(self) -> None:
        self.assertIn("/api/health", self.routes)

    def test_health_responds_to_get(self) -> None:
        self.assertIn("GET", self.routes["/api/health"])

    def test_state_endpoint_registered(self) -> None:
        self.assertIn("/api/state", self.routes)

    def test_events_sse_endpoint_registered(self) -> None:
        self.assertIn("/api/events", self.routes)

    def test_server_action_endpoint_registered(self) -> None:
        matching = [p for p in self.routes if "server" in p or "action" in p]
        self.assertTrue(len(matching) > 0, "Expected at least one server action route")

    def test_players_endpoint_registered(self) -> None:
        matching = [p for p in self.routes if "player" in p]
        self.assertTrue(len(matching) > 0, "Expected at least one players route")

    def test_analytics_endpoint_registered(self) -> None:
        matching = [p for p in self.routes if "analytic" in p or "metric" in p or "history" in p]
        self.assertTrue(len(matching) > 0, "Expected at least one analytics route")

    def test_docs_endpoint_registered(self) -> None:
        matching = [p for p in self.routes if "doc" in p or "openapi" in p or "swagger" in p]
        self.assertTrue(len(matching) > 0, "Expected at least one docs route")

    def test_all_routes_are_under_api_prefix_or_root(self) -> None:
        for path in self.routes:
            self.assertTrue(
                path.startswith("/api/") or path == "/" or path.startswith("/static/"),
                f"Unexpected route outside /api/ prefix: {path}",
            )

    def test_health_returns_200(self) -> None:
        client = self.app.test_client()
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()

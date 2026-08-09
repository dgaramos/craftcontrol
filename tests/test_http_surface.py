import json
import re
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from minecraft_manager.auth.http import auth_api
from minecraft_manager import create_app
from minecraft_manager.config import Settings
from minecraft_manager.routes import api


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps" / "frontend"
CONTRACT = ROOT / "packages" / "contracts" / "http-surface.json"


class HttpSurfaceContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(CONTRACT.read_text())
        app = Flask(__name__)
        app.register_blueprint(auth_api)
        app.register_blueprint(api)
        self.actual_routes = {}
        for rule in app.url_map.iter_rules():
            methods = self.actual_routes.setdefault(rule.rule, set())
            methods.update(rule.methods - {"HEAD", "OPTIONS"})

    def test_flask_routes_match_the_frozen_http_surface(self) -> None:
        expected = {
            route["path"]: sorted(route["methods"])
            for route in self.contract["routes"]
        }
        self.assertEqual(
            {path: sorted(methods) for path, methods in self.actual_routes.items()},
            expected,
        )

    def test_split_contract_keeps_one_origin_and_sse_under_api(self) -> None:
        self.assertEqual(self.contract["public_origin"], "frontend")
        self.assertEqual(self.contract["api_prefix"], "/api")
        self.assertEqual(self.contract["sse_path"], "/api/events")
        event_route = next(route for route in self.contract["routes"] if route["path"] == "/api/events")
        self.assertEqual(event_route["protocol"], "sse")

    def test_browser_api_calls_remain_inside_the_declared_api_boundary(self) -> None:
        sources = "\n".join(path.read_text() for path in [
            FRONTEND / "static" / "app.js",
            FRONTEND / "static" / "js" / "auth.js",
            FRONTEND / "static" / "js" / "events.js",
        ])
        calls = set(re.findall(r'["`](/api/[a-z0-9-]+(?:/[a-z0-9-]+)*)', sources))
        declared = {route["path"] for route in self.contract["routes"] if route["path"].startswith("/api/")}
        patterns = [
            re.compile("^" + re.sub(r"<(?:(?:path):)?[^>]+>", r"[^/]+(?:/[^/]+)*", path) + "$")
            for path in declared
        ]
        for call in calls:
            self.assertTrue(
                any(pattern.fullmatch(call) for pattern in patterns)
                or any(path.startswith(f"{call}/<") for path in declared),
                f"Browser endpoint is outside the frozen contract: {call}",
            )

    def test_flask_compatibility_serves_frontend_from_the_application_boundary(self) -> None:
        class FakeManager:
            def initialize(self) -> None:
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(container="bedrock", project=root, database=root / "manager.db", auth_cookie_secure=False)
            app = create_app(settings, FakeManager())  # type: ignore[arg-type]
            client = app.test_client()
            index = client.get("/")
            script = client.get("/static/app.js")
            index_status, index_data = index.status_code, index.data
            script_status, script_data = script.status_code, script.data
            index.close()
            script.close()

        self.assertEqual(index_status, 200)
        self.assertIn(b"CraftControl", index_data)
        self.assertEqual(script_status, 200)
        self.assertIn(b"const state", script_data)


if __name__ == "__main__":
    unittest.main()

import json
import re
from pathlib import Path

import pytest
from flask import Flask

from minecraft_manager import create_app
from minecraft_manager.auth.http import auth_api
from minecraft_manager.config import Settings
from minecraft_manager.routes import api


ROOT = Path(__file__).resolve().parents[3]
FRONTEND = ROOT / "apps" / "client"
CONTRACT = ROOT / "packages" / "contracts" / "http-surface.json"


@pytest.fixture(scope="module")
def http_surface_data():
    contract = json.loads(CONTRACT.read_text())
    app = Flask(__name__)
    app.register_blueprint(auth_api)
    app.register_blueprint(api)
    actual_routes: dict[str, set[str]] = {}
    for rule in app.url_map.iter_rules():
        methods = actual_routes.setdefault(rule.rule, set())
        methods.update(rule.methods - {"HEAD", "OPTIONS"})
    return contract, actual_routes


def test_flask_routes_match_the_frozen_http_surface(http_surface_data) -> None:
    contract, actual_routes = http_surface_data
    expected = {route["path"]: sorted(route["methods"]) for route in contract["routes"]}
    assert {path: sorted(methods) for path, methods in actual_routes.items()} == expected


def test_split_contract_keeps_one_origin_and_sse_under_api(http_surface_data) -> None:
    contract, _ = http_surface_data
    assert contract["public_origin"] == "frontend"
    assert contract["api_prefix"] == "/api"
    assert contract["sse_path"] == "/api/events"
    event_route = next(route for route in contract["routes"] if route["path"] == "/api/events")
    assert event_route["protocol"] == "sse"


def test_browser_api_calls_remain_inside_the_declared_api_boundary(http_surface_data) -> None:
    contract, _ = http_surface_data
    sources = "\n".join(path.read_text() for path in [
        FRONTEND / "static" / "app.js",
        FRONTEND / "static" / "js" / "auth.js",
        FRONTEND / "static" / "js" / "events.js",
    ])
    calls = set(re.findall(r'["`](/api/[a-z0-9-]+(?:/[a-z0-9-]+)*)', sources))
    declared = {route["path"] for route in contract["routes"] if route["path"].startswith("/api/")}
    patterns = [
        re.compile("^" + re.sub(r"<(?:(?:path):)?[^>]+>", r"[^/]+(?:/[^/]+)*", path) + "$")
        for path in declared
    ]
    for call in calls:
        assert (
            any(pattern.fullmatch(call) for pattern in patterns)
            or any(path.startswith(f"{call}/<") for path in declared)
        ), f"Browser endpoint is outside the frozen contract: {call}"


# The import-string assertions below (e.g. `?v=9`, `?v=7`) stay in Python
# because they test the HTTP surface: Flask must serve the correct versioned
# content to browsers. They are not testing JS module wiring or composition
# logic — that belongs in Jest (see apps/client/tests/players-contracts.test.js).
def test_flask_compatibility_serves_frontend_from_the_application_boundary(tmp_path: Path) -> None:
    class FakeManager:
        def initialize(self) -> None:
            pass

    settings = Settings(container="bedrock", project=tmp_path, database=tmp_path / "manager.db", auth_cookie_secure=False)
    app = create_app(settings, FakeManager())  # type: ignore[arg-type]
    client = app.test_client()
    index = client.get("/")
    script = client.get("/static/app.js")
    composition = client.get("/static/js/composition.js")
    state_module = client.get("/static/js/core/state.js")
    index_status, index_data = index.status_code, index.data
    script_status, script_data = script.status_code, script.data
    composition_status, composition_data = composition.status_code, composition.data
    state_status, state_data = state_module.status_code, state_module.data
    index.close()
    script.close()
    composition.close()
    state_module.close()

    assert index_status == 200
    assert b"CraftControl" in index_data
    assert script_status == 200
    assert b'import { startApplication } from "./js/composition.js?v=10"' in script_data
    assert composition_status == 200
    assert b'import { state } from "./core/state.js?v=7"' in composition_data
    assert state_status == 200
    assert b"export const state" in state_data

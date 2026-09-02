import json
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

from minecraft_manager import create_app
from minecraft_manager.core.config import Settings
from minecraft_manager.http.docs import contract_root
from minecraft_manager.routes import api
from packages.contracts.generate_types import OUTPUT_PATH, generate


ROOT = Path(__file__).resolve().parents[3]
OPENAPI = ROOT / "packages" / "contracts" / "openapi.json"
SURFACE = ROOT / "packages" / "contracts" / "http-surface.json"
DOC_PATHS = {"/api/docs", "/api/docs/assets/<path:filename>", "/api/openapi.json"}


def openapi_path(flask_path: str) -> str:
    output = flask_path
    while "<" in output:
        start, end = output.index("<"), output.index(">")
        parameter = output[start + 1:end].split(":")[-1]
        output = f"{output[:start]}{{{parameter}}}{output[end + 1:]}"
    return output


def validate_schema(value: Any, schema: dict[str, Any], spec: dict[str, Any], location: str = "response") -> None:
    if "$ref" in schema:
        target: Any = spec
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        validate_schema(value, target, spec, location)
        return
    for index, item in enumerate(schema.get("allOf", [])):
        validate_schema(value, item, spec, f"{location}.allOf[{index}]")
    if "const" in schema and value != schema["const"]:
        raise AssertionError(f"{location} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise AssertionError(f"{location} is outside {schema['enum']!r}")
    expected = schema.get("type")
    if isinstance(expected, list):
        errors = []
        for candidate in expected:
            try:
                validate_schema(value, {**schema, "type": candidate}, spec, location)
                return
            except AssertionError as error:
                errors.append(str(error))
        raise AssertionError("; ".join(errors))
    matches = {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
    }
    if expected in matches and not matches[expected]:
        raise AssertionError(f"{location} must be {expected}, got {type(value).__name__}")
    if expected == "object":
        required = set(schema.get("required", []))
        missing = required - set(value)
        if missing:
            raise AssertionError(f"{location} is missing {sorted(missing)!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = set(value) - set(properties)
            if unexpected:
                raise AssertionError(f"{location} has unexpected {sorted(unexpected)!r}")
        for name, item in properties.items():
            if name in value:
                validate_schema(value[name], item, spec, f"{location}.{name}")
    if expected == "array":
        for index, item in enumerate(value):
            validate_schema(item, schema.get("items", {}), spec, f"{location}[{index}]")


def response_schema(spec: dict[str, Any], path: str, status: int = 200) -> dict[str, Any]:
    response = spec["paths"][path]["get"]["responses"][str(status)]
    return response["content"]["application/json"]["schema"]


@pytest.fixture(scope="module")
def openapi_specs():
    return json.loads(OPENAPI.read_text()), json.loads(SURFACE.read_text())


def test_spec_is_openapi_31_with_cookie_and_csrf_security(openapi_specs) -> None:
    spec, _ = openapi_specs
    assert spec["openapi"] == "3.1.0"
    cookie = spec["components"]["securitySchemes"]["cookieAuth"]
    assert cookie == {
        "type": "apiKey", "in": "cookie", "name": "craftcontrol_session",
        "description": "HttpOnly session cookie issued by login or claim.",
    }
    csrf = spec["components"]["parameters"]["CsrfToken"]
    assert csrf["name"] == "X-CSRF-Token"
    assert csrf["required"]


def test_operation_pagination_documents_bad_request_response(openapi_specs) -> None:
    spec, _ = openapi_specs
    assert spec["paths"]["/api/operations"]["get"]["responses"]["400"] == {
        "$ref": "#/components/responses/BadRequest"
    }


def test_spec_methods_match_every_application_api_route(openapi_specs) -> None:
    spec, surface = openapi_specs
    expected = {
        openapi_path(route["path"]): {method.lower() for method in route["methods"]}
        for route in surface["routes"]
        if route["path"].startswith("/api/") and route["path"] not in DOC_PATHS
    }
    actual = {
        path: {method for method in item if method in {"get", "post", "put", "patch", "delete"}}
        for path, item in spec["paths"].items()
    }
    assert actual == expected


def test_operation_ids_are_unique_and_mutations_declare_csrf(openapi_specs) -> None:
    spec, _ = openapi_specs
    operation_ids = []
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation_ids.append(operation["operationId"])
            if method not in {"get"} and path not in {"/api/auth/login", "/api/auth/claim"}:
                references = {parameter.get("$ref") for parameter in operation.get("parameters", [])}
                assert "#/components/parameters/CsrfToken" in references, f"Missing CSRF contract for {method} {path}"
    assert len(operation_ids) == len(set(operation_ids))


def test_contract_paths_resolve_in_source_and_packaged_layouts() -> None:
    assert contract_root(ROOT / "apps" / "server" / "minecraft_manager") == ROOT / "packages" / "contracts"
    assert contract_root(Path("/app/minecraft_manager")) == Path("/app/packages/contracts")


def test_generated_frontend_types_match_openapi_schemas(openapi_specs) -> None:
    spec, _ = openapi_specs
    assert OUTPUT_PATH.read_text() == generate(spec)
    declarations = OUTPUT_PATH.read_text()
    assert "export type PlayerProfile" in declarations
    assert "export type ActivityPage" in declarations
    assert "export type TelemetryPackStatus" in declarations


def test_representative_flask_responses_match_published_schemas(openapi_specs) -> None:
    spec, _ = openapi_specs
    player = {
        "id": "player-1", "name": "Alex", "online": False, "sessions_count": 2,
        "total_play_seconds": 120, "deaths_count": 1, "permission": "member",
        "operator": False, "telemetry": {}, "telemetry_updated_at": None,
    }

    class FakeDocker:
        def status(self):
            return {"container": "bedrock", "state": "running", "online": True}

    class FakeManager:
        docker = FakeDocker()

        def public_state(self):
            return {"settings": {}, "gamerules": {}, "players": {}, "server": {}, "domains": {}, "telemetry": {}, "refreshing": False}

        def players(self):
            return [player]

        def player_profile(self, identity):
            return {**player, "aliases": ["Alex"], "history": [], "sessions": []}

        def player_activity(self, kind, name, source, search, days, page, page_size):
            return {"events": [], "page": page, "page_size": page_size, "total": 0, "pages": 1, "summary": {}}

        def player_rankings(self, limit):
            return {"period": "lifetime", "metrics": {}}

        def block_analytics(self, limit):
            return {"period": "lifetime", "totals": {}}

        def combat_analytics(self, limit):
            return {"period": "lifetime", "totals": {}}

        def exploration_analytics(self, limit):
            return {"period": "lifetime", "totals": {}}

        def period_analytics(self, days, limit):
            return {"period_days": days, "totals": {}}

    app = Flask(__name__)
    app.extensions["manager_service"] = FakeManager()
    app.register_blueprint(api)
    client = app.test_client()
    paths = [
        "/api/health", "/api/state", "/api/status", "/api/players",
        "/api/players/profile/player-1", "/api/analytics/activity",
        "/api/analytics/rankings", "/api/analytics/blocks", "/api/analytics/combat",
        "/api/analytics/exploration", "/api/analytics/periods?days=7",
    ]
    for request_path in paths:
        response = client.get(request_path)
        contract_path = request_path.split("?", 1)[0]
        if contract_path.startswith("/api/players/profile/"):
            contract_path = "/api/players/profile/{identity}"
        assert response.status_code == 200, request_path
        validate_schema(response.get_json(), response_schema(spec, contract_path), spec, request_path)
        response.close()


def test_openapi_and_swagger_are_authenticated_and_servable(tmp_path: Path) -> None:
    class FakeManager:
        def initialize(self) -> None:
            pass

    local = Settings(container="bedrock", project=tmp_path, database=tmp_path / "local.db", auth_cookie_secure=False)
    protected = create_app(local, FakeManager())  # type: ignore[arg-type]
    assert protected.test_client().get("/api/docs").status_code == 401
    disabled = Settings(container="bedrock", project=tmp_path, database=tmp_path / "disabled.db", auth_mode="disabled", auth_cookie_secure=False)
    public = create_app(disabled, FakeManager())  # type: ignore[arg-type]
    docs = public.test_client().get("/api/docs")
    spec_response = public.test_client().get("/api/openapi.json")
    asset = public.test_client().get("/api/docs/assets/swagger-ui.css")

    assert docs.status_code == 200
    assert b"SwaggerUIBundle" in docs.data
    assert b"X-CSRF-Token" in docs.data
    assert spec_response.status_code == 200
    assert spec_response.get_json()["info"]["title"] == "CraftControl API"
    assert asset.status_code == 200
    assert "text/css" in asset.content_type
    spec_response.close()
    asset.close()

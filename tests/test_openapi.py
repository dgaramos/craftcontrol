import json
import tempfile
import unittest
from pathlib import Path

from minecraft_manager import create_app
from minecraft_manager.config import Settings
from minecraft_manager.http.docs import contract_root


ROOT = Path(__file__).resolve().parents[1]
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


class OpenApiContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = json.loads(OPENAPI.read_text())
        self.surface = json.loads(SURFACE.read_text())

    def test_spec_is_openapi_31_with_cookie_and_csrf_security(self) -> None:
        self.assertEqual(self.spec["openapi"], "3.1.0")
        cookie = self.spec["components"]["securitySchemes"]["cookieAuth"]
        self.assertEqual(cookie, {
            "type": "apiKey", "in": "cookie", "name": "craftcontrol_session",
            "description": "HttpOnly session cookie issued by login or claim.",
        })
        csrf = self.spec["components"]["parameters"]["CsrfToken"]
        self.assertEqual(csrf["name"], "X-CSRF-Token")
        self.assertTrue(csrf["required"])

    def test_spec_methods_match_every_application_api_route(self) -> None:
        expected = {
            openapi_path(route["path"]): {method.lower() for method in route["methods"]}
            for route in self.surface["routes"]
            if route["path"].startswith("/api/") and route["path"] not in DOC_PATHS
        }
        actual = {
            path: {method for method in item if method in {"get", "post", "put", "patch", "delete"}}
            for path, item in self.spec["paths"].items()
        }
        self.assertEqual(actual, expected)

    def test_operation_ids_are_unique_and_mutations_declare_csrf(self) -> None:
        operation_ids = []
        for path, item in self.spec["paths"].items():
            for method, operation in item.items():
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue
                operation_ids.append(operation["operationId"])
                if method not in {"get"} and path not in {"/api/auth/login", "/api/auth/claim"}:
                    references = {parameter.get("$ref") for parameter in operation.get("parameters", [])}
                    self.assertIn("#/components/parameters/CsrfToken", references, f"Missing CSRF contract for {method} {path}")
        self.assertEqual(len(operation_ids), len(set(operation_ids)))

    def test_contract_paths_resolve_in_source_and_packaged_layouts(self) -> None:
        self.assertEqual(contract_root(ROOT / "apps" / "backend" / "minecraft_manager"), ROOT / "packages" / "contracts")
        self.assertEqual(contract_root(Path("/app/minecraft_manager")), Path("/app/packages/contracts"))

    def test_openapi_and_swagger_are_authenticated_and_servable(self) -> None:
        class FakeManager:
            def initialize(self) -> None:
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = Settings(container="bedrock", project=root, database=root / "local.db", auth_cookie_secure=False)
            protected = create_app(local, FakeManager())  # type: ignore[arg-type]
            self.assertEqual(protected.test_client().get("/api/docs").status_code, 401)
            disabled = Settings(container="bedrock", project=root, database=root / "disabled.db", auth_mode="disabled", auth_cookie_secure=False)
            public = create_app(disabled, FakeManager())  # type: ignore[arg-type]
            docs = public.test_client().get("/api/docs")
            spec = public.test_client().get("/api/openapi.json")
            asset = public.test_client().get("/api/docs/assets/swagger-ui.css")

            self.assertEqual(docs.status_code, 200)
            self.assertIn(b"SwaggerUIBundle", docs.data)
            self.assertIn(b"X-CSRF-Token", docs.data)
            self.assertEqual(spec.status_code, 200)
            self.assertEqual(spec.get_json()["info"]["title"], "CraftControl API")
            self.assertEqual(asset.status_code, 200)
            self.assertIn("text/css", asset.content_type)
            spec.close()
            asset.close()


if __name__ == "__main__":
    unittest.main()

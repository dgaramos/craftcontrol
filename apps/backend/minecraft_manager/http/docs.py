from __future__ import annotations

from pathlib import Path

from flask import Blueprint, Response, send_file, send_from_directory


docs_api = Blueprint("docs_api", __name__)


def contract_root(package_root: Path | None = None) -> Path:
    package_root = package_root or Path(__file__).resolve().parents[1]
    if package_root.parent.name == "backend":
        return package_root.parents[2] / "packages" / "contracts"
    return package_root.parent / "packages" / "contracts"


@docs_api.get("/api/openapi.json")
def openapi_document():
    response = send_file(contract_root() / "openapi.json", mimetype="application/vnd.oai.openapi+json")
    response.headers["Cache-Control"] = "no-cache"
    return response


@docs_api.get("/api/docs/assets/<path:filename>")
def swagger_asset(filename: str):
    from swagger_ui_bundle import swagger_ui_path

    return send_from_directory(swagger_ui_path, filename, max_age=86400)


@docs_api.get("/api/docs")
def swagger_docs():
    return Response(
        """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CraftControl API</title><link rel="stylesheet" href="/api/docs/assets/swagger-ui.css">
<style>body{margin:0;background:#0c120f}.swagger-ui .topbar{display:none}</style></head>
<body><div id="swagger-ui"></div><script src="/api/docs/assets/swagger-ui-bundle.js"></script>
<script src="/api/docs/assets/swagger-ui-standalone-preset.js"></script><script>
window.onload=async()=>{let csrf="";try{const response=await fetch("/api/auth/me");if(response.ok)csrf=(await response.json()).csrf_token||""}catch(_){}
window.ui=SwaggerUIBundle({url:"/api/openapi.json",dom_id:"#swagger-ui",deepLinking:true,displayRequestDuration:true,
presets:[SwaggerUIBundle.presets.apis,SwaggerUIStandalonePreset],layout:"StandaloneLayout",
requestInterceptor:(request)=>{if(csrf&&!['GET','HEAD','OPTIONS'].includes(String(request.method).toUpperCase()))request.headers['X-CSRF-Token']=csrf;return request}})};
</script></body></html>""",
        mimetype="text/html",
    )


__all__ = ["contract_root", "docs_api"]

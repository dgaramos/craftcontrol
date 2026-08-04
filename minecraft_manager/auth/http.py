from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, Flask, current_app, g, jsonify, request

from .service import AuthService

auth_api = Blueprint("auth_api", __name__)
COOKIE_NAME = "craftcontrol_session"


def auth_service() -> AuthService:
    from flask import current_app
    return current_app.extensions["auth_service"]


def install_auth(app: Flask, service: AuthService, mode: str, secure_cookie: bool = True) -> None:
    app.extensions["auth_service"] = service
    app.config["AUTH_MODE"] = mode
    app.config["AUTH_COOKIE_SECURE"] = secure_cookie

    @app.before_request
    def authenticate_request():
        if mode == "disabled":
            g.user = {"id": "disabled", "name": "Local administrator", "role": "owner", "capabilities": ["*"]}
            return None
        g.user = service.authenticate(request.cookies.get(COOKIE_NAME))
        public = request.path == "/" or request.path.startswith("/static/") or request.path == "/api/health" or request.path.startswith("/api/auth/")
        if public:
            return None
        if g.user is None:
            return jsonify(error="authentication required"), 401
        return None


def require(capability: str):
    def decorate(function: Callable[..., Any]):
        @wraps(function)
        def authorized(*args: Any, **kwargs: Any):
            if getattr(g, "user", None) is None:
                return jsonify(error="authentication required"), 401
            try:
                auth_service().require_capability(g.user, capability)
            except PermissionError:
                return jsonify(error="insufficient permission", capability=capability), 403
            return function(*args, **kwargs)
        return authorized
    return decorate


@auth_api.get("/api/auth/me")
def me():
    if getattr(g, "user", None) is None:
        return jsonify(error="authentication required"), 401
    return jsonify(user=g.user)


def _session_response(user: dict[str, Any], token: str):
    response = jsonify(user=user)
    response.set_cookie(
        COOKIE_NAME, token, max_age=604800, secure=current_app.config["AUTH_COOKIE_SECURE"],
        httponly=True, samesite="Lax", path="/",
    )
    return response


@auth_api.post("/api/auth/login")
def login():
    try:
        payload = request.get_json(force=True)
        token, user = auth_service().login(str(payload.get("player", "")), str(payload.get("password", "")))
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 401
    return _session_response(user, token)


@auth_api.post("/api/auth/claim")
def claim():
    try:
        payload = request.get_json(force=True)
        token, user = auth_service().claim(
            str(payload.get("player", "")), str(payload.get("token", "")), str(payload.get("password", "")),
        )
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    return _session_response(user, token)


@auth_api.post("/api/auth/logout")
def logout():
    auth_service().logout(request.cookies.get(COOKIE_NAME))
    response = jsonify(ok=True)
    response.delete_cookie(COOKIE_NAME, path="/")
    return response

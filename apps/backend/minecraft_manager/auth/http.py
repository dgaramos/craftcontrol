from __future__ import annotations

from functools import wraps
from typing import Any, Callable
from urllib.parse import urlsplit

from flask import Blueprint, Flask, current_app, g, jsonify, request

from .service import AuthService

auth_api = Blueprint("auth_api", __name__)
COOKIE_NAME = "craftcontrol_session"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT_PATHS = {"/api/auth/login", "/api/auth/claim"}


def _same_origin() -> bool:
    origin = request.headers.get("Origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc.casefold() == request.host.casefold()


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
        public = (
            request.path == "/" or request.path.startswith("/static/") or request.path == "/api/health"
            or request.path in {"/api/auth/me", *CSRF_EXEMPT_PATHS}
        )
        if g.user is None:
            if public:
                return None
            return jsonify(error="authentication required"), 401
        if request.method not in SAFE_METHODS and request.path not in CSRF_EXEMPT_PATHS:
            if not _same_origin():
                return jsonify(error="invalid request origin"), 403
            if not service.verify_csrf(request.cookies.get(COOKIE_NAME), request.headers.get(CSRF_HEADER)):
                return jsonify(error="invalid or missing CSRF token"), 403
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
    session_token = request.cookies.get(COOKIE_NAME)
    if current_app.config["AUTH_MODE"] == "disabled":
        return jsonify(user=g.user)
    return jsonify(user=g.user, csrf_token=auth_service().csrf_token(session_token))


def _session_response(user: dict[str, Any], token: str):
    response = jsonify(user=user, csrf_token=auth_service().csrf_token(token))
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


@auth_api.put("/api/auth/password")
def change_password():
    try:
        payload = request.get_json(force=True)
        token, user = auth_service().change_password(
            request.cookies.get(COOKIE_NAME) or "",
            str(payload.get("current_password", "")),
            str(payload.get("new_password", "")),
        )
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    return _session_response(user, token)


@auth_api.get("/api/auth/access")
@require("security.manage_users")
def access_list():
    return jsonify(players=auth_service().access_list())


@auth_api.post("/api/auth/access/invite")
@require("security.manage_users")
def invite():
    try:
        payload = request.get_json(force=True)
        player = str(payload.get("player", ""))
        role = str(payload.get("role", "viewer"))
        token = auth_service().create_invitation(player, role, actor=g.user["id"])
        return jsonify(player=player, role=role, token=token, expires_in=900)
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400


@auth_api.put("/api/auth/access/<path:player>/suspend")
@require("security.manage_users")
def suspend(player: str):
    try:
        auth_service().suspend(player, g.user["id"])
        return jsonify(ok=True, player=player, status="suspended")
    except ValueError as error:
        return jsonify(error=str(error)), 400

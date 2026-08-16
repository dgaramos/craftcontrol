"""Tests for auth/http.py endpoints not covered by test_auth.py integration tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask, jsonify

from minecraft_manager.auth.http import auth_api, install_auth, require
from minecraft_manager.auth.service import AuthService


def _make_app(auth: MagicMock, *, mode: str = "local") -> Flask:
    app = Flask(__name__)
    install_auth(app, auth, mode=mode, secure_cookie=False)
    app.register_blueprint(auth_api)
    return app


@pytest.fixture
def auth() -> MagicMock:
    mock = MagicMock(spec=AuthService)
    mock.authenticate.return_value = {"id": "1", "name": "VonCrush", "role": "owner", "capabilities": ["*"]}
    mock.verify_csrf.return_value = True
    mock.csrf_token.return_value = "csrftoken"
    mock.require_capability.return_value = None
    return mock


@pytest.fixture
def client(auth: MagicMock):
    return _make_app(auth).test_client()


# ---------------------------------------------------------------------------
# /api/auth/me
# ---------------------------------------------------------------------------

def test_me_returns_user_and_csrf_in_local_mode(client, auth: MagicMock) -> None:
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["user"]["name"] == "VonCrush"
    assert data["csrf_token"] == "csrftoken"


def test_me_returns_401_when_unauthenticated(auth: MagicMock) -> None:
    auth.authenticate.return_value = None
    c = _make_app(auth).test_client()
    resp = c.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_omits_csrf_token_in_disabled_mode(auth: MagicMock) -> None:
    app = _make_app(auth, mode="disabled")
    c = app.test_client()
    resp = c.get("/api/auth/me")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "csrf_token" not in data


# ---------------------------------------------------------------------------
# /api/auth/login
# ---------------------------------------------------------------------------

def test_login_returns_session_cookie_on_success(auth: MagicMock) -> None:
    auth.login.return_value = ("tok", {"id": "1", "name": "VonCrush", "role": "owner", "capabilities": ["*"]})
    app = _make_app(auth)
    c = app.test_client()
    resp = c.post("/api/auth/login", json={"player": "VonCrush", "password": "securepass"})
    assert resp.status_code == 200
    assert "craftcontrol_session" in resp.headers.get("Set-Cookie", "")


def test_login_returns_401_on_invalid_credentials(auth: MagicMock) -> None:
    auth.login.side_effect = ValueError("invalid credentials")
    app = _make_app(auth)
    c = app.test_client()
    resp = c.post("/api/auth/login", json={"player": "VonCrush", "password": "wrong"})
    assert resp.status_code == 401
    assert "invalid credentials" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# /api/auth/claim
# ---------------------------------------------------------------------------

def test_claim_returns_400_on_invalid_token(auth: MagicMock) -> None:
    auth.claim.side_effect = ValueError("invalid or expired")
    app = _make_app(auth)
    c = app.test_client()
    resp = c.post("/api/auth/claim", json={"player": "Nicole", "token": "bad", "password": "longpassword"})
    assert resp.status_code == 400
    assert "invalid or expired" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# /api/auth/access — access_list
# ---------------------------------------------------------------------------

def test_access_list_returns_players_for_owner(auth: MagicMock) -> None:
    auth.access_list.return_value = [{"name": "VonCrush", "role": "owner"}]
    resp = client_from(auth).get("/api/auth/access")
    assert resp.status_code == 200
    assert resp.get_json()["players"][0]["name"] == "VonCrush"


def test_access_list_returns_403_for_insufficient_role(auth: MagicMock) -> None:
    auth.require_capability.side_effect = PermissionError("no")
    resp = client_from(auth).get("/api/auth/access")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /api/auth/access/invite
# ---------------------------------------------------------------------------

def test_invite_returns_token_for_owner(auth: MagicMock) -> None:
    auth.create_invitation.return_value = "invite-tok"
    resp = client_from(auth).post("/api/auth/access/invite", json={"player": "Nicole", "role": "viewer"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["token"] == "invite-tok"
    assert data["player"] == "Nicole"
    assert data["expires_in"] == 900


def test_invite_returns_400_on_value_error(auth: MagicMock) -> None:
    auth.create_invitation.side_effect = ValueError("player not found")
    resp = client_from(auth).post("/api/auth/access/invite", json={"player": "Unknown", "role": "viewer"})
    assert resp.status_code == 400
    assert "player not found" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# /api/auth/access/<player>/suspend
# ---------------------------------------------------------------------------

def test_suspend_returns_ok_for_owner(auth: MagicMock) -> None:
    resp = client_from(auth).put("/api/auth/access/Nicole/suspend")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["status"] == "suspended"


def test_suspend_returns_400_on_last_owner(auth: MagicMock) -> None:
    auth.suspend.side_effect = ValueError("last active owner")
    resp = client_from(auth).put("/api/auth/access/VonCrush/suspend")
    assert resp.status_code == 400
    assert "last active owner" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# require() decorator — standalone
# ---------------------------------------------------------------------------

def test_require_returns_401_when_no_user_in_context(auth: MagicMock) -> None:
    app = Flask(__name__)
    install_auth(app, auth, mode="local", secure_cookie=False)
    auth.authenticate.return_value = None

    @app.get("/api/protected")
    @require("server.read")
    def protected():
        return jsonify(ok=True)

    c = app.test_client()
    resp = c.get("/api/protected")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def client_from(auth: MagicMock):
    return _make_app(auth).test_client()

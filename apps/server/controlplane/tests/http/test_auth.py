import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from flask import Flask, jsonify

from src.auth.http import auth_api, install_auth, require
from src.auth.service import AuthService
from src.players.repository import SQLitePlayerRepository
from conftest import make_operation_db


@pytest.fixture
def auth_db(tmp_path: Path) -> tuple[Path, AuthService]:
    path = make_operation_db(tmp_path, "manager.db")
    player_repo = SQLitePlayerRepository(path)
    player_repo.observe_player("VonCrush", True, "123")
    player_repo.observe_player("Nicole", False, "456")
    auth = AuthService(path, idle_seconds=60, absolute_seconds=120)
    return path, auth


def test_bootstrap_claim_creates_first_owner_and_one_time_session(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.bootstrap("VonCrush")
    session, user = auth.claim("VonCrush", invitation, "correct horse battery")
    assert user["role"] == "owner"
    assert "*" in user["capabilities"]
    assert auth.authenticate(session)["name"] == "VonCrush"
    with pytest.raises(ValueError, match="invalid or expired"):
        auth.claim("VonCrush", invitation, "another secure password")
    with pytest.raises(ValueError, match="active owner"):
        auth.bootstrap("VonCrush")


def test_bootstrap_raises_on_pending_owner_invitation(auth_db) -> None:
    _, auth = auth_db
    auth.bootstrap("VonCrush")
    with pytest.raises(ValueError, match="pending owner invitation"):
        auth.bootstrap("VonCrush")


def test_bootstrap_raises_on_pending_owner_invitation_when_active_operator_exists(auth_db) -> None:
    """Bootstrap must detect a pending owner invitation via panel_invitations.role,
    not via a join to panel_accounts. If an active operator account exists with no
    active owner, the join-based guard would miss any outstanding invitation and
    allow a second one to be created for a different identity."""
    path, auth = auth_db
    # Create an active operator account for Nicole — no active owner exists yet.
    operator_inv = auth.create_invitation("Nicole", "operator")
    auth.claim("Nicole", operator_inv, "a sufficiently long password")
    # First bootstrap for VonCrush: must succeed and leave a pending owner invitation.
    auth.bootstrap("VonCrush")
    # Second bootstrap for Nicole: must be rejected because the invitation already exists
    # in panel_invitations with role='owner', regardless of Nicole's active operator role.
    with pytest.raises(ValueError, match="pending owner invitation"):
        auth.bootstrap("Nicole")


def test_login_logout_and_alias_identity(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    first_session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    auth.logout(first_session)
    assert auth.authenticate(first_session) is None
    second_session, user = auth.login("Nicole", "a sufficiently long password")
    assert user["role"] == "operator"
    assert auth.authenticate(second_session) is not None


def test_lists_safe_sessions_and_revokes_only_another_session(auth_db) -> None:
    _, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    current, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    other, _ = auth.login("Nicole", "a sufficiently long password")
    sessions = auth.sessions(current)
    assert {"id", "created_at", "last_seen_at", "current"} == set(sessions[0])
    assert all(other not in str(session) and current not in str(session) for session in sessions)
    other_id = next(session["id"] for session in sessions if not session["current"])
    auth.revoke_session(current, other_id)
    assert auth.authenticate(other) is None
    assert auth.authenticate(current) is not None


def test_revoking_other_sessions_preserves_current_session(auth_db) -> None:
    _, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    current, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    other, _ = auth.login("Nicole", "a sufficiently long password")
    auth.revoke_other_sessions(current)
    assert auth.authenticate(current) is not None
    assert auth.authenticate(other) is None


def test_session_actions_reject_a_revoked_current_session(auth_db) -> None:
    _, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    auth.logout(session)
    with pytest.raises(ValueError, match="session not found"):
        auth.sessions(session)
    with pytest.raises(ValueError, match="session not found"):
        auth.revoke_other_sessions(session)


def test_session_list_is_bounded(auth_db) -> None:
    _, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    for _ in range(auth.SESSION_LIST_LIMIT + 2):
        auth.login("Nicole", "a sufficiently long password")
    assert len(auth.sessions(session)) == auth.SESSION_LIST_LIMIT


def test_change_password_rotates_current_session_and_revokes_existing_sessions(auth_db) -> None:
    _, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    current_session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    other_session, _ = auth.login("Nicole", "a sufficiently long password")

    rotated_session, user = auth.change_password(
        current_session, "a sufficiently long password", "a different secure password",
    )

    assert user["name"] == "Nicole"
    assert rotated_session != current_session
    assert auth.authenticate(current_session) is None
    assert auth.authenticate(other_session) is None
    assert auth.authenticate(rotated_session) is not None
    with pytest.raises(ValueError, match="invalid credentials"):
        auth.login("Nicole", "a sufficiently long password")
    replacement_session, _ = auth.login("Nicole", "a different secure password")
    assert auth.authenticate(replacement_session) is not None


def test_change_password_rejects_invalid_current_password_without_state_changes(auth_db) -> None:
    _, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")

    with pytest.raises(ValueError, match="current password is incorrect"):
        auth.change_password(session, "wrong password", "a different secure password")

    assert auth.authenticate(session) is not None
    replacement_session, _ = auth.login("Nicole", "a sufficiently long password")
    assert auth.authenticate(replacement_session) is not None


def test_change_password_rejects_an_oversized_current_password(auth_db) -> None:
    _, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")

    with pytest.raises(ValueError, match="8 to 128"):
        auth.change_password(session, "x" * 129, "a different secure password")

    assert auth.authenticate(session) is not None


def test_authentication_throttles_session_writes(auth_db) -> None:
    path, auth = auth_db
    auth.idle_seconds = 120
    invitation = auth.create_invitation("Nicole", "operator")
    session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    with sqlite3.connect(path) as connection:
        before = connection.execute("SELECT last_seen_at FROM panel_sessions WHERE revoked_at IS NULL").fetchone()[0]
    with patch("src.auth.service.time.time", return_value=before + 30):
        assert auth.authenticate(session) is not None
    with sqlite3.connect(path) as connection:
        unchanged = connection.execute("SELECT last_seen_at FROM panel_sessions WHERE revoked_at IS NULL").fetchone()[0]
    assert unchanged == before
    with patch("src.auth.service.time.time", return_value=before + 61):
        assert auth.authenticate(session) is not None
    with sqlite3.connect(path) as connection:
        touched = connection.execute("SELECT last_seen_at FROM panel_sessions WHERE revoked_at IS NULL").fetchone()[0]
    assert touched == before + 61


def test_rejects_unknown_player_and_short_password(auth_db) -> None:
    path, auth = auth_db
    with pytest.raises(ValueError, match="not been observed"):
        auth.create_invitation("Stranger", "viewer")
    invitation = auth.create_invitation("Nicole", "viewer")
    with pytest.raises(ValueError, match="8 to 128"):
        auth.claim("Nicole", invitation, "short")


def test_accepts_eight_character_password(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    session, user = auth.claim("Nicole", invitation, "12345678")
    assert user["role"] == "viewer"
    assert auth.authenticate(session) is not None


def test_tokens_and_passwords_are_not_stored_in_plaintext(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    auth.claim("Nicole", invitation, "a sufficiently long password")
    with sqlite3.connect(path) as connection:
        token_hash = connection.execute("SELECT token_hash FROM panel_invitations").fetchone()[0]
        password_hash = connection.execute("SELECT password_hash FROM panel_accounts").fetchone()[0]
    assert token_hash != invitation
    assert "sufficiently" not in password_hash
    assert password_hash.startswith("scrypt$")


def test_role_capabilities_are_enforced(auth_db) -> None:
    path, auth = auth_db
    viewer = {"capabilities": ["server.read"]}
    auth.require_capability(viewer, "server.read")
    with pytest.raises(PermissionError):
        auth.require_capability(viewer, "world.manage")


def test_owner_can_list_access_and_last_owner_cannot_be_suspended(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.bootstrap("VonCrush")
    auth.claim("VonCrush", invitation, "ownerpass")
    access = {item["name"]: item for item in auth.access_list()}
    assert access["VonCrush"]["role"] == "owner"
    with pytest.raises(ValueError, match="last active owner"):
        auth.suspend("VonCrush", "test-owner")


def test_suspension_revokes_sessions_without_deleting_player(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    session, _ = auth.claim("Nicole", invitation, "operator1")
    auth.suspend("Nicole", "test-owner")
    assert auth.authenticate(session) is None
    access = {item["name"]: item for item in auth.access_list()}
    assert access["Nicole"]["status"] == "suspended"


def test_recovery_preserves_existing_role(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    first_session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    auth.logout(first_session)
    recovery, role = auth.create_recovery("Nicole")
    assert role == "viewer"
    _, user = auth.claim("Nicole", recovery, "a different secure password")
    assert user["role"] == "viewer"


def test_recovery_rejects_player_without_active_panel_account(auth_db) -> None:
    path, auth = auth_db
    with pytest.raises(ValueError, match="no active panel account"):
        auth.create_recovery("Nicole")


def test_http_boundary_rejects_anonymous_and_sets_secure_session_cookie(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    app = Flask(__name__)
    install_auth(app, auth, "local", secure_cookie=True)
    app.register_blueprint(auth_api)

    @app.get("/api/private")
    def private():
        return jsonify(ok=True)

    @app.post("/api/world-test")
    @require("world.manage")
    def world_test():
        return jsonify(ok=True)

    client = app.test_client()
    assert client.get("/api/private").status_code == 401
    response = client.post("/api/auth/claim", json={
        "player": "Nicole", "token": invitation, "password": "a sufficiently long password",
    })
    assert response.status_code == 200
    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert client.get("/api/private", base_url="https://localhost").status_code == 200
    csrf_token = response.get_json()["csrf_token"]
    missing = client.post("/api/world-test", base_url="https://localhost")
    assert missing.status_code == 403
    assert missing.get_json()["error"] == "invalid or missing CSRF token"
    invalid = client.post("/api/world-test", base_url="https://localhost", headers={"X-CSRF-Token": "invalid"})
    assert invalid.status_code == 403
    cross_origin = client.post(
        "/api/world-test", base_url="https://localhost",
        headers={"X-CSRF-Token": csrf_token, "Origin": "https://attacker.example"},
    )
    assert cross_origin.status_code == 403
    assert cross_origin.get_json()["error"] == "invalid request origin"
    authorized_csrf = client.post(
        "/api/world-test", base_url="https://localhost",
        headers={"X-CSRF-Token": csrf_token, "Origin": "https://localhost"},
    )
    assert authorized_csrf.status_code == 403
    assert authorized_csrf.get_json()["error"] == "insufficient permission"


def test_csrf_token_is_session_bound_and_protects_logout(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    app = Flask(__name__)
    install_auth(app, auth, "local", secure_cookie=False)
    app.register_blueprint(auth_api)
    client = app.test_client()
    claim = client.post("/api/auth/claim", json={
        "player": "Nicole", "token": invitation, "password": "a sufficiently long password",
    })
    csrf_token = claim.get_json()["csrf_token"]
    assert len(csrf_token) == 64
    assert client.post("/api/auth/logout").status_code == 403
    assert client.get("/api/auth/me").status_code == 200
    logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
    assert logout.status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_csrf_tokens_cannot_be_reused_across_sessions(auth_db) -> None:
    path, auth = auth_db
    first, _ = auth.claim(
        "Nicole", auth.create_invitation("Nicole", "operator"), "a sufficiently long password",
    )
    second, _ = auth.login("Nicole", "a sufficiently long password")
    assert auth.csrf_token(first) != auth.csrf_token(second)
    assert not auth.verify_csrf(second, auth.csrf_token(first))


def test_http_password_change_requires_csrf_and_rotates_cookie_session(auth_db) -> None:
    _, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    app = Flask(__name__)
    install_auth(app, auth, "local", secure_cookie=False)
    app.register_blueprint(auth_api)
    client = app.test_client()
    claim = client.post("/api/auth/claim", json={
        "player": "Nicole", "token": invitation, "password": "a sufficiently long password",
    })
    csrf_token = claim.get_json()["csrf_token"]
    old_cookie = claim.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]

    assert client.put("/api/auth/password", json={
        "current_password": "a sufficiently long password", "new_password": "a different secure password",
    }).status_code == 403
    response = client.put("/api/auth/password", headers={"X-CSRF-Token": csrf_token}, json={
        "current_password": "a sufficiently long password", "new_password": "a different secure password",
    })

    assert response.status_code == 200
    new_cookie = response.headers["Set-Cookie"].split(";", 1)[0].split("=", 1)[1]
    assert new_cookie != old_cookie
    assert auth.authenticate(old_cookie) is None
    assert auth.authenticate(new_cookie) is not None
    assert response.get_json()["csrf_token"] != csrf_token


def test_expired_session_is_rejected_before_csrf_validation(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    app = Flask(__name__)
    expired_auth = AuthService(path, idle_seconds=-1, absolute_seconds=120)
    install_auth(app, expired_auth, "local", secure_cookie=False)
    app.register_blueprint(auth_api)

    @app.post("/api/mutation")
    @require("server.configure")
    def mutation():
        return jsonify(ok=True)

    client = app.test_client()
    claim = client.post("/api/auth/claim", json={
        "player": "Nicole", "token": invitation, "password": "a sufficiently long password",
    })
    response = client.post("/api/mutation", headers={"X-CSRF-Token": claim.get_json()["csrf_token"]})
    assert response.status_code == 401
    assert response.get_json()["error"] == "authentication required"


# ---------------------------------------------------------------------------
# Audit trail tests for change_password, revoke_session, revoke_other_sessions
# ---------------------------------------------------------------------------

def _audit_rows(db_path: Path) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT actor_identity, action, target, result FROM audit_log ORDER BY occurred_at"
        ).fetchall()


def test_change_password_emits_audit_on_success(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    before = len(_audit_rows(path))

    auth.change_password(session, "a sufficiently long password", "a different secure password")

    rows = _audit_rows(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    actor, action, target, result = new_rows[0]
    assert action == "auth.password.changed"
    assert result == "success"
    assert actor == target  # actor is the identity who changed password


def test_change_password_emits_denied_audit_on_wrong_password(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    before = len(_audit_rows(path))

    with pytest.raises(ValueError):
        auth.change_password(session, "wrong password123", "a different secure password")

    rows = _audit_rows(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    _, action, _, result = new_rows[0]
    assert action == "auth.password.changed"
    assert result == "denied"


def test_revoke_session_emits_audit_on_success(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    current, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    auth.login("Nicole", "a sufficiently long password")
    sessions = auth.sessions(current)
    other_id = next(s["id"] for s in sessions if not s["current"])
    before = len(_audit_rows(path))

    auth.revoke_session(current, other_id)

    rows = _audit_rows(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    _, action, target, result = new_rows[0]
    assert action == "auth.session.revoked"
    assert result == "success"
    assert target == other_id  # sanitized 24-hex session id, not raw token_hash


def test_revoke_session_emits_denied_audit_on_invalid_target(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    current, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    before = len(_audit_rows(path))

    with pytest.raises(ValueError):
        auth.revoke_session(current, "nonexistentsessionid12345")

    rows = _audit_rows(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    _, action, _, result = new_rows[0]
    assert action == "auth.session.revoked"
    assert result == "denied"


def test_revoke_other_sessions_emits_audit(auth_db) -> None:
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "viewer")
    current, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    auth.login("Nicole", "a sufficiently long password")
    before = len(_audit_rows(path))

    auth.revoke_other_sessions(current)

    rows = _audit_rows(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    _, action, _, result = new_rows[0]
    assert action == "auth.sessions.revoked_all"
    assert result == "success"


def test_audit_details_never_contain_secrets(auth_db) -> None:
    import json as _json
    path, auth = auth_db
    invitation = auth.create_invitation("Nicole", "operator")
    session, _ = auth.claim("Nicole", invitation, "a sufficiently long password")
    auth.change_password(session, "a sufficiently long password", "a different secure password")

    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT details FROM audit_log WHERE action='auth.password.changed'").fetchall()

    forbidden = {"token", "token_hash", "password", "password_hash", "123", "456"}
    for (details_str,) in rows:
        details = _json.loads(details_str)
        details_text = _json.dumps(details).lower()
        for bad in forbidden:
            assert bad not in details_text, f"Secret '{bad}' found in audit details: {details_str}"


# ---------------------------------------------------------------------------
# Audit trail tests for create_invitation and suspend (issue #266)
# ---------------------------------------------------------------------------

def _audit_rows_with_details(db_path: Path) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT actor_identity, action, target, result, details FROM audit_log ORDER BY occurred_at"
        ).fetchall()


def test_invite_emits_audit_on_success(auth_db) -> None:
    path, auth = auth_db
    # Bootstrap an owner to act as the inviter
    invitation_bootstrap = auth.bootstrap("VonCrush")
    auth.claim("VonCrush", invitation_bootstrap, "a sufficiently long password")
    before = len(_audit_rows_with_details(path))

    auth.create_invitation("Nicole", "viewer", actor="VonCrush")

    rows = _audit_rows_with_details(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    actor, action, target, result, _ = new_rows[0]
    assert action == "auth.invitation.created"
    assert result == "success"
    assert target is not None  # internal identity for Nicole
    assert actor == "VonCrush"


def test_invite_audit_contains_role_not_secret(auth_db) -> None:
    import json as _json
    path, auth = auth_db
    before = len(_audit_rows_with_details(path))

    auth.create_invitation("Nicole", "operator", actor="VonCrush")

    rows = _audit_rows_with_details(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    _, _, _, _, details_str = new_rows[0]
    details = _json.loads(details_str)
    assert details.get("role") == "operator"
    # No secrets must appear in the stored details
    forbidden = {"password", "token_hash", "password_hash"}
    for bad in forbidden:
        assert bad not in _json.dumps(details).lower()


def test_suspend_emits_audit_on_success(auth_db) -> None:
    path, auth = auth_db
    # Create Nicole as a real user first
    invitation = auth.create_invitation("Nicole", "viewer")
    auth.claim("Nicole", invitation, "a sufficiently long password")
    before = len(_audit_rows_with_details(path))

    auth.suspend("Nicole", "VonCrush")

    rows = _audit_rows_with_details(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    actor, action, target, result, _ = new_rows[0]
    assert action == "auth.access.suspended"
    assert result == "success"
    assert target is not None  # internal identity for Nicole
    assert actor == "VonCrush"


def test_suspend_nonexistent_user_emits_failure_audit(auth_db) -> None:
    path, auth = auth_db
    before = len(_audit_rows_with_details(path))

    with pytest.raises(ValueError):
        auth.suspend("ghost-player", "VonCrush")

    rows = _audit_rows_with_details(path)
    new_rows = rows[before:]
    assert len(new_rows) == 1
    _, action, _, result, _ = new_rows[0]
    assert action == "auth.access.suspended"
    assert result == "failure"

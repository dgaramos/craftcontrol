import sqlite3
import tempfile
import unittest
from pathlib import Path

from minecraft_manager.auth.service import AuthService
from minecraft_manager.repository import StateRepository
from minecraft_manager.auth.http import auth_api, install_auth, require
from flask import Flask, jsonify


class AuthServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "manager.db"
        repository = StateRepository(self.path)
        repository.initialize()
        repository.observe_player("VonCrush", True, "123")
        repository.observe_player("Nicole", False, "456")
        self.auth = AuthService(self.path, idle_seconds=60, absolute_seconds=120)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_bootstrap_claim_creates_first_owner_and_one_time_session(self) -> None:
        invitation = self.auth.bootstrap("VonCrush")
        session, user = self.auth.claim("VonCrush", invitation, "correct horse battery")
        self.assertEqual(user["role"], "owner")
        self.assertIn("*", user["capabilities"])
        self.assertEqual(self.auth.authenticate(session)["name"], "VonCrush")
        with self.assertRaisesRegex(ValueError, "invalid or expired"):
            self.auth.claim("VonCrush", invitation, "another secure password")
        with self.assertRaisesRegex(ValueError, "active owner"):
            self.auth.bootstrap("VonCrush")

    def test_login_logout_and_alias_identity(self) -> None:
        invitation = self.auth.create_invitation("Nicole", "operator")
        first_session, _ = self.auth.claim("Nicole", invitation, "a sufficiently long password")
        self.auth.logout(first_session)
        self.assertIsNone(self.auth.authenticate(first_session))
        second_session, user = self.auth.login("Nicole", "a sufficiently long password")
        self.assertEqual(user["role"], "operator")
        self.assertIsNotNone(self.auth.authenticate(second_session))

    def test_rejects_unknown_player_and_short_password(self) -> None:
        with self.assertRaisesRegex(ValueError, "not been observed"):
            self.auth.create_invitation("Stranger", "viewer")
        invitation = self.auth.create_invitation("Nicole", "viewer")
        with self.assertRaisesRegex(ValueError, "8 to 128"):
            self.auth.claim("Nicole", invitation, "short")

    def test_accepts_eight_character_password(self) -> None:
        invitation = self.auth.create_invitation("Nicole", "viewer")
        session, user = self.auth.claim("Nicole", invitation, "12345678")
        self.assertEqual(user["role"], "viewer")
        self.assertIsNotNone(self.auth.authenticate(session))

    def test_tokens_and_passwords_are_not_stored_in_plaintext(self) -> None:
        invitation = self.auth.create_invitation("Nicole", "viewer")
        self.auth.claim("Nicole", invitation, "a sufficiently long password")
        with sqlite3.connect(self.path) as connection:
            token_hash = connection.execute("SELECT token_hash FROM panel_invitations").fetchone()[0]
            password_hash = connection.execute("SELECT password_hash FROM panel_accounts").fetchone()[0]
        self.assertNotEqual(token_hash, invitation)
        self.assertNotIn("sufficiently", password_hash)
        self.assertTrue(password_hash.startswith("scrypt$"))

    def test_role_capabilities_are_enforced(self) -> None:
        viewer = {"capabilities": ["server.read"]}
        self.auth.require_capability(viewer, "server.read")
        with self.assertRaises(PermissionError):
            self.auth.require_capability(viewer, "world.manage")

    def test_owner_can_list_access_and_last_owner_cannot_be_suspended(self) -> None:
        invitation = self.auth.bootstrap("VonCrush")
        self.auth.claim("VonCrush", invitation, "ownerpass")
        access = {item["name"]: item for item in self.auth.access_list()}
        self.assertEqual(access["VonCrush"]["role"], "owner")
        with self.assertRaisesRegex(ValueError, "last active owner"):
            self.auth.suspend("VonCrush", "test-owner")

    def test_suspension_revokes_sessions_without_deleting_player(self) -> None:
        invitation = self.auth.create_invitation("Nicole", "operator")
        session, _ = self.auth.claim("Nicole", invitation, "operator1")
        self.auth.suspend("Nicole", "test-owner")
        self.assertIsNone(self.auth.authenticate(session))
        access = {item["name"]: item for item in self.auth.access_list()}
        self.assertEqual(access["Nicole"]["status"], "suspended")

    def test_http_boundary_rejects_anonymous_and_sets_secure_session_cookie(self) -> None:
        invitation = self.auth.create_invitation("Nicole", "viewer")
        app = Flask(__name__)
        install_auth(app, self.auth, "local", secure_cookie=True)
        app.register_blueprint(auth_api)

        @app.get("/api/private")
        def private():
            return jsonify(ok=True)

        @app.post("/api/world-test")
        @require("world.manage")
        def world_test():
            return jsonify(ok=True)

        client = app.test_client()
        self.assertEqual(client.get("/api/private").status_code, 401)
        response = client.post("/api/auth/claim", json={
            "player": "Nicole", "token": invitation, "password": "a sufficiently long password",
        })
        self.assertEqual(response.status_code, 200)
        cookie = response.headers["Set-Cookie"]
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertEqual(client.get("/api/private", base_url="https://localhost").status_code, 200)
        csrf_token = response.get_json()["csrf_token"]
        missing = client.post("/api/world-test", base_url="https://localhost")
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(missing.get_json()["error"], "invalid or missing CSRF token")
        invalid = client.post("/api/world-test", base_url="https://localhost", headers={"X-CSRF-Token": "invalid"})
        self.assertEqual(invalid.status_code, 403)
        cross_origin = client.post(
            "/api/world-test", base_url="https://localhost",
            headers={"X-CSRF-Token": csrf_token, "Origin": "https://attacker.example"},
        )
        self.assertEqual(cross_origin.status_code, 403)
        self.assertEqual(cross_origin.get_json()["error"], "invalid request origin")
        authorized_csrf = client.post(
            "/api/world-test", base_url="https://localhost",
            headers={"X-CSRF-Token": csrf_token, "Origin": "https://localhost"},
        )
        self.assertEqual(authorized_csrf.status_code, 403)
        self.assertEqual(authorized_csrf.get_json()["error"], "insufficient permission")

    def test_csrf_token_is_session_bound_and_protects_logout(self) -> None:
        invitation = self.auth.create_invitation("Nicole", "operator")
        app = Flask(__name__)
        install_auth(app, self.auth, "local", secure_cookie=False)
        app.register_blueprint(auth_api)
        client = app.test_client()
        claim = client.post("/api/auth/claim", json={
            "player": "Nicole", "token": invitation, "password": "a sufficiently long password",
        })
        csrf_token = claim.get_json()["csrf_token"]
        self.assertEqual(len(csrf_token), 64)
        self.assertEqual(client.post("/api/auth/logout").status_code, 403)
        self.assertEqual(client.get("/api/auth/me").status_code, 200)
        logout = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf_token})
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(client.get("/api/auth/me").status_code, 401)

    def test_csrf_tokens_cannot_be_reused_across_sessions(self) -> None:
        first, _ = self.auth.claim(
            "Nicole", self.auth.create_invitation("Nicole", "operator"), "a sufficiently long password",
        )
        second, _ = self.auth.login("Nicole", "a sufficiently long password")
        self.assertNotEqual(self.auth.csrf_token(first), self.auth.csrf_token(second))
        self.assertFalse(self.auth.verify_csrf(second, self.auth.csrf_token(first)))

    def test_expired_session_is_rejected_before_csrf_validation(self) -> None:
        invitation = self.auth.create_invitation("Nicole", "operator")
        app = Flask(__name__)
        expired_auth = AuthService(self.path, idle_seconds=-1, absolute_seconds=120)
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
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "authentication required")

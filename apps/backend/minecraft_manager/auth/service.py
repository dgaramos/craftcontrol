from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Any
from contextlib import contextmanager
from collections.abc import Iterator

from .._db import _record_connection_wait, _record_contention_failure


ROLE_CAPABILITIES = {
    "viewer": {"server.read"},
    "operator": {
        "server.read", "server.configure", "world.manage", "players.manage_permissions",
        "server.lifecycle.start", "server.lifecycle.restart",
    },
    "owner": {"*"},
}


class AuthService:
    SCRYPT_N = 1 << 14
    SCRYPT_R = 8
    SCRYPT_P = 1
    SESSION_TOUCH_INTERVAL_SECONDS = 60

    def __init__(self, database: Path, idle_seconds: int = 43200, absolute_seconds: int = 604800) -> None:
        self.database = database
        self.idle_seconds = idle_seconds
        self.absolute_seconds = absolute_seconds

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        started = time.perf_counter()
        connection = sqlite3.connect(self.database, timeout=30)
        _record_connection_wait((time.perf_counter() - started) * 1000)
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except sqlite3.OperationalError as error:
            connection.rollback()
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                _record_contention_failure()
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def csrf_token(session_token: str) -> str:
        """Derive a CSRF token bound to an opaque session without persisting another secret."""
        return hmac.new(session_token.encode(), b"craftcontrol:csrf:v1", hashlib.sha256).hexdigest()

    def verify_csrf(self, session_token: str | None, candidate: str | None) -> bool:
        if not session_token or not candidate:
            return False
        return hmac.compare_digest(self.csrf_token(session_token), candidate)

    @classmethod
    def hash_password(cls, password: str) -> str:
        cls.validate_password(password)
        salt = os.urandom(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=cls.SCRYPT_N, r=cls.SCRYPT_R, p=cls.SCRYPT_P, dklen=32)
        return f"scrypt${cls.SCRYPT_N}${cls.SCRYPT_R}${cls.SCRYPT_P}${salt.hex()}${digest.hex()}"

    @classmethod
    def verify_password(cls, password: str, encoded: str | None) -> bool:
        if not encoded:
            return False
        try:
            algorithm, n, r, p, salt, expected = encoded.split("$")
            if algorithm != "scrypt":
                return False
            actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
            return hmac.compare_digest(actual, bytes.fromhex(expected))
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_password(password: str) -> None:
        if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
            raise ValueError("password must contain 8 to 128 characters")

    def create_invitation(self, player: str, role: str, actor: str | None = None, lifetime: int = 900) -> str:
        if role not in ROLE_CAPABILITIES:
            raise ValueError("invalid panel role")
        now = time.time()
        token = secrets.token_urlsafe(24)
        with self._connect() as connection:
            identity = self._resolve_identity(connection, player)
            connection.execute(
                "INSERT INTO panel_accounts(identity,role,status,created_at,updated_at) VALUES(?,?,'invited',?,?) "
                "ON CONFLICT(identity) DO UPDATE SET role=CASE WHEN panel_accounts.status='active' THEN panel_accounts.role "
                "ELSE excluded.role END,status=CASE WHEN panel_accounts.status='active' THEN panel_accounts.status "
                "ELSE 'invited' END,updated_at=excluded.updated_at",
                (identity, role, now, now),
            )
            connection.execute("DELETE FROM panel_invitations WHERE identity=? AND used_at IS NULL", (identity,))
            connection.execute(
                "INSERT INTO panel_invitations(token_hash,identity,role,created_at,expires_at,created_by) VALUES(?,?,?,?,?,?)",
                (self._token_hash(token), identity, role, now, now + lifetime, actor),
            )
            self._audit(connection, actor, "auth.invitation.created", identity, "success", {"role": role})
        return token

    def bootstrap(self, player: str) -> str:
        with self._connect() as connection:
            if connection.execute("SELECT 1 FROM panel_accounts WHERE role='owner' AND status='active'").fetchone():
                raise ValueError("an active owner already exists")
        return self.create_invitation(player, "owner", actor=None, lifetime=1800)

    def create_recovery(self, player: str, lifetime: int = 900) -> tuple[str, str]:
        """Create a one-time credential reset without changing the account's panel role."""
        with self._connect() as connection:
            identity = self._resolve_identity(connection, player)
            account = connection.execute(
                "SELECT role,status FROM panel_accounts WHERE identity=?", (identity,),
            ).fetchone()
            if not account or account[1] != "active":
                raise ValueError("player has no active panel account")
            role = str(account[0])
        return self.create_invitation(player, role, actor=identity, lifetime=lifetime), role

    def claim(self, player: str, token: str, password: str) -> tuple[str, dict[str, Any]]:
        password_hash = self.hash_password(password)
        now = time.time()
        with self._connect() as connection:
            identity = self._resolve_identity(connection, player)
            invitation = connection.execute(
                "SELECT role,expires_at,used_at FROM panel_invitations WHERE token_hash=? AND identity=?",
                (self._token_hash(token), identity),
            ).fetchone()
            if not invitation or invitation[2] is not None or float(invitation[1]) < now:
                self._audit(connection, identity, "auth.claim", identity, "denied", {})
                raise ValueError("invalid or expired invitation")
            current = connection.execute("SELECT role,status FROM panel_accounts WHERE identity=?", (identity,)).fetchone()
            if current and current[0] == "owner" and current[1] == "active" and invitation[0] != "owner":
                owners = connection.execute("SELECT count(*) FROM panel_accounts WHERE role='owner' AND status='active'").fetchone()[0]
                if owners <= 1:
                    raise ValueError("cannot demote the last active owner")
            connection.execute("UPDATE panel_invitations SET used_at=? WHERE token_hash=?", (now, self._token_hash(token)))
            connection.execute(
                "UPDATE panel_accounts SET role=?,status='active',password_hash=?,updated_at=? WHERE identity=?",
                (invitation[0], password_hash, now, identity),
            )
            self._audit(connection, identity, "auth.claim", identity, "success", {"role": invitation[0]})
            return self._create_session(connection, identity, now)

    def login(self, player: str, password: str) -> tuple[str, dict[str, Any]]:
        key = player.casefold()[:64]
        now = time.time()
        with self._connect() as connection:
            failures = connection.execute(
                "SELECT count(*) FROM auth_attempts WHERE login_key=? AND successful=0 AND occurred_at>?",
                (key, now - 900),
            ).fetchone()[0]
            if failures >= 5:
                raise ValueError("too many login attempts; try again later")
            try:
                identity = self._resolve_identity(connection, player)
            except ValueError:
                identity = ""
            row = connection.execute(
                "SELECT password_hash,status FROM panel_accounts WHERE identity=?", (identity,)
            ).fetchone() if identity else None
            valid = bool(row and row[1] == "active" and self.verify_password(password, row[0]))
            connection.execute("INSERT INTO auth_attempts(login_key,occurred_at,successful) VALUES(?,?,?)", (key, now, int(valid)))
            connection.execute("DELETE FROM auth_attempts WHERE occurred_at<?", (now - 86400,))
            if not valid:
                self._audit(connection, identity or None, "auth.login", None, "denied", {})
                raise ValueError("invalid credentials")
            self._audit(connection, identity, "auth.login", identity, "success", {})
            return self._create_session(connection, identity, now)

    def authenticate(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        now = time.time()
        token_hash = self._token_hash(token)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT s.identity,a.role,a.status,p.current_name,s.idle_expires_at,s.absolute_expires_at,s.revoked_at,s.last_seen_at "
                "FROM panel_sessions s JOIN panel_accounts a ON a.identity=s.identity "
                "JOIN player_profiles p ON p.identity=s.identity WHERE s.token_hash=?",
                (token_hash,),
            ).fetchone()
            if not row or row[2] != "active" or row[6] is not None or min(row[4], row[5]) < now:
                return None
            last_seen_at = float(row[7])
            if now - last_seen_at >= self.SESSION_TOUCH_INTERVAL_SECONDS:
                connection.execute(
                    "UPDATE panel_sessions SET last_seen_at=?,idle_expires_at=? WHERE token_hash=?",
                    (now, min(now + self.idle_seconds, row[5]), token_hash),
                )
            return self._public_user(row[0], row[3], row[1])

    def logout(self, token: str | None) -> None:
        if token:
            with self._connect() as connection:
                connection.execute("UPDATE panel_sessions SET revoked_at=? WHERE token_hash=?", (time.time(), self._token_hash(token)))

    def sessions(self, session_token: str) -> list[dict[str, Any]]:
        """Return safe activity evidence for the authenticated account only."""
        now = time.time()
        current_hash = self._token_hash(session_token)
        with self._connect() as connection:
            identity = connection.execute("SELECT identity FROM panel_sessions WHERE token_hash=?", (current_hash,)).fetchone()
            if not identity:
                raise ValueError("session not found")
            rows = connection.execute(
                "SELECT token_hash,created_at,last_seen_at FROM panel_sessions WHERE identity=? AND revoked_at IS NULL "
                "AND idle_expires_at>=? AND absolute_expires_at>=? ORDER BY last_seen_at DESC",
                (identity[0], now, now),
            ).fetchall()
        return [{"id": hashlib.sha256(row[0].encode()).hexdigest()[:24], "created_at": row[1], "last_seen_at": row[2], "current": hmac.compare_digest(row[0], current_hash)} for row in rows]

    def revoke_session(self, session_token: str, session_id: str) -> None:
        current_hash = self._token_hash(session_token)
        now = time.time()
        with self._connect() as connection:
            identity = connection.execute("SELECT identity FROM panel_sessions WHERE token_hash=?", (current_hash,)).fetchone()
            if not identity:
                raise ValueError("session not found")
            rows = connection.execute("SELECT token_hash FROM panel_sessions WHERE identity=? AND revoked_at IS NULL", (identity[0],)).fetchall()
            target = next((row[0] for row in rows if hmac.compare_digest(hashlib.sha256(row[0].encode()).hexdigest()[:24], session_id)), None)
            if target is None or hmac.compare_digest(target, current_hash):
                raise ValueError("session cannot be revoked")
            connection.execute("UPDATE panel_sessions SET revoked_at=? WHERE token_hash=?", (now, target))

    def revoke_other_sessions(self, session_token: str) -> None:
        with self._connect() as connection:
            identity = connection.execute("SELECT identity FROM panel_sessions WHERE token_hash=?", (self._token_hash(session_token),)).fetchone()
            if not identity:
                raise ValueError("session not found")
            connection.execute("UPDATE panel_sessions SET revoked_at=? WHERE identity=? AND token_hash<>? AND revoked_at IS NULL", (time.time(), identity[0], self._token_hash(session_token)))

    def change_password(self, session_token: str, current_password: str, new_password: str) -> tuple[str, dict[str, Any]]:
        """Replace an authenticated account password and rotate all of its sessions."""
        self.validate_password(current_password)
        password_hash = self.hash_password(new_password)
        now = time.time()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT s.identity,a.password_hash,a.status FROM panel_sessions s "
                "JOIN panel_accounts a ON a.identity=s.identity WHERE s.token_hash=? "
                "AND s.revoked_at IS NULL AND s.idle_expires_at>=? AND s.absolute_expires_at>=?",
                (self._token_hash(session_token), now, now),
            ).fetchone()
            if not row or row[2] != "active" or not self.verify_password(current_password, row[1]):
                raise ValueError("current password is incorrect")
            identity = str(row[0])
            connection.execute(
                "UPDATE panel_accounts SET password_hash=?,updated_at=? WHERE identity=?",
                (password_hash, now, identity),
            )
            connection.execute(
                "UPDATE panel_sessions SET revoked_at=? WHERE identity=? AND revoked_at IS NULL",
                (now, identity),
            )
            return self._create_session(connection, identity, now)

    def access_list(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT p.identity,p.current_name,a.role,a.status,a.updated_at,"
                "(SELECT count(*) FROM panel_sessions s WHERE s.identity=p.identity AND s.revoked_at IS NULL "
                "AND s.absolute_expires_at>?) FROM player_profiles p LEFT JOIN panel_accounts a ON a.identity=p.identity "
                "ORDER BY p.online DESC,p.last_seen_at DESC",
                (time.time(),),
            ).fetchall()
        return [{
            "id": hashlib.sha256(row[0].encode()).hexdigest()[:24], "name": row[1],
            "role": row[2], "status": row[3] or "none", "updated_at": row[4], "active_sessions": row[5],
        } for row in rows]

    def suspend(self, player: str, actor: str) -> None:
        now = time.time()
        with self._connect() as connection:
            identity = self._resolve_identity(connection, player)
            account = connection.execute("SELECT role,status FROM panel_accounts WHERE identity=?", (identity,)).fetchone()
            if not account:
                raise ValueError("player has no panel access")
            if account[0] == "owner" and account[1] == "active":
                owners = connection.execute("SELECT count(*) FROM panel_accounts WHERE role='owner' AND status='active'").fetchone()[0]
                if owners <= 1:
                    raise ValueError("cannot suspend the last active owner")
            connection.execute("UPDATE panel_accounts SET status='suspended',updated_at=? WHERE identity=?", (now, identity))
            connection.execute("UPDATE panel_sessions SET revoked_at=? WHERE identity=? AND revoked_at IS NULL", (now, identity))
            self._audit(connection, actor, "auth.access.suspended", identity, "success", {})

    def require_capability(self, user: dict[str, Any], capability: str) -> None:
        capabilities = set(user.get("capabilities", []))
        if "*" not in capabilities and capability not in capabilities:
            raise PermissionError(capability)

    def _create_session(self, connection: sqlite3.Connection, identity: str, now: float) -> tuple[str, dict[str, Any]]:
        token = secrets.token_urlsafe(32)
        absolute = now + self.absolute_seconds
        connection.execute(
            "INSERT INTO panel_sessions(token_hash,identity,created_at,last_seen_at,idle_expires_at,absolute_expires_at) VALUES(?,?,?,?,?,?)",
            (self._token_hash(token), identity, now, now, min(now + self.idle_seconds, absolute), absolute),
        )
        row = connection.execute(
            "SELECT p.current_name,a.role FROM player_profiles p JOIN panel_accounts a ON a.identity=p.identity WHERE p.identity=?",
            (identity,),
        ).fetchone()
        return token, self._public_user(identity, row[0], row[1])

    @staticmethod
    def _public_user(identity: str, name: str, role: str) -> dict[str, Any]:
        return {
            "id": hashlib.sha256(identity.encode()).hexdigest()[:24],
            "name": name,
            "role": role,
            "capabilities": sorted(ROLE_CAPABILITIES[role]),
        }

    @staticmethod
    def _resolve_identity(connection: sqlite3.Connection, player: str) -> str:
        row = connection.execute(
            "SELECT p.identity FROM player_profiles p LEFT JOIN player_aliases a ON a.identity=p.identity "
            "WHERE lower(p.current_name)=lower(?) OR lower(a.name)=lower(?) ORDER BY p.last_seen_at DESC LIMIT 1",
            (player, player),
        ).fetchone()
        if not row:
            raise ValueError("player has not been observed by this server")
        return str(row[0])

    @staticmethod
    def _audit(connection: sqlite3.Connection, actor: str | None, action: str, target: str | None, result: str, details: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO audit_log(occurred_at,actor_identity,action,target,result,details) VALUES(?,?,?,?,?,?)",
            (time.time(), actor, action, target, result, json.dumps(details, separators=(",", ":"))),
        )

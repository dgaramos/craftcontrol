#!/usr/bin/env python3
"""CraftControl host agent.

Runs on the Docker host (outside all containers). Accepts authenticated
HTTP requests from the CraftControl backend and executes exactly the permitted
host-level operations defined in docs/host-agent-contract.md.

Environment variables:
  HOST_AGENT_BIND          Bind address for the HTTP server. Default: 0.0.0.0:7890
  HOST_AGENT_SECRET_FILE   Path to the shared-secret token file.
                           Default: /etc/craftcontrol/host-agent-token
  HOST_AGENT_COMPOSE_PROJECT  Docker Compose project name. Default: minecraft-bedrock
  HOST_AGENT_COMPOSE_FILE     Path to the docker-compose.yml file.
                              Default: /opt/craftcontrol/docker-compose.yml
  HOST_AGENT_BEDROCK_DATA     Path to the Bedrock data directory.
                              Default: /opt/craftcontrol/data/bedrock
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import socket
import struct
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

VERSION = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("host-agent")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BIND_DEFAULT = "0.0.0.0:7890"
SECRET_FILE_DEFAULT = "/etc/craftcontrol/host-agent-token"
COMPOSE_PROJECT_DEFAULT = "minecraft-bedrock"
COMPOSE_FILE_DEFAULT = "/opt/craftcontrol/docker-compose.yml"
BEDROCK_DATA_DEFAULT = "/opt/craftcontrol/data/bedrock"

HEALTH_TIMEOUT_MIN = 10
HEALTH_TIMEOUT_MAX = 600
HEALTH_TIMEOUT_DEFAULT = 120
RESTART_TIMEOUT_MIN = 10
RESTART_TIMEOUT_MAX = 300
RESTART_TIMEOUT_DEFAULT = 60

# RakNet constants
RAKNET_MAGIC = bytes([0x00, 0xFF, 0xFF, 0x00, 0xFE, 0xFE, 0xFE, 0xFE, 0xFD, 0xFD, 0xFD, 0xFD, 0x12, 0x34, 0x56, 0x78])
BEDROCK_DEFAULT_PORT = 19132
PROBE_INTERVAL_SECONDS = 5
PROBE_READ_TIMEOUT_SECONDS = 2

# Results are retained at least this long after completion (seconds)
RESULT_RETENTION_SECONDS = 600

MAX_BODY_BYTES = 64 * 1024


def _load_token(path: str) -> str:
    p = Path(path)
    try:
        token = p.read_text().strip()
    except OSError as exc:
        raise RuntimeError(f"Cannot read secret file {path}: {exc}") from exc
    if not token:
        raise RuntimeError(f"Secret file {path} is empty")
    return token


def _load_config() -> dict[str, str]:
    return {
        "bind": os.environ.get("HOST_AGENT_BIND", BIND_DEFAULT),
        "secret_file": os.environ.get("HOST_AGENT_SECRET_FILE", SECRET_FILE_DEFAULT),
        "compose_project": os.environ.get("HOST_AGENT_COMPOSE_PROJECT", COMPOSE_PROJECT_DEFAULT),
        "compose_file": os.environ.get("HOST_AGENT_COMPOSE_FILE", COMPOSE_FILE_DEFAULT),
        "bedrock_data": os.environ.get("HOST_AGENT_BEDROCK_DATA", BEDROCK_DATA_DEFAULT),
    }


# ---------------------------------------------------------------------------
# In-memory operation store
# ---------------------------------------------------------------------------

class OperationRecord:
    def __init__(self, operation_id: str) -> None:
        self.operation_id = operation_id
        self.status = "running"          # running | done
        self.current_stage: str | None = "prepare"
        self.outcome: str | None = None  # ok | error
        self.executor_ref: str | None = None
        self.health_reached: bool | None = None
        self.failed_stage: str | None = None
        self.detail: str | None = None
        self.error_code: str | None = None
        self.exception_type: str | None = None
        self.completed_at: float | None = None

    def to_running_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "status": "running",
            "current_stage": self.current_stage,
        }

    def to_done_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "status": "done",
            "outcome": self.outcome,
            "executor_ref": self.executor_ref,
            "health_reached": self.health_reached,
            "failed_stage": self.failed_stage,
            "detail": self.detail,
            "error_code": self.error_code,
            "exception_type": self.exception_type,
        }


class OperationStore:
    def __init__(self, time_func: Callable[[], float] = time.monotonic) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, OperationRecord] = {}
        self._time_func = time_func

    def get(self, operation_id: str) -> OperationRecord | None:
        with self._lock:
            return self._records.get(operation_id)

    def create(self, operation_id: str) -> OperationRecord | None:
        """Create a record. Returns None if already exists (conflict)."""
        with self._lock:
            if operation_id in self._records:
                return None
            rec = OperationRecord(operation_id)
            self._records[operation_id] = rec
            return rec

    def update(self, operation_id: str, **kwargs: Any) -> None:
        with self._lock:
            rec = self._records.get(operation_id)
            if rec is None:
                return
            for k, v in kwargs.items():
                setattr(rec, k, v)

    def evict_expired(self) -> None:
        """Remove completed records older than RESULT_RETENTION_SECONDS."""
        now = self._time_func()
        cutoff = now - RESULT_RETENTION_SECONDS
        with self._lock:
            expired = [
                oid for oid, rec in self._records.items()
                if rec.completed_at is not None and rec.completed_at < cutoff
            ]
            for oid in expired:
                del self._records[oid]


# ---------------------------------------------------------------------------
# Health probe (RakNet UDP unconnected ping)
# ---------------------------------------------------------------------------

def _build_unconnected_ping() -> bytes:
    """Build a 33-byte RakNet unconnected ping datagram."""
    packet_id = b'\x01'
    timestamp = struct.pack('>Q', int(time.monotonic() * 1000))
    client_guid = struct.pack('>Q', uuid.uuid4().int & 0xFFFFFFFFFFFFFFFF)
    return packet_id + timestamp + RAKNET_MAGIC + client_guid


def _validate_pong(data: bytes) -> bool:
    """Return True if data is a valid RakNet ID_UNCONNECTED_PONG."""
    if len(data) < 35:
        return False
    if data[0] != 0x1C:
        return False
    # magic is at bytes 17-32 (inclusive)
    if data[17:33] != RAKNET_MAGIC:
        return False
    return True


def _probe_bedrock(host: str, port: int, timeout: float) -> bool:
    """Send one unconnected ping and return True on valid pong."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(_build_unconnected_ping(), (host, port))
            data, _ = sock.recvfrom(4096)
            return _validate_pong(data)
        finally:
            sock.close()
    except OSError:
        return False


def _wait_for_health(host: str, port: int, timeout_seconds: int) -> bool:
    """Poll the Bedrock health probe. Returns True if healthy within timeout."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _probe_bedrock(host, port, PROBE_READ_TIMEOUT_SECONDS):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(PROBE_INTERVAL_SECONDS, remaining))
    return False


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

_ENUM_ALLOWED: dict[str, frozenset[str]] = {
    "difficulty": frozenset({"peaceful", "easy", "normal", "hard"}),
    "gamemode": frozenset({"survival", "creative", "adventure"}),
    "default_player_permission_level": frozenset({"visitor", "member", "operator"}),
    "chat_restriction": frozenset({"None", "Dropped", "Disabled"}),
    "level_type": frozenset({"DEFAULT", "FLAT", "LEGACY"}),
    "server_authoritative_movement": frozenset({
        "client-auth",
        "client-auth-with-rewind",
        "server-auth",
        "server-auth-with-rewind",
    }),
}

_INT_FIELDS = frozenset({
    "max_players", "server_port", "server_portv6", "view_distance",
    "tick_distance", "player_idle_timeout", "max_threads",
    "compression_threshold", "player_movement_score_threshold",
    "player_movement_duration_threshold_in_ms",
})

_PORT_FIELDS = frozenset({"server_port", "server_portv6"})

_BOOL_FIELDS = frozenset({
    "online_mode", "white_list", "allow_list", "allow_cheats",
    "enable_lan_visibility", "texturepack_required",
    "content_log_file_enabled", "correct_player_movement",
    "server_authoritative_block_breaking",
    "disable_player_interaction",
    "client_side_chunk_generation_enabled", "block_network_ids_are_hashes",
    "disable_persona", "disable_custom_skins",
})

_FLOAT_FIELDS = frozenset({
    "player_movement_action_direction_threshold",
    "player_movement_distance_threshold",
    "server_build_radius_ratio",
})

_INTENDED_STATE_FIELDS = frozenset({
    "server_name",
    "difficulty",
    "max_players",
    "gamemode",
    "server_port",
    "level_name",
    "level_seed",
    "online_mode",
    "white_list",
    "allow_list",
    "view_distance",
    "tick_distance",
    "player_idle_timeout",
    "max_threads",
    "level_type",
    "allow_cheats",
    "server_portv6",
    "enable_lan_visibility",
    "default_player_permission_level",
    "texturepack_required",
    "content_log_file_enabled",
    "compression_threshold",
    "server_authoritative_movement",
    "player_movement_score_threshold",
    "player_movement_action_direction_threshold",
    "player_movement_distance_threshold",
    "player_movement_duration_threshold_in_ms",
    "correct_player_movement",
    "server_authoritative_block_breaking",
    "chat_restriction",
    "disable_player_interaction",
    "client_side_chunk_generation_enabled",
    "block_network_ids_are_hashes",
    "disable_persona",
    "disable_custom_skins",
    "server_build_radius_ratio",
})


def _validate_intended_state_values(intended_state: dict[str, Any]) -> str | None:
    """Validate intended_state field values. Returns an error message or None."""
    for field, value in intended_state.items():
        if field in _ENUM_ALLOWED:
            if str(value) not in _ENUM_ALLOWED[field]:
                allowed = ", ".join(sorted(_ENUM_ALLOWED[field]))
                return f"'{field}' must be one of: {allowed}"
        elif field in _INT_FIELDS:
            if not isinstance(value, int) or isinstance(value, bool):
                return f"'{field}' must be an integer"
            if field in _PORT_FIELDS and not (1 <= value <= 65535):
                return f"'{field}' must be between 1 and 65535"
        elif field in _BOOL_FIELDS:
            if not isinstance(value, bool):
                return f"'{field}' must be a boolean"
        elif field in _FLOAT_FIELDS:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return f"'{field}' must be a number"
        else:
            # Text field: reject control characters that break the properties format
            str_val = str(value)
            if "\n" in str_val or "\r" in str_val:
                return f"'{field}' must not contain newline characters"
    return None


def _render_field_value(field: str, value: Any) -> str:
    """Render an intended_state value to a server.properties-compatible string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class OperationExecutor:
    def __init__(
        self,
        config: dict[str, str],
        subprocess_run: Any = None,
    ) -> None:
        self._config = config
        self._subprocess_run = subprocess_run or subprocess.run

    def run(self, record: OperationRecord, store: OperationStore, intended_state: dict[str, Any], health_timeout: int, restart_timeout: int) -> None:
        """Execute operation stages. Mutates record via store.update."""
        operation_id = record.operation_id

        # Stage: prepare
        try:
            store.update(operation_id, current_stage="prepare")
            self._prepare(intended_state)
        except Exception as exc:
            logger.exception("prepare failed for %s", operation_id)
            store.update(
                operation_id,
                status="done",
                current_stage=None,
                outcome="error",
                executor_ref=None,
                health_reached=False,
                failed_stage="prepare",
                detail=str(exc),
                error_code="preparation_write_failed",
                exception_type=type(exc).__name__,
                completed_at=time.monotonic(),
            )
            return

        # Stage: restart
        executor_ref: str | None = None
        try:
            store.update(operation_id, current_stage="restart")
            executor_ref = self._restart(restart_timeout)
        except subprocess.TimeoutExpired as exc:
            logger.error("restart timeout for %s: %s", operation_id, exc)
            store.update(
                operation_id,
                status="done",
                current_stage=None,
                outcome="error",
                executor_ref=None,
                health_reached=False,
                failed_stage="restart",
                detail="docker compose restart timed out",
                error_code="restart_timeout",
                exception_type=type(exc).__name__,
                completed_at=time.monotonic(),
            )
            return
        except Exception as exc:
            logger.exception("restart failed for %s", operation_id)
            store.update(
                operation_id,
                status="done",
                current_stage=None,
                outcome="error",
                executor_ref=None,
                health_reached=False,
                failed_stage="restart",
                detail=str(exc),
                error_code="restart_command_failed",
                exception_type=type(exc).__name__,
                completed_at=time.monotonic(),
            )
            return

        # Stage: health_wait
        store.update(operation_id, current_stage="health_wait")
        try:
            port = int(intended_state.get("server_port", BEDROCK_DEFAULT_PORT))
            health_reached = _wait_for_health("127.0.0.1", port, health_timeout)
        except Exception as exc:
            logger.exception("health_wait failed for %s", operation_id)
            store.update(
                operation_id,
                status="done",
                current_stage=None,
                outcome="error",
                executor_ref=executor_ref,
                health_reached=False,
                failed_stage="health_wait",
                detail=str(exc),
                error_code="health_wait_error",
                exception_type=type(exc).__name__,
                completed_at=time.monotonic(),
            )
            return

        if health_reached:
            elapsed_msg = "Server reached healthy state"
            store.update(
                operation_id,
                status="done",
                current_stage=None,
                outcome="ok",
                executor_ref=executor_ref,
                health_reached=True,
                failed_stage=None,
                detail=elapsed_msg,
                error_code=None,
                exception_type=None,
                completed_at=time.monotonic(),
            )
            logger.info("operation %s completed successfully (executor_ref=%s)", operation_id, executor_ref)
        else:
            store.update(
                operation_id,
                status="done",
                current_stage=None,
                outcome="error",
                executor_ref=executor_ref,
                health_reached=False,
                failed_stage="health_wait",
                detail=f"Server did not reach healthy state within {health_timeout}s",
                error_code="health_probe_timeout",
                exception_type=None,
                completed_at=time.monotonic(),
            )
            logger.error("operation %s health probe timed out after %ss", operation_id, health_timeout)

    def _prepare(self, intended_state: dict[str, Any]) -> None:
        """Merge-write server.properties in the Bedrock data directory.

        Reads the existing file (if present), updates only the keys supplied in
        ``intended_state``, and preserves all other lines (comments, blank lines,
        unknown keys) in their original order.
        """
        data_dir = Path(self._config["bedrock_data"])
        props_file = data_dir / "server.properties"

        field_map = {
            "server_name": "server-name",
            "difficulty": "difficulty",
            "max_players": "max-players",
            "gamemode": "gamemode",
            "server_port": "server-port",
            "level_name": "level-name",
            "level_seed": "level-seed",
            "online_mode": "online-mode",
            "white_list": "white-list",
            "allow_list": "allow-list",
            "view_distance": "view-distance",
            "tick_distance": "tick-distance",
            "player_idle_timeout": "player-idle-timeout",
            "max_threads": "max-threads",
            "level_type": "level-type",
            "allow_cheats": "allow-cheats",
            "server_portv6": "server-portv6",
            "enable_lan_visibility": "enable-lan-visibility",
            "default_player_permission_level": "default-player-permission-level",
            "texturepack_required": "texturepack-required",
            "content_log_file_enabled": "content-log-file-enabled",
            "compression_threshold": "compression-threshold",
            "server_authoritative_movement": "server-authoritative-movement",
            "player_movement_score_threshold": "player-movement-score-threshold",
            "player_movement_action_direction_threshold": "player-movement-action-direction-threshold",
            "player_movement_distance_threshold": "player-movement-distance-threshold",
            "player_movement_duration_threshold_in_ms": "player-movement-duration-threshold-in-ms",
            "correct_player_movement": "correct-player-movement",
            "server_authoritative_block_breaking": "server-authoritative-block-breaking",
            "chat_restriction": "chat-restriction",
            "disable_player_interaction": "disable-player-interaction",
            "client_side_chunk_generation_enabled": "client-side-chunk-generation-enabled",
            "block_network_ids_are_hashes": "block-network-ids-are-hashes",
            "disable_persona": "disable-persona",
            "disable_custom_skins": "disable-custom-skins",
            "server_build_radius_ratio": "server-build-radius-ratio",
        }

        # Build the validated update map (prop_key → rendered value)
        updates: dict[str, str] = {}
        for field, prop_key in field_map.items():
            if field in intended_state:
                updates[prop_key] = _render_field_value(field, intended_state[field])

        if not updates:
            logger.info("No configuration fields to write in prepare stage")
            return

        if not data_dir.is_dir():
            raise RuntimeError(f"Bedrock data directory not found: {data_dir}")

        # Read existing file to preserve unknown keys and comments
        existing_lines: list[str] = []
        if props_file.exists():
            try:
                raw = props_file.read_text(encoding="utf-8")
                existing_lines = raw.splitlines(keepends=True)
            except OSError as exc:
                raise RuntimeError(
                    f"Cannot read existing server.properties; aborting to avoid data loss: {exc}"
                ) from exc

        # Merge: replace lines whose key appears in updates; collect written keys
        merged: list[str] = []
        written: set[str] = set()
        for line in existing_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    merged.append(f"{k}={updates[k]}\n")
                    written.add(k)
                    continue
            merged.append(line if line.endswith("\n") else line + "\n" if line else line)

        # Append keys not found in the existing file
        for k, v in updates.items():
            if k not in written:
                merged.append(f"{k}={v}\n")

        tmp_file = props_file.with_suffix(".tmp")
        try:
            tmp_file.write_text("".join(merged), encoding="utf-8")
            tmp_file.replace(props_file)
        except OSError as exc:
            raise RuntimeError(f"Failed to write server.properties: {exc}") from exc

        logger.info("Wrote/updated %d properties in %s", len(updates), props_file)

    def _restart(self, timeout: int) -> str:
        """Run docker compose restart and return an executor_ref string."""
        project = self._config["compose_project"]
        compose_file = self._config["compose_file"]
        cmd = [
            "docker", "compose",
            "--project-name", project,
            "--file", compose_file,
            "restart", "minecraft-server",
        ]
        logger.info("Running: %s (timeout=%ds)", " ".join(cmd), timeout)
        result = self._subprocess_run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(f"docker compose restart failed (exit {result.returncode}): {stderr}")
        ts = int(time.time())
        return f"{project}_minecraft-server_restart_{ts}"


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class AgentHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the host agent."""

    # Set by the server before accepting connections
    token: str = ""
    store: OperationStore
    executor: OperationExecutor

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        logger.info(format, *args)

    def _send_json(self, status: int, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authenticate(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        received = auth[len("Bearer "):]
        return hmac.compare_digest(received.encode(), self.token.encode())

    def _require_auth(self) -> bool:
        if not self._authenticate():
            logger.warning("Unauthorized request from %s: %s %s", self.client_address, self.command, self.path)
            self._send_json(401, {"error": "unauthorized", "message": "Invalid or missing token"})
            return False
        return True

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._send_json(400, {"error": "bad_request", "message": "Invalid Content-Length"})
            return None
        if length < 0 or length > MAX_BODY_BYTES:
            self._send_json(400, {"error": "bad_request", "message": "Request body too large or invalid"})
            return None
        if length == 0:
            return {}
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": "bad_request", "message": f"Invalid JSON: {exc}"})
            return None
        if not isinstance(body, dict):
            self._send_json(400, {"error": "bad_request", "message": "Request body must be a JSON object"})
            return None
        return body

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/v1/health":
            self._handle_health()
        elif path.startswith("/v1/status/"):
            if not self._require_auth():
                return
            operation_id = path[len("/v1/status/"):]
            self._handle_status(operation_id)
        else:
            self._send_json(404, {"error": "not_found", "message": "Unknown path"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/v1/execute":
            if not self._require_auth():
                return
            body = self._read_json_body()
            if body is None:
                return
            self._handle_execute(body)
        else:
            self._send_json(404, {"error": "not_found", "message": "Unknown path"})

    def _handle_health(self) -> None:
        self._send_json(200, {"status": "ok", "version": VERSION})

    def _handle_status(self, operation_id: str) -> None:
        # Evict expired records opportunistically
        self.store.evict_expired()

        rec = self.store.get(operation_id)
        if rec is None:
            self._send_json(404, {
                "error": "not_found",
                "operation_id": operation_id,
                "message": "Unknown operation",
            })
            return

        if rec.status == "running":
            self._send_json(200, rec.to_running_dict())
        else:
            self._send_json(200, rec.to_done_dict())

    def _handle_execute(self, body: dict[str, Any]) -> None:
        # Validate required fields
        operation_id = body.get("operation_id")
        if not operation_id or not isinstance(operation_id, str):
            self._send_json(400, {"error": "bad_request", "message": "'operation_id' is required and must be a string"})
            return

        intended_state = body.get("intended_state")
        if not isinstance(intended_state, dict):
            self._send_json(400, {"error": "bad_request", "message": "'intended_state' is required and must be an object"})
            return

        # Reject unknown fields in intended_state
        unknown = set(intended_state) - _INTENDED_STATE_FIELDS
        if unknown:
            self._send_json(400, {
                "error": "bad_request",
                "message": f"Unrecognised fields in intended_state: {', '.join(sorted(unknown))}",
            })
            return

        # Validate field values (type, domain, and injection safety)
        value_error = _validate_intended_state_values(intended_state)
        if value_error is not None:
            self._send_json(400, {"error": "bad_request", "message": value_error})
            return

        # Validate optional timeouts
        health_timeout = body.get("health_timeout_seconds", HEALTH_TIMEOUT_DEFAULT)
        restart_timeout = body.get("restart_timeout_seconds", RESTART_TIMEOUT_DEFAULT)

        if not isinstance(health_timeout, int) or not (HEALTH_TIMEOUT_MIN <= health_timeout <= HEALTH_TIMEOUT_MAX):
            self._send_json(400, {
                "error": "bad_request",
                "message": f"'health_timeout_seconds' must be an integer between {HEALTH_TIMEOUT_MIN} and {HEALTH_TIMEOUT_MAX}",
            })
            return

        if not isinstance(restart_timeout, int) or not (RESTART_TIMEOUT_MIN <= restart_timeout <= RESTART_TIMEOUT_MAX):
            self._send_json(400, {
                "error": "bad_request",
                "message": f"'restart_timeout_seconds' must be an integer between {RESTART_TIMEOUT_MIN} and {RESTART_TIMEOUT_MAX}",
            })
            return

        # Check for duplicate / replay
        existing = self.store.get(operation_id)
        if existing is not None:
            if existing.status == "running":
                self._send_json(409, {
                    "error": "conflict",
                    "operation_id": operation_id,
                    "message": "Operation already in progress",
                })
                return
            # Done — idempotent replay
            self._send_json(202, {"operation_id": operation_id, "status": "accepted"})
            return

        record = self.store.create(operation_id)
        if record is None:
            # Race: another thread created it between our get() and create()
            self._send_json(409, {
                "error": "conflict",
                "operation_id": operation_id,
                "message": "Operation already in progress",
            })
            return

        logger.info("Accepted operation %s", operation_id)

        thread = threading.Thread(
            target=self.executor.run,
            args=(record, self.store, intended_state, health_timeout, restart_timeout),
            daemon=True,
            name=f"op-{operation_id[:8]}",
        )
        thread.start()

        self._send_json(202, {"operation_id": operation_id, "status": "accepted"})


# ---------------------------------------------------------------------------
# Server wiring
# ---------------------------------------------------------------------------

def build_handler_class(token: str, store: OperationStore, executor: OperationExecutor) -> type:
    """Return an AgentHandler subclass with dependencies injected as class attributes."""

    class BoundHandler(AgentHandler):
        pass

    BoundHandler.token = token
    BoundHandler.store = store  # type: ignore[assignment]
    BoundHandler.executor = executor  # type: ignore[assignment]
    return BoundHandler


def run(*, bind: str, token: str, config: dict[str, str], subprocess_run: Any = None) -> None:
    host, _, port_str = bind.rpartition(":")
    host = host or "0.0.0.0"
    port = int(port_str)

    store = OperationStore()
    executor = OperationExecutor(config, subprocess_run=subprocess_run)
    handler_class = build_handler_class(token, store, executor)

    server = HTTPServer((host, port), handler_class)
    logger.info("Host agent v%s listening on %s:%d", VERSION, host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")


def main() -> None:
    config = _load_config()
    token = _load_token(config["secret_file"])
    run(bind=config["bind"], token=token, config=config)


if __name__ == "__main__":
    main()

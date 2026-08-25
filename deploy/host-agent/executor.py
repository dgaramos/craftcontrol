"""OperationExecutor: prepare/restart/health_wait phases and RakNet UDP probe."""
from __future__ import annotations

import logging
import socket
import struct
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from store import OperationRecord, OperationStore

logger = logging.getLogger("host-agent")

# RakNet constants
RAKNET_MAGIC = bytes([0x00, 0xFF, 0xFF, 0x00, 0xFE, 0xFE, 0xFE, 0xFE, 0xFD, 0xFD, 0xFD, 0xFD, 0x12, 0x34, 0x56, 0x78])
BEDROCK_DEFAULT_PORT = 19132
PROBE_INTERVAL_SECONDS = 5
PROBE_READ_TIMEOUT_SECONDS = 2

# ---------------------------------------------------------------------------
# Field validation tables
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
        # Capture the original file's mode so we can replicate it on the
        # replacement.  Fall back to 0o644 when the file does not yet exist.
        original_mode = props_file.stat().st_mode if props_file.exists() else 0o644
        try:
            tmp_file.write_text("".join(merged), encoding="utf-8")
            tmp_file.chmod(original_mode)
            tmp_file.replace(props_file)
        except OSError as exc:
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                pass
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

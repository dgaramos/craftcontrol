"""OperationExecutor: use-case layer for prepare / restart / health_wait.

This module orchestrates the three operation stages exclusively through the
ports defined in ``ports.py``.  It must import **zero** stdlib infrastructure
modules (subprocess, socket, pathlib).  All infrastructure concerns live in the
concrete adapters under ``adapters/``.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from proxy.ports import ContainerRunner, FileSystem, HealthProbe, RestartTimeoutError
from proxy.store.store import OperationRecord, OperationStore

logger = logging.getLogger("bedrock-proxy")

# ---------------------------------------------------------------------------
# Field validation tables (pure Python — no I/O)
# ---------------------------------------------------------------------------

BEDROCK_DEFAULT_PORT = 19132

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
    "force_gamemode",
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
    "force_gamemode",
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

# Mapping from intended_state field names to server.properties key names.
_FIELD_MAP: dict[str, str] = {
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
    "force_gamemode": "force-gamemode",
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


def _build_updates(intended_state: dict[str, Any]) -> dict[str, str]:
    """Map intended_state fields to rendered server.properties key→value pairs."""
    return {
        _FIELD_MAP[field]: _render_field_value(field, value)
        for field, value in intended_state.items()
        if field in _FIELD_MAP
    }


# ---------------------------------------------------------------------------
# Use-case orchestrator
# ---------------------------------------------------------------------------

class OperationExecutor:
    """Orchestrate prepare / restart / health_wait via injected ports.

    All infrastructure concerns (subprocess, filesystem, UDP) are delegated
    to the constructor-injected port implementations.
    """

    def __init__(
        self,
        container_runner: ContainerRunner,
        filesystem: FileSystem,
        health_probe: HealthProbe,
    ) -> None:
        self._runner = container_runner
        self._filesystem = filesystem
        self._probe = health_probe

    def run(
        self,
        record: OperationRecord,
        store: OperationStore,
        intended_state: dict[str, Any],
        health_timeout: int,
        restart_timeout: int,
    ) -> None:
        """Execute operation stages. Mutates record via store.update."""
        operation_id = record.operation_id

        # Stage: prepare
        try:
            store.update(operation_id, current_stage="prepare")
            updates = _build_updates(intended_state)
            if updates:
                self._filesystem.write_server_properties(updates)
            else:
                logger.info("No configuration fields to write in prepare stage")
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
                completed_at=time.time(),
            )
            return

        # Stage: restart
        executor_ref: str | None = None
        try:
            store.update(operation_id, current_stage="restart")
            executor_ref = self._runner.restart(restart_timeout)
        except RestartTimeoutError as exc:
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
                completed_at=time.time(),
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
                completed_at=time.time(),
            )
            return

        # Stage: health_wait
        store.update(operation_id, current_stage="health_wait")
        try:
            port = int(intended_state.get("server_port", BEDROCK_DEFAULT_PORT))
            health_reached = self._probe.wait("127.0.0.1", port, health_timeout)
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
                completed_at=time.time(),
            )
            return

        if health_reached:
            store.update(
                operation_id,
                status="done",
                current_stage=None,
                outcome="ok",
                executor_ref=executor_ref,
                health_reached=True,
                failed_stage=None,
                detail="Server reached healthy state",
                error_code=None,
                exception_type=None,
                completed_at=time.time(),
            )
            logger.info(
                "operation %s completed successfully (executor_ref=%s)",
                operation_id, executor_ref,
            )
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
                completed_at=time.time(),
            )
            logger.error(
                "operation %s health probe timed out after %ss",
                operation_id, health_timeout,
            )

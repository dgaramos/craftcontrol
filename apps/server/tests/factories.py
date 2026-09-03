"""Shared test-data factories for the craftcontrol backend test suite.

Use these builders instead of constructing raw dicts inline so that envelope
and snapshot shapes stay consistent when the schema evolves.
"""
from __future__ import annotations

from typing import Any

from controlplane.audit.model import AuditRecord
from controlplane.core.events import Event
from controlplane.operations.lifecycle import (
    OperationStage,
    OperationState,
    StageRecord,
    StageResult,
    ServerOperation,
)
from controlplane.telemetry.installer import TelemetryPackStatus


def telemetry_envelope(
    event_type: str = "blocks.changed",
    sequence: int = 1,
    player: str | None = "VonCrush",
    data: dict | None = None,
    timestamp: int = 1,
) -> dict:
    """Return a well-formed telemetry envelope dict.

    Args:
        event_type: The event type string (e.g. ``"blocks.changed"``).
        sequence: Monotonically increasing sequence number from the pack.
        player: Player name to embed in ``{"name": player}``; pass ``None``
            for server-level events that carry no player context.
        data: Payload dict. Defaults to an empty dict.
        timestamp: Unix timestamp. Defaults to ``1``.

    Returns:
        A dict matching the telemetry envelope schema v1.
    """
    return {
        "schema": 1,
        "sequence": sequence,
        "type": event_type,
        "timestamp": timestamp,
        "player": {"name": player} if player is not None else None,
        "data": data if data is not None else {},
    }


def player_snapshot(
    name: str = "VonCrush",
    online: bool = True,
    xuid: str = "999",
) -> dict:
    """Return a minimal player-snapshot dict suitable for seeding tests.

    Args:
        name: Display name.
        online: Whether the player is currently connected.
        xuid: Internal Xbox User ID (never exposed externally).

    Returns:
        A dict with ``name``, ``online``, and ``xuid`` keys.
    """
    return {"name": name, "online": online, "xuid": xuid}


def audit_record(
    id: int = 1,
    occurred_at: float = 1.0,
    actor: str | None = "alice",
    action: str = "auth.login",
    target: str | None = "alice",
    result: str = "success",
    metadata: dict[str, Any] | None = None,
) -> AuditRecord:
    return AuditRecord(
        id=id,
        occurred_at=occurred_at,
        actor=actor,
        action=action,
        target=target,
        result=result,
        metadata=metadata if metadata is not None else {},
    )


def event(
    id: int = 1,
    topic: str = "server.status",
    timestamp: float = 1.0,
    source: str = "test",
    payload: dict[str, Any] | None = None,
) -> Event:
    return Event(
        id=id,
        topic=topic,
        timestamp=timestamp,
        source=source,
        payload=payload if payload is not None else {},
    )


def stage_record(
    stage: OperationStage = OperationStage.REVIEW,
    result: StageResult = StageResult.PENDING,
    started_at: float | None = None,
    completed_at: float | None = None,
    evidence: dict[str, Any] | None = None,
    error: str | None = None,
) -> StageRecord:
    return StageRecord(
        stage=stage,
        result=result,
        started_at=started_at,
        completed_at=completed_at,
        evidence=evidence if evidence is not None else {},
        error=error,
    )


def server_operation(
    operation_id: str = "op-1",
    server_id: str = "default",
    requested_changes: dict[str, Any] | None = None,
    state: OperationState = OperationState.PENDING,
    stages: list[StageRecord] | None = None,
    created_at: float = 1.0,
    updated_at: float = 1.0,
    completed_at: float | None = None,
    terminal_error: str | None = None,
) -> ServerOperation:
    return ServerOperation(
        operation_id=operation_id,
        server_id=server_id,
        requested_changes=requested_changes if requested_changes is not None else {},
        state=state,
        stages=stages if stages is not None else [StageRecord(stage=s) for s in OperationStage.ordered()],
        created_at=created_at,
        updated_at=updated_at,
        completed_at=completed_at,
        terminal_error=terminal_error,
    )


def telemetry_pack_status(
    world: str = "Bedrock level",
    source_version: str = "1.0.0",
    installed_version: str | None = "1.0.0",
    enabled_version: str | None = "1.0.0",
    installed: bool = True,
    enabled: bool = True,
    upgrade_available: bool = False,
    legacy_directory: bool = False,
    restart_required: bool | None = False,
    installed_updated_at: float | None = 1.0,
) -> TelemetryPackStatus:
    return TelemetryPackStatus(
        world=world,
        source_version=source_version,
        installed_version=installed_version,
        enabled_version=enabled_version,
        installed=installed,
        enabled=enabled,
        upgrade_available=upgrade_available,
        legacy_directory=legacy_directory,
        restart_required=restart_required,
        installed_updated_at=installed_updated_at,
    )

"""Shared test-data factories for the craftcontrol backend test suite.

Use these builders instead of constructing raw dicts inline so that envelope
and snapshot shapes stay consistent when the schema evolves.
"""
from __future__ import annotations


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

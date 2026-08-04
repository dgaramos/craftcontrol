from __future__ import annotations

import json
from typing import Any

PREFIX = "[BEDROCK_TELEMETRY]"
TOPICS = {
    "telemetry.started", "player.joined", "player.left", "player.respawned",
    "player.dimension.changed", "entity.died", "block.broken", "block.placed",
    "snapshot.started", "snapshot.player", "snapshot.finished",
}


def parse_telemetry_line(line: str) -> dict[str, Any] | None:
    marker = line.find(PREFIX)
    if marker < 0:
        return None
    raw = line[marker + len(PREFIX):].strip()
    if len(raw) > 65536:
        raise ValueError("telemetry payload too large")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise ValueError("unsupported telemetry schema")
    if payload.get("type") not in TOPICS:
        raise ValueError("unsupported telemetry topic")
    if not isinstance(payload.get("sequence"), int) or payload["sequence"] < 0:
        raise ValueError("invalid telemetry sequence")
    player = payload.get("player")
    if player is not None:
        if not isinstance(player, dict) or not isinstance(player.get("name"), str) or not 1 <= len(player["name"]) <= 32:
            raise ValueError("invalid telemetry player")
    if not isinstance(payload.get("data"), dict):
        raise ValueError("invalid telemetry data")
    return payload

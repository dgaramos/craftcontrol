"""Player export resources (issue #270).

Resolves the resources named in ``docs/exports.md`` to bounded public records.
Reads go through the same service the API already uses, so an export can never
become a second, wider read path into the database.
"""

from __future__ import annotations

import json
from typing import Any

from ..core.exports import ROW_LIMIT, enforce_row_limit

RESOURCES = ("profiles", "sessions", "activity", "deaths")
PERIODS = (0, 7, 30)

# Public columns only, in a stable order. A field absent here is absent from the
# export, which is how the privacy floor in docs/exports.md is enforced in code.
COLUMNS: dict[str, list[str]] = {
    "profiles": [
        "id", "name", "online", "sessions_count", "total_play_seconds",
        "deaths_count", "permission", "operator",
    ],
    "sessions": [
        "player.id", "player.name", "id", "connected_at", "disconnected_at",
        "duration_seconds", "close_reason", "inferred", "active",
    ],
    "activity": [
        "id", "timestamp", "topic", "source", "player.id", "player.name", "details",
    ],
}
COLUMNS["deaths"] = COLUMNS["activity"]

# The activity service caps a page at 50 and validates the period itself; the
# export pages through that boundary instead of widening it.
_ACTIVITY_PAGE_SIZE = 50


class UnknownExportResource(Exception):
    """Raised for a resource name outside ``RESOURCES``."""


class PlayerExportService:
    """Builds bounded, public record sets for the player export resources."""

    def __init__(self, players: Any, row_limit: int = ROW_LIMIT) -> None:
        self._players = players
        self._row_limit = row_limit

    def columns(self, resource: str) -> list[str]:
        try:
            return list(COLUMNS[resource])
        except KeyError as error:
            raise UnknownExportResource(resource) from error

    def records(
        self,
        resource: str,
        *,
        player: str = "",
        days: int = 0,
        source: str = "all",
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Return the records and the effective filters that produced them."""
        if resource not in RESOURCES:
            raise UnknownExportResource(resource)
        if days not in PERIODS:
            raise ValueError("invalid export period")
        if len(player) > 64:
            raise ValueError("invalid export player filter")

        if resource == "profiles":
            return self._profiles(player, days)
        if resource == "sessions":
            return self._sessions(player, days)
        return self._activity(resource, player, days, source)

    # -- resources ---------------------------------------------------------

    def _profiles(self, player: str, days: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if days:
            raise ValueError("profiles export does not support a period filter")
        rows = [
            self._public_profile(profile)
            for profile in self._players.list_profiles()
            if not player or self._matches(profile, player)
        ]
        enforce_row_limit(len(rows), self._row_limit)
        return rows, {"player": player} if player else {}

    def _sessions(self, player: str, days: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if days:
            raise ValueError("sessions export does not support a period filter")
        if not player:
            # Sessions are only readable per profile, and exporting every
            # session of every player is exactly the unbounded request the
            # contract refuses. Requiring the filter keeps the export inside
            # the existing read path.
            raise ValueError("sessions export requires a player filter")
        profile = self._players.profile(player)
        if profile is None:
            return [], {"player": player}
        reference = {"id": profile.get("id"), "name": profile.get("name")}
        rows = [
            {
                "player": reference,
                "id": session.get("id"),
                "connected_at": session.get("connected_at"),
                "disconnected_at": session.get("disconnected_at"),
                "duration_seconds": session.get("duration_seconds"),
                "close_reason": session.get("close_reason"),
                "inferred": session.get("inferred"),
                "active": session.get("active"),
            }
            for session in profile.get("sessions") or []
        ]
        enforce_row_limit(len(rows), self._row_limit)
        return rows, {"player": player}

    def _activity(
        self, resource: str, player: str, days: int, source: str
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        kind = "deaths" if resource == "deaths" else "all"
        first = self._players.activity(kind, player, source, "", days, 1, _ACTIVITY_PAGE_SIZE)
        enforce_row_limit(int(first.get("total", 0)), self._row_limit)

        rows = [self._public_event(event) for event in first.get("events", [])]
        pages = int(first.get("pages", 1))
        for page in range(2, pages + 1):
            batch = self._players.activity(kind, player, source, "", days, page, _ACTIVITY_PAGE_SIZE)
            rows.extend(self._public_event(event) for event in batch.get("events", []))

        filters: dict[str, Any] = {"kind": kind, "source": source}
        if player:
            filters["player"] = player
        if days:
            filters["days"] = days
        return rows, filters

    # -- shaping -----------------------------------------------------------

    @staticmethod
    def _matches(profile: dict[str, Any], player: str) -> bool:
        wanted = player.casefold()
        return wanted in {str(profile.get("id", "")).casefold(), str(profile.get("name", "")).casefold()}

    @staticmethod
    def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
        return {column: profile.get(column) for column in COLUMNS["profiles"]}

    @staticmethod
    def _public_event(event: dict[str, Any]) -> dict[str, Any]:
        """Carry the free-form detail map as one JSON value.

        Detail keys vary per topic, so flattening them would make the CSV column
        set depend on the rows it happens to contain. One column keeps the shape
        stable and the JSON export identical in content.
        """
        player = event.get("player") or {}
        return {
            "id": event.get("id"),
            "timestamp": event.get("timestamp"),
            "topic": event.get("topic"),
            "source": event.get("source"),
            "player": {"id": player.get("id"), "name": player.get("name")},
            "details": json.dumps(event.get("details") or {}, ensure_ascii=False, sort_keys=True),
        }

"""Analytics export resources (issue #271).

The analytics endpoints answer with nested aggregates, each shaped for its own
screen. An export needs rows with stable columns, so every payload is flattened
into one long table: a value, and the coordinates that identify it.

Event-shaped lists are deliberately not exported here. Dimension transitions are
``player.dimension.changed`` events and duels come from deaths, both already
exportable through the player ``activity`` and ``deaths`` resources; carrying
them again in a measure table would mean inventing a second shape for the same
records.
"""

from __future__ import annotations

from typing import Any, Callable, Iterator

from ..core.exports import ROW_LIMIT, enforce_row_limit

RESOURCES = ("rankings", "periods", "blocks", "combat", "exploration")
PERIODS = (7, 30)
LIMITS = range(1, 26)

# One stable column set for every analytics resource: what the value measures,
# which slice it came from, and whom it belongs to.
COLUMNS = ["section", "metric", "key", "rank", "player.id", "player.name", "value", "source"]


class UnknownExportResource(Exception):
    """Raised for a resource name outside ``RESOURCES``."""


def _row(section: str, metric: str, value: Any, *, key: str = "", rank: int | None = None,
         player: dict[str, Any] | None = None, source: str = "") -> dict[str, Any]:
    reference = player or {}
    return {
        "section": section,
        "metric": metric,
        "key": key,
        "rank": rank,
        "player": {"id": reference.get("id"), "name": reference.get("name")} if reference else None,
        "value": value,
        "source": source,
    }


def _totals(payload: dict[str, Any], section: str = "totals") -> Iterator[dict[str, Any]]:
    for metric, value in (payload.get(section) or {}).items():
        yield _row(section, str(metric), value)


def _rankings(rankings: dict[str, Any], section: str = "rankings") -> Iterator[dict[str, Any]]:
    for metric, entries in (rankings or {}).items():
        if isinstance(entries, dict):
            # blocks nests one ranking per ore under rankings.ores.
            yield from _rankings(entries, f"{section}.{metric}")
            continue
        for position, entry in enumerate(entries or [], start=1):
            yield _row(
                section, str(metric), entry.get("value"), rank=position,
                player=entry.get("player"), source=str(entry.get("source") or ""),
            )


def _counted(entries: list[dict[str, Any]] | None, section: str, key_field: str,
             value_field: str = "count", metric: str = "count") -> Iterator[dict[str, Any]]:
    for position, entry in enumerate(entries or [], start=1):
        yield _row(section, metric, entry.get(value_field), rank=position,
                   key=str(entry.get(key_field) or ""))


def _measures(entries: list[dict[str, Any]] | None, section: str, key_field: str,
              metrics: tuple[str, ...]) -> Iterator[dict[str, Any]]:
    """Emit one row per measure of a record that carries several."""
    for entry in entries or []:
        key = str(entry.get(key_field) or "")
        for metric in metrics:
            if metric in entry:
                yield _row(section, metric, entry.get(metric), key=key)


class AnalyticsExportService:
    """Flattens the analytics aggregates into bounded, public measure rows."""

    def __init__(self, players: Any, row_limit: int = ROW_LIMIT) -> None:
        self._players = players
        self._row_limit = row_limit

    def columns(self, resource: str) -> list[str]:
        if resource not in RESOURCES:
            raise UnknownExportResource(resource)
        return list(COLUMNS)

    def records(
        self, resource: str, *, days: int = 30, limit: int = 10
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if resource not in RESOURCES:
            raise UnknownExportResource(resource)
        if limit not in LIMITS:
            raise ValueError("invalid export limit")

        builder: Callable[[], tuple[list[dict[str, Any]], dict[str, Any]]] = {
            "rankings": lambda: self._rankings(limit),
            "periods": lambda: self._periods(days, limit),
            "blocks": lambda: self._blocks(limit),
            "combat": lambda: self._combat(limit),
            "exploration": lambda: self._exploration(limit),
        }[resource]
        rows, filters = builder()
        enforce_row_limit(len(rows), self._row_limit)
        return rows, filters

    # -- resources ---------------------------------------------------------

    def _rankings(self, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = self._players.rankings(limit)
        return list(_rankings(payload.get("metrics"))), {"limit": limit}

    def _periods(self, days: int, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if days not in PERIODS:
            raise ValueError("invalid export period")
        payload = self._players.periods(days, limit)
        calendar_metrics = ("play_seconds", "sessions", "joins", "deaths", "player_kills",
                            "mob_kills", "blocks_broken", "blocks_placed")
        rows = [
            *_totals(payload),
            *_rankings(payload.get("rankings")),
            *_measures(payload.get("calendar"), "calendar", "day", calendar_metrics),
        ]
        for entry in payload.get("heatmap") or []:
            rows.append(_row("heatmap", "seconds", entry.get("seconds"),
                             key=f"{entry.get('weekday')}:{entry.get('hour')}"))
        # The timezone that produced the day keys travels in the manifest.
        return rows, {"days": days, "limit": limit, "timezone": payload.get("timezone", "")}

    def _blocks(self, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = self._players.blocks(limit)
        rows = [
            *_totals(payload),
            *(_row("ores", str(ore), count) for ore, count in (payload.get("ores") or {}).items()),
            *_counted(payload.get("top_broken"), "top_broken", "block"),
            *_counted(payload.get("top_placed"), "top_placed", "block"),
            *_rankings(payload.get("rankings")),
        ]
        return rows, {"limit": limit}

    def _combat(self, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = self._players.combat(limit)
        breakdowns = payload.get("breakdowns") or {}
        rows = [
            *_totals(payload),
            *_rankings(payload.get("rankings")),
            *_counted(payload.get("top_targets"), "top_targets", "target", "kills"),
        ]
        for kind in ("causes", "opponents", "projectiles"):
            rows.extend(_counted(breakdowns.get(kind), f"breakdowns.{kind}", "key"))
        for position, duel in enumerate(payload.get("pvp") or [], start=1):
            rows.append(_row("pvp", "duels", duel.get("count"), rank=position,
                             player=duel.get("attacker"),
                             key=str((duel.get("victim") or {}).get("name") or "")))
        return rows, {"limit": limit}

    def _exploration(self, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = self._players.exploration(limit)
        rows = [
            *_totals(payload),
            *_rankings(payload.get("rankings")),
            *_measures(payload.get("dimensions"), "dimensions", "dimension",
                       ("distance", "active_seconds", "visits", "first_seen_at", "last_seen_at")),
        ]
        return rows, {"limit": limit}

"""Analytics export resources (issue #271).

The analytics endpoints answer with nested aggregates shaped for their screens.
These tests pin the flattening: one long measure table with a stable column set,
the coordinates that identify each value, and the event-shaped lists left out.
"""

from __future__ import annotations

import pytest

from src.core.exports import ExportTooLarge
from src.players.analytics_exports import (
    COLUMNS,
    AnalyticsExportService,
    UnknownExportResource,
)


class _FakeAnalytics:
    def __init__(self, **payloads) -> None:
        self._payloads = payloads
        self.calls: list[tuple] = []

    def rankings(self, limit):
        self.calls.append(("rankings", limit))
        return self._payloads.get("rankings", {"metrics": {}})

    def periods(self, days, limit):
        self.calls.append(("periods", days, limit))
        return self._payloads.get("periods", {"totals": {}, "rankings": {}})

    def blocks(self, limit):
        self.calls.append(("blocks", limit))
        return self._payloads.get("blocks", {"totals": {}, "rankings": {}})

    def combat(self, limit):
        self.calls.append(("combat", limit))
        return self._payloads.get("combat", {"totals": {}, "rankings": {}})

    def exploration(self, limit):
        self.calls.append(("exploration", limit))
        return self._payloads.get("exploration", {"totals": {}, "rankings": {}})


def _entry(name="Steve", value=10, source="telemetry-pack"):
    return {"player": {"id": f"pub-{name}", "name": name, "xuid": "2535428139999999"},
            "value": value, "source": source}


def _find(rows, **match):
    return [row for row in rows if all(row.get(k) == v for k, v in match.items())]


# -- shape -------------------------------------------------------------------

def test_every_resource_shares_one_column_set() -> None:
    service = AnalyticsExportService(_FakeAnalytics())
    for resource in ("rankings", "periods", "blocks", "combat", "exploration"):
        assert service.columns(resource) == COLUMNS


def test_unknown_resource_is_rejected() -> None:
    service = AnalyticsExportService(_FakeAnalytics())
    with pytest.raises(UnknownExportResource):
        service.records("passwords")
    with pytest.raises(UnknownExportResource):
        service.columns("passwords")


def test_ranking_rows_carry_metric_rank_player_and_source() -> None:
    payload = {"metrics": {"play_time": [_entry("Steve", 30), _entry("Alex", 20)]}}
    rows, filters = AnalyticsExportService(_FakeAnalytics(rankings=payload)).records("rankings")
    assert [row["rank"] for row in rows] == [1, 2]
    assert rows[0] == {
        "section": "rankings", "metric": "play_time", "key": "", "rank": 1,
        "player": {"id": "pub-Steve", "name": "Steve"}, "value": 30,
        "source": "telemetry-pack",
    }
    assert filters == {"limit": 10}


def test_player_references_drop_private_fields() -> None:
    payload = {"metrics": {"play_time": [_entry()]}}
    rows, _ = AnalyticsExportService(_FakeAnalytics(rankings=payload)).records("rankings")
    assert rows[0]["player"] == {"id": "pub-Steve", "name": "Steve"}


def test_totals_become_rows_without_a_player_or_rank() -> None:
    payload = {"totals": {"broken": 12, "placed": 4}, "rankings": {}}
    rows, _ = AnalyticsExportService(_FakeAnalytics(blocks=payload)).records("blocks")
    broken = _find(rows, section="totals", metric="broken")[0]
    assert broken["value"] == 12
    assert broken["player"] is None
    assert broken["rank"] is None


# -- per-resource flattening -------------------------------------------------

def test_blocks_carries_ores_top_lists_and_nested_ore_rankings() -> None:
    payload = {
        "totals": {"broken": 1}, "ores": {"diamond": 7},
        "top_broken": [{"block": "minecraft:stone", "count": 5}],
        "top_placed": [{"block": "minecraft:brick", "count": 3}],
        "rankings": {"miners": [_entry("Steve", 9)], "ores": {"diamond": [_entry("Alex", 4)]}},
    }
    rows, _ = AnalyticsExportService(_FakeAnalytics(blocks=payload)).records("blocks")
    assert _find(rows, section="ores", metric="diamond")[0]["value"] == 7
    assert _find(rows, section="top_broken")[0]["key"] == "minecraft:stone"
    assert _find(rows, section="top_placed")[0]["value"] == 3
    assert _find(rows, section="rankings", metric="miners")[0]["value"] == 9
    # An ore leaderboard is a ranking of its own, not a row of the ore totals.
    nested = _find(rows, section="rankings.ores", metric="diamond")[0]
    assert nested["player"]["name"] == "Alex"
    assert nested["rank"] == 1


def test_combat_carries_breakdowns_targets_and_duels() -> None:
    payload = {
        "totals": {"deaths": 2}, "rankings": {},
        "breakdowns": {"causes": [{"key": "fall", "count": 2}], "opponents": [], "projectiles": []},
        "top_targets": [{"target": "minecraft:zombie", "kills": 6}],
        "pvp": [{"attacker": {"id": "pub-Steve", "name": "Steve"},
                 "victim": {"id": "pub-Alex", "name": "Alex"}, "count": 3}],
    }
    rows, _ = AnalyticsExportService(_FakeAnalytics(combat=payload)).records("combat")
    assert _find(rows, section="breakdowns.causes")[0]["key"] == "fall"
    assert _find(rows, section="top_targets")[0]["value"] == 6
    duel = _find(rows, section="pvp")[0]
    assert duel["player"]["name"] == "Steve"
    assert duel["key"] == "Alex"
    assert duel["value"] == 3


def test_exploration_emits_one_row_per_dimension_measure() -> None:
    payload = {
        "totals": {"distance": 10.5}, "rankings": {},
        "dimensions": [{"dimension": "minecraft:overworld", "distance": 8.0,
                        "active_seconds": 60, "first_seen_at": 1.0, "last_seen_at": 2.0}],
    }
    rows, _ = AnalyticsExportService(_FakeAnalytics(exploration=payload)).records("exploration")
    dimension_rows = _find(rows, section="dimensions", key="minecraft:overworld")
    assert {row["metric"] for row in dimension_rows} == {
        "distance", "active_seconds", "first_seen_at", "last_seen_at"
    }
    assert _find(rows, section="dimensions", metric="distance")[0]["value"] == 8.0


def test_exploration_leaves_transitions_to_the_player_activity_export() -> None:
    """Transitions are `player.dimension.changed` events, already exportable."""
    payload = {"totals": {}, "rankings": {},
               "transitions": [{"player": {"id": "pub-Steve", "name": "Steve"},
                                "from": "a", "to": "b", "timestamp": 1.0}]}
    rows, _ = AnalyticsExportService(_FakeAnalytics(exploration=payload)).records("exploration")
    assert _find(rows, section="transitions") == []


def test_periods_carries_calendar_days_and_the_heatmap() -> None:
    payload = {
        "totals": {"sessions": 4}, "rankings": {}, "timezone": "America/Sao_Paulo",
        "calendar": [{"day": "2026-09-07", "play_seconds": 90.0, "sessions": 2}],
        "heatmap": [{"weekday": 1, "hour": 20, "seconds": 45.0}],
    }
    rows, filters = AnalyticsExportService(_FakeAnalytics(periods=payload)).records(
        "periods", days=7
    )
    day = _find(rows, section="calendar", key="2026-09-07", metric="play_seconds")[0]
    assert day["value"] == 90.0
    assert _find(rows, section="heatmap")[0]["key"] == "1:20"
    # The day keys are local, so the export records which timezone produced them.
    assert filters == {"days": 7, "limit": 10, "timezone": "America/Sao_Paulo"}


# -- filters and bounds ------------------------------------------------------

def test_period_outside_the_supported_set_is_rejected() -> None:
    service = AnalyticsExportService(_FakeAnalytics())
    with pytest.raises(ValueError, match="invalid export period"):
        service.records("periods", days=1)


def test_limit_outside_the_analytics_bound_is_rejected() -> None:
    service = AnalyticsExportService(_FakeAnalytics())
    for limit in (0, 26):
        with pytest.raises(ValueError, match="invalid export limit"):
            service.records("rankings", limit=limit)


def test_limit_reaches_the_analytics_use_case_unchanged() -> None:
    players = _FakeAnalytics()
    AnalyticsExportService(players).records("rankings", limit=25)
    assert players.calls == [("rankings", 25)]


def test_record_ceiling_refuses_an_oversized_flattening() -> None:
    payload = {"metrics": {"play_time": [_entry(str(index)) for index in range(5)]}}
    service = AnalyticsExportService(_FakeAnalytics(rankings=payload), row_limit=4)
    with pytest.raises(ExportTooLarge) as error:
        service.records("rankings")
    assert error.value.limit == "record"

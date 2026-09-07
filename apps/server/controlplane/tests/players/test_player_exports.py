"""Player export resources (issue #270).

Covers resource resolution, filter validation, the record ceiling as a
pre-check, and the privacy floor: an export carries only public fields.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.core.exports import ExportTooLarge
from src.players.exports import PlayerExportService, UnknownExportResource


class _FakePlayers:
    """Stands in for PlayerService, recording how the export reads it."""

    def __init__(self, profiles: list[dict] | None = None, events: list[dict] | None = None,
                 profile: dict | None = None) -> None:
        self._profiles = profiles or []
        self._events = events or []
        self._profile = profile
        self.activity_calls: list[tuple] = []
        self.listed = False

    def list_profiles(self) -> list[dict]:
        self.listed = True
        return list(self._profiles)

    def profile_count(self) -> int:
        return len(self._profiles)

    def profile(self, identity: str) -> dict | None:
        return self._profile

    def activity(self, kind, player, source, search, days, page, page_size) -> dict[str, Any]:
        self.activity_calls.append((kind, player, source, search, days, page, page_size))
        start = (page - 1) * page_size
        window = self._events[start:start + page_size]
        pages = max(1, -(-len(self._events) // page_size))
        return {"events": window, "total": len(self._events), "page": page,
                "page_size": page_size, "pages": pages}


def _profile(name: str = "Steve", **extra) -> dict[str, Any]:
    base = {
        "id": f"pub-{name}", "name": name, "online": True, "sessions_count": 3,
        "total_play_seconds": 120, "deaths_count": 1, "permission": "member",
        "operator": False,
        # Private and internal values the API keeps out of its payloads.
        "xuid": "2535428139999999", "telemetry": {"mobKills": 4},
    }
    base.update(extra)
    return base


def _event(identifier: int = 1, topic: str = "player.death") -> dict[str, Any]:
    return {
        "id": identifier, "topic": topic, "timestamp": 1788806153.0, "source": "behavior-pack",
        "player": {"id": "pub-Steve", "name": "Steve", "xuid": "2535428139999999"},
        "details": {"cause": "fall"},
    }


# -- resources --------------------------------------------------------------

def test_unknown_resource_is_rejected() -> None:
    service = PlayerExportService(_FakePlayers())
    with pytest.raises(UnknownExportResource):
        service.records("passwords")
    with pytest.raises(UnknownExportResource):
        service.columns("passwords")


def test_profiles_export_carries_only_public_columns() -> None:
    service = PlayerExportService(_FakePlayers(profiles=[_profile()]))
    records, filters = service.records("profiles")
    assert records == [{
        "id": "pub-Steve", "name": "Steve", "online": True, "sessions_count": 3,
        "total_play_seconds": 120, "deaths_count": 1, "permission": "member", "operator": False,
    }]
    assert filters == {}
    assert "xuid" not in json.dumps(records)


def test_profiles_export_filters_by_public_id_or_gamertag() -> None:
    service = PlayerExportService(_FakePlayers(profiles=[_profile("Steve"), _profile("Alex")]))
    by_name, filters = service.records("profiles", player="alex")
    assert [record["name"] for record in by_name] == ["Alex"]
    assert filters == {"player": "alex"}
    by_id, _ = service.records("profiles", player="pub-Steve")
    assert [record["name"] for record in by_id] == ["Steve"]


def test_sessions_export_requires_a_player_filter() -> None:
    """Every session of every player is the unbounded request the contract refuses."""
    service = PlayerExportService(_FakePlayers())
    with pytest.raises(ValueError, match="requires a player filter"):
        service.records("sessions")


def test_sessions_export_carries_the_player_reference_and_public_fields() -> None:
    profile = _profile()
    profile["sessions"] = [{
        "id": 7, "connected_at": 1788806153.0, "disconnected_at": None, "duration_seconds": 60,
        "close_reason": None, "inferred": False, "active": True,
    }]
    service = PlayerExportService(_FakePlayers(profile=profile))
    records, filters = service.records("sessions", player="Steve")
    assert records[0]["player"] == {"id": "pub-Steve", "name": "Steve"}
    assert records[0]["duration_seconds"] == 60
    assert filters == {"player": "Steve"}


def test_sessions_export_of_an_unknown_player_is_empty_not_an_error() -> None:
    service = PlayerExportService(_FakePlayers(profile=None))
    records, filters = service.records("sessions", player="Ghost")
    assert records == []
    assert filters == {"player": "Ghost"}


def test_activity_export_pages_through_the_existing_read_path() -> None:
    events = [_event(index) for index in range(1, 121)]
    players = _FakePlayers(events=events)
    records, filters = PlayerExportService(players).records("activity")
    assert len(records) == 120
    # Three pages of the service's own maximum, never a widened page size.
    assert [call[6] for call in players.activity_calls] == [50, 50, 50]
    assert [call[5] for call in players.activity_calls] == [1, 2, 3]
    assert filters == {"kind": "all", "source": "all"}


def test_deaths_export_restricts_the_kind() -> None:
    players = _FakePlayers(events=[_event()])
    _, filters = PlayerExportService(players).records("deaths")
    assert players.activity_calls[0][0] == "deaths"
    assert filters["kind"] == "deaths"


def test_activity_export_drops_private_player_fields_and_serializes_details() -> None:
    service = PlayerExportService(_FakePlayers(events=[_event()]))
    records, _ = service.records("activity")
    assert records[0]["player"] == {"id": "pub-Steve", "name": "Steve"}
    assert "xuid" not in json.dumps(records)
    # Detail keys vary per topic; one JSON column keeps the CSV shape stable.
    assert records[0]["details"] == '{"cause":"fall"}'


def test_activity_export_reports_the_effective_filters() -> None:
    service = PlayerExportService(_FakePlayers(events=[_event()]))
    _, filters = service.records("activity", player="Steve", days=7, source="structured")
    assert filters == {"kind": "all", "source": "structured", "player": "Steve", "days": 7}


# -- filters ----------------------------------------------------------------

def test_period_outside_the_supported_set_is_rejected() -> None:
    service = PlayerExportService(_FakePlayers())
    with pytest.raises(ValueError, match="invalid export period"):
        service.records("activity", days=1)


def test_profiles_and_sessions_reject_a_period_instead_of_ignoring_it() -> None:
    service = PlayerExportService(_FakePlayers(profiles=[_profile()]))
    with pytest.raises(ValueError, match="does not support a period"):
        service.records("profiles", days=7)
    with pytest.raises(ValueError, match="does not support a period"):
        service.records("sessions", player="Steve", days=7)


def test_oversized_player_filter_is_rejected() -> None:
    service = PlayerExportService(_FakePlayers())
    with pytest.raises(ValueError, match="invalid export player filter"):
        service.records("profiles", player="x" * 65)


# -- ceiling ----------------------------------------------------------------

def test_record_ceiling_refuses_profiles_before_building_them() -> None:
    """Counting is cheap; building profiles parses every telemetry blob."""
    players = _FakePlayers(profiles=[_profile(str(i)) for i in range(5)])
    service = PlayerExportService(players, row_limit=4)
    with pytest.raises(ExportTooLarge) as error:
        service.records("profiles")
    assert error.value.limit == "record"
    assert players.listed is False


def test_record_ceiling_refuses_activity_from_the_first_page_total() -> None:
    """The total on page one refuses the export before the rest is fetched."""
    players = _FakePlayers(events=[_event(index) for index in range(1, 121)])
    service = PlayerExportService(players, row_limit=10)
    with pytest.raises(ExportTooLarge):
        service.records("activity")
    assert len(players.activity_calls) == 1

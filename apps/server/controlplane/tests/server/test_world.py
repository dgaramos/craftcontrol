"""Tests for WorldService.query_world_state."""
from __future__ import annotations

import pytest

from src.server.world import WorldService


class _FakeBedrock:
    def __init__(self, responses: dict[tuple, str] | None = None, raise_on: set | None = None) -> None:
        self.commands: list[list[str]] = []
        self._responses: dict[tuple, str] = responses or {}
        self._raise_on: set[tuple] = raise_on or set()

    def send_and_read(self, parts: list[str]) -> str:
        self.commands.append(parts)
        key = tuple(parts)
        if key in self._raise_on:
            raise RuntimeError(f"simulated error for {parts}")
        return self._responses.get(key, "")

    def send(self, parts: list[str]) -> None:
        self.commands.append(parts)


class _FakeBroker:
    def publish(self, *args, **kwargs) -> None:
        pass


def _make_world(bedrock=None):
    bedrock = bedrock or _FakeBedrock()
    return WorldService(bedrock, _FakeBroker())  # type: ignore[arg-type]


def test_query_world_state_returns_daytime_day_and_weather() -> None:
    bedrock = _FakeBedrock(responses={
        ("time", "query", "daytime"): "The time is 6000",
        ("time", "query", "day"): "The time is 5",
        ("weather", "query"): "weather is clear",
    })
    svc = _make_world(bedrock)

    result = svc.query_world_state()

    assert result["daytime"] == "6000"
    assert result["day"] == "5"
    assert result["weather"] == "clear"


def test_query_world_state_weather_priority_thunder_over_rain() -> None:
    bedrock = _FakeBedrock(responses={
        ("time", "query", "daytime"): "The time is 0",
        ("time", "query", "day"): "The time is 0",
        ("weather", "query"): "weather is thunder and rain",
    })
    svc = _make_world(bedrock)

    result = svc.query_world_state()

    assert result["weather"] == "thunder"


def test_query_world_state_survives_bedrock_error_on_daytime() -> None:
    bedrock = _FakeBedrock(
        responses={
            ("time", "query", "day"): "The time is 2",
            ("weather", "query"): "weather is clear",
        },
        raise_on={("time", "query", "daytime")},
    )
    svc = _make_world(bedrock)

    result = svc.query_world_state()

    assert "daytime" not in result
    assert result["day"] == "2"
    assert result["weather"] == "clear"


def test_query_world_state_survives_bedrock_error_on_weather() -> None:
    bedrock = _FakeBedrock(
        responses={
            ("time", "query", "daytime"): "The time is 100",
            ("time", "query", "day"): "The time is 1",
        },
        raise_on={("weather", "query")},
    )
    svc = _make_world(bedrock)

    result = svc.query_world_state()

    assert result["daytime"] == "100"
    assert "weather" not in result


def test_query_world_state_returns_empty_when_all_queries_fail() -> None:
    bedrock = _FakeBedrock(
        raise_on={
            ("time", "query", "daytime"),
            ("time", "query", "day"),
            ("weather", "query"),
        }
    )
    svc = _make_world(bedrock)

    result = svc.query_world_state()

    assert result == {}


def test_query_world_state_returns_empty_on_unrecognised_output() -> None:
    bedrock = _FakeBedrock(responses={
        ("time", "query", "daytime"): "no numbers here",
        ("time", "query", "day"): "still nothing",
        ("weather", "query"): "undefined",
    })
    svc = _make_world(bedrock)

    result = svc.query_world_state()

    assert result == {}


def test_query_world_state_picks_last_number_from_output() -> None:
    bedrock = _FakeBedrock(responses={
        ("time", "query", "daytime"): "Tick 1200 of 24000",
        ("time", "query", "day"): "Day 7",
        ("weather", "query"): "clear",
    })
    svc = _make_world(bedrock)

    result = svc.query_world_state()

    assert result["daytime"] == "24000"
    assert result["day"] == "7"

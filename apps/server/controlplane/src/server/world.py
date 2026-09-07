"""World and time use cases for the Minecraft server domain."""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Any

from ..ports import EventPublisher, ServerConsole, StateStore


class WorldQueryError(Exception):
    """Raised when every Bedrock query in query_world_state fails."""

    def __init__(self, causes: list[Exception]) -> None:
        super().__init__(f"all world queries failed ({len(causes)} error(s))")
        self.causes = causes


class WorldService:
    """Handles time, weather, and world preset actions via the Bedrock console."""

    WORLD_ACTIONS: MappingProxyType[str, tuple[str, ...]] = MappingProxyType({
        "day": ("time", "set", "day"),
        "night": ("time", "set", "night"),
        "clear-weather": ("weather", "clear"),
    })
    TIME_PRESETS: frozenset[str] = frozenset({"sunrise", "day", "noon", "sunset", "night", "midnight"})
    WEATHER_TYPES: frozenset[str] = frozenset({"clear", "rain", "thunder"})
    TIME_QUERIES: frozenset[str] = frozenset({"daytime", "gametime", "day"})
    # Deterministic priority order for weather-query: most severe first.
    WEATHER_QUERY_ORDER: tuple[str, ...] = ("thunder", "rain", "clear")
    # `send_and_read` returns every line the server logged in the last second,
    # not just the answer to the command. The telemetry pack writes JSON lines
    # milliseconds after a response, so a value must be read from the line that
    # answers the query — never from the surrounding log.
    SCRIPT_LOG_MARKERS: tuple[str, ...] = ("[Scripting]", "BEDROCK_TELEMETRY")
    TIME_RESPONSES: MappingProxyType[str, re.Pattern[str]] = MappingProxyType({
        "day": re.compile(r"\bDay is (-?\d+)", re.IGNORECASE),
        "daytime": re.compile(r"\bDaytime is (-?\d+)", re.IGNORECASE),
        "gametime": re.compile(r"\bGame ?time is (-?\d+)", re.IGNORECASE),
    })
    WEATHER_RESPONSE: re.Pattern[str] = re.compile(
        r"\bWeather state is:\s*(\w+)", re.IGNORECASE
    )

    @classmethod
    def _console_lines(cls, output: str) -> list[str]:
        """Return the server's own lines, dropping behavior-pack log output."""
        return [
            line for line in output.splitlines()
            if not any(marker in line for marker in cls.SCRIPT_LOG_MARKERS)
        ]

    @classmethod
    def _read_time_response(cls, output: str, query: str) -> str | None:
        """Return the number the server answered for ``query``, or None.

        Reporting nothing is preferable to reporting a number taken from an
        unrelated line: the panel already renders an unavailable state.
        """
        pattern = cls.TIME_RESPONSES.get(query)
        if pattern is None:
            return None
        matches = [match.group(1) for line in cls._console_lines(output)
                   if (match := pattern.search(line))]
        return matches[-1] if matches else None

    @classmethod
    def _read_weather_response(cls, output: str) -> str | None:
        """Return the weather the server answered, or None."""
        states = [match.group(1).lower() for line in cls._console_lines(output)
                  if (match := cls.WEATHER_RESPONSE.search(line))]
        for state in reversed(states):
            if state in cls.WEATHER_QUERY_ORDER:
                return state
        return None

    def __init__(self, bedrock: ServerConsole, broker: EventPublisher, state_store: StateStore | None = None) -> None:
        self.bedrock = bedrock
        self.broker = broker
        self.state_store = state_store

    def _observe_world(self, values: dict[str, str], action: str, domains: list[str] | None = None) -> None:
        """Persist only values confirmed by a console response or mutation."""
        if self.state_store is not None:
            self.state_store.store("world", values, "manager")
        self.broker.publish("state.changed", "manager", {"domains": domains or ["world"], "action": action})

    def query_world_state(self) -> dict[str, str]:
        """Query current time and weather from the Bedrock console.

        Partial failures (individual queries) are tolerated — the successfully
        retrieved values are still returned. If every query fails, a
        ``WorldQueryError`` is raised so the caller can record the failure.
        """
        result: dict[str, str] = {}
        errors: list[Exception] = []
        for query in ("daytime", "day"):
            try:
                output = self.bedrock.send_and_read(["time", "query", query])
                value = self._read_time_response(output, query)
                if value is not None:
                    result[query] = value
            except Exception as exc:
                errors.append(exc)
        try:
            output = self.bedrock.send_and_read(["weather", "query"])
            weather = self._read_weather_response(output)
            if weather:
                result["weather"] = weather
        except Exception as exc:
            errors.append(exc)
        if errors and not result:
            raise WorldQueryError(errors) from errors[0]
        return result

    def run_world_action(self, action: str) -> None:
        if action not in self.WORLD_ACTIONS:
            raise KeyError(action)
        self.bedrock.send(list(self.WORLD_ACTIONS[action]))

    def time_action(self, action: str, payload: Any) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        if action == "preset" and payload.get("value") in self.TIME_PRESETS:
            value = payload["value"]
            self.bedrock.send(["time", "set", value])
            self.broker.publish("state.changed", "manager", {"domains": ["time"], "action": action})
            return {"action": action, "value": value}
        if action in {"set", "add"}:
            value = int(payload.get("value"))
            minimum, maximum = (0, 24000) if action == "set" else (1, 240000)
            if value < minimum or value > maximum:
                raise ValueError("valor fora do intervalo")
            self.bedrock.send(["time", action, str(value)])
            self.broker.publish("state.changed", "manager", {"domains": ["time"], "action": action})
            return {"action": action, "value": value}
        if action == "reset-days":
            self.bedrock.send(["time", "set", "0"])
            self.broker.publish("state.changed", "manager", {"domains": ["time"], "action": action})
            return {"action": action, "value": 0}
        if action == "query" and payload.get("value") in self.TIME_QUERIES:
            query = payload["value"]
            output = self.bedrock.send_and_read(["time", "query", query])
            answer = self._read_time_response(output, query)
            value = int(answer) if answer is not None else None
            if value is not None:
                self._observe_world({query: str(value)}, action)
            return {"action": action, "query": query, "value": value}
        if action == "weather" and payload.get("value") in self.WEATHER_TYPES:
            weather = payload["value"]
            parts = ["weather", weather]
            duration = payload.get("duration")
            if duration not in (None, ""):
                ticks = int(duration)
                if ticks < 1 or ticks > 1000000:
                    raise ValueError("valor fora do intervalo")
                parts.append(str(ticks))
            self.bedrock.send(parts)
            self._observe_world({"weather": weather}, action, ["weather", "world"])
            return {"action": action, "value": weather, "duration": duration}
        if action == "weather-query":
            output = self.bedrock.send_and_read(["weather", "query"])
            weather = self._read_weather_response(output) or "unknown"
            if weather != "unknown":
                self._observe_world({"weather": weather}, action)
            return {"action": action, "value": weather}
        raise KeyError(action)

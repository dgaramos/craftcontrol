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
                numbers = re.findall(r"-?\d+", output)
                if numbers:
                    result[query] = numbers[-1]
            except Exception as exc:
                errors.append(exc)
        try:
            output = self.bedrock.send_and_read(["weather", "query"])
            lowered = output.lower()
            weather = next((w for w in self.WEATHER_QUERY_ORDER if w in lowered), None)
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
            numbers = re.findall(r"-?\d+", output)
            value = int(numbers[-1]) if numbers else None
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
            lowered = output.lower()
            weather = next((w for w in self.WEATHER_QUERY_ORDER if w in lowered), "unknown")
            if weather != "unknown":
                self._observe_world({"weather": weather}, action)
            return {"action": action, "value": weather}
        raise KeyError(action)

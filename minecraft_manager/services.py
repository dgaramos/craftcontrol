from __future__ import annotations

import threading
import re
from typing import Any

from .bedrock import BedrockClient
from .config import Settings
from .docker_ops import DockerOperations
from .files import ServerFiles
from .repository import StateRepository
from .schema import GAMERULES, PROPERTY_NAMES, SETTINGS, validate_value


class ManagerService:
    WORLD_ACTIONS = {
        "day": ["time", "set", "day"],
        "night": ["time", "set", "night"],
        "clear-weather": ["weather", "clear"],
    }
    TIME_PRESETS = {"sunrise", "day", "noon", "sunset", "night", "midnight"}
    WEATHER_TYPES = {"clear", "rain", "thunder"}
    TIME_QUERIES = {"daytime", "gametime", "day"}

    def __init__(self, repository: StateRepository, files: ServerFiles, bedrock: BedrockClient, docker: DockerOperations) -> None:
        self.repository = repository
        self.files = files
        self.bedrock = bedrock
        self.docker = docker
        self._refresh_lock = threading.Lock()
        self._refreshing = False

    @classmethod
    def build(cls, settings: Settings) -> "ManagerService":
        return cls(
            StateRepository(settings.database),
            ServerFiles(settings.env_file, settings.properties_file),
            BedrockClient(settings.container, list(GAMERULES), settings.console_wait_seconds),
            DockerOperations(settings.container, settings.project),
        )

    def initialize(self) -> None:
        self.repository.initialize()
        self.refresh_async()

    def state(self) -> dict[str, Any]:
        return self.repository.snapshot(self._refreshing)

    def refresh(self) -> None:
        if not self._refresh_lock.acquire(blocking=False):
            return
        self._refreshing = True
        try:
            _, env_values = self.files.read_env()
            properties = self.files.read_properties()
            settings = {key: env_values.get(key) or properties.get(PROPERTY_NAMES.get(key, ""), "") for key in SETTINGS}
            self.repository.store("settings", settings, "env+server.properties")
            gamerules, players, online, maximum = self.bedrock.query_state()
            if gamerules:
                self.repository.store("gamerules", gamerules, "bedrock-console")
            if maximum == 0:
                maximum = int(env_values.get("MAX_PLAYERS") or properties.get("max-players") or 0)
            self.repository.replace("players", {name: "online" for name in players}, "bedrock-console")
            self.repository.store("server", {"online": str(online), "max_players": str(maximum)}, "bedrock-console")
        finally:
            self._refreshing = False
            self._refresh_lock.release()

    def refresh_async(self) -> None:
        threading.Thread(target=self.refresh, name="state-refresh", daemon=True).start()

    def save_settings(self, payload: Any) -> list[str]:
        if not isinstance(payload, dict):
            raise TypeError("Formato inválido")
        changes = {key: validate_value(SETTINGS[key], value) for key, value in payload.items() if key in SETTINGS}
        if not changes:
            raise ValueError("Nenhuma configuração válida")
        self.files.write_env(changes)
        self.repository.store("settings", changes, "manager")
        return list(changes)

    def set_gamerule(self, rule: str, value: Any) -> str:
        if rule not in GAMERULES:
            raise KeyError(rule)
        validated = validate_value(GAMERULES[rule], value)
        self.bedrock.send(["gamerule", rule, validated])
        self.repository.store("gamerules", {rule: validated}, "manager")
        return validated

    def run_world_action(self, action: str) -> None:
        if action not in self.WORLD_ACTIONS:
            raise KeyError(action)
        self.bedrock.send(self.WORLD_ACTIONS[action])

    def time_action(self, action: str, payload: Any) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}
        if action == "preset" and payload.get("value") in self.TIME_PRESETS:
            value = payload["value"]
            self.bedrock.send(["time", "set", value])
            return {"action": action, "value": value}
        if action in {"set", "add"}:
            value = int(payload.get("value"))
            minimum, maximum = (0, 24000) if action == "set" else (1, 240000)
            if value < minimum or value > maximum:
                raise ValueError("valor fora do intervalo")
            self.bedrock.send(["time", action, str(value)])
            return {"action": action, "value": value}
        if action == "reset-days":
            self.bedrock.send(["time", "set", "0"])
            return {"action": action, "value": 0}
        if action == "query" and payload.get("value") in self.TIME_QUERIES:
            query = payload["value"]
            output = self.bedrock.send_and_read(["time", "query", query])
            numbers = re.findall(r"-?\d+", output)
            return {"action": action, "query": query, "value": int(numbers[-1]) if numbers else None}
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
            return {"action": action, "value": weather, "duration": duration}
        if action == "weather-query":
            output = self.bedrock.send_and_read(["weather", "query"])
            lowered = output.lower()
            weather = next((item for item in self.WEATHER_TYPES if item in lowered), "unknown")
            return {"action": action, "value": weather}
        raise KeyError(action)

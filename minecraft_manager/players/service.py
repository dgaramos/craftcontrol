from __future__ import annotations

import hashlib
import time
from typing import Any

from ..ports import EventPublisher, ServerConfiguration, ServerConsole, StateStore


class PlayerService:
    """Application use cases for durable players and in-game permissions."""

    def __init__(
        self,
        repository: StateStore,
        files: ServerConfiguration,
        console: ServerConsole,
        events: EventPublisher,
        bootstrap_operator: str = "",
    ) -> None:
        self.repository = repository
        self.files = files
        self.console = console
        self.events = events
        self.bootstrap_operator = bootstrap_operator

    def observe_presence(self, player: str, connected: bool, xuid: str = "") -> None:
        snapshot = self.repository.snapshot()
        players = {name.casefold(): name for name in snapshot["players"]}
        if connected:
            players[player.casefold()] = player
        else:
            players.pop(player.casefold(), None)
        self.repository.replace("players", {name: "online" for name in players.values()}, "bedrock-log")
        if xuid:
            self.repository.store("known_players", {player: xuid}, "bedrock-log")
        self.repository.observe_player(player, connected, xuid, "bedrock-log")
        self.repository.store("server", {"online": str(len(players))}, "bedrock-log")
        self.events.publish("state.changed", "bedrock-log", {"domains": ["players", "server"]})

    def record_derived_death(self, player: str, cause: str, raw: str) -> bool:
        fingerprint = hashlib.sha256(f"{raw}|{int(time.time() / 3)}".encode()).hexdigest()
        inserted = self.repository.record_player_death(player, cause, raw, "bedrock-log", fingerprint)
        if inserted:
            self.events.publish("player.death", "bedrock-log", {"player": player, "cause": cause, "derived": True})
            self.events.publish("state.changed", "bedrock-log", {"domains": ["player_profiles"], "player": player})
        return inserted

    def close_online_sessions(self, reason: str) -> list[str]:
        return self.repository.close_online_sessions(reason, "docker-events")

    def refresh_permissions(self, publish: bool = True) -> None:
        known = self.repository.snapshot().get("known_players", {})
        names_by_xuid = {xuid: name for name, xuid in known.items()}
        values: dict[str, str] = {}
        try:
            permissions = self.files.read_permissions()
        except Exception as error:
            self.events.publish("permissions.reconciliation.failed", "permissions.json", {"error": str(error)[:240]})
            return
        for item in permissions:
            name = names_by_xuid.get(str(item["xuid"]))
            if name:
                values[name.casefold()] = str(item["permission"])
                self.repository.set_player_permission(name, str(item["permission"]), "permissions.json")
        self.repository.replace("permissions", values, "permissions.json")
        if publish:
            self.events.publish("state.changed", "permissions.json", {"domains": ["permissions"]})

    def bootstrap(self, online_players: list[str]) -> None:
        if not self.bootstrap_operator or self.repository.snapshot().get("bootstrap", {}).get("operator") == "done":
            return
        if self.bootstrap_operator.casefold() not in {name.casefold() for name in online_players}:
            return
        self.set_operator(self.bootstrap_operator, True)
        self.repository.store("bootstrap", {"operator": "done"}, "manager")

    def list_profiles(self) -> list[dict[str, Any]]:
        return self.repository.player_profiles()

    def profile(self, identity: str) -> dict[str, Any] | None:
        return self.repository.player_profile(identity)

    def set_operator(self, player: str, enabled: bool) -> None:
        self.console.set_operator(player, enabled)
        permission = "operator" if enabled else "member"
        self.repository.store("permissions", {player.casefold(): permission}, "manager")
        self.repository.set_player_permission(player, permission, "manager")
        self.events.publish("state.changed", "manager", {"domains": ["permissions"], "player": player})

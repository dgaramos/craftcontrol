from __future__ import annotations

import threading
import re
import time
from typing import Any

from .config import Settings
from .schema import GAMERULES, PROPERTY_NAMES, SETTINGS, validate_value
from .events import EventBroker
from .ports import ContainerOperations, EventPublisher, RuntimeSupervisor, ServerConfiguration, ServerConsole, StateStore
from .players import PlayerService
from .telemetry import PREFIX as TELEMETRY_PREFIX, parse_telemetry_line
from .telemetry_service import TelemetryService


class ManagerService:
    WORLD_ACTIONS = {
        "day": ["time", "set", "day"],
        "night": ["time", "set", "night"],
        "clear-weather": ["weather", "clear"],
    }
    TIME_PRESETS = {"sunrise", "day", "noon", "sunset", "night", "midnight"}
    WEATHER_TYPES = {"clear", "rain", "thunder"}
    TIME_QUERIES = {"daytime", "gametime", "day"}

    def __init__(
        self,
        repository: StateStore,
        files: ServerConfiguration,
        bedrock: ServerConsole,
        docker: ContainerOperations,
        bootstrap_operator: str = "",
        reconcile_seconds: int = 900,
        broker: EventPublisher | None = None,
        runtime: RuntimeSupervisor | None = None,
        player_service: PlayerService | None = None,
        telemetry_service: TelemetryService | None = None,
    ) -> None:
        self.repository = repository
        self.files = files
        self.bedrock = bedrock
        self.docker = docker
        self.bootstrap_operator = bootstrap_operator
        # The default keeps direct construction backwards-compatible for tests and
        # downstream imports. Production dependencies are assembled explicitly in
        # composition.compose_manager().
        self.broker = broker or EventBroker(repository)
        self.player_service = player_service or PlayerService(repository, files, bedrock, self.broker, bootstrap_operator)
        self.telemetry_service = telemetry_service or TelemetryService(repository, self.broker)
        self.runtime = runtime
        self._refresh_lock = threading.Lock()
        self._refreshing = False
        self._pending_rules: set[str] = set()
        self._pending_rules_lock = threading.Lock()
        self._gamerule_worker_running = False
        self._telemetry_sync_lock = threading.Lock()
        self._telemetry_sync_running = False
        self._telemetry_last_request = 0.0

    @classmethod
    def build(cls, settings: Settings) -> "ManagerService":
        """Compatibility constructor; new code should use compose_manager()."""
        from .composition import compose_manager

        return compose_manager(settings)

    def attach_runtime(self, runtime: RuntimeSupervisor) -> None:
        if self.runtime is not None:
            raise RuntimeError("runtime supervisor is already attached")
        self.runtime = runtime

    def initialize(self) -> None:
        self.repository.initialize()
        if self.runtime is not None:
            self.runtime.start()
        self.refresh_async(reason="manager-startup")

    @property
    def refreshing(self) -> bool:
        return self._refreshing

    def state(self) -> dict[str, Any]:
        return self.repository.snapshot(self._refreshing)

    def public_state(self) -> dict[str, Any]:
        snapshot = self.state()
        snapshot.pop("known_players", None)
        snapshot.pop("bootstrap", None)
        return snapshot

    def refresh(self, reason: str = "manual") -> None:
        if not self._refresh_lock.acquire(blocking=False):
            return
        self._refreshing = True
        started = time.time()
        self.broker.publish("state.reconciliation.started", reason, {"scope": "full"})
        try:
            _, env_values = self.files.read_env()
            properties = self.files.read_properties()
            settings = {key: env_values.get(key) or properties.get(PROPERTY_NAMES.get(key, ""), "") for key in SETTINGS}
            self.repository.store("settings", settings, "env+server.properties")
            gamerules, players, online, maximum, xuids = self.bedrock.query_state()
            if gamerules:
                self.repository.store("gamerules", gamerules, "bedrock-console")
            if maximum == 0:
                maximum = int(env_values.get("MAX_PLAYERS") or properties.get("max-players") or 0)
            if xuids:
                self.repository.store("known_players", xuids, "bedrock-log")
            self.repository.reconcile_online_players(players, xuids, "bedrock-console")
            self.repository.replace("players", {name: "online" for name in players}, "bedrock-console")
            self.repository.store("server", {"online": str(online), "max_players": str(maximum)}, "bedrock-console")
            self.refresh_permissions(publish=False)
            self.player_service.bootstrap(players)
            self.broker.publish("state.changed", reason, {"domains": ["settings", "gamerules", "players", "server"]})
            self.request_telemetry_snapshot_async(reason)
        except Exception as error:
            self.broker.publish("state.reconciliation.failed", reason, {"error": str(error)[:240]})
            raise
        finally:
            self.broker.publish("state.reconciliation.finished", reason, {"duration_seconds": time.time() - started})
            self._refreshing = False
            self._refresh_lock.release()

    def refresh_async(self, reason: str = "manual") -> None:
        threading.Thread(target=self.refresh, args=(reason,), name="state-refresh", daemon=True).start()

    def refresh_gamerules_async(self, rules: set[str]) -> None:
        with self._pending_rules_lock:
            self._pending_rules.update(rules)
            if self._gamerule_worker_running:
                return
            self._gamerule_worker_running = True

        def work() -> None:
            try:
                while True:
                    time.sleep(2)
                    with self._pending_rules_lock:
                        pending = set(self._pending_rules)
                        self._pending_rules.clear()
                    if not pending:
                        return
                    with self._refresh_lock:
                        self._refreshing = True
                        try:
                            values = self.bedrock.query_gamerules(pending)
                            if values:
                                self.repository.store("gamerules", values, "targeted-console")
                                self.broker.publish("state.changed", "targeted-console", {"domains": ["gamerules"], "keys": sorted(values)})
                        finally:
                            self._refreshing = False
            finally:
                with self._pending_rules_lock:
                    self._gamerule_worker_running = False
                    restart = bool(self._pending_rules)
                if restart:
                    self.refresh_gamerules_async(set())
        threading.Thread(target=work, name="gamerule-refresh", daemon=True).start()

    def player_event(self, player: str, connected: bool, xuid: str = "") -> None:
        self.player_service.observe_presence(player, connected, xuid)

    def close_online_sessions(self, reason: str) -> list[str]:
        """Application boundary used by lifecycle supervisors on abrupt stops."""
        return self.player_service.close_online_sessions(reason)

    def player_death_event(self, player: str, cause: str, raw: str) -> bool:
        return self.player_service.record_derived_death(player, cause, raw)

    def telemetry_event(self, envelope: dict[str, Any]) -> None:
        self.telemetry_service.ingest(envelope, self.request_telemetry_snapshot_async)

    def request_telemetry_snapshot_async(self, reason: str) -> None:
        with self._telemetry_sync_lock:
            now = time.monotonic()
            if self._telemetry_sync_running or now - self._telemetry_last_request < 5:
                self.broker.publish("telemetry.snapshot.coalesced", reason)
                return
            self._telemetry_sync_running = True
            self._telemetry_last_request = now

        def work() -> None:
            try:
                self.request_telemetry_snapshot(reason)
            finally:
                with self._telemetry_sync_lock:
                    self._telemetry_sync_running = False

        threading.Thread(target=work, name="telemetry-sync", daemon=True).start()

    def request_telemetry_snapshot(self, reason: str) -> int:
        try:
            self.repository.store("telemetry", {
                "status": "syncing", "sync_reason": reason, "last_request_at": str(time.time()),
            }, "manager")
            logs = self.bedrock.request_telemetry_snapshot()
            accepted = 0
            for line in logs.splitlines():
                if TELEMETRY_PREFIX not in line:
                    continue
                envelope = parse_telemetry_line(line)
                if envelope:
                    self.telemetry_event(envelope)
                    accepted += 1
            self.broker.publish("telemetry.snapshot.requested", reason)
            self.broker.publish("telemetry.snapshot.read", reason, {"envelopes": accepted})
            if accepted == 0 or self.state().get("telemetry", {}).get("status") != "healthy":
                message = "snapshot returned no envelopes" if accepted == 0 else "snapshot did not finish"
                self.repository.store("telemetry", {"status": "degraded", "last_error": message}, "manager")
                self.broker.publish("telemetry.snapshot.incomplete", reason, {"envelopes": accepted, "error": message})
            return accepted
        except Exception as error:
            self.repository.store("telemetry", {
                "status": "degraded", "last_error": str(error)[:240],
            }, "manager")
            self.broker.publish("telemetry.snapshot.failed", reason, {"error": str(error)[:240]})
            return 0

    def refresh_permissions(self, publish: bool = True) -> None:
        self.player_service.refresh_permissions(publish)

    def save_settings(self, payload: Any) -> list[str]:
        if not isinstance(payload, dict):
            raise TypeError("Formato inválido")
        changes = {key: validate_value(SETTINGS[key], value) for key, value in payload.items() if key in SETTINGS}
        if not changes:
            raise ValueError("Nenhuma configuração válida")
        self.files.write_env(changes)
        self.repository.store("settings", changes, "manager")
        self.broker.publish("state.changed", "manager", {"domains": ["settings"], "keys": list(changes)})
        return list(changes)

    def set_gamerule(self, rule: str, value: Any) -> str:
        if rule not in GAMERULES:
            raise KeyError(rule)
        validated = validate_value(GAMERULES[rule], value)
        self.bedrock.send(["gamerule", rule, validated])
        self.repository.store("gamerules", {rule: validated}, "manager")
        self.broker.publish("state.changed", "manager", {"domains": ["gamerules"], "keys": [rule]})
        return validated

    def run_world_action(self, action: str) -> None:
        if action not in self.WORLD_ACTIONS:
            raise KeyError(action)
        self.bedrock.send(self.WORLD_ACTIONS[action])

    def _bootstrap_operator(self, players: list[str]) -> None:
        self.player_service.bootstrap(players)

    def players(self) -> list[dict[str, Any]]:
        return self.player_service.list_profiles()

    def player_profile(self, identity: str) -> dict[str, Any] | None:
        return self.player_service.profile(identity)

    def player_activity(self, kind: str, player: str, source: str, search: str, days: int, page: int, page_size: int) -> dict[str, Any]:
        return self.player_service.activity(kind, player, source, search, days, page, page_size)

    def player_rankings(self, limit: int = 10) -> dict[str, Any]:
        return self.player_service.rankings(limit)

    def block_analytics(self, limit: int = 10) -> dict[str, Any]:
        return self.player_service.blocks(limit)

    def set_player_operator(self, player: str, enabled: bool) -> None:
        self.player_service.set_operator(player, enabled)

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
            self.broker.publish("state.changed", "manager", {"domains": ["weather"], "action": action})
            return {"action": action, "value": weather, "duration": duration}
        if action == "weather-query":
            output = self.bedrock.send_and_read(["weather", "query"])
            lowered = output.lower()
            weather = next((item for item in self.WEATHER_TYPES if item in lowered), "unknown")
            return {"action": action, "value": weather}
        raise KeyError(action)

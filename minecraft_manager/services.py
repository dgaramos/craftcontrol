from __future__ import annotations

import threading
import re
import time
import hashlib
import json
from typing import Any

from .bedrock import BedrockClient
from .config import Settings
from .docker_ops import DockerOperations
from .files import ServerFiles
from .repository import StateRepository
from .schema import GAMERULES, PROPERTY_NAMES, SETTINGS, validate_value
from .events import EventBroker
from .runtime import EventRuntime
from .telemetry import PREFIX as TELEMETRY_PREFIX, parse_telemetry_line


class ManagerService:
    WORLD_ACTIONS = {
        "day": ["time", "set", "day"],
        "night": ["time", "set", "night"],
        "clear-weather": ["weather", "clear"],
    }
    TIME_PRESETS = {"sunrise", "day", "noon", "sunset", "night", "midnight"}
    WEATHER_TYPES = {"clear", "rain", "thunder"}
    TIME_QUERIES = {"daytime", "gametime", "day"}

    def __init__(self, repository: StateRepository, files: ServerFiles, bedrock: BedrockClient, docker: DockerOperations, bootstrap_operator: str = "", reconcile_seconds: int = 900) -> None:
        self.repository = repository
        self.files = files
        self.bedrock = bedrock
        self.docker = docker
        self.bootstrap_operator = bootstrap_operator
        self.broker = EventBroker(repository)
        self.runtime = EventRuntime(self, self.broker, getattr(bedrock, "container_name", "minecraft-bedrock"), reconcile_seconds)
        self._refresh_lock = threading.Lock()
        self._refreshing = False
        self._pending_rules: set[str] = set()
        self._pending_rules_lock = threading.Lock()
        self._gamerule_worker_running = False
        self._telemetry_lock = threading.RLock()
        self._telemetry_sync_lock = threading.Lock()
        self._telemetry_sync_running = False
        self._telemetry_last_request = 0.0

    @classmethod
    def build(cls, settings: Settings) -> "ManagerService":
        return cls(
            StateRepository(settings.database),
            ServerFiles(settings.env_file, settings.properties_file, settings.permissions_file),
            BedrockClient(settings.container, list(GAMERULES), settings.console_wait_seconds),
            DockerOperations(settings.container, settings.project),
            settings.bootstrap_operator,
            settings.reconcile_seconds,
        )

    def initialize(self) -> None:
        self.repository.initialize()
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
            self._bootstrap_operator(players)
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
        snapshot = self.state()
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
        self.broker.publish("state.changed", "bedrock-log", {"domains": ["players", "server"]})

    def player_death_event(self, player: str, cause: str, raw: str) -> bool:
        fingerprint = hashlib.sha256(f"{raw}|{int(time.time() / 3)}".encode()).hexdigest()
        inserted = self.repository.record_player_death(player, cause, raw, "bedrock-log", fingerprint)
        if inserted:
            self.broker.publish("player.death", "bedrock-log", {"player": player, "cause": cause, "derived": True})
            self.broker.publish("state.changed", "bedrock-log", {"domains": ["player_profiles"], "player": player})
        return inserted

    def telemetry_event(self, envelope: dict[str, Any]) -> None:
        with self._telemetry_lock:
            topic = envelope["type"]
            sequence = int(envelope["sequence"])
            snapshot_topic = topic.startswith("snapshot.")
            telemetry = self.state().get("telemetry", {})
            last_sequence = int(telemetry["sequence"]) if telemetry.get("sequence", "").isdigit() else None
            status = telemetry.get("status", "waiting")
            resync_reason: str | None = None
            storage = envelope.get("data", {}).get("storage")
            storage = storage if isinstance(storage, dict) else None
            capabilities = envelope.get("data", {}).get("capabilities")
            capabilities = capabilities if isinstance(capabilities, dict) else None
            storage_blocked = bool(storage and (storage.get("persistenceBlocked") is True or storage.get("status") == "blocked"))
            known_storage_blocked = storage_blocked or telemetry.get("persistence_blocked") == "true"

            pack_reset = topic == "telemetry.started" and last_sequence is not None and sequence < last_sequence
            if not snapshot_topic and last_sequence is not None and sequence <= last_sequence and not pack_reset:
                self.broker.publish("telemetry.sequence.rejected", "behavior-pack", {
                    "sequence": sequence, "last_sequence": last_sequence, "topic": topic,
                })
                return

            updates = {
                "schema": str(envelope["schema"]), "sequence": str(sequence),
                "expected_sequence": str(sequence + 1), "last_topic": topic,
                "last_event_at": str(time.time()),
            }
            if storage:
                updates.update(
                    storage_version=str(storage.get("storageVersion", "")),
                    storage_status=str(storage.get("status", "unknown")),
                    persistence_blocked="true" if storage_blocked else "false",
                )
                if storage.get("migratedFrom") is not None:
                    updates["storage_migrated_from"] = str(storage["migratedFrom"])
            if capabilities:
                supported = sum(1 for value in capabilities.values() if isinstance(value, dict) and value.get("supported") is True)
                updates.update(
                    capabilities=json.dumps(capabilities, ensure_ascii=False, sort_keys=True),
                    capability_status="full" if supported == len(capabilities) else "limited",
                    capabilities_supported=str(supported),
                    capabilities_total=str(len(capabilities)),
                )
            if snapshot_topic:
                if topic == "snapshot.started":
                    updates.update(status="degraded" if storage_blocked else "syncing", snapshot_started_at=str(time.time()))
                elif topic == "snapshot.finished":
                    if known_storage_blocked:
                        updates.update(status="degraded", last_error="telemetry pack persistence is blocked")
                    else:
                        updates.update(status="healthy", last_snapshot_at=str(time.time()), last_error="")
            elif last_sequence is not None and sequence > last_sequence + 1:
                missing = sequence - last_sequence - 1
                updates.update(
                    status="degraded",
                    gap_count=str(int(telemetry.get("gap_count", "0")) + 1),
                    missing_events=str(int(telemetry.get("missing_events", "0")) + missing),
                    last_gap=f"{last_sequence + 1}-{sequence - 1}",
                    last_error=f"sequence gap: expected {last_sequence + 1}, received {sequence}",
                )
                resync_reason = "sequence-gap"
            elif topic == "telemetry.started":
                updates["status"] = "syncing"
                if pack_reset:
                    updates.update(
                        reset_count=str(int(telemetry.get("reset_count", "0")) + 1),
                        last_error=f"pack sequence reset: {last_sequence} -> {sequence}",
                    )
                resync_reason = "pack-started"
            elif status not in {"syncing", "degraded"}:
                updates["status"] = "healthy"

            if storage_blocked:
                updates.update(status="degraded", last_error=str(storage.get("error") or "telemetry pack persistence is blocked")[:240])

            accepted, players = self.repository.ingest_telemetry(envelope)
            if not accepted:
                return
            self.repository.store("telemetry", updates, "behavior-pack")
        self.broker.publish(f"telemetry.{topic}", "behavior-pack", {"players": players, "sequence": envelope["sequence"]})
        if players or topic in {"snapshot.finished", "telemetry.started"}:
            self.broker.publish("state.changed", "behavior-pack", {"domains": ["telemetry", "player_profiles"], "players": players})
        if resync_reason:
            self.broker.publish("telemetry.reconciliation.required", "behavior-pack", {
                "reason": resync_reason, "sequence": sequence,
            })
            self.request_telemetry_snapshot_async(resync_reason)

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
        known = self.state().get("known_players", {})
        names_by_xuid = {xuid: name for name, xuid in known.items()}
        values: dict[str, str] = {}
        try:
            permissions = self.files.read_permissions()
        except Exception as error:
            self.broker.publish("permissions.reconciliation.failed", "permissions.json", {"error": str(error)[:240]})
            return
        for item in permissions:
            name = names_by_xuid.get(str(item["xuid"]))
            if name:
                values[name.casefold()] = str(item["permission"])
                self.repository.set_player_permission(name, str(item["permission"]), "permissions.json")
        self.repository.replace("permissions", values, "permissions.json")
        if publish:
            self.broker.publish("state.changed", "permissions.json", {"domains": ["permissions"]})

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
        if not self.bootstrap_operator or self.repository.snapshot().get("bootstrap", {}).get("operator") == "done":
            return
        if self.bootstrap_operator.casefold() not in {name.casefold() for name in players}:
            return
        self.set_player_operator(self.bootstrap_operator, True)
        self.repository.store("bootstrap", {"operator": "done"}, "manager")

    def players(self) -> list[dict[str, Any]]:
        return self.repository.player_profiles()

    def player_profile(self, identity: str) -> dict[str, Any] | None:
        return self.repository.player_profile(identity)

    def set_player_operator(self, player: str, enabled: bool) -> None:
        self.bedrock.set_operator(player, enabled)
        self.repository.store("permissions", {player.casefold(): "operator" if enabled else "member"}, "manager")
        self.repository.set_player_permission(player, "operator" if enabled else "member", "manager")
        self.broker.publish("state.changed", "manager", {"domains": ["permissions"], "player": player})

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

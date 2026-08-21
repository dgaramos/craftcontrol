from __future__ import annotations

from typing import Any

from .ports import ContainerOperations, EventPublisher, RuntimeSupervisor, ServerConfiguration, ServerConsole, StateStore
from .players import PlayerService
from .telemetry_service import TelemetryService
from .server import WorldService
from .reconciliation import ReconciliationService
from .operations import ServerOperationService


class ManagerService:
    # Class-level constants preserved for callers that reference them directly.
    WORLD_ACTIONS = WorldService.WORLD_ACTIONS
    TIME_PRESETS = WorldService.TIME_PRESETS
    WEATHER_TYPES = WorldService.WEATHER_TYPES
    TIME_QUERIES = WorldService.TIME_QUERIES

    def __init__(
        self,
        repository: StateStore,
        files: ServerConfiguration,
        bedrock: ServerConsole,
        docker: ContainerOperations,
        broker: EventPublisher,
        bootstrap_operator: str = "",
        reconcile_seconds: int = 900,
        runtime: RuntimeSupervisor | None = None,
        player_service: PlayerService | None = None,
        telemetry_service: TelemetryService | None = None,
        world_service: WorldService | None = None,
        reconciliation_service: ReconciliationService | None = None,
        operation_service: ServerOperationService | None = None,
    ) -> None:
        self.repository = repository
        self.files = files
        self.bedrock = bedrock
        self.docker = docker
        self.bootstrap_operator = bootstrap_operator
        self.broker = broker
        if player_service is None:
            raise TypeError(
                "player_service is required. "
                "Use composition.compose_manager() to build ManagerService "
                "with all domain repositories injected."
            )
        self.player_service = player_service
        if telemetry_service is None:
            raise TypeError(
                "telemetry_service is required. "
                "Use composition.compose_manager() to build ManagerService "
                "with all domain repositories injected."
            )
        self.telemetry_service = telemetry_service
        self.runtime = runtime
        if world_service is None:
            raise TypeError(
                "world_service is required. "
                "Use composition.compose_manager() to build ManagerService "
                "with all domain services injected."
            )
        self._world = world_service
        if reconciliation_service is None:
            raise TypeError(
                "reconciliation_service is required. "
                "Use composition.compose_manager() to build ManagerService "
                "with all domain services injected."
            )
        self._reconciliation = reconciliation_service
        # operation_service is optional; None disables durable operation tracking.
        self.operation_service: ServerOperationService | None = operation_service

    def attach_runtime(self, runtime: RuntimeSupervisor) -> None:
        if self.runtime is not None:
            raise RuntimeError("runtime supervisor is already attached")
        self.runtime = runtime

    def initialize(self) -> None:
        self.repository.initialize()
        if self.runtime is not None:
            self.runtime.start()
        self.refresh_async(reason="manager-startup")

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def refreshing(self) -> bool:
        return self._reconciliation.refreshing

    def state(self) -> dict[str, Any]:
        return self.repository.snapshot(self._reconciliation.refreshing)

    def public_state(self) -> dict[str, Any]:
        snapshot = self.state()
        snapshot.pop("known_players", None)
        snapshot.pop("bootstrap", None)
        return snapshot

    # ------------------------------------------------------------------
    # Reconciliation delegates
    # ------------------------------------------------------------------

    def refresh(self, reason: str = "manual") -> None:
        self._reconciliation.refresh(reason)

    def refresh_async(self, reason: str = "manual") -> None:
        self._reconciliation.refresh_async(reason)

    def refresh_gamerules_async(self, rules: set[str]) -> None:
        self._reconciliation.refresh_gamerules_async(rules)

    def request_telemetry_snapshot_async(self, reason: str) -> None:
        self._reconciliation.request_telemetry_snapshot_async(reason)

    def request_telemetry_snapshot(self, reason: str) -> int:
        return self._reconciliation.request_telemetry_snapshot(reason)

    # ------------------------------------------------------------------
    # Telemetry event ingestion
    # ------------------------------------------------------------------

    def telemetry_event(self, envelope: dict[str, Any]) -> None:
        self.telemetry_service.ingest(envelope, self.request_telemetry_snapshot_async)

    # ------------------------------------------------------------------
    # World and time delegates
    # ------------------------------------------------------------------

    def run_world_action(self, action: str) -> None:
        self._world.run_world_action(action)

    def time_action(self, action: str, payload: Any) -> dict[str, Any]:
        return self._world.time_action(action, payload)

    # ------------------------------------------------------------------
    # Settings and gamerules
    # ------------------------------------------------------------------

    def save_settings(self, payload: Any) -> list[str]:
        from .schema import SETTINGS, validate_value
        if not isinstance(payload, dict):
            raise TypeError("Formato inválido")
        changes = {key: validate_value(SETTINGS[key], value) for key, value in payload.items() if key in SETTINGS}
        if not changes:
            raise ValueError("Nenhuma configuração válida")

        if self.operation_service is not None:
            # Route through the durable operation lifecycle (issue #190).
            # The apply_fn performs the actual disk write inside the operation.
            def _apply() -> None:
                self.files.write_env(changes)
                self.repository.store("settings", changes, "manager")
                self.broker.publish("state.changed", "manager", {"domains": ["settings"], "keys": list(changes)})

            self.operation_service.apply_restart_required(changes, _apply)
        else:
            # Fallback for contexts where operation tracking is not wired in
            # (e.g. existing tests that compose ManagerService directly).
            self.files.write_env(changes)
            self.repository.store("settings", changes, "manager")
            self.broker.publish("state.changed", "manager", {"domains": ["settings"], "keys": list(changes)})

        return list(changes)

    def set_gamerule(self, rule: str, value: Any) -> str:
        from .schema import GAMERULES, validate_value
        if rule not in GAMERULES:
            raise KeyError(rule)
        validated = validate_value(GAMERULES[rule], value)
        self.bedrock.send(["gamerule", rule, validated])
        self.repository.store("gamerules", {rule: validated}, "manager")
        self.broker.publish("state.changed", "manager", {"domains": ["gamerules"], "keys": [rule]})
        return validated

    # ------------------------------------------------------------------
    # Player delegates
    # ------------------------------------------------------------------

    def player_event(self, player: str, connected: bool, xuid: str = "") -> None:
        self.player_service.observe_presence(player, connected, xuid)

    def close_online_sessions(self, reason: str) -> list[str]:
        """Application boundary used by lifecycle supervisors on abrupt stops."""
        return self.player_service.close_online_sessions(reason)

    def player_death_event(self, player: str, cause: str, raw: str) -> bool:
        return self.player_service.record_derived_death(player, cause, raw)

    def refresh_permissions(self, publish: bool = True) -> None:
        self.player_service.refresh_permissions(publish)

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

    def combat_analytics(self, limit: int = 10) -> dict[str, Any]:
        return self.player_service.combat(limit)

    def exploration_analytics(self, limit: int = 10) -> dict[str, Any]:
        return self.player_service.exploration(limit)

    def period_analytics(self, days: int = 30, limit: int = 10) -> dict[str, Any]:
        return self.player_service.periods(days, limit)

    def set_player_operator(self, player: str, enabled: bool) -> None:
        self.player_service.set_operator(player, enabled)

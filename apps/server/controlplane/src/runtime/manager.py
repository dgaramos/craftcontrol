from __future__ import annotations

from typing import Any

from ..ports import ContainerOperations, EventPublisher, RuntimeSupervisor, ServerConfiguration, ServerConsole, StateStore
from ..players import PlayerService
from ..telemetry.service import TelemetryService
from ..server import WorldService
from .reconciliation import ReconciliationService
from ..operations import ServerOperationService
from ..audit import AuditService
from ..core.sqlite import database_size_bytes, sqlite_diagnostics


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
        audit_service: AuditService | None = None,
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
        # audit_service is optional; None disables durable audit records.
        self.audit_service: AuditService | None = audit_service

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

    def diagnostics(self) -> dict[str, Any]:
        broker_diagnostics = getattr(self.broker, "diagnostics", None)
        telemetry_state = self.state().get("telemetry", {})
        return {
            "domains": self.telemetry_service.repository.domain_freshness(),
            "telemetry": self.telemetry_service.diagnostics(),
            "broker": broker_diagnostics() if callable(broker_diagnostics) else {},
            "runtime_refreshing": self.refreshing,
            "persistence": {
                **sqlite_diagnostics(),
                "database_size_bytes": database_size_bytes(self.repository.path),
            },
            "runtime": self._reconciliation.diagnostics(),
            "telemetry_state": {
                key: telemetry_state.get(key)
                for key in ("status", "sequence", "expected_sequence", "gap_count", "missing_events", "reset_count", "last_snapshot_at", "last_event_at")
            },
        }

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

    def run_world_action(self, action: str, actor: str | None = None) -> None:
        try:
            self._world.run_world_action(action)
        except KeyError:
            self._audit(actor=actor, action="world.action", target=None, result="failure")
            raise
        self._audit(actor=actor, action="world.action", target=action, result="success")

    def time_action(self, action: str, payload: Any, actor: str | None = None) -> dict[str, Any]:
        try:
            result = self._world.time_action(action, payload)
        except (KeyError, ValueError):
            self._audit(actor=actor, action="world.time.action", target=None, result="failure")
            raise
        self._audit(actor=actor, action="world.time.action", target=action, result="success")
        return result

    # ------------------------------------------------------------------
    # Settings and gamerules
    # ------------------------------------------------------------------

    def save_settings(self, payload: Any, actor: str | None = None) -> tuple[list[str], str | None]:
        """Persist restart-required settings and return the changed keys and operation id.

        When an operation service is wired, the change is routed through the
        durable operation lifecycle (issue #190) before the server is restarted.
        The operation id is returned so the HTTP layer can expose it for polling.
        Returns ``(changed_keys, operation_id)``; ``operation_id`` is ``None``
        when operation tracking is not active.
        """
        from ..core.schema import SETTINGS, validate_value
        if not isinstance(payload, dict):
            self._audit(actor=actor, action="server.settings.changed", target=None, result="failure")
            raise TypeError("Formato inválido")
        changes = {key: validate_value(SETTINGS[key], value) for key, value in payload.items() if key in SETTINGS}
        if not changes:
            self._audit(actor=actor, action="server.settings.changed", target=None, result="failure")
            raise ValueError("Nenhuma configuração válida")

        if self.operation_service is not None:
            # Route through the durable operation lifecycle (issue #190).
            # The host agent writes server.properties in its PREPARE stage.
            # The backend stores only observed state after verification.
            def _apply() -> None:
                return None

            operation = self.operation_service.apply_restart_required(changes, _apply)
            self._audit(
                actor=actor,
                action="server.settings.changed",
                target=None,
                result="success",
                metadata={"changed": sorted(changes)},
            )
            return list(changes), operation.operation_id
        else:
            # Fallback for contexts where operation tracking is not wired in
            # (e.g. existing tests that compose ManagerService directly).
            from ..core.schema import PROPERTY_NAMES
            self.files.write_properties({PROPERTY_NAMES[key]: value for key, value in changes.items()})
            self.repository.store("settings", changes, "server.properties")
            self.broker.publish("state.changed", "manager", {"domains": ["settings"], "keys": list(changes)})

        self._audit(
            actor=actor,
            action="server.settings.changed",
            target=None,
            result="success",
            metadata={"changed": sorted(changes)},
        )
        return list(changes), None

    def retry_settings_operation(self, operation_id: str) -> str:
        """Retry a failed or divergent settings operation as a new linked operation.

        Issue #194: the original operation is preserved; the retry is linked via
        ``parent_operation_id``.  Returns the new operation id.

        Raises ``ValueError`` if the operation does not exist, is not a
        failed/divergent settings operation, or no operation service is wired.
        Raises ``ConflictingOperationError`` if another operation is active.
        """
        if self.operation_service is None:
            raise ValueError("operation tracking not active")
        origin = self.operation_service.get_operation(operation_id)
        if origin is None:
            raise ValueError(f"operation {operation_id!r} not found")
        changes = origin.requested_changes

        def _apply() -> None:
            return None

        retry = self.operation_service.retry_operation(operation_id, _apply)
        return retry.operation_id

    # ------------------------------------------------------------------
    # Audit helper
    # ------------------------------------------------------------------

    def _audit(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        result: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write a sanitized audit record when audit_service is wired."""
        if self.audit_service is not None:
            self.audit_service.write(
                actor=actor,
                action=action,
                target=target,
                result=result,
                metadata=metadata or {},
            )

    def set_gamerule(self, rule: str, value: Any, actor: str | None = None) -> str:
        from ..core.schema import GAMERULES, validate_value
        if rule not in GAMERULES:
            self._audit(actor=actor, action="server.gamerule.changed", target=None, result="failure")
            raise KeyError(rule)
        validated = validate_value(GAMERULES[rule], value)
        self.bedrock.send(["gamerule", rule, validated])
        self.repository.store("gamerules", {rule: validated}, "manager")
        self.broker.publish("state.changed", "manager", {"domains": ["gamerules"], "keys": [rule]})
        self._audit(actor=actor, action="server.gamerule.changed", target=rule, result="success", metadata={"value": validated})
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

    def set_player_operator(self, player: str, enabled: bool, actor: str | None = None) -> None:
        self.player_service.set_operator(player, enabled)
        self._audit(
            actor=actor,
            action="players.operator.changed",
            target=player,
            result="success",
            metadata={"enabled": enabled},
        )

    def set_player_game_mode(self, player: str, mode: str) -> str | None:
        return self.player_service.set_game_mode(player, mode)

"""Full and targeted reconciliation use cases."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .ports import EventPublisher, ServerConfiguration, ServerConsole, StateStore
from .schema import GAMERULES, PROPERTY_NAMES, SETTINGS
from .telemetry.telemetry import PREFIX as TELEMETRY_PREFIX, parse_telemetry_line

if TYPE_CHECKING:
    from .players import PlayerService
    from .telemetry.service import TelemetryService


class ReconciliationService:
    """Coordinates full reconciliation, targeted gamerule refresh, and telemetry snapshots.

    Injects a ``telemetry_snapshot_fn`` callback so callers (e.g. ManagerService) can
    keep the async-coalescing logic in one place and remain patchable in tests.
    """

    def __init__(
        self,
        repository: StateStore,
        files: ServerConfiguration,
        bedrock: ServerConsole,
        broker: EventPublisher,
        player_service: "PlayerService",
        telemetry_service: "TelemetryService",
        telemetry_snapshot_fn: Callable[[str], None] | None = None,
        thread_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.repository = repository
        self.files = files
        self.bedrock = bedrock
        self.broker = broker
        self.player_service = player_service
        self.telemetry_service = telemetry_service
        # Callback used when a refresh wants to trigger a telemetry snapshot.
        # Defaults to self.request_telemetry_snapshot_async so this class is
        # self-contained when used standalone.
        self._telemetry_snapshot_fn: Callable[[str], None] = (
            telemetry_snapshot_fn or self.request_telemetry_snapshot_async
        )
        self._thread_factory = thread_factory or threading.Thread
        self._time_fn: Callable[[], float] = time.time

        self._refresh_lock = threading.Lock()
        self._refreshing = False
        self._pending_rules: set[str] = set()
        self._pending_rules_lock = threading.Lock()
        self._gamerule_worker_running = False
        self._telemetry_sync_lock = threading.Lock()
        self._telemetry_sync_running = False
        self._telemetry_last_request = 0.0
        self._reconciliation_diagnostics: dict[str, int | float] = {
            "count": 0,
            "duration_ms_total": 0.0,
            "duration_ms_max": 0.0,
            "duration_ms_last": 0.0,
        }

    @property
    def refreshing(self) -> bool:
        return self._refreshing

    def diagnostics(self) -> dict[str, int | bool | dict[str, int | float]]:
        with self._pending_rules_lock, self._telemetry_sync_lock:
            return {
                "refreshing": self._refreshing,
                "pending_gamerule_refreshes": len(self._pending_rules),
                "gamerule_worker_running": self._gamerule_worker_running,
                "snapshot_running": self._telemetry_sync_running,
                "reconciliation": dict(self._reconciliation_diagnostics),
            }

    # ------------------------------------------------------------------
    # Full reconciliation
    # ------------------------------------------------------------------

    def refresh(self, reason: str = "manual") -> None:
        if not self._refresh_lock.acquire(blocking=False):
            return
        self._refreshing = True
        started = self._time_fn()
        trigger_telemetry = False
        try:
            self.broker.publish("state.reconciliation.started", reason, {"scope": "full"})
            properties = self.files.read_properties()
            settings = {
                key: properties.get(PROPERTY_NAMES.get(key, ""), "")
                for key in SETTINGS
            }
            self.repository.store("settings", settings, "server.properties")
            gamerules, players, online, maximum, xuids = self.bedrock.query_state()
            if gamerules:
                self.repository.store("gamerules", gamerules, "bedrock-console")
            if maximum == 0:
                maximum = int(properties.get("max-players") or 0)
            if xuids:
                self.repository.store("known_players", xuids, "bedrock-log")
            self.player_service.reconcile_online_players(players, xuids, "bedrock-console")
            self.repository.replace("players", {name: "online" for name in players}, "bedrock-console")
            self.repository.store("server", {"online": str(online), "max_players": str(maximum)}, "bedrock-console")
            self.player_service.refresh_permissions(publish=False)
            self.player_service.bootstrap(players)
            self.broker.publish("state.changed", reason, {"domains": ["settings", "gamerules", "players", "server"]})
            trigger_telemetry = True
        except Exception as error:
            self.broker.publish("state.reconciliation.failed", reason, {"error": str(error)[:240]})
            raise
        finally:
            elapsed_s = self._time_fn() - started
            elapsed_ms = elapsed_s * 1000
            try:
                self.broker.publish(
                    "state.reconciliation.finished", reason, {"duration_seconds": elapsed_s}
                )
            finally:
                if trigger_telemetry:
                    self._reconciliation_diagnostics["count"] = int(self._reconciliation_diagnostics["count"]) + 1
                    self._reconciliation_diagnostics["duration_ms_total"] = float(self._reconciliation_diagnostics["duration_ms_total"]) + elapsed_ms
                    self._reconciliation_diagnostics["duration_ms_last"] = elapsed_ms
                    if elapsed_ms > float(self._reconciliation_diagnostics["duration_ms_max"]):
                        self._reconciliation_diagnostics["duration_ms_max"] = elapsed_ms
                self._refreshing = False
                self._refresh_lock.release()

        # Called outside the lock so a slow or synchronous callback cannot
        # block concurrent refresh attempts from being skipped.
        if trigger_telemetry:
            try:
                self._telemetry_snapshot_fn(reason)
            except Exception as error:
                self.broker.publish("telemetry.snapshot.trigger.failed", reason, {"error": str(error)[:240]})

    def refresh_async(self, reason: str = "manual") -> None:
        self._thread_factory(target=self.refresh, args=(reason,), name="state-refresh", daemon=True).start()

    def refresh_settings_from_properties(self, reason: str = "operation-failure") -> None:
        """Refresh settings from Bedrock's effective configuration without mutation.

        ``server.properties`` is the canonical Bedrock configuration. The
        deployment ``.env`` intentionally does not participate in settings
        reconciliation, preventing stale Compose inputs from masking reality.
        """
        properties = self.files.read_properties()
        settings = {
            key: properties.get(PROPERTY_NAMES.get(key, ""), "")
            for key in SETTINGS
        }
        self.repository.store("settings", settings, "server.properties")
        self.broker.publish("state.changed", reason, {"domains": ["settings"]})

    # ------------------------------------------------------------------
    # Targeted gamerule refresh
    # ------------------------------------------------------------------

    def refresh_gamerules_async(self, rules: set[str]) -> None:
        unknown = rules - GAMERULES.keys()
        if unknown:
            import logging
            logging.getLogger(__name__).warning(
                "refresh_gamerules_async: ignoring unknown gamerule names: %s", sorted(unknown)
            )
            rules = rules - unknown
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
                                self.broker.publish(
                                    "state.changed", "targeted-console",
                                    {"domains": ["gamerules"], "keys": sorted(values)},
                                )
                        except Exception:
                            with self._pending_rules_lock:
                                self._pending_rules.update(pending)
                            raise
                        finally:
                            self._refreshing = False
            finally:
                with self._pending_rules_lock:
                    self._gamerule_worker_running = False
                    restart = bool(self._pending_rules)
                if restart:
                    self.refresh_gamerules_async(set())

        self._thread_factory(target=work, name="gamerule-refresh", daemon=True).start()

    # ------------------------------------------------------------------
    # Telemetry snapshot
    # ------------------------------------------------------------------

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

        self._thread_factory(target=work, name="telemetry-sync", daemon=True).start()

    def request_telemetry_snapshot(self, reason: str) -> int:
        try:
            self.repository.store(
                "telemetry",
                {"status": "syncing", "sync_reason": reason, "last_request_at": str(time.time())},
                "manager",
            )
            logs = self.bedrock.request_telemetry_snapshot()
            accepted = 0
            for line in logs.splitlines():
                if TELEMETRY_PREFIX not in line:
                    continue
                envelope = parse_telemetry_line(line)
                if envelope:
                    self.telemetry_service.ingest(envelope, self._telemetry_snapshot_fn)
                    accepted += 1
            self.broker.publish("telemetry.snapshot.requested", reason)
            self.broker.publish("telemetry.snapshot.read", reason, {"envelopes": accepted})
            state = self.repository.snapshot(self._refreshing)
            if accepted == 0 or state.get("telemetry", {}).get("status") != "healthy":
                message = "snapshot returned no envelopes" if accepted == 0 else "snapshot did not finish"
                self.repository.store("telemetry", {"status": "degraded", "last_error": message}, "manager")
                self.broker.publish(
                    "telemetry.snapshot.incomplete", reason, {"envelopes": accepted, "error": message}
                )
            return accepted
        except Exception as error:
            self.repository.store(
                "telemetry", {"status": "degraded", "last_error": str(error)[:240]}, "manager"
            )
            self.broker.publish("telemetry.snapshot.failed", reason, {"error": str(error)[:240]})
            return 0

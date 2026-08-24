"""Server-operation orchestration service.

Routes restart-required server changes through the durable lifecycle contract,
serialises conflicting mutations, and performs bounded Bedrock observation to
confirm or report a divergent outcome.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from typing import Any

# Minimum age (seconds) an orphan operation must have before it is abandoned.
# This prevents a new worker from racing against a still-running worker in
# graceful-reload scenarios (e.g. Gunicorn SIGWINCH).  An operation updated
# within this window is left untouched; the previous worker will either finish
# or the next startup cycle will catch it once it truly stalls.
ORPHAN_STALENESS_SECONDS = 30

from .lifecycle import (
    OperationStage,
    OperationState,
    ServerOperation,
)
from ..ports import ContainerOperations, EventPublisher, OperationStore, ServerConfiguration, ThreadFactory
from ..schema import PROPERTY_NAMES, SETTINGS, validate_value

LOGGER = logging.getLogger(__name__)

# Maximum seconds to wait for Bedrock to become healthy after restart.
DEFAULT_HEALTH_TIMEOUT_SECONDS = 120
# Polling interval while waiting for health.
HEALTH_POLL_INTERVAL_SECONDS = 5


class ConflictingOperationError(Exception):
    """Raised when a mutation is requested while another operation is active."""


class ServerOperationService:
    """Orchestrates restart-required changes as tracked server operations.

    Issue #189 (reconcile) and #190 (tracked execution) are both implemented
    here:
    - All restart-required mutations go through ``apply_restart_required``.
    - A single non-terminal operation per server_id is enforced.
    - After Compose recreation, bounded polling verifies Bedrock health.
    - The terminal state is CONFIRMED, FAILED, or DIVERGENT — never optimistic.
    """

    def __init__(
        self,
        operation_repository: OperationStore,
        docker: ContainerOperations,
        broker: EventPublisher,
        configuration: ServerConfiguration,
        thread_factory: ThreadFactory,
        server_id: str = "default",
        health_timeout: int = DEFAULT_HEALTH_TIMEOUT_SECONDS,
    ) -> None:
        self._repo = operation_repository
        self._docker = docker
        self._broker = broker
        self._configuration = configuration
        self._server_id = server_id
        self._health_timeout = health_timeout
        self._thread_factory = thread_factory
        # Protects the check-then-create sequence on this process.
        self._lock = threading.Lock()
        self._reconcile_startup_orphans()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_restart_required(
        self,
        changes: dict[str, Any],
        apply_fn: Any,
        *,
        correlation_id: str | None = None,
    ) -> ServerOperation:
        """Execute a restart-required change as a tracked operation.

        ``apply_fn`` is a zero-argument callable that writes the change to disk
        (e.g. write_env) and must raise on failure.  It is called after the
        operation is created and before the container is restarted.

        The operation progresses through all stages synchronously in a
        background thread so the HTTP response returns immediately with the
        operation record.
        """
        operation = self._create_or_reject(changes, correlation_id)
        thread = self._thread_factory(
            target=self._run,
            args=(operation, apply_fn),
            daemon=True,
            name=f"op-{operation.operation_id[:8]}",
        )
        thread.start()
        return operation

    def get_operation(self, operation_id: str) -> ServerOperation | None:
        return self._repo.get(operation_id)

    def get_latest(self) -> ServerOperation | None:
        return self._repo.get_latest(self._server_id)

    def get_active(self) -> ServerOperation | None:
        return self._repo.get_active(self._server_id)

    def list_recent(self, limit: int = 10) -> list[ServerOperation]:
        return self._repo.list_recent(self._server_id, limit)

    def request_reconciliation(self, operation_id: str) -> ServerOperation | None:
        """Re-observe Bedrock for a terminal operation and update its outcome.

        Issue #194 recovery action: re-observes the container and, when the
        server is online and the operation has verifiable changes, re-evaluates
        whether the effective configuration matches to produce a confirmed,
        divergent, or failed terminal state.  Returns the refreshed operation
        or None if the operation does not exist or is still running.

        The read-modify-write is performed atomically via ``fetch_and_update``
        (issue #251) so the snapshot fed to the reconciliation logic is always
        fresh at the moment the write lock is granted.
        """
        # A quick non-locking read lets us bail out early (wrong server, not
        # terminal, or not found) without acquiring the write lock at all.
        probe = self._repo.get(operation_id)
        if (
            probe is None
            or probe.server_id != self._server_id
            or probe.state not in {OperationState.FAILED, OperationState.DIVERGENT}
        ):
            return probe

        # Observe the container outside the write lock — it may be slow.
        obs = self._observe_container()

        result: ServerOperation | None = None

        def _apply(operation: ServerOperation) -> None:
            nonlocal result
            # Re-check eligibility on the fresh snapshot inside the write lock.
            if (
                operation.server_id != self._server_id
                or operation.state not in {OperationState.FAILED, OperationState.DIVERGENT}
            ):
                result = operation
                return

            operation.update_observation(obs)

            unverifiable = sorted(set(operation.requested_changes) - PROPERTY_NAMES.keys())
            verifiable_changes = {k: v for k, v in operation.requested_changes.items() if k in PROPERTY_NAMES}

            if unverifiable:
                # Any unverifiable key blocks confirmation — mirrors _run REVIEW rejection.
                operation.observation["reconciliation_result"] = {
                    "state": operation.state.value,
                    "reconciled_at": _now(),
                    "evidence": {"unverifiable_settings": unverifiable},
                }
            elif obs.get("online") and verifiable_changes:
                try:
                    verified, evidence = self._verify_configuration(operation)
                    operation.update_observation(evidence)
                    if not evidence.get("online"):
                        operation.state = OperationState.FAILED
                        operation.terminal_error = "server offline during configuration verification"
                    elif verified:
                        operation.state = OperationState.CONFIRMED
                        operation.terminal_error = None
                    else:
                        operation.state = OperationState.DIVERGENT
                        if not operation.terminal_error:
                            operation.terminal_error = "effective configuration differs from requested changes"
                    operation.observation["reconciliation_result"] = {
                        "state": operation.state.value,
                        "reconciled_at": _now(),
                        "evidence": evidence,
                    }
                except Exception as exc:
                    operation.state = OperationState.FAILED
                    operation.terminal_error = f"reconciliation verification failed: {exc}"
                    operation.observation["reconciliation_result"] = {
                        "state": OperationState.FAILED.value,
                        "reconciled_at": _now(),
                        "evidence": {"error": str(exc)},
                    }
                    LOGGER.warning(
                        "server_operation reconciliation verification failed operation_id=%s: %s",
                        operation_id, exc,
                    )
            elif not obs.get("online") and operation.state == OperationState.DIVERGENT:
                # Server is now offline; divergent result is no longer observable.
                operation.state = OperationState.FAILED
                operation.terminal_error = "server offline during reconciliation"

            result = operation

        updated = self._repo.fetch_and_update(operation_id, _apply)
        if updated is None:
            return None
        operation = result if result is not None else updated
        self._publish(operation)
        return operation

    def retry_operation(
        self,
        operation_id: str,
        apply_fn: Any,
        *,
        correlation_id: str | None = None,
    ) -> ServerOperation:
        """Create a new linked operation as a retry of a failed or divergent one.

        Issue #194: the original operation is preserved unchanged.  The retry
        is recorded as a separate operation with ``parent_operation_id`` set to
        the origin's ID so the relationship is auditable.

        Raises ``ValueError`` if the origin operation does not exist or is not
        in a terminal failure state.  Raises ``ConflictingOperationError`` if
        another non-terminal operation is already active.
        """
        with self._lock:
            origin = self._repo.get(operation_id)
            if origin is None:
                raise ValueError(f"operation {operation_id!r} not found")
            if origin.server_id != self._server_id:
                raise ValueError(f"operation {operation_id!r} belongs to a different server")
            if origin.state not in {OperationState.FAILED, OperationState.DIVERGENT}:
                raise ValueError(
                    f"operation {operation_id!r} is in state {origin.state.value!r}; "
                    "only failed or divergent operations may be retried"
                )
            active = self._repo.get_active(self._server_id)
            if active is not None:
                raise ConflictingOperationError(
                    f"Operation {active.operation_id} is already active in state {active.state.value}"
                )
            retry = ServerOperation.create(
                server_id=self._server_id,
                requested_changes=origin.requested_changes,
                correlation_id=correlation_id or origin.correlation_id,
                parent_operation_id=operation_id,
            )
            self._repo.save(retry)
        thread = self._thread_factory(
            target=self._run,
            args=(retry, apply_fn),
            daemon=True,
            name=f"op-{retry.operation_id[:8]}",
        )
        thread.start()
        return retry

    # ------------------------------------------------------------------
    # Background execution
    # ------------------------------------------------------------------

    def _run(self, operation: ServerOperation, apply_fn: Any) -> None:
        try:
            operation.start()
            self._repo.save(operation)

            # Stage: REVIEW
            self._begin(operation, OperationStage.REVIEW)
            unverifiable = sorted(set(operation.requested_changes) - PROPERTY_NAMES.keys())
            if unverifiable:
                self._fail(
                    operation,
                    OperationStage.REVIEW,
                    "requested changes cannot be verified against Bedrock properties",
                    evidence={"unverifiable_settings": unverifiable},
                )
                return
            normalized_changes: dict[str, str] = {}
            invalid_settings: dict[str, str] = {}
            for key, value in operation.requested_changes.items():
                try:
                    normalized_changes[key] = validate_value(SETTINGS[key], value)
                except (TypeError, ValueError) as exc:
                    invalid_settings[key] = str(exc)
            if invalid_settings:
                self._fail(
                    operation,
                    OperationStage.REVIEW,
                    "requested changes are invalid",
                    evidence={"invalid_settings": invalid_settings},
                )
                return
            operation.requested_changes = normalized_changes
            self._repo.save(operation)
            self._complete(operation, OperationStage.REVIEW, evidence={"changes": list(operation.requested_changes)})

            # Stage: BACKUP_VERIFY (skipped in basic delivery — no backup dep here)
            operation.skip_stage(OperationStage.BACKUP_VERIFY, reason="no_backup_required")
            self._repo.update_stage(operation, OperationStage.BACKUP_VERIFY)
            self._publish(operation)

            # Stage: PREPARE — write change to disk
            self._begin(operation, OperationStage.PREPARE)
            try:
                apply_fn()
            except Exception as exc:
                self._fail(operation, OperationStage.PREPARE, str(exc))
                return
            self._complete(operation, OperationStage.PREPARE)

            # Stage: RESTART — recreate the container
            self._begin(operation, OperationStage.RESTART)
            try:
                self._docker.execute("apply")
            except Exception as exc:
                obs = self._observe_container()
                operation.update_observation(obs)
                self._fail(operation, OperationStage.RESTART, str(exc), evidence=obs)
                return
            self._complete(operation, OperationStage.RESTART)

            # Stage: HEALTH_WAIT — poll until Bedrock is running
            self._begin(operation, OperationStage.HEALTH_WAIT)
            healthy, health_evidence = self._wait_for_health(operation)
            if not healthy:
                self._fail(
                    operation,
                    OperationStage.HEALTH_WAIT,
                    f"Bedrock did not become healthy within {self._health_timeout}s",
                    evidence=health_evidence,
                )
                return
            self._complete(operation, OperationStage.HEALTH_WAIT, evidence=health_evidence)

            # Stage: VERIFY — confirm effective Bedrock configuration matches request
            self._begin(operation, OperationStage.VERIFY)
            try:
                verified, evidence = self._verify_configuration(operation)
            except Exception as exc:
                evidence = {
                    **self._observe_container(),
                    "configuration_checked_at": _now(),
                    "verification_error": str(exc),
                }
                operation.update_observation(evidence)
                self._fail(
                    operation,
                    OperationStage.VERIFY,
                    f"could not verify effective configuration: {exc}",
                    evidence=evidence,
                )
                return
            operation.update_observation(evidence)
            if not evidence.get("online"):
                self._fail(
                    operation,
                    OperationStage.VERIFY,
                    "Bedrock became unhealthy during configuration verification",
                    evidence=evidence,
                )
                return
            if not verified:
                operation.diverge("effective configuration differs from requested changes", evidence=evidence)
                self._repo.save(operation)
                self._publish(operation)
                LOGGER.warning(
                    "server_operation divergent operation_id=%s differences=%s",
                    operation.operation_id,
                    evidence["differences"],
                )
                return
            self._complete(operation, OperationStage.VERIFY, evidence=evidence)

            # Stage: CONFIRM
            self._begin(operation, OperationStage.CONFIRM)
            operation.confirm(evidence={"confirmed_at": _now(), "last_confirmed_at": _now()})
            self._repo.save(operation)
            self._publish(operation)
            LOGGER.info(
                "server_operation confirmed operation_id=%s changes=%s",
                operation.operation_id,
                list(operation.requested_changes),
            )

        except Exception as exc:
            LOGGER.exception("server_operation unexpected failure operation_id=%s", operation.operation_id)
            if not operation.state.is_terminal:
                active = operation.active_stage
                stage = active.stage if active else OperationStage.REVIEW
                operation.fail_stage(stage, f"internal error: {exc}")
                self._repo.save(operation)
                self._publish(operation)

    # ------------------------------------------------------------------
    # Stage helpers
    # ------------------------------------------------------------------

    def _begin(self, operation: ServerOperation, stage: OperationStage) -> None:
        operation.begin_stage(stage)
        self._repo.update_stage(operation, stage)
        self._publish(operation)

    def _complete(
        self, operation: ServerOperation, stage: OperationStage, evidence: dict[str, Any] | None = None
    ) -> None:
        operation.complete_stage(stage, evidence)
        self._repo.update_stage(operation, stage)
        self._publish(operation)

    def _fail(
        self, operation: ServerOperation, stage: OperationStage, error: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        operation.fail_stage(stage, error, evidence)
        self._repo.save(operation)
        self._publish(operation)
        LOGGER.warning(
            "server_operation failed operation_id=%s stage=%s error=%s",
            operation.operation_id, stage.value, error,
        )

    # ------------------------------------------------------------------
    # Reconciliation helpers (issue #189)
    # ------------------------------------------------------------------

    def _wait_for_health(
        self, operation: ServerOperation
    ) -> tuple[bool, dict[str, Any]]:
        """Poll the container until it reports healthy or the deadline expires.

        Persists every observation so the active stage retains current evidence
        and ``updated_at`` stays within ``ORPHAN_STALENESS_SECONDS``. Without
        this heartbeat, a new worker
        started more than ``ORPHAN_STALENESS_SECONDS`` into a health-wait
        window would incorrectly classify the still-live operation as an orphan
        and clobber it.
        """
        deadline = time.monotonic() + self._health_timeout
        observations: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            obs = self._observe_container()
            observations.append(obs)
            self._record_health_observation(operation, obs, len(observations))
            if obs.get("online"):
                return True, {"observations": len(observations), "last": obs}
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(HEALTH_POLL_INTERVAL_SECONDS, remaining))
        return False, {
            "observations": len(observations),
            "timed_out": True,
            "last": observations[-1] if observations else {},
        }

    def _record_health_observation(
        self, operation: ServerOperation, observation: dict[str, Any], count: int
    ) -> None:
        """Persist the latest health evidence while the operation is waiting."""
        operation.update_observation(observation)
        active_stage = operation.active_stage
        if active_stage is not None:
            active_stage.evidence.update({"observations": count, "last": observation})
        self._repo.update_stage(operation, OperationStage.HEALTH_WAIT)
        self._publish(operation)

    def _observe_container(self) -> dict[str, Any]:
        """Return a snapshot of current container state."""
        try:
            status = self._docker.status()
            return {
                "container_state": status.get("state", "unknown"),
                "online": bool(status.get("online")),
                "observed_at": _now(),
            }
        except Exception as exc:
            return {
                "container_state": "error",
                "online": False,
                "error": str(exc),
                "observed_at": _now(),
            }

    def _verify_configuration(self, operation: ServerOperation) -> tuple[bool, dict[str, Any]]:
        """Compare requested settings with Bedrock's generated server.properties.

        The Compose environment is only the requested input.  Bedrock writes its
        effective startup configuration to ``server.properties``; comparing the
        mapped properties after the health probe avoids treating a successful
        container command as confirmation.
        """
        properties = self._configuration.read_properties()
        expected = {
            PROPERTY_NAMES[key]: value
            for key, value in operation.requested_changes.items()
            if key in PROPERTY_NAMES
        }
        observed = {name: properties.get(name) for name in expected}
        differences = [
            {"property": name, "expected": value, "observed": observed[name]}
            for name, value in expected.items()
            if observed[name] != value
        ]
        return not differences, {
            **self._observe_container(),
            "configuration_checked_at": _now(),
            "expected_settings": expected,
            "observed_settings": observed,
            "differences": differences,
        }
    # ------------------------------------------------------------------
    # Startup reconciliation
    # ------------------------------------------------------------------

    def _reconcile_startup_orphans(self) -> None:
        """Fail non-terminal operations abandoned by a previous process instance.

        A daemon thread is killed on backend restart, leaving its operation
        record in PENDING or RUNNING state.  ``get_active`` would then block
        every future operation until the database is manually repaired.  This
        method runs synchronously during ``__init__`` — before any thread is
        created — so no lock is required.
        """
        try:
            active = self._repo.get_active(self._server_id)
        except sqlite3.OperationalError:
            # Schema not yet migrated (e.g. first boot or test DB without migrations).
            # No orphans can exist in an empty schema.
            return
        if active is None:
            return
        # Guard against racing with a still-running worker during a graceful
        # reload (e.g. Gunicorn SIGWINCH).  The previous worker updates
        # `updated_at` on every stage transition, so a recently-touched
        # operation is still alive in another process and must not be clobbered.
        # CraftControl targets a single-worker homelab deployment, so this
        # window is ordinarily zero; the guard is a safety net for any
        # deployment that introduces overlapping workers.
        age = datetime.now(timezone.utc).timestamp() - active.updated_at
        if age < ORPHAN_STALENESS_SECONDS:
            LOGGER.info(
                "server_operation skipping orphan reclaim: operation_id=%s updated %.1fs ago"
                " (threshold %ds) — may still be running in another worker",
                active.operation_id,
                age,
                ORPHAN_STALENESS_SECONDS,
            )
            return
        LOGGER.warning(
            "server_operation orphan detected on startup operation_id=%s state=%s age=%.1fs — marking as failed",
            active.operation_id,
            active.state.value,
            age,
        )
        # Use the currently running stage if one exists, otherwise the first
        # stage so that fail_stage has a valid stage record to update.
        active_stage = active.active_stage
        stage = active_stage.stage if active_stage else OperationStage.REVIEW
        active.fail_stage(stage, "abandoned: process restarted")
        self._repo.save(active)
        self._publish(active)

    # ------------------------------------------------------------------
    # Lock and creation
    # ------------------------------------------------------------------

    def _create_or_reject(
        self,
        changes: dict[str, Any],
        correlation_id: str | None,
        parent_operation_id: str | None = None,
    ) -> ServerOperation:
        with self._lock:
            active = self._repo.get_active(self._server_id)
            if active is not None:
                raise ConflictingOperationError(
                    f"Operation {active.operation_id} is already active in state {active.state.value}"
                )
            operation = ServerOperation.create(
                server_id=self._server_id,
                requested_changes=changes,
                correlation_id=correlation_id,
                parent_operation_id=parent_operation_id,
            )
            self._repo.save(operation)
        return operation

    # ------------------------------------------------------------------
    # SSE publishing (issue #191)
    # ------------------------------------------------------------------

    def _publish(self, operation: ServerOperation) -> None:
        try:
            self._broker.publish(
                "operation.updated",
                "server-operation-service",
                operation.as_dict(),
            )
        except Exception:
            LOGGER.warning("failed to publish operation event", exc_info=True)


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()

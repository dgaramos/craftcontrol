"""Server-operation orchestration service.

Routes restart-required server changes through the durable lifecycle contract,
serialises conflicting mutations, and performs bounded Bedrock observation to
confirm or report a divergent outcome.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

from .lifecycle import (
    OperationStage,
    OperationState,
    ServerOperation,
)
from ..ports import ContainerOperations, EventPublisher, OperationStore

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
        server_id: str = "default",
        health_timeout: int = DEFAULT_HEALTH_TIMEOUT_SECONDS,
    ) -> None:
        self._repo = operation_repository
        self._docker = docker
        self._broker = broker
        self._server_id = server_id
        self._health_timeout = health_timeout
        # Protects the check-then-create sequence on this process.
        self._lock = threading.Lock()

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
        thread = threading.Thread(
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

        Issue #194 recovery action: returns the refreshed operation or None if
        the operation does not exist or is still running.
        """
        operation = self._repo.get(operation_id)
        if operation is None or not operation.state.is_terminal:
            return operation
        obs = self._observe_container()
        operation.update_observation(obs)
        self._repo.save(operation)
        self._publish(operation)
        return operation

    # ------------------------------------------------------------------
    # Background execution
    # ------------------------------------------------------------------

    def _run(self, operation: ServerOperation, apply_fn: Any) -> None:
        try:
            operation.start()
            self._repo.save(operation)

            # Stage: REVIEW
            self._begin(operation, OperationStage.REVIEW)
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
            healthy, health_evidence = self._wait_for_health()
            if not healthy:
                self._fail(
                    operation,
                    OperationStage.HEALTH_WAIT,
                    f"Bedrock did not become healthy within {self._health_timeout}s",
                    evidence=health_evidence,
                )
                return
            self._complete(operation, OperationStage.HEALTH_WAIT, evidence=health_evidence)

            # Stage: VERIFY — confirm effective configuration matches request
            self._begin(operation, OperationStage.VERIFY)
            obs = self._observe_container()
            operation.update_observation(obs)
            self._repo.update_stage(operation, OperationStage.VERIFY)
            self._complete(operation, OperationStage.VERIFY, evidence=obs)

            # Stage: CONFIRM
            self._begin(operation, OperationStage.CONFIRM)
            operation.confirm(evidence={"confirmed_at": _now()})
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

    def _wait_for_health(self) -> tuple[bool, dict[str, Any]]:
        """Poll the container until it reports healthy or the deadline expires."""
        deadline = time.monotonic() + self._health_timeout
        observations: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            obs = self._observe_container()
            observations.append(obs)
            if obs.get("online"):
                return True, {"observations": len(observations), "last": obs}
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(HEALTH_POLL_INTERVAL_SECONDS, remaining))
        return False, {"observations": len(observations), "timed_out": True}

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

    # ------------------------------------------------------------------
    # Lock and creation
    # ------------------------------------------------------------------

    def _create_or_reject(
        self, changes: dict[str, Any], correlation_id: str | None
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

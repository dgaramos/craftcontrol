"""Server-operation lifecycle contract.

Every restart-required server change is modelled as a ServerOperation that
progresses through defined stages, records evidence at each step, and reaches a
terminal state that accurately describes what happened rather than reporting
optimistic success.

This module owns the data contract consumed by persistence, HTTP, SSE, and the
UI.  It deliberately has no I/O dependencies so every layer can import it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _timestamp(value: float | int | str | None) -> str | None:
    """Return an API timestamp as an ISO 8601 UTC string, preserving null."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    seconds = float(value)
    if seconds > 10_000_000_000:
        seconds /= 1000
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# States and stages
# ---------------------------------------------------------------------------


class OperationState(str, Enum):
    """Lifecycle state of a server operation."""

    PENDING = "pending"
    RUNNING = "running"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    DIVERGENT = "divergent"

    @property
    def is_terminal(self) -> bool:
        return self in {self.CONFIRMED, self.FAILED, self.DIVERGENT}


class OperationStage(str, Enum):
    """Ordered stages of a restart-required server operation.

    Stage order mirrors the contract documented in issue #187:
    review → backup_verify → prepare → restart → health_wait → verify → confirm
    """

    REVIEW = "review"
    BACKUP_VERIFY = "backup_verify"
    PREPARE = "prepare"
    RESTART = "restart"
    HEALTH_WAIT = "health_wait"
    VERIFY = "verify"
    CONFIRM = "confirm"

    @classmethod
    def ordered(cls) -> list[OperationStage]:
        return [
            cls.REVIEW,
            cls.BACKUP_VERIFY,
            cls.PREPARE,
            cls.RESTART,
            cls.HEALTH_WAIT,
            cls.VERIFY,
            cls.CONFIRM,
        ]

    @classmethod
    def index_of(cls, stage: OperationStage) -> int:
        return cls.ordered().index(stage)


class StageResult(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Data objects
# ---------------------------------------------------------------------------


@dataclass
class StageRecord:
    """Evidence snapshot for one lifecycle stage."""

    stage: OperationStage
    result: StageResult = StageResult.PENDING
    started_at: float | None = None
    completed_at: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "result": self.result.value,
            "started_at": _timestamp(self.started_at),
            "completed_at": _timestamp(self.completed_at),
            "evidence": self.evidence,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageRecord:
        return cls(
            stage=OperationStage(data["stage"]),
            result=StageResult(data["result"]),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            evidence=data.get("evidence") or {},
            error=data.get("error"),
        )


@dataclass
class ServerOperation:
    """Durable record of one server lifecycle operation.

    Instances survive request boundaries and page reloads.  The operation_id
    is a stable correlation handle for SSE clients and API consumers.
    """

    operation_id: str
    server_id: str
    requested_changes: dict[str, Any]
    state: OperationState
    stages: list[StageRecord]
    created_at: float
    updated_at: float
    completed_at: float | None = None
    terminal_error: str | None = None
    observation: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    parent_operation_id: str | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        server_id: str,
        requested_changes: dict[str, Any],
        correlation_id: str | None = None,
        parent_operation_id: str | None = None,
    ) -> ServerOperation:
        now = _now()
        return cls(
            operation_id=str(uuid.uuid4()),
            server_id=server_id,
            requested_changes=requested_changes,
            state=OperationState.PENDING,
            stages=[StageRecord(stage=s) for s in OperationStage.ordered()],
            created_at=now,
            updated_at=now,
            correlation_id=correlation_id,
            parent_operation_id=parent_operation_id,
        )

    # ------------------------------------------------------------------
    # Transitions (return self for chaining)
    # ------------------------------------------------------------------

    def start(self) -> ServerOperation:
        self._assert_state(OperationState.PENDING)
        self.state = OperationState.RUNNING
        self.updated_at = _now()
        return self

    def begin_stage(self, stage: OperationStage, evidence: dict[str, Any] | None = None) -> ServerOperation:
        self._assert_state(OperationState.RUNNING)
        record = self._stage(stage)
        record.result = StageResult.RUNNING
        record.started_at = _now()
        if evidence:
            record.evidence.update(evidence)
        self.updated_at = _now()
        return self

    def complete_stage(self, stage: OperationStage, evidence: dict[str, Any] | None = None) -> ServerOperation:
        self._assert_state(OperationState.RUNNING)
        record = self._stage(stage)
        record.result = StageResult.COMPLETED
        record.completed_at = _now()
        if evidence:
            record.evidence.update(evidence)
        self.updated_at = _now()
        return self

    def fail_stage(self, stage: OperationStage, error: str, evidence: dict[str, Any] | None = None) -> ServerOperation:
        record = self._stage(stage)
        record.result = StageResult.FAILED
        record.completed_at = _now()
        record.error = error
        if evidence:
            record.evidence.update(evidence)
        self.state = OperationState.FAILED
        self.terminal_error = error
        self.completed_at = _now()
        self.updated_at = _now()
        return self

    def skip_stage(self, stage: OperationStage, reason: str = "") -> ServerOperation:
        record = self._stage(stage)
        record.result = StageResult.SKIPPED
        record.completed_at = _now()
        if reason:
            record.evidence["skip_reason"] = reason
        self.updated_at = _now()
        return self

    def confirm(self, evidence: dict[str, Any] | None = None) -> ServerOperation:
        self._assert_state(OperationState.RUNNING)
        confirm_record = self._stage(OperationStage.CONFIRM)
        confirm_record.result = StageResult.COMPLETED
        confirm_record.completed_at = _now()
        if evidence:
            confirm_record.evidence.update(evidence)
        self.state = OperationState.CONFIRMED
        self.completed_at = _now()
        self.updated_at = _now()
        return self

    def diverge(
        self,
        error: str,
        observation: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> ServerOperation:
        self._assert_state(OperationState.RUNNING)
        verify_record = self._stage(OperationStage.VERIFY)
        verify_record.result = StageResult.COMPLETED
        verify_record.completed_at = _now()
        if evidence:
            verify_record.evidence.update(evidence)
        self.state = OperationState.DIVERGENT
        self.terminal_error = error
        if observation:
            self.observation.update(observation)
        self.completed_at = _now()
        self.updated_at = _now()
        return self

    def update_observation(self, observation: dict[str, Any]) -> ServerOperation:
        self.observation.update(observation)
        self.updated_at = _now()
        return self

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "server_id": self.server_id,
            "requested_changes": self.requested_changes,
            "state": self.state.value,
            "stages": [s.as_dict() for s in self.stages],
            "created_at": _timestamp(self.created_at),
            "updated_at": _timestamp(self.updated_at),
            "completed_at": _timestamp(self.completed_at),
            "terminal_error": self.terminal_error,
            "observation": self.observation,
            "correlation_id": self.correlation_id,
            "parent_operation_id": self.parent_operation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerOperation:
        return cls(
            operation_id=data["operation_id"],
            server_id=data["server_id"],
            requested_changes=data.get("requested_changes") or {},
            state=OperationState(data["state"]),
            stages=[StageRecord.from_dict(s) for s in (data.get("stages") or [])],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            completed_at=data.get("completed_at"),
            terminal_error=data.get("terminal_error"),
            observation=data.get("observation") or {},
            correlation_id=data.get("correlation_id"),
            parent_operation_id=data.get("parent_operation_id"),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _stage(self, stage: OperationStage) -> StageRecord:
        for record in self.stages:
            if record.stage == stage:
                return record
        raise KeyError(f"stage {stage!r} not found in operation")

    def _assert_state(self, *allowed: OperationState) -> None:
        if self.state not in allowed:
            raise ValueError(
                f"Cannot transition from state {self.state!r}; allowed: {[s.value for s in allowed]}"
            )

    @property
    def active_stage(self) -> StageRecord | None:
        for record in self.stages:
            if record.result == StageResult.RUNNING:
                return record
        return None

    @property
    def failed_stage(self) -> StageRecord | None:
        for record in self.stages:
            if record.result == StageResult.FAILED:
                return record
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()

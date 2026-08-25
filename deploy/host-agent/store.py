"""In-memory operation store with TTL eviction."""
from __future__ import annotations

import threading
import time
from typing import Any, Callable

# Results are retained at least this long after completion (seconds)
RESULT_RETENTION_SECONDS = 600


class OperationRecord:
    def __init__(self, operation_id: str) -> None:
        self.operation_id = operation_id
        self.status = "running"          # running | done
        self.current_stage: str | None = "prepare"
        self.outcome: str | None = None  # ok | error
        self.executor_ref: str | None = None
        self.health_reached: bool | None = None
        self.failed_stage: str | None = None
        self.detail: str | None = None
        self.error_code: str | None = None
        self.exception_type: str | None = None
        self.completed_at: float | None = None

    def to_running_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "status": "running",
            "current_stage": self.current_stage,
        }

    def to_done_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "status": "done",
            "outcome": self.outcome,
            "executor_ref": self.executor_ref,
            "health_reached": self.health_reached,
            "failed_stage": self.failed_stage,
            "detail": self.detail,
            "error_code": self.error_code,
            "exception_type": self.exception_type,
        }


class OperationStore:
    def __init__(self, time_func: Callable[[], float] = time.monotonic) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, OperationRecord] = {}
        self._time_func = time_func

    def get(self, operation_id: str) -> OperationRecord | None:
        with self._lock:
            return self._records.get(operation_id)

    def create(self, operation_id: str) -> OperationRecord | None:
        """Create a record. Returns None if already exists (conflict)."""
        with self._lock:
            if operation_id in self._records:
                return None
            rec = OperationRecord(operation_id)
            self._records[operation_id] = rec
            return rec

    def update(self, operation_id: str, **kwargs: Any) -> None:
        with self._lock:
            rec = self._records.get(operation_id)
            if rec is None:
                return
            for k, v in kwargs.items():
                setattr(rec, k, v)

    def evict_expired(self) -> None:
        """Remove completed records older than RESULT_RETENTION_SECONDS."""
        now = self._time_func()
        cutoff = now - RESULT_RETENTION_SECONDS
        with self._lock:
            expired = [
                oid for oid, rec in self._records.items()
                if rec.completed_at is not None and rec.completed_at < cutoff
            ]
            for oid in expired:
                del self._records[oid]

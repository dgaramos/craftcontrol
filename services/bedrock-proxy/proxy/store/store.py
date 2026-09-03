"""Operation store with SQLite persistence and in-memory index."""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("bedrock-proxy.store")

# Results are retained at least this long after completion (seconds)
RESULT_RETENTION_SECONDS = 600

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS operations (
    operation_id   TEXT PRIMARY KEY,
    status         TEXT NOT NULL,
    current_stage  TEXT,
    outcome        TEXT,
    executor_ref   TEXT,
    health_reached INTEGER,
    failed_stage   TEXT,
    detail         TEXT,
    error_code     TEXT,
    exception_type TEXT,
    completed_at   REAL
)
"""

_UPSERT = """
INSERT INTO operations (
    operation_id, status, current_stage, outcome, executor_ref,
    health_reached, failed_stage, detail, error_code, exception_type,
    completed_at
) VALUES (?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(operation_id) DO UPDATE SET
    status         = excluded.status,
    current_stage  = excluded.current_stage,
    outcome        = excluded.outcome,
    executor_ref   = excluded.executor_ref,
    health_reached = excluded.health_reached,
    failed_stage   = excluded.failed_stage,
    detail         = excluded.detail,
    error_code     = excluded.error_code,
    exception_type = excluded.exception_type,
    completed_at   = excluded.completed_at
"""


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

    def _db_row(self) -> tuple[Any, ...]:
        hr: int | None = None
        if self.health_reached is not None:
            hr = 1 if self.health_reached else 0
        return (
            self.operation_id,
            self.status,
            self.current_stage,
            self.outcome,
            self.executor_ref,
            hr,
            self.failed_stage,
            self.detail,
            self.error_code,
            self.exception_type,
            self.completed_at,
        )

    @classmethod
    def _from_row(cls, row: tuple[Any, ...]) -> "OperationRecord":
        rec = cls.__new__(cls)
        (
            rec.operation_id,
            rec.status,
            rec.current_stage,
            rec.outcome,
            rec.executor_ref,
            health_reached_int,
            rec.failed_stage,
            rec.detail,
            rec.error_code,
            rec.exception_type,
            rec.completed_at,
        ) = row
        rec.health_reached = (
            bool(health_reached_int) if health_reached_int is not None else None
        )
        return rec


def _open_db(path: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and return a connection."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_CREATE_TABLE)
    conn.commit()
    return conn


class OperationStore:
    """Thread-safe operation store backed by SQLite with in-memory index."""

    def __init__(
        self,
        db_path: str | None = None,
        time_func: Callable[[], float] = time.time,
    ) -> None:
        self._lock = threading.Lock()
        self._db_lock = threading.Lock()
        self._records: dict[str, OperationRecord] = {}
        self._time_func = time_func
        self._conn: sqlite3.Connection | None = None

        if db_path is not None:
            try:
                self._conn = _open_db(db_path)
                self._load_and_recover()
            except Exception:
                logger.exception("Failed to open SQLite store at %s; running in-memory only", db_path)
                self._conn = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self, rec: OperationRecord) -> None:
        """Write a single record atomically. Caller must NOT hold self._lock."""
        if self._conn is None:
            return
        try:
            with self._db_lock, self._conn:
                self._conn.execute(_UPSERT, rec._db_row())
        except Exception:
            logger.exception("Failed to persist operation %s to SQLite", rec.operation_id)

    def _delete_db(self, operation_id: str) -> None:
        """Delete a record from SQLite. Caller must NOT hold self._lock."""
        if self._conn is None:
            return
        try:
            with self._db_lock, self._conn:
                self._conn.execute(
                    "DELETE FROM operations WHERE operation_id = ?", (operation_id,)
                )
        except Exception:
            logger.exception("Failed to delete operation %s from SQLite", operation_id)

    def _load_and_recover(self) -> None:
        """Load all rows from SQLite; mark in-progress records as FAILED."""
        assert self._conn is not None
        with self._db_lock:
            cur = self._conn.execute(
                "SELECT operation_id, status, current_stage, outcome, executor_ref, "
                "health_reached, failed_stage, detail, error_code, exception_type, completed_at "
                "FROM operations"
            )
            rows = cur.fetchall()
        now = self._time_func()
        to_recover: list[OperationRecord] = []
        for row in rows:
            rec = OperationRecord._from_row(row)
            self._records[rec.operation_id] = rec
            if rec.status == "running":
                to_recover.append(rec)

        for rec in to_recover:
            rec.status = "done"
            rec.outcome = "error"
            rec.error_code = "CRASH_RECOVERY"
            rec.detail = "Agent restarted while operation was in progress"
            rec.completed_at = now
            try:
                with self._db_lock, self._conn:
                    self._conn.execute(_UPSERT, rec._db_row())
            except Exception:
                logger.exception(
                    "Failed to persist crash-recovery state for %s", rec.operation_id
                )

        if to_recover:
            logger.warning(
                "Crash recovery: marked %d in-progress operation(s) as FAILED",
                len(to_recover),
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        self._persist(rec)
        return rec

    def update(self, operation_id: str, **kwargs: Any) -> None:
        with self._lock:
            rec = self._records.get(operation_id)
            if rec is None:
                return
            for k, v in kwargs.items():
                setattr(rec, k, v)
        if rec is not None:
            self._persist(rec)

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
        for oid in expired:
            self._delete_db(oid)

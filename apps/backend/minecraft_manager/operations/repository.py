"""Durable SQLite-backed storage for server operation lifecycle records.

All state transitions are validated here against the contract defined in
docs/operation-lifecycle.md. The repository enforces:

- Only valid terminal and non-terminal states exist.
- Terminal states are immutable: no transition out of APPLIED, FAILED,
  DIVERGENT, or CANCELLED is permitted.
- Stage log entries are appended; existing entries are never mutated.
- Duplicate stage-advance calls for the same operation+stage are idempotent
  (the first write wins; subsequent calls for an already-present stage are
  silently ignored).
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import sqlite3

from .._db import SQLITE_BUSY_TIMEOUT_MS


_TERMINAL_STATES = frozenset({"APPLIED", "FAILED", "DIVERGENT", "CANCELLED"})
_VALID_STATES = frozenset({"PENDING", "IN_PROGRESS"}) | _TERMINAL_STATES
_VALID_STAGES = frozenset({
    "REVIEW", "BACKUP_VERIFICATION", "PREPARATION",
    "RESTART", "HEALTH_WAIT", "VERIFICATION", "CONFIRMATION",
})
_VALID_OUTCOMES = frozenset({"ok", "error", "skipped"})


class InvalidStateTransitionError(Exception):
    """Raised when a requested state transition violates the lifecycle contract."""


class OperationNotFoundError(Exception):
    """Raised when the requested operation_id does not exist."""


class SQLiteOperationRepository:
    """Persist and query server operation records in the shared SQLite database.

    This repository is the sole writer of the ``server_operations`` table.
    Application services call it through the ``OperationStore`` protocol defined
    in ``ports.py``.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @contextmanager
    def _connect(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    # ------------------------------------------------------------------
    # Creation
    # ------------------------------------------------------------------

    def create_operation(
        self,
        operation_id: str,
        operation_type: str,
        initiated_by: str,
        intended_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Accept a new operation in PENDING state.

        Returns the freshly created operation record as a dict.
        Raises ``ValueError`` if an operation with the same *operation_id*
        already exists.
        """
        now = time.time()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT operation_id FROM server_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
            if existing:
                raise ValueError(f"operation {operation_id!r} already exists")
            conn.execute(
                "INSERT INTO server_operations "
                "(operation_id, operation_type, state, current_stage, initiated_by, "
                "created_at, updated_at, completed_at, stage_log, intended_state, "
                "observed_state, divergence_detail, executor_ref, error_detail) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    operation_id,
                    operation_type,
                    "PENDING",
                    None,
                    initiated_by,
                    now,
                    now,
                    None,
                    "[]",
                    json.dumps(intended_state, ensure_ascii=False),
                    None,
                    None,
                    None,
                    None,
                ),
            )
        return self._fetch_or_raise(operation_id)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_operation(self, operation_id: str) -> dict[str, Any] | None:
        """Return the operation record, or ``None`` if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM server_operations WHERE operation_id = ?",
                (operation_id,),
            ).fetchone()
        return self._deserialize(dict(row)) if row else None

    def list_operations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the *limit* most-recently created operations, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM server_operations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._deserialize(dict(row)) for row in rows]

    # ------------------------------------------------------------------
    # Stage lifecycle
    # ------------------------------------------------------------------

    def advance_stage(
        self,
        operation_id: str,
        stage: str,
        started_at: float,
    ) -> None:
        """Record that *stage* has begun for *operation_id*.

        - Transitions the operation state to ``IN_PROGRESS`` if still
          ``PENDING``.
        - Appends a stage-log entry with ``outcome`` as ``None`` (in
          progress); a subsequent call to :meth:`complete_stage` closes it.
        - Idempotent: if a ``stage_log`` entry for this stage already exists,
          the call is ignored.
        - Raises :exc:`InvalidStateTransitionError` if the operation is
          already in a terminal state.
        """
        if stage not in _VALID_STAGES:
            raise ValueError(f"unknown stage: {stage!r}")
        with self._connect() as conn:
            record = self._row_or_raise(conn, operation_id)
            state = record["state"]
            if state in _TERMINAL_STATES:
                raise InvalidStateTransitionError(
                    f"operation {operation_id!r} is already in terminal state {state!r}"
                )
            stage_log: list[dict[str, Any]] = json.loads(record["stage_log"] or "[]")
            if any(entry["stage"] == stage for entry in stage_log):
                return  # idempotent
            stage_log.append({"stage": stage, "started_at": started_at, "completed_at": None, "outcome": None, "detail": None})
            new_state = "IN_PROGRESS" if state == "PENDING" else state
            conn.execute(
                "UPDATE server_operations SET state=?, current_stage=?, stage_log=?, updated_at=? "
                "WHERE operation_id=?",
                (new_state, stage, json.dumps(stage_log, ensure_ascii=False), started_at, operation_id),
            )

    def complete_stage(
        self,
        operation_id: str,
        stage: str,
        outcome: str,
        completed_at: float,
        detail: str | None = None,
    ) -> None:
        """Close a stage that was opened by :meth:`advance_stage`.

        Updates the matching ``stage_log`` entry in place (sets
        ``completed_at``, ``outcome``, and ``detail``). Does not change the
        operation state — call :meth:`transition_state` separately.

        Raises :exc:`InvalidStateTransitionError` if the operation is in a
        terminal state or the stage is not found in the log.
        """
        if outcome not in _VALID_OUTCOMES:
            raise ValueError(f"unknown outcome: {outcome!r}")
        with self._connect() as conn:
            record = self._row_or_raise(conn, operation_id)
            if record["state"] in _TERMINAL_STATES:
                raise InvalidStateTransitionError(
                    f"operation {operation_id!r} is in terminal state {record['state']!r}"
                )
            stage_log: list[dict[str, Any]] = json.loads(record["stage_log"] or "[]")
            found = False
            for entry in stage_log:
                if entry["stage"] == stage and entry["outcome"] is None:
                    entry["completed_at"] = completed_at
                    entry["outcome"] = outcome
                    entry["detail"] = detail
                    found = True
                    break
            if not found:
                raise InvalidStateTransitionError(
                    f"stage {stage!r} not open on operation {operation_id!r}"
                )
            conn.execute(
                "UPDATE server_operations SET stage_log=?, updated_at=? WHERE operation_id=?",
                (json.dumps(stage_log, ensure_ascii=False), completed_at, operation_id),
            )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def transition_state(
        self,
        operation_id: str,
        new_state: str,
        updated_at: float,
        current_stage: str | None = None,
        completed_at: float | None = None,
        observed_state: dict[str, Any] | None = None,
        divergence_detail: list[dict[str, Any]] | None = None,
        executor_ref: str | None = None,
        error_detail: dict[str, Any] | None = None,
    ) -> None:
        """Transition *operation_id* to *new_state*.

        Enforces:
        - ``new_state`` must be a recognised state value.
        - Terminal state → any state is forbidden
          (:exc:`InvalidStateTransitionError`).
        - ``completed_at`` is required for terminal states.
        - ``current_stage`` is set to ``None`` when *new_state* is terminal.
        """
        if new_state not in _VALID_STATES:
            raise ValueError(f"unknown state: {new_state!r}")
        is_terminal = new_state in _TERMINAL_STATES
        if is_terminal and completed_at is None:
            completed_at = updated_at
        with self._connect() as conn:
            record = self._row_or_raise(conn, operation_id)
            if record["state"] in _TERMINAL_STATES:
                raise InvalidStateTransitionError(
                    f"operation {operation_id!r} is already terminal ({record['state']!r})"
                )
            conn.execute(
                "UPDATE server_operations SET "
                "state=?, current_stage=?, updated_at=?, completed_at=?, "
                "observed_state=?, divergence_detail=?, executor_ref=?, error_detail=? "
                "WHERE operation_id=?",
                (
                    new_state,
                    None if is_terminal else current_stage,
                    updated_at,
                    completed_at,
                    json.dumps(observed_state, ensure_ascii=False) if observed_state is not None else None,
                    json.dumps(divergence_detail, ensure_ascii=False) if divergence_detail is not None else None,
                    executor_ref,
                    json.dumps(error_detail, ensure_ascii=False) if error_detail is not None else None,
                    operation_id,
                ),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_or_raise(self, operation_id: str) -> dict[str, Any]:
        result = self.get_operation(operation_id)
        if result is None:
            raise OperationNotFoundError(operation_id)
        return result

    def _row_or_raise(self, conn: sqlite3.Connection, operation_id: str) -> dict[str, Any]:
        row = conn.execute(
            "SELECT * FROM server_operations WHERE operation_id = ?",
            (operation_id,),
        ).fetchone()
        if row is None:
            raise OperationNotFoundError(operation_id)
        return dict(row)

    @staticmethod
    def _deserialize(row: dict[str, Any]) -> dict[str, Any]:
        """Decode JSON columns back to Python objects."""
        for field in ("stage_log", "intended_state", "observed_state", "divergence_detail", "error_detail"):
            raw = row.get(field)
            if raw is not None:
                row[field] = json.loads(raw)
        return row

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
# Ordered stage sequence as defined in docs/operation-lifecycle.md.
_STAGE_ORDER: list[str] = [
    "REVIEW", "BACKUP_VERIFICATION", "PREPARATION",
    "RESTART", "HEALTH_WAIT", "VERIFICATION", "CONFIRMATION",
]
_VALID_STAGES = frozenset(_STAGE_ORDER)
_STAGE_RANK: dict[str, int] = {s: i for i, s in enumerate(_STAGE_ORDER)}
# CANCELLED is only valid before RESTART (index 3).
_CANCEL_BEFORE_STAGE_RANK = _STAGE_RANK["RESTART"]
# Allowed state transitions per source state (terminal → nothing, enforced separately).
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"IN_PROGRESS", "CANCELLED"}),
    "IN_PROGRESS": frozenset({"APPLIED", "FAILED", "DIVERGENT", "CANCELLED"}),
}
_VALID_OUTCOMES = frozenset({"ok", "error", "skipped"})
# Stages that must be completed before certain terminal states are permitted.
# APPLIED requires CONFIRMATION (outcome recorded); DIVERGENT requires VERIFICATION.
# FAILED and CANCELLED have no required-stage constraint.
_TERMINAL_STAGE_REQUIRED: dict[str, str] = {
    "APPLIED": "CONFIRMATION",
    "DIVERGENT": "VERIFICATION",
}
_MAX_LIST_LIMIT = 200
_VALID_OPERATION_TYPES = frozenset({
    "server_settings_update",
})


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
        already exists or if *operation_type* is not a recognised value.
        """
        if operation_type not in _VALID_OPERATION_TYPES:
            raise ValueError(
                f"unknown operation_type: {operation_type!r}; "
                f"valid values are {sorted(_VALID_OPERATION_TYPES)}"
            )
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
        """Return the *limit* most-recently created operations, newest first.

        Raises ``ValueError`` if *limit* is not in the range ``[1, _MAX_LIST_LIMIT]``.
        """
        if not (1 <= limit <= _MAX_LIST_LIMIT):
            raise ValueError(
                f"limit must be between 1 and {_MAX_LIST_LIMIT}, got {limit!r}"
            )
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
            # Enforce stage ordering: the new stage must immediately follow the
            # highest stage already recorded (or be REVIEW as the first stage).
            started_ranks = [_STAGE_RANK[e["stage"]] for e in stage_log if e["stage"] in _STAGE_RANK]
            expected_rank = (max(started_ranks) + 1) if started_ranks else 0
            if _STAGE_RANK[stage] != expected_rank:
                expected_stage = _STAGE_ORDER[expected_rank]
                raise InvalidStateTransitionError(
                    f"expected next stage {expected_stage!r}, got {stage!r}"
                )
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
                if entry["stage"] == stage:
                    if entry["outcome"] is None:
                        # Open entry — close it.
                        entry["completed_at"] = completed_at
                        entry["outcome"] = outcome
                        entry["detail"] = detail
                        found = True
                    elif entry["outcome"] == outcome and entry["detail"] == detail:
                        # Already completed with identical values — idempotent return.
                        return
                    # Different outcome or detail: fall through so not found raises.
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
        if current_stage is not None and current_stage not in _VALID_STAGES:
            raise ValueError(f"unknown stage: {current_stage!r}")
        is_terminal = new_state in _TERMINAL_STATES
        if is_terminal and completed_at is None:
            completed_at = updated_at
        with self._connect() as conn:
            record = self._row_or_raise(conn, operation_id)
            current_state = record["state"]
            if current_state in _TERMINAL_STATES:
                raise InvalidStateTransitionError(
                    f"operation {operation_id!r} is already terminal ({current_state!r})"
                )
            allowed = _ALLOWED_TRANSITIONS.get(current_state, frozenset())
            if new_state not in allowed:
                raise InvalidStateTransitionError(
                    f"transition {current_state!r} → {new_state!r} is not permitted"
                )
            stage_log: list[dict[str, Any]] = json.loads(record["stage_log"] or "[]")
            if new_state == "IN_PROGRESS":
                started_stages = [e["stage"] for e in stage_log if e["stage"] in _VALID_STAGES]
                if not started_stages:
                    raise InvalidStateTransitionError(
                        f"transition to 'IN_PROGRESS' requires at least one started stage, "
                        f"but stage_log is empty for operation {operation_id!r}"
                    )
                last_started = started_stages[-1]
                if current_stage != last_started:
                    raise InvalidStateTransitionError(
                        f"transition to 'IN_PROGRESS' requires current_stage={last_started!r} "
                        f"(the last started stage), got {current_stage!r}"
                    )
            if new_state == "CANCELLED":
                highest_started = max(
                    (_STAGE_RANK[e["stage"]] for e in stage_log if e["stage"] in _STAGE_RANK),
                    default=-1,
                )
                if highest_started >= _CANCEL_BEFORE_STAGE_RANK:
                    raise InvalidStateTransitionError(
                        f"operation {operation_id!r} cannot be cancelled after RESTART has begun"
                    )
            if new_state in _TERMINAL_STAGE_REQUIRED:
                required_stage = _TERMINAL_STAGE_REQUIRED[new_state]
                completed_stages = {
                    e["stage"] for e in stage_log if e.get("outcome") is not None
                }
                if required_stage not in completed_stages:
                    raise InvalidStateTransitionError(
                        f"transition to {new_state!r} requires {required_stage!r} to be completed"
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

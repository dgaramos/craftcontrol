"""SQLite persistence for server operation lifecycle records.

Implements the OperationStore port so the storage implementation is replaceable
without changing application services.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from .lifecycle import OperationState, OperationStage, ServerOperation, StageRecord


SQLITE_BUSY_TIMEOUT_MS = 30_000


@contextmanager
def _connect(path: Path) -> Generator[sqlite3.Connection, None, None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    connection.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class SQLiteOperationRepository:
    """Durable operation store backed by SQLite.

    All writes use IMMEDIATE transactions so concurrent readers are blocked
    only briefly — the WAL is already enabled by the state repository
    initialization.
    """

    def __init__(self, database: Path) -> None:
        self._path = database

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def save(self, operation: ServerOperation) -> None:
        """Insert or fully replace an operation record."""
        with _connect(self._path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._upsert(connection, operation)

    def update_stage(self, operation: ServerOperation, stage: OperationStage) -> None:
        """Persist the current state of one stage without re-serialising all stages."""
        record = next((s for s in operation.stages if s.stage == stage), None)
        if record is None:
            return
        with _connect(self._path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO operation_stages"
                "(operation_id, stage, result, started_at, completed_at, evidence, error)"
                " VALUES (?,?,?,?,?,?,?)"
                " ON CONFLICT(operation_id, stage) DO UPDATE SET"
                " result=excluded.result, started_at=excluded.started_at,"
                " completed_at=excluded.completed_at, evidence=excluded.evidence,"
                " error=excluded.error",
                (
                    operation.operation_id,
                    stage.value,
                    record.result.value,
                    record.started_at,
                    record.completed_at,
                    json.dumps(record.evidence, ensure_ascii=False),
                    record.error,
                ),
            )
            connection.execute(
                "UPDATE server_operations SET state=?, updated_at=?, completed_at=?,"
                " terminal_error=?, observation=? WHERE operation_id=?",
                (
                    operation.state.value,
                    operation.updated_at,
                    operation.completed_at,
                    operation.terminal_error,
                    json.dumps(operation.observation, ensure_ascii=False),
                    operation.operation_id,
                ),
            )

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get(self, operation_id: str) -> ServerOperation | None:
        with _connect(self._path) as connection:
            row = connection.execute(
                "SELECT * FROM server_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if row is None:
                return None
            return self._load(connection, dict(row))

    def get_latest(self, server_id: str) -> ServerOperation | None:
        with _connect(self._path) as connection:
            row = connection.execute(
                "SELECT * FROM server_operations WHERE server_id=?"
                " ORDER BY created_at DESC LIMIT 1",
                (server_id,),
            ).fetchone()
            if row is None:
                return None
            return self._load(connection, dict(row))

    def get_active(self, server_id: str) -> ServerOperation | None:
        """Return the single non-terminal operation for this server, if any."""
        with _connect(self._path) as connection:
            row = connection.execute(
                "SELECT * FROM server_operations WHERE server_id=? AND state NOT IN (?,?,?)"
                " ORDER BY created_at DESC LIMIT 1",
                (server_id, OperationState.CONFIRMED.value, OperationState.FAILED.value, OperationState.DIVERGENT.value),
            ).fetchone()
            if row is None:
                return None
            return self._load(connection, dict(row))

    def list_recent(self, server_id: str, limit: int = 10) -> list[ServerOperation]:
        with _connect(self._path) as connection:
            rows = connection.execute(
                "SELECT * FROM server_operations WHERE server_id=?"
                " ORDER BY created_at DESC LIMIT ?",
                (server_id, limit),
            ).fetchall()
            return [self._load(connection, dict(row)) for row in rows]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _upsert(self, connection: sqlite3.Connection, operation: ServerOperation) -> None:
        connection.execute(
            "INSERT OR REPLACE INTO server_operations"
            "(operation_id, server_id, state, requested_changes, created_at,"
            " updated_at, completed_at, terminal_error, observation, correlation_id,"
            " parent_operation_id)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                operation.operation_id,
                operation.server_id,
                operation.state.value,
                json.dumps(operation.requested_changes, ensure_ascii=False),
                operation.created_at,
                operation.updated_at,
                operation.completed_at,
                operation.terminal_error,
                json.dumps(operation.observation, ensure_ascii=False),
                operation.correlation_id,
                operation.parent_operation_id,
            ),
        )
        for record in operation.stages:
            connection.execute(
                "INSERT INTO operation_stages"
                "(operation_id, stage, result, started_at, completed_at, evidence, error)"
                " VALUES (?,?,?,?,?,?,?)"
                " ON CONFLICT(operation_id, stage) DO UPDATE SET"
                " result=excluded.result, started_at=excluded.started_at,"
                " completed_at=excluded.completed_at, evidence=excluded.evidence,"
                " error=excluded.error",
                (
                    operation.operation_id,
                    record.stage.value,
                    record.result.value,
                    record.started_at,
                    record.completed_at,
                    json.dumps(record.evidence, ensure_ascii=False),
                    record.error,
                ),
            )

    def _load(self, connection: sqlite3.Connection, row: dict[str, Any]) -> ServerOperation:
        stage_rows = connection.execute(
            "SELECT * FROM operation_stages WHERE operation_id=? ORDER BY rowid",
            (row["operation_id"],),
        ).fetchall()
        stages: list[StageRecord] = []
        for sr in stage_rows:
            stages.append(
                StageRecord.from_dict(
                    {
                        "stage": sr["stage"],
                        "result": sr["result"],
                        "started_at": sr["started_at"],
                        "completed_at": sr["completed_at"],
                        "evidence": json.loads(sr["evidence"] or "{}"),
                        "error": sr["error"],
                    }
                )
            )
        return ServerOperation.from_dict(
            {
                "operation_id": row["operation_id"],
                "server_id": row["server_id"],
                "state": row["state"],
                "requested_changes": json.loads(row["requested_changes"] or "{}"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "completed_at": row.get("completed_at"),
                "terminal_error": row.get("terminal_error"),
                "observation": json.loads(row["observation"] or "{}"),
                "correlation_id": row.get("correlation_id"),
                "parent_operation_id": row.get("parent_operation_id"),
                "stages": [
                    {
                        "stage": s.stage.value,
                        "result": s.result.value,
                        "started_at": s.started_at,
                        "completed_at": s.completed_at,
                        "evidence": s.evidence,
                        "error": s.error,
                    }
                    for s in stages
                ],
            }
        )

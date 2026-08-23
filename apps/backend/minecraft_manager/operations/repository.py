"""SQLite persistence for server operation lifecycle records.

Implements the OperationStore port so the storage implementation is replaceable
without changing application services.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from .lifecycle import OperationState, OperationStage, ServerOperation, StageRecord


SQLITE_BUSY_TIMEOUT_MS = 30_000


def _open(path: Path, *, autocommit: bool = False) -> sqlite3.Connection:
    """Open a SQLite connection with standard pragmas applied.

    Parameters
    ----------
    path:
        Database file path.  The parent directory is created when absent.
    autocommit:
        When ``True`` the connection is opened with ``isolation_level=None``
        so callers can issue explicit ``BEGIN IMMEDIATE`` / ``COMMIT`` /
        ``ROLLBACK`` statements without interference from the sqlite3 module's
        implicit transaction management.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {"timeout": SQLITE_BUSY_TIMEOUT_MS / 1000}
    if autocommit:
        kwargs["isolation_level"] = None
    connection = sqlite3.connect(path, **kwargs)
    connection.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.row_factory = sqlite3.Row
    return connection


@contextmanager
def _connect(path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Read-path context manager.  Uses the sqlite3 module's implicit
    transaction management (DEFERRED begin) — suitable for read-only or
    idempotent single-statement writes that do not require exclusive access
    from the start of the transaction."""
    connection = _open(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


@contextmanager
def _write_connect(path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Write-path context manager.

    Opens the connection with ``isolation_level=None`` (autocommit) and
    immediately issues ``BEGIN IMMEDIATE``.  This gives SQLite an exclusive
    write lock from the start of the transaction, preventing lost updates when
    two connections race to read-then-write the same row.

    The isolation_level=None mode is required because Python's sqlite3 module
    would otherwise inject its own implicit ``BEGIN`` (DEFERRED) before the
    first DML, which can silently downgrade an explicit ``BEGIN IMMEDIATE``
    issued inside a ``with connection:`` block on Python 3.12+.
    """
    connection = _open(path, autocommit=True)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
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
        with _write_connect(self._path) as connection:
            self._upsert(connection, operation)

    def fetch_and_update(
        self,
        operation_id: str,
        modifier: Callable[[ServerOperation], None],
    ) -> ServerOperation | None:
        """Atomically fetch, modify, and persist an operation under a single write lock.

        Moves the ``get()`` snapshot inside the same ``BEGIN IMMEDIATE``
        transaction as the write, so the record read by *modifier* is always
        fresh at the moment the write lock is granted.  Concurrent callers are
        serialised by SQLite rather than relying on a stale Python-side
        snapshot, which eliminates the lost-update race described in issue #251.

        *modifier* receives the live ``ServerOperation`` and must mutate it
        in-place.  If *modifier* raises, the transaction is rolled back.

        Returns the updated operation, or ``None`` when *operation_id* does not
        exist.
        """
        with _write_connect(self._path) as connection:
            row = connection.execute(
                "SELECT * FROM server_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if row is None:
                return None
            operation = self._load(connection, dict(row))
            modifier(operation)
            self._upsert(connection, operation)
            return operation

    def update_stage(self, operation: ServerOperation, stage: OperationStage) -> None:
        """Persist the current state of one stage without re-serialising all stages."""
        record = next((s for s in operation.stages if s.stage == stage), None)
        if record is None:
            return
        with _write_connect(self._path) as connection:
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

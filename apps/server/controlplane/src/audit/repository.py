"""SQLite-backed audit repository.

Writes sanitized audit records to the ``audit_log`` table and provides
paginated, filtered queries over them.  All persistence goes through
explicit constructor-injected dependencies so the class needs no
``unittest.mock.patch`` in tests.
"""

from __future__ import annotations

import json
import math
import sqlite3
import time as _time_module
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .model import AuditRecord

# Keys that must never appear in persisted metadata.
_SECRET_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "token_hash",
        "session_id",
        "secret",
        "credential",
        "xuid",
        "hash",
    }
)


def _sanitize(metadata: dict[str, Any]) -> dict[str, Any]:
    """Remove known secret keys from *metadata* before persistence."""
    return {k: v for k, v in metadata.items() if k.lower() not in _SECRET_KEYS}


class SQLiteAuditRepository:
    """Reads and writes audit records in the shared ``audit_log`` table.

    Parameters
    ----------
    database:
        Path to the SQLite database file.
    time_fn:
        Callable that returns the current UNIX timestamp.  Injected for
        deterministic tests; defaults to ``time.time``.
    """

    def __init__(
        self,
        database: Path,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._database = database
        self._time_fn: Callable[[], float] = time_fn or _time_module.time

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        result: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist one sanitized audit record.

        *metadata* is sanitized before persistence — secret keys are
        stripped.  Callers must not pass credentials, tokens, hashes,
        XUIDs, or session identifiers.
        """
        safe_meta = _sanitize(metadata or {})
        conn = sqlite3.connect(self._database)
        try:
            conn.execute(
                "INSERT INTO audit_log(occurred_at, actor_identity, action, target, result, details) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    self._time_fn(),
                    actor,
                    action,
                    target,
                    result,
                    json.dumps(safe_meta, separators=(",", ":")),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def query(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        actor: str | None = None,
        action: str | None = None,
    ) -> dict[str, Any]:
        """Return a page of audit records, newest first.

        Parameters
        ----------
        page:
            One-based page number.
        page_size:
            Maximum records per page.
        actor:
            If set, restricts results to records with this actor.
        action:
            If set, restricts results to records with this action.

        Returns
        -------
        dict with keys ``records``, ``total``, ``page``, ``page_size``,
        ``pages``.
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 200))
        offset = (page - 1) * page_size

        conditions: list[str] = []
        params: list[Any] = []
        if actor is not None:
            conditions.append("actor_identity = ?")
            params.append(actor)
        if action is not None:
            conditions.append("action = ?")
            params.append(action)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        conn = sqlite3.connect(self._database)
        try:
            total: int = conn.execute(
                f"SELECT COUNT(*) FROM audit_log {where}", params
            ).fetchone()[0]

            rows = conn.execute(
                f"SELECT id, occurred_at, actor_identity, action, target, result, details "
                f"FROM audit_log {where} ORDER BY occurred_at DESC, id DESC LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            ).fetchall()
        finally:
            conn.close()

        records = [
            AuditRecord(
                id=row[0],
                occurred_at=row[1],
                actor=row[2],
                action=row[3],
                target=row[4],
                result=row[5],
                metadata=json.loads(row[6]) if row[6] else {},
            )
            for row in rows
        ]

        pages = math.ceil(total / page_size) if total else 0
        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }

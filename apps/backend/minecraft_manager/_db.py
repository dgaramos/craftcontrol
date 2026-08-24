"""Shared SQLite helpers for player-domain persistence.

These utilities are used by both SQLitePlayerRepository and
SQLiteTelemetryRepository because telemetry ingestion writes directly to
player tables (player_profiles, player_history, player_daily).  Keeping them
here avoids duplicating the logic while leaving each repository autonomous —
neither repository delegates to the other.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import AbstractContextManager
from typing import Any, Callable, Protocol, TypeVar

_T = TypeVar("_T")
from zoneinfo import ZoneInfo


class ConnectionFactory(Protocol):
    """A callable that accepts a ``Path`` and returns a context manager
    yielding a ``sqlite3.Connection``.

    The default implementation is :func:`open_connection`.  Tests may supply
    a fake factory to avoid real filesystem access.
    """

    def __call__(self, path: Path) -> AbstractContextManager[sqlite3.Connection]:
        ...


SQLITE_BUSY_TIMEOUT_MS = 30_000
_SQLITE_METRICS = {
    "connections": 0,
    "wait_ms_total": 0.0,
    "wait_ms_max": 0.0,
    "contention_failures": 0,
    "retries": 0,
}
_SQLITE_METRICS_LOCK = threading.Lock()

#: Maximum number of retry attempts for idempotent read operations.
SQLITE_MAX_RETRIES = 3
#: Base delay in seconds between retry attempts (doubles each attempt).
SQLITE_RETRY_BASE_DELAY_S = 0.05


def _record_connection_wait(elapsed_ms: float) -> None:
    """Record a single connection-open wait into the shared diagnostics counters.

    Called by every SQLite connection helper across all manager paths so that
    ``sqlite_diagnostics`` covers auth, operations, core state, player, and
    telemetry connections consistently.
    """
    with _SQLITE_METRICS_LOCK:
        _SQLITE_METRICS["connections"] += 1
        _SQLITE_METRICS["wait_ms_total"] += elapsed_ms
        _SQLITE_METRICS["wait_ms_max"] = max(float(_SQLITE_METRICS["wait_ms_max"]), elapsed_ms)


def _record_contention_failure() -> None:
    """Increment the shared contention-failure counter."""
    with _SQLITE_METRICS_LOCK:
        _SQLITE_METRICS["contention_failures"] += 1


def _record_retry() -> None:
    """Increment the shared retry counter.

    Called once per retry attempt by ``open_connection_with_retry`` so that
    ``sqlite_diagnostics`` exposes cumulative retry pressure across all
    idempotent manager paths.
    """
    with _SQLITE_METRICS_LOCK:
        _SQLITE_METRICS["retries"] += 1


def database_size_bytes(path: Path) -> int | None:
    """Return the byte size of the SQLite database file at *path*, or ``None``
    if the file does not exist.

    Only the file size is reported — no file-system path or database contents
    are exposed through this function.
    """
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return None


def sqlite_diagnostics() -> dict[str, float | int]:
    with _SQLITE_METRICS_LOCK:
        connections = int(_SQLITE_METRICS["connections"])
        return {
            "connections": connections,
            "wait_ms_average": round(float(_SQLITE_METRICS["wait_ms_total"]) / connections, 2) if connections else 0,
            "wait_ms_max": round(float(_SQLITE_METRICS["wait_ms_max"]), 2),
            "contention_failures": int(_SQLITE_METRICS["contention_failures"]),
            "retries": int(_SQLITE_METRICS["retries"]),
        }

ALLOWED_DAILY_FIELDS = frozenset({
    "play_seconds", "sessions", "joins", "deaths", "player_kills", "mob_kills",
    "blocks_broken", "blocks_placed", "damage_dealt", "damage_taken",
    "distance", "dimension_transitions",
})


@contextmanager
def open_connection(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    connection = sqlite3.connect(path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    _record_connection_wait((time.perf_counter() - started) * 1000)
    connection.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    try:
        with connection:
            yield connection
    except sqlite3.OperationalError as error:
        if "locked" in str(error).lower() or "busy" in str(error).lower():
            _record_contention_failure()
        raise
    finally:
        connection.close()


def open_connection_with_retry(
    path: Path,
    executor: Callable[[sqlite3.Connection], _T],
    max_retries: int = SQLITE_MAX_RETRIES,
    *,
    connection_factory: ConnectionFactory = open_connection,
) -> _T:
    """Open a SQLite connection with bounded retries for transient contention.

    Use this only for **idempotent read operations** that are safe to retry
    without side effects.  Write operations that are not idempotent must use
    ``open_connection`` directly so that contention fails immediately and never
    produces duplicate side effects.

    ``executor`` receives an open connection and performs the desired read
    operation.  It is called inside each retry attempt so that only failures
    that occur during connection open or operation execution — not errors
    thrown by the caller after the call returns — are eligible for retry.

    ``connection_factory`` defaults to ``open_connection`` and may be replaced
    in tests to inject a fake connection without global monkey-patching.

    Each transient "locked" or "busy" failure decrements the retry budget and
    increments the shared ``retries`` counter so diagnostics reflect cumulative
    retry pressure.  When the budget is exhausted the final failure is recorded
    as a contention failure and re-raised.
    """
    if not isinstance(max_retries, int) or isinstance(max_retries, bool):
        raise ValueError(
            f"max_retries must be an integer; got {type(max_retries).__name__!r}"
        )
    if max_retries < 0:
        raise ValueError(
            f"max_retries must be >= 0; got {max_retries}"
        )
    if max_retries > SQLITE_MAX_RETRIES:
        raise ValueError(
            f"max_retries must be <= SQLITE_MAX_RETRIES ({SQLITE_MAX_RETRIES}); got {max_retries}"
        )
    last_error: sqlite3.OperationalError | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            _record_retry()
            time.sleep(SQLITE_RETRY_BASE_DELAY_S * (2 ** (attempt - 1)))
        try:
            with connection_factory(path) as conn:
                return executor(conn)
        except sqlite3.OperationalError as error:
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                last_error = error
                continue
            raise
    # Budget exhausted — final failure already recorded by connection_factory's
    # except clause; raise to surface the error to the caller.
    raise last_error  # type: ignore[misc]


def temporary_identity(name: str) -> str:
    return f"name:{name.casefold()}"


def public_player_id(identity: str) -> str:
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def calendar_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(os.environ.get("TZ", "America/Sao_Paulo"))
    except Exception:
        return ZoneInfo("UTC")


def day_key(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, calendar_timezone()).date().isoformat()


def add_daily(
    connection: sqlite3.Connection,
    identity: str,
    timestamp: float,
    **values: float,
) -> None:
    filtered = {key: value for key, value in values.items() if key in ALLOWED_DAILY_FIELDS and value > 0}
    if not filtered:
        return
    day = day_key(timestamp)
    connection.execute(
        "INSERT OR IGNORE INTO player_daily(identity,day,updated_at) VALUES(?,?,?)",
        (identity, day, timestamp),
    )
    assignments = ",".join(f"{key}={key}+?" for key in filtered)
    connection.execute(
        f"UPDATE player_daily SET {assignments},updated_at=? WHERE identity=? AND day=?",
        (*filtered.values(), timestamp, identity, day),
    )


def allocate_daily_play(
    connection: sqlite3.Connection,
    identity: str,
    started_at: float,
    ended_at: float,
) -> None:
    cursor = max(0.0, started_at)
    end = max(cursor, ended_at)
    timezone = calendar_timezone()
    while cursor < end:
        local = datetime.fromtimestamp(cursor, timezone)
        next_midnight = datetime.combine(
            local.date() + timedelta(days=1),
            datetime.min.time(),
            timezone,
        ).timestamp()
        boundary = min(end, next_midnight)
        add_daily(connection, identity, cursor, play_seconds=max(0, boundary - cursor))
        cursor = boundary


def player_identity(
    connection: sqlite3.Connection,
    name: str,
    xuid: str = "",
) -> str:
    if xuid:
        identity = f"xuid:{xuid}"
        temp = temporary_identity(name)
        if temp != identity:
            existing = connection.execute(
                "SELECT identity FROM player_profiles WHERE identity = ?", (temp,)
            ).fetchone()
            target = connection.execute(
                "SELECT identity FROM player_profiles WHERE identity = ?", (identity,)
            ).fetchone()
            if existing and not target:
                connection.execute(
                    "UPDATE player_profiles SET identity=?,xuid=? WHERE identity=?",
                    (identity, xuid, temp),
                )
                for table in (
                    "player_aliases", "player_sessions", "player_history",
                    "player_telemetry",
                ):
                    connection.execute(
                        f"UPDATE {table} SET identity=? WHERE identity=?",
                        (identity, temp),
                    )
                # Merge temp daily rows into the target identity, aggregating
                # counters so no accumulated data is lost even if a player_daily
                # row for the target identity already exists (e.g. written by
                # telemetry before the profile was promoted from temp).
                fields = ", ".join(
                    f"{f}={f}+excluded.{f}" for f in sorted(ALLOWED_DAILY_FIELDS)
                )
                connection.execute(
                    "INSERT INTO player_daily(identity,day,updated_at,"
                    + ",".join(sorted(ALLOWED_DAILY_FIELDS))
                    + ") SELECT ?,day,updated_at,"
                    + ",".join(sorted(ALLOWED_DAILY_FIELDS))
                    + " FROM player_daily WHERE identity=?"
                    + " ON CONFLICT(identity,day) DO UPDATE SET "
                    + fields
                    + ",updated_at=MAX(updated_at,excluded.updated_at)",
                    (identity, temp),
                )
                connection.execute(
                    "DELETE FROM player_daily WHERE identity=?", (temp,)
                )
        return identity
    row = connection.execute(
        "SELECT p.identity FROM player_profiles p "
        "LEFT JOIN player_aliases a ON a.identity=p.identity "
        "WHERE lower(p.current_name)=lower(?) OR lower(a.name)=lower(?) "
        "ORDER BY p.last_seen_at DESC LIMIT 1",
        (name, name),
    ).fetchone()
    return str(row[0]) if row else temporary_identity(name)


def record_player_history(
    connection: sqlite3.Connection,
    identity: str,
    topic: str,
    source: str,
    payload: dict[str, Any],
    occurred_at: float,
    event_key: str | None = None,
) -> bool:
    import json
    cursor = connection.execute(
        "INSERT OR IGNORE INTO player_history"
        "(identity,topic,occurred_at,source,payload,event_key) VALUES(?,?,?,?,?,?)",
        (identity, topic, occurred_at, source, json.dumps(payload, ensure_ascii=False), event_key),
    )
    return cursor.rowcount > 0

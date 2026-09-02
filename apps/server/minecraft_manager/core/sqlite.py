"""Shared SQLite connection and diagnostics infrastructure."""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from contextlib import AbstractContextManager
from typing import Callable, Protocol, TypeVar

_T = TypeVar("_T")


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

@contextmanager
def open_connection(path: Path, *, record_contention: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    connection = sqlite3.connect(path, timeout=SQLITE_BUSY_TIMEOUT_MS / 1000)
    _record_connection_wait((time.perf_counter() - started) * 1000)
    connection.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    try:
        with connection:
            yield connection
    except sqlite3.OperationalError as error:
        if record_contention and ("locked" in str(error).lower() or "busy" in str(error).lower()):
            _record_contention_failure()
        raise
    finally:
        connection.close()


@contextmanager
def open_retryable_connection(path: Path):
    """Open a read connection without recording transient retry attempts as failures."""
    with open_connection(path, record_contention=False) as connection:
        yield connection


def open_connection_with_retry(
    path: Path,
    executor: Callable[[sqlite3.Connection], _T],
    max_retries: int = SQLITE_MAX_RETRIES,
    *,
    connection_factory: ConnectionFactory = open_retryable_connection,
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
    # Only the final failure is reported; transient contention is represented
    # by the retry counter.
    _record_contention_failure()
    raise last_error  # type: ignore[misc]

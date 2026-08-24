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
from typing import Any
from zoneinfo import ZoneInfo


SQLITE_BUSY_TIMEOUT_MS = 30_000
_SQLITE_METRICS = {"connections": 0, "wait_ms_total": 0.0, "wait_ms_max": 0.0, "contention_failures": 0}
_SQLITE_METRICS_LOCK = threading.Lock()


def sqlite_diagnostics() -> dict[str, float | int]:
    with _SQLITE_METRICS_LOCK:
        connections = int(_SQLITE_METRICS["connections"])
        return {
            "connections": connections,
            "wait_ms_average": round(float(_SQLITE_METRICS["wait_ms_total"]) / connections, 2) if connections else 0,
            "wait_ms_max": round(float(_SQLITE_METRICS["wait_ms_max"]), 2),
            "contention_failures": int(_SQLITE_METRICS["contention_failures"]),
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
    elapsed = (time.perf_counter() - started) * 1000
    with _SQLITE_METRICS_LOCK:
        _SQLITE_METRICS["connections"] += 1
        _SQLITE_METRICS["wait_ms_total"] += elapsed
        _SQLITE_METRICS["wait_ms_max"] = max(float(_SQLITE_METRICS["wait_ms_max"]), elapsed)
    connection.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    try:
        with connection:
            yield connection
    except sqlite3.OperationalError as error:
        if "locked" in str(error).lower() or "busy" in str(error).lower():
            with _SQLITE_METRICS_LOCK:
                _SQLITE_METRICS["contention_failures"] += 1
        raise
    finally:
        connection.close()


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

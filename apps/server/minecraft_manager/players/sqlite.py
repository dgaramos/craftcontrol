"""SQLite persistence helpers owned by the player domain.

Telemetry ingestion uses these helpers when it writes player-owned tables, so
the reconciliation rules stay in one place without making either repository
delegate to the other.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


ALLOWED_DAILY_FIELDS = frozenset({
    "play_seconds", "sessions", "joins", "deaths", "player_kills", "mob_kills",
    "blocks_broken", "blocks_placed", "damage_dealt", "damage_taken",
    "distance", "dimension_transitions",
})


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


def _merge_daily_records(connection: sqlite3.Connection, temporary: str, canonical: str) -> None:
    fields = ", ".join(
        f"{field}={field}+excluded.{field}" for field in sorted(ALLOWED_DAILY_FIELDS)
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
        (canonical, temporary),
    )
    connection.execute("DELETE FROM player_daily WHERE identity=?", (temporary,))


def _merge_temporary_player(connection: sqlite3.Connection, temporary: str, canonical: str) -> None:
    connection.execute(
        "INSERT INTO player_aliases(identity,name,first_seen_at,last_seen_at) "
        "SELECT ?,name,first_seen_at,last_seen_at FROM player_aliases WHERE identity=? "
        "ON CONFLICT(identity,name) DO UPDATE SET "
        "first_seen_at=MIN(first_seen_at,excluded.first_seen_at),"
        "last_seen_at=MAX(last_seen_at,excluded.last_seen_at)",
        (canonical, temporary),
    )
    connection.execute("DELETE FROM player_aliases WHERE identity=?", (temporary,))
    connection.execute("UPDATE player_sessions SET identity=? WHERE identity=?", (canonical, temporary))
    connection.execute("UPDATE OR IGNORE player_history SET identity=? WHERE identity=?", (canonical, temporary))
    connection.execute("DELETE FROM player_history WHERE identity=?", (temporary,))
    temporary_telemetry = connection.execute(
        "SELECT stats,sequence,updated_at FROM player_telemetry WHERE identity=?", (temporary,)
    ).fetchone()
    canonical_telemetry = connection.execute(
        "SELECT sequence,updated_at FROM player_telemetry WHERE identity=?", (canonical,)
    ).fetchone()
    if temporary_telemetry and (
        not canonical_telemetry
        or temporary_telemetry[2] > canonical_telemetry[1]
        or (
            temporary_telemetry[2] == canonical_telemetry[1]
            and temporary_telemetry[1] > canonical_telemetry[0]
        )
    ):
        connection.execute(
            "INSERT INTO player_telemetry(identity,stats,sequence,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(identity) DO UPDATE SET "
            "stats=excluded.stats,sequence=excluded.sequence,updated_at=excluded.updated_at",
            (canonical, *temporary_telemetry),
        )
    connection.execute("DELETE FROM player_telemetry WHERE identity=?", (temporary,))
    _merge_daily_records(connection, temporary, canonical)
    connection.execute("DELETE FROM player_profiles WHERE identity=?", (temporary,))


def player_identity(
    connection: sqlite3.Connection,
    name: str,
    xuid: str = "",
) -> str:
    if xuid:
        identity = f"xuid:{xuid}"
        temporary = temporary_identity(name)
        if temporary != identity:
            existing = connection.execute(
                "SELECT identity FROM player_profiles WHERE identity = ?", (temporary,)
            ).fetchone()
            target = connection.execute(
                "SELECT identity FROM player_profiles WHERE identity = ?", (identity,)
            ).fetchone()
            if existing and not target:
                connection.execute(
                    "UPDATE player_profiles SET identity=?,xuid=? WHERE identity=?",
                    (identity, xuid, temporary),
                )
                for table in (
                    "player_aliases", "player_sessions", "player_history", "player_telemetry",
                ):
                    connection.execute(
                        f"UPDATE {table} SET identity=? WHERE identity=?", (identity, temporary)
                    )
                _merge_daily_records(connection, temporary, identity)
            elif existing and target:
                _merge_temporary_player(connection, temporary, identity)
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
    cursor = connection.execute(
        "INSERT OR IGNORE INTO player_history"
        "(identity,topic,occurred_at,source,payload,event_key) VALUES(?,?,?,?,?,?)",
        (identity, topic, occurred_at, source, json.dumps(payload, ensure_ascii=False), event_key),
    )
    return cursor.rowcount > 0

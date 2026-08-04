from __future__ import annotations

from collections.abc import Callable, Mapping
import sqlite3


Migration = Callable[[sqlite3.Connection], None]


def _migration_001_initial_schema(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS state (kind TEXT, key TEXT, value TEXT, updated_at REAL, "
        "source TEXT, changed_at REAL, PRIMARY KEY(kind,key))"
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(state)")}
    if "changed_at" not in columns:
        connection.execute("ALTER TABLE state ADD COLUMN changed_at REAL")
    connection.execute("UPDATE state SET changed_at = updated_at WHERE changed_at IS NULL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, "
        "created_at REAL NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS player_profiles (identity TEXT PRIMARY KEY, xuid TEXT UNIQUE, "
        "current_name TEXT NOT NULL, first_seen_at REAL NOT NULL, last_seen_at REAL NOT NULL, "
        "online INTEGER NOT NULL DEFAULT 0, connected_at REAL, sessions_count INTEGER NOT NULL DEFAULT 0, "
        "total_play_seconds REAL NOT NULL DEFAULT 0, deaths_count INTEGER NOT NULL DEFAULT 0, "
        "last_death_at REAL, permission TEXT NOT NULL DEFAULT 'member')"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS player_aliases (identity TEXT NOT NULL, name TEXT NOT NULL, "
        "first_seen_at REAL NOT NULL, last_seen_at REAL NOT NULL, PRIMARY KEY(identity,name))"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS player_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "identity TEXT NOT NULL, connected_at REAL NOT NULL, disconnected_at REAL, duration_seconds REAL, "
        "close_reason TEXT, inferred INTEGER NOT NULL DEFAULT 0)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS player_history (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "identity TEXT NOT NULL, topic TEXT NOT NULL, occurred_at REAL NOT NULL, source TEXT NOT NULL, "
        "payload TEXT NOT NULL, event_key TEXT UNIQUE)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_player_history_identity ON player_history(identity,occurred_at DESC)")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_player_sessions_identity ON player_sessions(identity,connected_at DESC)")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS player_telemetry (identity TEXT PRIMARY KEY, stats TEXT NOT NULL, "
        "sequence INTEGER NOT NULL, updated_at REAL NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS telemetry_events (event_key TEXT PRIMARY KEY, sequence INTEGER NOT NULL, "
        "topic TEXT NOT NULL, received_at REAL NOT NULL)"
    )


def _migration_002_retain_telemetry_payloads(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(telemetry_events)")}
    if "payload" not in columns:
        connection.execute("ALTER TABLE telemetry_events ADD COLUMN payload TEXT")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_events_received ON telemetry_events(received_at DESC)")


MIGRATIONS: Mapping[int, Migration] = {
    1: _migration_001_initial_schema,
    2: _migration_002_retain_telemetry_payloads,
}
LATEST_SCHEMA_VERSION = max(MIGRATIONS)


def schema_version(connection: sqlite3.Connection) -> int:
    return int(connection.execute("PRAGMA user_version").fetchone()[0])


def run_migrations(connection: sqlite3.Connection, migrations: Mapping[int, Migration] = MIGRATIONS) -> int:
    current = schema_version(connection)
    latest = max(migrations, default=0)
    if current > latest:
        raise RuntimeError(f"Database schema version {current} is newer than supported version {latest}")
    expected_versions = list(range(1, latest + 1))
    if sorted(migrations) != expected_versions:
        raise RuntimeError("Database migrations must be contiguous and start at version 1")

    for version in expected_versions:
        if version <= current:
            continue
        try:
            connection.execute("BEGIN IMMEDIATE")
            migrations[version](connection)
            connection.execute(f"PRAGMA user_version = {version}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        current = version
    return current

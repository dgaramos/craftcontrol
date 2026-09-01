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


def _migration_003_local_accounts(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS panel_accounts (identity TEXT PRIMARY KEY, role TEXT NOT NULL, "
        "status TEXT NOT NULL, password_hash TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL, "
        "CHECK(role IN ('owner','operator','viewer')), CHECK(status IN ('invited','active','suspended')))"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS panel_invitations (token_hash TEXT PRIMARY KEY, identity TEXT NOT NULL, "
        "role TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL, used_at REAL, created_by TEXT, "
        "CHECK(role IN ('owner','operator','viewer')))"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS panel_sessions (token_hash TEXT PRIMARY KEY, identity TEXT NOT NULL, "
        "created_at REAL NOT NULL, last_seen_at REAL NOT NULL, idle_expires_at REAL NOT NULL, "
        "absolute_expires_at REAL NOT NULL, revoked_at REAL)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_panel_sessions_identity ON panel_sessions(identity)")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS auth_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, login_key TEXT NOT NULL, "
        "occurred_at REAL NOT NULL, successful INTEGER NOT NULL)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_auth_attempts_key ON auth_attempts(login_key,occurred_at DESC)")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at REAL NOT NULL, "
        "actor_identity TEXT, action TEXT NOT NULL, target TEXT, result TEXT NOT NULL, details TEXT NOT NULL)"
    )


def _migration_004_daily_player_aggregates(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS player_daily (identity TEXT NOT NULL, day TEXT NOT NULL, "
        "play_seconds REAL NOT NULL DEFAULT 0, sessions INTEGER NOT NULL DEFAULT 0, joins INTEGER NOT NULL DEFAULT 0, "
        "deaths INTEGER NOT NULL DEFAULT 0, player_kills INTEGER NOT NULL DEFAULT 0, mob_kills INTEGER NOT NULL DEFAULT 0, "
        "blocks_broken INTEGER NOT NULL DEFAULT 0, blocks_placed INTEGER NOT NULL DEFAULT 0, "
        "damage_dealt REAL NOT NULL DEFAULT 0, damage_taken REAL NOT NULL DEFAULT 0, distance REAL NOT NULL DEFAULT 0, "
        "dimension_transitions INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL, PRIMARY KEY(identity,day))"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_player_daily_day ON player_daily(day,identity)")


def _migration_005_server_operations(connection: sqlite3.Connection) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS server_operations ("
        "operation_id TEXT PRIMARY KEY, "
        "server_id TEXT NOT NULL, "
        "state TEXT NOT NULL CHECK(state IN ('pending','running','confirmed','failed','divergent')), "
        "requested_changes TEXT NOT NULL DEFAULT '{}', "
        "created_at REAL NOT NULL, "
        "updated_at REAL NOT NULL, "
        "completed_at REAL, "
        "terminal_error TEXT, "
        "observation TEXT NOT NULL DEFAULT '{}', "
        "correlation_id TEXT)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_operations_server ON server_operations(server_id,created_at DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_server_operations_state ON server_operations(server_id,state)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS operation_stages ("
        "operation_id TEXT NOT NULL REFERENCES server_operations(operation_id), "
        "stage TEXT NOT NULL, "
        "result TEXT NOT NULL CHECK(result IN ('pending','running','completed','failed','skipped')), "
        "started_at REAL, "
        "completed_at REAL, "
        "evidence TEXT NOT NULL DEFAULT '{}', "
        "error TEXT, "
        "PRIMARY KEY(operation_id, stage))"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_operation_stages_op ON operation_stages(operation_id)"
    )


def _migration_006_operation_parent_link(connection: sqlite3.Connection) -> None:
    """Add parent_operation_id to link retry operations to their origin (issue #194)."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(server_operations)")}
    if "parent_operation_id" not in columns:
        connection.execute(
            "ALTER TABLE server_operations ADD COLUMN parent_operation_id TEXT"
        )


def _migration_007_player_preferred_game_mode(connection: sqlite3.Connection) -> None:
    """Add preferred_game_mode column to player_profiles (issue #408).

    NULL means no preference — the server default applies.
    This column is managed exclusively by the panel and never inferred from telemetry.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(player_profiles)")}
    if "preferred_game_mode" not in columns:
        connection.execute(
            "ALTER TABLE player_profiles ADD COLUMN preferred_game_mode TEXT DEFAULT NULL"
        )


MIGRATIONS: Mapping[int, Migration] = {
    1: _migration_001_initial_schema,
    2: _migration_002_retain_telemetry_payloads,
    3: _migration_003_local_accounts,
    4: _migration_004_daily_player_aggregates,
    5: _migration_005_server_operations,
    6: _migration_006_operation_parent_link,
    7: _migration_007_player_preferred_game_mode,
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

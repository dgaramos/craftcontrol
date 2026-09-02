import sqlite3
from pathlib import Path

import pytest

from minecraft_manager.core.migrations import LATEST_SCHEMA_VERSION, run_migrations, schema_version
from minecraft_manager.core.repository import StateRepository


def test_fresh_database_reaches_latest_version(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "manager.db")
    repository.initialize()
    assert repository.database_schema_version() == LATEST_SCHEMA_VERSION
    repository.store("settings", {"SERVER_NAME": "CraftControl"}, "test")
    assert repository.snapshot()["settings"]["SERVER_NAME"] == "CraftControl"


def test_unversioned_legacy_database_is_upgraded_without_data_loss(tmp_path: Path) -> None:
    path = tmp_path / "manager.db"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE state (kind TEXT, key TEXT, value TEXT, updated_at REAL, source TEXT, PRIMARY KEY(kind,key))"
    )
    connection.execute("INSERT INTO state VALUES ('settings','SERVER_NAME','Legacy World',10,'legacy')")
    connection.commit()
    connection.close()

    repository = StateRepository(path)
    repository.initialize()
    assert repository.database_schema_version() == LATEST_SCHEMA_VERSION
    assert repository.snapshot()["settings"]["SERVER_NAME"] == "Legacy World"
    backup_path = path.parent / "backups" / "manager.db.pre-v0.bak"
    assert backup_path.is_file()
    backup = sqlite3.connect(backup_path)
    try:
        assert backup.execute("SELECT value FROM state WHERE key='SERVER_NAME'").fetchone()[0] == "Legacy World"
    finally:
        backup.close()
    upgraded = sqlite3.connect(path)
    try:
        columns = {row[1] for row in upgraded.execute("PRAGMA table_info(state)")}
        changed_at = upgraded.execute("SELECT changed_at FROM state WHERE key='SERVER_NAME'").fetchone()[0]
    finally:
        upgraded.close()
    assert "changed_at" in columns
    assert changed_at == 10


def test_failed_migration_rolls_back_schema_and_version(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "manager.db")

    def fail(candidate: sqlite3.Connection) -> None:
        candidate.execute("CREATE TABLE should_not_survive (id INTEGER)")
        raise RuntimeError("simulated failure")

    with pytest.raises(RuntimeError, match="simulated"):
        run_migrations(connection, {1: fail})
    assert schema_version(connection) == 0
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "should_not_survive" not in tables
    connection.close()


def test_newer_database_is_rejected(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "manager.db")
    connection.execute(f"PRAGMA user_version = {LATEST_SCHEMA_VERSION + 1}")
    with pytest.raises(RuntimeError, match="newer than supported"):
        run_migrations(connection)
    connection.close()


def test_migration_008_adds_audit_log_indices(tmp_path: Path) -> None:
    """Migration 008 must add performance indices on audit_log."""
    connection = sqlite3.connect(tmp_path / "manager.db")
    run_migrations(connection)
    indices = {row[1] for row in connection.execute("SELECT type, name FROM sqlite_master WHERE type='index'")}
    connection.close()
    assert "idx_audit_log_occurred_at" in indices
    assert "idx_audit_log_actor" in indices

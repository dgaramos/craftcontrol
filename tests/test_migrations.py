import sqlite3
import tempfile
import unittest
from pathlib import Path

from minecraft_manager.migrations import LATEST_SCHEMA_VERSION, run_migrations, schema_version
from minecraft_manager.repository import StateRepository


class DatabaseMigrationTest(unittest.TestCase):
    def test_fresh_database_reaches_latest_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "manager.db")
            repository.initialize()
            self.assertEqual(repository.database_schema_version(), LATEST_SCHEMA_VERSION)
            repository.store("settings", {"SERVER_NAME": "CraftControl"}, "test")
            self.assertEqual(repository.snapshot()["settings"]["SERVER_NAME"], "CraftControl")

    def test_unversioned_legacy_database_is_upgraded_without_data_loss(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manager.db"
            connection = sqlite3.connect(path)
            connection.execute(
                "CREATE TABLE state (kind TEXT, key TEXT, value TEXT, updated_at REAL, source TEXT, PRIMARY KEY(kind,key))"
            )
            connection.execute("INSERT INTO state VALUES ('settings','SERVER_NAME','Legacy World',10,'legacy')")
            connection.commit()
            connection.close()

            repository = StateRepository(path)
            repository.initialize()
            self.assertEqual(repository.database_schema_version(), LATEST_SCHEMA_VERSION)
            self.assertEqual(repository.snapshot()["settings"]["SERVER_NAME"], "Legacy World")
            backup_path = path.parent / "backups" / "manager.db.pre-v0.bak"
            self.assertTrue(backup_path.is_file())
            backup = sqlite3.connect(backup_path)
            try:
                self.assertEqual(backup.execute("SELECT value FROM state WHERE key='SERVER_NAME'").fetchone()[0], "Legacy World")
            finally:
                backup.close()
            upgraded = sqlite3.connect(path)
            try:
                columns = {row[1] for row in upgraded.execute("PRAGMA table_info(state)")}
                changed_at = upgraded.execute("SELECT changed_at FROM state WHERE key='SERVER_NAME'").fetchone()[0]
            finally:
                upgraded.close()
            self.assertIn("changed_at", columns)
            self.assertEqual(changed_at, 10)

    def test_failed_migration_rolls_back_schema_and_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = sqlite3.connect(Path(directory) / "manager.db")

            def fail(candidate: sqlite3.Connection) -> None:
                candidate.execute("CREATE TABLE should_not_survive (id INTEGER)")
                raise RuntimeError("simulated failure")

            with self.assertRaisesRegex(RuntimeError, "simulated"):
                run_migrations(connection, {1: fail})
            self.assertEqual(schema_version(connection), 0)
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertNotIn("should_not_survive", tables)
            connection.close()

    def test_newer_database_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = sqlite3.connect(Path(directory) / "manager.db")
            connection.execute(f"PRAGMA user_version = {LATEST_SCHEMA_VERSION + 1}")
            with self.assertRaisesRegex(RuntimeError, "newer than supported"):
                run_migrations(connection)
            connection.close()

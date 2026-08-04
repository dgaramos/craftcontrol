import json
import sqlite3
import tarfile
import tempfile
import unittest
from pathlib import Path

from minecraft_manager.operations.backup import BackupService


class FakeConsole:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def send(self, parts: list[str]) -> None:
        self.commands.append(parts)

    def send_and_read(self, parts: list[str]) -> str:
        self.commands.append(parts)
        return "Data saved. Files are now ready to be copied."


class BackupServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = self.root / "minecraft-bedrock"
        self.world = self.project / "data" / "worlds" / "BedrockLevel"
        self.world.mkdir(parents=True)
        (self.world / "level.dat").write_bytes(b"original-world")
        (self.project / "data" / "server.properties").write_text("level-name=BedrockLevel\n")
        (self.project / ".env").write_text("LEVEL_NAME=BedrockLevel\n")
        self.database = self.root / "data" / "manager.db"
        self.database.parent.mkdir()
        with sqlite3.connect(self.database) as connection:
            connection.execute("CREATE TABLE marker(value TEXT)")
            connection.execute("INSERT INTO marker VALUES('original')")
            connection.execute("PRAGMA user_version=1")
        self.console = FakeConsole()
        self.running = True
        self.service = BackupService(
            self.database,
            self.project,
            self.root / "backups",
            self.console,  # type: ignore[arg-type]
            lambda: self.running,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_creates_verifiable_coordinated_backup_and_resumes_saves(self) -> None:
        result = self.service.create()
        self.assertTrue(result["ok"])
        self.assertEqual(self.console.commands[0], ["save", "hold"])
        self.assertEqual(self.console.commands[-1], ["save", "resume"])
        identifier = str(result["id"])
        self.assertEqual(self.service.list()[0]["id"], identifier)
        manifest = json.loads((self.root / "backups" / identifier / "manifest.json").read_text())
        self.assertEqual(manifest["world"], "BedrockLevel")
        self.assertEqual(manifest["database_schema"], 1)
        with tarfile.open(self.root / "backups" / identifier / "configuration.tar.gz") as archive:
            self.assertIn(".env", archive.getnames())
            self.assertIn("data/server.properties", archive.getnames())

    def test_detects_corrupted_artifact(self) -> None:
        identifier = str(self.service.create()["id"])
        with (self.root / "backups" / identifier / "world.tar.gz").open("ab") as stream:
            stream.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.service.verify(identifier)

    def test_restore_refuses_while_bedrock_is_running(self) -> None:
        identifier = str(self.service.create()["id"])
        with self.assertRaisesRegex(RuntimeError, "stop the Bedrock"):
            self.service.restore(identifier, confirmed=True)

    def test_offline_restore_replaces_world_and_database_with_recovery_copy(self) -> None:
        identifier = str(self.service.create()["id"])
        (self.world / "level.dat").write_bytes(b"changed-world")
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE marker SET value='changed'")
        self.running = False

        result = self.service.restore(identifier, confirmed=True)

        self.assertEqual((self.world / "level.dat").read_bytes(), b"original-world")
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT value FROM marker").fetchone()[0], "original")
        self.assertTrue(Path(str(result["recovery"]), "manager.db").is_file())

    def test_restore_requires_explicit_confirmation(self) -> None:
        identifier = str(self.service.create()["id"])
        self.running = False
        with self.assertRaisesRegex(ValueError, "confirmation"):
            self.service.restore(identifier)

    def test_prune_is_dry_run_until_confirmed(self) -> None:
        self.service.create()
        self.service.create()
        preview = self.service.prune(1)
        self.assertTrue(preview["dry_run"])
        self.assertEqual(len(preview["candidates"]), 1)
        self.assertEqual(len(self.service.list()), 2)
        applied = self.service.prune(1, confirmed=True)
        self.assertEqual(len(applied["deleted"]), 1)
        self.assertEqual(len(self.service.list()), 1)

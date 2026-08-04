import json
import tempfile
import unittest
from pathlib import Path

from minecraft_manager.telemetry_installer import LEGACY_DIRECTORY, PACK_DIRECTORY, PACK_ID, TelemetryPackInstaller


class TelemetryPackInstallerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.project = root / "project"
        self.source = root / "source"
        self.world = self.project / "data" / "worlds" / "BedrockLevel"
        self.world.mkdir(parents=True)
        self.source.mkdir()
        (self.project / ".env").write_text("LEVEL_NAME=BedrockLevel\n", encoding="utf-8")
        (self.source / "scripts").mkdir()
        (self.source / "scripts" / "main.js").write_text("// pack\n", encoding="utf-8")
        (self.source / "manifest.json").write_text(json.dumps({
            "format_version": 2,
            "header": {"name": "CraftControl Telemetry Pack", "uuid": PACK_ID, "version": [0, 2, 0]},
        }), encoding="utf-8")
        self.installer = TelemetryPackInstaller(self.project, self.source)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @property
    def association(self) -> Path:
        return self.world / "world_behavior_packs.json"

    def test_install_migrates_legacy_directory_and_is_idempotent(self) -> None:
        legacy = self.project / "data" / "behavior_packs" / LEGACY_DIRECTORY
        legacy.mkdir(parents=True)
        (legacy / "legacy.txt").write_text("old")
        self.association.write_text(json.dumps([{"pack_id": PACK_ID, "version": [0, 1, 1]}]))

        result = self.installer.install()
        self.assertTrue(result["changed"])
        self.assertTrue(result["restart_required"])
        self.assertFalse(legacy.exists())
        self.assertTrue((self.project / "data" / "behavior_packs" / PACK_DIRECTORY / "scripts" / "main.js").is_file())
        self.assertEqual(json.loads(self.association.read_text())[0]["version"], [0, 2, 0])
        status = self.installer.status()
        self.assertTrue(status.installed)
        self.assertTrue(status.enabled)
        self.assertFalse(status.upgrade_available)

        repeated = self.installer.install()
        self.assertFalse(repeated["changed"])
        self.assertFalse(repeated["restart_required"])

    def test_disable_and_rollback_restore_association(self) -> None:
        self.installer.install()
        disabled = self.installer.disable()
        self.assertFalse(self.installer.status().enabled)
        restored = self.installer.rollback(disabled["backup"])
        self.assertEqual(restored["action"], "rollback")
        self.assertTrue(self.installer.status().enabled)

    def test_remove_keeps_recoverable_backup(self) -> None:
        self.installer.install()
        result = self.installer.remove()
        self.assertTrue(result["changed"])
        self.assertFalse(self.installer.status().installed)
        self.assertTrue((self.project / "backups" / "craftcontrol-telemetry" / result["backup"] / "backup.json").is_file())

    def test_rejects_world_path_traversal(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.installer.status("../BedrockLevel")

"""Tests for the craftcontrol CLI entrypoint (cli.py)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class ParserTest(unittest.TestCase):
    def setUp(self) -> None:
        from minecraft_manager.cli import parser
        self.parser = parser()

    def test_telemetry_status(self) -> None:
        args = self.parser.parse_args(["telemetry", "status"])
        self.assertEqual(args.command, "telemetry")
        self.assertEqual(args.action, "status")

    def test_telemetry_install(self) -> None:
        args = self.parser.parse_args(["telemetry", "install", "--world", "Bedrock level"])
        self.assertEqual(args.action, "install")
        self.assertEqual(args.world, "Bedrock level")

    def test_telemetry_remove_requires_yes(self) -> None:
        args = self.parser.parse_args(["telemetry", "remove", "--yes"])
        self.assertTrue(args.yes)

    def test_telemetry_rollback_accepts_backup(self) -> None:
        args = self.parser.parse_args(["telemetry", "rollback", "--backup", "bak1", "--yes"])
        self.assertEqual(args.backup, "bak1")
        self.assertTrue(args.yes)

    def test_telemetry_project_flag(self) -> None:
        args = self.parser.parse_args(["telemetry", "--project", "/tmp/proj", "status"])
        self.assertEqual(args.project, Path("/tmp/proj"))

    def test_backup_create(self) -> None:
        args = self.parser.parse_args(["backup", "create"])
        self.assertEqual(args.command, "backup")
        self.assertEqual(args.action, "create")

    def test_backup_list(self) -> None:
        args = self.parser.parse_args(["backup", "list"])
        self.assertEqual(args.action, "list")

    def test_backup_verify(self) -> None:
        args = self.parser.parse_args(["backup", "verify", "abc123"])
        self.assertEqual(args.backup_id, "abc123")

    def test_backup_prune_default_keep(self) -> None:
        args = self.parser.parse_args(["backup", "prune"])
        self.assertEqual(args.keep, 7)

    def test_backup_prune_custom_keep(self) -> None:
        args = self.parser.parse_args(["backup", "prune", "--keep", "3", "--yes"])
        self.assertEqual(args.keep, 3)
        self.assertTrue(args.yes)

    def test_backup_restore_requires_yes(self) -> None:
        args = self.parser.parse_args(["backup", "restore", "bak1", "--yes"])
        self.assertTrue(args.yes)

    def test_auth_bootstrap(self) -> None:
        args = self.parser.parse_args(["auth", "bootstrap", "--player", "Steve"])
        self.assertEqual(args.command, "auth")
        self.assertEqual(args.action, "bootstrap")
        self.assertEqual(args.player, "Steve")

    def test_auth_invite(self) -> None:
        args = self.parser.parse_args(["auth", "invite", "Alex", "--role", "operator"])
        self.assertEqual(args.player, "Alex")
        self.assertEqual(args.role, "operator")

    def test_auth_invite_default_role(self) -> None:
        args = self.parser.parse_args(["auth", "invite", "Alex"])
        self.assertEqual(args.role, "viewer")

    def test_auth_recover(self) -> None:
        args = self.parser.parse_args(["auth", "recover", "Steve"])
        self.assertEqual(args.action, "recover")
        self.assertEqual(args.player, "Steve")

    def test_missing_command_exits(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])


class MainAuthTest(unittest.TestCase):
    def _fake_settings(self, tmp_path: Path) -> MagicMock:
        s = MagicMock()
        s.database = tmp_path / "manager.db"
        s.bootstrap_operator = "Steve"
        return s

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.StateRepository")
    @patch("minecraft_manager.cli.AuthService")
    def test_auth_bootstrap_prints_json(self, MockAuth, MockRepo, MockSettings) -> None:
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.database = Path(d) / "db"
            s.bootstrap_operator = "Steve"
            MockSettings.return_value = s
            MockAuth.return_value.bootstrap.return_value = "tok123"

            from minecraft_manager.cli import main
            import io
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                rc = main(["auth", "bootstrap", "--player", "Steve"])

        self.assertEqual(rc, 0)
        result = json.loads(captured.getvalue())
        self.assertEqual(result["action"], "bootstrap")
        self.assertEqual(result["player"], "Steve")
        self.assertEqual(result["token"], "tok123")

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.StateRepository")
    @patch("minecraft_manager.cli.AuthService")
    def test_auth_invite_prints_json(self, MockAuth, MockRepo, MockSettings) -> None:
        import tempfile, io
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.database = Path(d) / "db"
            s.bootstrap_operator = None
            MockSettings.return_value = s
            MockAuth.return_value.create_invitation.return_value = "inv_tok"

            from minecraft_manager.cli import main
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                rc = main(["auth", "invite", "Alex", "--role", "operator"])

        self.assertEqual(rc, 0)
        result = json.loads(captured.getvalue())
        self.assertEqual(result["action"], "invite")
        self.assertEqual(result["token"], "inv_tok")

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.StateRepository")
    @patch("minecraft_manager.cli.AuthService")
    def test_auth_recover_prints_json(self, MockAuth, MockRepo, MockSettings) -> None:
        import tempfile, io
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.database = Path(d) / "db"
            s.bootstrap_operator = None
            MockSettings.return_value = s
            MockAuth.return_value.create_recovery.return_value = ("rec_tok", "owner")

            from minecraft_manager.cli import main
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                rc = main(["auth", "recover", "Steve"])

        self.assertEqual(rc, 0)
        result = json.loads(captured.getvalue())
        self.assertEqual(result["action"], "recover")
        self.assertEqual(result["token"], "rec_tok")

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.StateRepository")
    @patch("minecraft_manager.cli.AuthService")
    def test_auth_bootstrap_no_player_raises(self, MockAuth, MockRepo, MockSettings) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.database = Path(d) / "db"
            s.bootstrap_operator = None
            MockSettings.return_value = s

            from minecraft_manager.cli import main
            with self.assertRaises(SystemExit):
                main(["auth", "bootstrap"])


class MainBackupTest(unittest.TestCase):
    def _patch_backup(self):
        patches = [
            patch("minecraft_manager.cli.Settings.from_env"),
            patch("minecraft_manager.cli.BackupService"),
            patch("minecraft_manager.cli.BedrockClient"),
            patch("minecraft_manager.cli.docker_container_running", return_value=True),
        ]
        return patches

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.BackupService")
    @patch("minecraft_manager.cli.BedrockClient")
    @patch("minecraft_manager.cli.docker_container_running", return_value=True)
    def test_backup_list_prints_json(self, mock_running, MockBedrock, MockBackup, MockSettings) -> None:
        import tempfile, io
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.database = Path(d) / "db"
            s.project = Path(d)
            s.backup_root = Path(d)
            s.container = "bedrock"
            s.console_wait_seconds = 5
            MockSettings.return_value = s
            MockBackup.return_value.list.return_value = []

            from minecraft_manager.cli import main
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                rc = main(["backup", "list"])

        self.assertEqual(rc, 0)
        result = json.loads(captured.getvalue())
        self.assertIn("backups", result)

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.BackupService")
    @patch("minecraft_manager.cli.BedrockClient")
    @patch("minecraft_manager.cli.docker_container_running", return_value=True)
    def test_backup_restore_without_yes_raises(self, mock_running, MockBedrock, MockBackup, MockSettings) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.database = Path(d) / "db"
            s.project = Path(d)
            s.backup_root = Path(d)
            s.container = "bedrock"
            s.console_wait_seconds = 5
            MockSettings.return_value = s

            from minecraft_manager.cli import main
            with self.assertRaises(SystemExit):
                main(["backup", "restore", "bak1"])


class MainTelemetryTest(unittest.TestCase):
    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.TelemetryPackInstaller")
    def test_telemetry_status_prints_json(self, MockInstaller, MockSettings) -> None:
        import tempfile, io
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.project = Path(d)
            MockSettings.return_value = s
            fake_status = MagicMock()
            fake_status.to_dict.return_value = {"installed": False}
            MockInstaller.bundled.return_value.status.return_value = fake_status

            from minecraft_manager.cli import main
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                rc = main(["telemetry", "status"])

        self.assertEqual(rc, 0)
        result = json.loads(captured.getvalue())
        self.assertFalse(result["changed"])

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.TelemetryPackInstaller")
    def test_telemetry_remove_without_yes_raises(self, MockInstaller, MockSettings) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.project = Path(d)
            MockSettings.return_value = s

            from minecraft_manager.cli import main
            with self.assertRaises(SystemExit):
                main(["telemetry", "remove"])

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.TelemetryPackInstaller")
    def test_telemetry_rollback_without_yes_raises(self, MockInstaller, MockSettings) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.project = Path(d)
            MockSettings.return_value = s

            from minecraft_manager.cli import main
            with self.assertRaises(SystemExit):
                main(["telemetry", "rollback"])

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.TelemetryPackInstaller")
    def test_telemetry_install_prints_json(self, MockInstaller, MockSettings) -> None:
        import tempfile, io
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.project = Path(d)
            MockSettings.return_value = s
            MockInstaller.bundled.return_value.install.return_value = {"changed": True}

            from minecraft_manager.cli import main
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                rc = main(["telemetry", "install"])

        self.assertEqual(rc, 0)
        result = json.loads(captured.getvalue())
        self.assertEqual(result["action"], "install")

    @patch("minecraft_manager.cli.Settings.from_env")
    @patch("minecraft_manager.cli.TelemetryPackInstaller")
    def test_telemetry_disable_prints_json(self, MockInstaller, MockSettings) -> None:
        import tempfile, io
        with tempfile.TemporaryDirectory() as d:
            s = MagicMock()
            s.project = Path(d)
            MockSettings.return_value = s
            MockInstaller.bundled.return_value.disable.return_value = {"changed": False, "action": "disable"}

            from minecraft_manager.cli import main
            captured = io.StringIO()
            with patch("sys.stdout", captured):
                rc = main(["telemetry", "disable"])

        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

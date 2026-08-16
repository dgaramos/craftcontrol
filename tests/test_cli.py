"""Tests for the craftcontrol CLI entrypoint (cli.py)."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def cli_parser():
    from minecraft_manager.cli import parser
    return parser()


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

def test_telemetry_status(cli_parser) -> None:
    args = cli_parser.parse_args(["telemetry", "status"])
    assert args.command == "telemetry"
    assert args.action == "status"


def test_telemetry_install(cli_parser) -> None:
    args = cli_parser.parse_args(["telemetry", "install", "--world", "Bedrock level"])
    assert args.action == "install"
    assert args.world == "Bedrock level"


def test_telemetry_remove_requires_yes(cli_parser) -> None:
    args = cli_parser.parse_args(["telemetry", "remove", "--yes"])
    assert args.yes


def test_telemetry_rollback_accepts_backup(cli_parser) -> None:
    args = cli_parser.parse_args(["telemetry", "rollback", "--backup", "bak1", "--yes"])
    assert args.backup == "bak1"
    assert args.yes


def test_telemetry_project_flag(cli_parser) -> None:
    args = cli_parser.parse_args(["telemetry", "--project", "/tmp/proj", "status"])
    assert args.project == Path("/tmp/proj")


def test_backup_create(cli_parser) -> None:
    args = cli_parser.parse_args(["backup", "create"])
    assert args.command == "backup"
    assert args.action == "create"


def test_backup_list(cli_parser) -> None:
    args = cli_parser.parse_args(["backup", "list"])
    assert args.action == "list"


def test_backup_verify(cli_parser) -> None:
    args = cli_parser.parse_args(["backup", "verify", "abc123"])
    assert args.backup_id == "abc123"


def test_backup_prune_default_keep(cli_parser) -> None:
    args = cli_parser.parse_args(["backup", "prune"])
    assert args.keep == 7


def test_backup_prune_custom_keep(cli_parser) -> None:
    args = cli_parser.parse_args(["backup", "prune", "--keep", "3", "--yes"])
    assert args.keep == 3
    assert args.yes


def test_backup_restore_requires_yes(cli_parser) -> None:
    args = cli_parser.parse_args(["backup", "restore", "bak1", "--yes"])
    assert args.yes


def test_auth_bootstrap(cli_parser) -> None:
    args = cli_parser.parse_args(["auth", "bootstrap", "--player", "Steve"])
    assert args.command == "auth"
    assert args.action == "bootstrap"
    assert args.player == "Steve"


def test_auth_invite(cli_parser) -> None:
    args = cli_parser.parse_args(["auth", "invite", "Alex", "--role", "operator"])
    assert args.player == "Alex"
    assert args.role == "operator"


def test_auth_invite_default_role(cli_parser) -> None:
    args = cli_parser.parse_args(["auth", "invite", "Alex"])
    assert args.role == "viewer"


def test_auth_recover(cli_parser) -> None:
    args = cli_parser.parse_args(["auth", "recover", "Steve"])
    assert args.action == "recover"
    assert args.player == "Steve"


def test_missing_command_exits(cli_parser) -> None:
    with pytest.raises(SystemExit):
        cli_parser.parse_args([])


# ---------------------------------------------------------------------------
# Main auth tests
# ---------------------------------------------------------------------------

@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.StateRepository")
@patch("minecraft_manager.cli.AuthService")
def test_auth_bootstrap_prints_json(MockAuth, MockRepo, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.database = tmp_path / "db"
    s.bootstrap_operator = "Steve"
    MockSettings.return_value = s
    MockAuth.return_value.bootstrap.return_value = "tok123"

    from minecraft_manager.cli import main
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        rc = main(["auth", "bootstrap", "--player", "Steve"])

    assert rc == 0
    result = json.loads(captured.getvalue())
    assert result["action"] == "bootstrap"
    assert result["player"] == "Steve"
    assert result["token"] == "tok123"


@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.StateRepository")
@patch("minecraft_manager.cli.AuthService")
def test_auth_invite_prints_json(MockAuth, MockRepo, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.database = tmp_path / "db"
    s.bootstrap_operator = None
    MockSettings.return_value = s
    MockAuth.return_value.create_invitation.return_value = "inv_tok"

    from minecraft_manager.cli import main
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        rc = main(["auth", "invite", "Alex", "--role", "operator"])

    assert rc == 0
    result = json.loads(captured.getvalue())
    assert result["action"] == "invite"
    assert result["token"] == "inv_tok"


@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.StateRepository")
@patch("minecraft_manager.cli.AuthService")
def test_auth_recover_prints_json(MockAuth, MockRepo, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.database = tmp_path / "db"
    s.bootstrap_operator = None
    MockSettings.return_value = s
    MockAuth.return_value.create_recovery.return_value = ("rec_tok", "owner")

    from minecraft_manager.cli import main
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        rc = main(["auth", "recover", "Steve"])

    assert rc == 0
    result = json.loads(captured.getvalue())
    assert result["action"] == "recover"
    assert result["token"] == "rec_tok"


@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.StateRepository")
@patch("minecraft_manager.cli.AuthService")
def test_auth_bootstrap_no_player_raises(MockAuth, MockRepo, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.database = tmp_path / "db"
    s.bootstrap_operator = None
    MockSettings.return_value = s

    from minecraft_manager.cli import main
    with pytest.raises(SystemExit):
        main(["auth", "bootstrap"])


# ---------------------------------------------------------------------------
# Main backup tests
# ---------------------------------------------------------------------------

@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.BackupService")
@patch("minecraft_manager.cli.BedrockClient")
@patch("minecraft_manager.cli.docker_container_running", return_value=True)
def test_backup_list_prints_json(mock_running, MockBedrock, MockBackup, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.database = tmp_path / "db"
    s.project = tmp_path
    s.backup_root = tmp_path
    s.container = "bedrock"
    s.console_wait_seconds = 5
    MockSettings.return_value = s
    MockBackup.return_value.list.return_value = []

    from minecraft_manager.cli import main
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        rc = main(["backup", "list"])

    assert rc == 0
    result = json.loads(captured.getvalue())
    assert "backups" in result


@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.BackupService")
@patch("minecraft_manager.cli.BedrockClient")
@patch("minecraft_manager.cli.docker_container_running", return_value=True)
def test_backup_restore_without_yes_raises(mock_running, MockBedrock, MockBackup, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.database = tmp_path / "db"
    s.project = tmp_path
    s.backup_root = tmp_path
    s.container = "bedrock"
    s.console_wait_seconds = 5
    MockSettings.return_value = s

    from minecraft_manager.cli import main
    with pytest.raises(SystemExit):
        main(["backup", "restore", "bak1"])


# ---------------------------------------------------------------------------
# Main telemetry tests
# ---------------------------------------------------------------------------

@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.TelemetryPackInstaller")
def test_telemetry_status_prints_json(MockInstaller, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.project = tmp_path
    MockSettings.return_value = s
    fake_status = MagicMock()
    fake_status.to_dict.return_value = {"installed": False}
    MockInstaller.bundled.return_value.status.return_value = fake_status

    from minecraft_manager.cli import main
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        rc = main(["telemetry", "status"])

    assert rc == 0
    result = json.loads(captured.getvalue())
    assert not result["changed"]


@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.TelemetryPackInstaller")
def test_telemetry_remove_without_yes_raises(MockInstaller, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.project = tmp_path
    MockSettings.return_value = s

    from minecraft_manager.cli import main
    with pytest.raises(SystemExit):
        main(["telemetry", "remove"])


@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.TelemetryPackInstaller")
def test_telemetry_rollback_without_yes_raises(MockInstaller, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.project = tmp_path
    MockSettings.return_value = s

    from minecraft_manager.cli import main
    with pytest.raises(SystemExit):
        main(["telemetry", "rollback"])


@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.TelemetryPackInstaller")
def test_telemetry_install_prints_json(MockInstaller, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.project = tmp_path
    MockSettings.return_value = s
    MockInstaller.bundled.return_value.install.return_value = {"changed": True}

    from minecraft_manager.cli import main
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        rc = main(["telemetry", "install"])

    assert rc == 0
    result = json.loads(captured.getvalue())
    assert result["action"] == "install"


@patch("minecraft_manager.cli.Settings.from_env")
@patch("minecraft_manager.cli.TelemetryPackInstaller")
def test_telemetry_disable_prints_json(MockInstaller, MockSettings, tmp_path: Path) -> None:
    s = MagicMock()
    s.project = tmp_path
    MockSettings.return_value = s
    MockInstaller.bundled.return_value.disable.return_value = {"changed": False, "action": "disable"}

    from minecraft_manager.cli import main
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        rc = main(["telemetry", "disable"])

    assert rc == 0

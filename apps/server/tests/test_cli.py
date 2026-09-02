"""Tests for the craftcontrol CLI entrypoint (cli.py)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from controlplane.cli import CliDependencies


class _FakeRepository:
    def initialize(self) -> None:
        pass


@pytest.fixture
def cli_parser():
    from controlplane.cli import parser
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

def test_auth_bootstrap_prints_json(tmp_path: Path, capsys) -> None:
    settings = SimpleNamespace(database=tmp_path / "db", bootstrap_operator="Steve")
    fake_auth = MagicMock()
    fake_auth.bootstrap.return_value = "tok123"
    deps = CliDependencies(
        repository_factory=lambda settings: _FakeRepository(),
        auth_service_factory=lambda settings: fake_auth,
    )

    from controlplane.cli import main
    rc = main(["auth", "bootstrap", "--player", "Steve"], settings=settings, deps=deps)

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["action"] == "bootstrap"
    assert result["player"] == "Steve"
    assert result["token"] == "tok123"


def test_auth_invite_prints_json(tmp_path: Path, capsys) -> None:
    settings = SimpleNamespace(database=tmp_path / "db", bootstrap_operator=None)
    fake_auth = MagicMock()
    fake_auth.create_invitation.return_value = "inv_tok"
    deps = CliDependencies(
        repository_factory=lambda settings: _FakeRepository(),
        auth_service_factory=lambda settings: fake_auth,
    )

    from controlplane.cli import main
    rc = main(["auth", "invite", "Alex", "--role", "operator"], settings=settings, deps=deps)

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["action"] == "invite"
    assert result["token"] == "inv_tok"


def test_auth_recover_prints_json(tmp_path: Path, capsys) -> None:
    settings = SimpleNamespace(database=tmp_path / "db", bootstrap_operator=None)
    fake_auth = MagicMock()
    fake_auth.create_recovery.return_value = ("rec_tok", "owner")
    deps = CliDependencies(
        repository_factory=lambda settings: _FakeRepository(),
        auth_service_factory=lambda settings: fake_auth,
    )

    from controlplane.cli import main
    rc = main(["auth", "recover", "Steve"], settings=settings, deps=deps)

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["action"] == "recover"
    assert result["token"] == "rec_tok"


def test_auth_bootstrap_no_player_raises(tmp_path: Path) -> None:
    settings = SimpleNamespace(database=tmp_path / "db", bootstrap_operator=None)
    deps = CliDependencies(
        repository_factory=lambda settings: _FakeRepository(),
        auth_service_factory=lambda settings: MagicMock(),
    )

    from controlplane.cli import main
    with pytest.raises(SystemExit):
        main(["auth", "bootstrap"], settings=settings, deps=deps)


# ---------------------------------------------------------------------------
# Main backup tests
# ---------------------------------------------------------------------------

def test_backup_list_prints_json(tmp_path: Path, capsys) -> None:
    settings = SimpleNamespace(
        database=tmp_path / "db",
        project=tmp_path,
        backup_root=tmp_path,
        container="bedrock",
        console_wait_seconds=5,
    )
    fake_backup = MagicMock()
    fake_backup.list.return_value = []
    deps = CliDependencies(backup_service_factory=lambda settings: fake_backup)

    from controlplane.cli import main
    rc = main(["backup", "list"], settings=settings, deps=deps)

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert "backups" in result


def test_backup_restore_without_yes_raises(tmp_path: Path) -> None:
    settings = SimpleNamespace(
        database=tmp_path / "db",
        project=tmp_path,
        backup_root=tmp_path,
        container="bedrock",
        console_wait_seconds=5,
    )
    deps = CliDependencies(backup_service_factory=lambda settings: MagicMock())

    from controlplane.cli import main
    with pytest.raises(SystemExit):
        main(["backup", "restore", "bak1"], settings=settings, deps=deps)


# ---------------------------------------------------------------------------
# Main telemetry tests
# ---------------------------------------------------------------------------

def test_telemetry_status_prints_json(tmp_path: Path, capsys) -> None:
    settings = SimpleNamespace(project=tmp_path)
    fake_status = MagicMock()
    fake_status.to_dict.return_value = {"installed": False}
    fake_installer = MagicMock()
    fake_installer.status.return_value = fake_status
    deps = CliDependencies(installer_factory=lambda settings, project: fake_installer)

    from controlplane.cli import main
    rc = main(["telemetry", "status"], settings=settings, deps=deps)

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert not result["changed"]


def test_telemetry_remove_without_yes_raises(tmp_path: Path) -> None:
    settings = SimpleNamespace(project=tmp_path)
    deps = CliDependencies(installer_factory=lambda settings, project: MagicMock())

    from controlplane.cli import main
    with pytest.raises(SystemExit):
        main(["telemetry", "remove"], settings=settings, deps=deps)


def test_telemetry_rollback_without_yes_raises(tmp_path: Path) -> None:
    settings = SimpleNamespace(project=tmp_path)
    deps = CliDependencies(installer_factory=lambda settings, project: MagicMock())

    from controlplane.cli import main
    with pytest.raises(SystemExit):
        main(["telemetry", "rollback"], settings=settings, deps=deps)


def test_telemetry_install_prints_json(tmp_path: Path, capsys) -> None:
    settings = SimpleNamespace(project=tmp_path)
    fake_installer = MagicMock()
    fake_installer.install.return_value = {"changed": True}
    deps = CliDependencies(installer_factory=lambda settings, project: fake_installer)

    from controlplane.cli import main
    rc = main(["telemetry", "install"], settings=settings, deps=deps)

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["action"] == "install"


def test_telemetry_disable_prints_json(tmp_path: Path, capsys) -> None:
    settings = SimpleNamespace(project=tmp_path)
    fake_installer = MagicMock()
    fake_installer.disable.return_value = {"changed": False, "action": "disable"}
    deps = CliDependencies(installer_factory=lambda settings, project: fake_installer)

    from controlplane.cli import main
    rc = main(["telemetry", "disable"], settings=settings, deps=deps)

    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["changed"] is False
    assert result["action"] == "disable"

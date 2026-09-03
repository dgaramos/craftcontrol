import json
from pathlib import Path

import pytest

from src.telemetry.installer import LEGACY_DIRECTORY, PACK_DIRECTORY, PACK_ID, TelemetryPackInstaller


@pytest.fixture
def installer_env(tmp_path: Path):
    root = tmp_path
    project = root / "project"
    source = root / "source"
    world = project / "data" / "worlds" / "BedrockLevel"
    world.mkdir(parents=True)
    source.mkdir()
    (project / ".env").write_text("LEVEL_NAME=BedrockLevel\n", encoding="utf-8")
    (source / "scripts").mkdir()
    (source / "scripts" / "main.js").write_text("// pack\n", encoding="utf-8")
    (source / "manifest.json").write_text(json.dumps({
        "format_version": 2,
        "header": {"name": "CraftControl Telemetry Pack", "uuid": PACK_ID, "version": [0, 2, 0]},
    }), encoding="utf-8")
    installer = TelemetryPackInstaller(project, source)
    return {"project": project, "source": source, "world": world, "installer": installer}


@pytest.fixture
def association(installer_env) -> Path:
    return installer_env["world"] / "world_behavior_packs.json"


def test_install_migrates_legacy_directory_and_is_idempotent(installer_env, association: Path) -> None:
    env = installer_env
    legacy = env["project"] / "data" / "behavior_packs" / LEGACY_DIRECTORY
    legacy.mkdir(parents=True)
    (legacy / "legacy.txt").write_text("old")
    association.write_text(json.dumps([{"pack_id": PACK_ID, "version": [0, 1, 1]}]))

    result = env["installer"].install()
    assert result["changed"]
    assert result["restart_required"]
    assert not legacy.exists()
    assert (env["project"] / "data" / "behavior_packs" / PACK_DIRECTORY / "scripts" / "main.js").is_file()
    assert json.loads(association.read_text())[0]["version"] == [0, 2, 0]
    status = env["installer"].status()
    assert status.installed
    assert status.enabled
    assert not status.upgrade_available

    repeated = env["installer"].install()
    assert not repeated["changed"]
    assert not repeated["restart_required"]


def test_disable_and_rollback_restore_association(installer_env) -> None:
    env = installer_env
    env["installer"].install()
    disabled = env["installer"].disable()
    assert not env["installer"].status().enabled
    restored = env["installer"].rollback(disabled["backup"])
    assert restored["action"] == "rollback"
    assert env["installer"].status().enabled


def test_remove_keeps_recoverable_backup(installer_env) -> None:
    env = installer_env
    env["installer"].install()
    result = env["installer"].remove()
    assert result["changed"]
    assert not env["installer"].status().installed
    assert (env["project"] / "backups" / "craftcontrol-telemetry" / result["backup"] / "backup.json").is_file()


def test_snapshot_creates_backup_and_returns_name(installer_env) -> None:
    env = installer_env
    env["installer"].install()
    name = env["installer"].snapshot()
    backup_dir = env["project"] / "backups" / "craftcontrol-telemetry" / name
    assert backup_dir.is_dir()
    assert (backup_dir / "backup.json").is_file()


def test_latest_backup_name_returns_most_recent_then_none(installer_env) -> None:
    env = installer_env
    assert env["installer"].latest_backup_name() is None
    env["installer"].install()
    name1 = env["installer"].snapshot()
    assert env["installer"].latest_backup_name() == name1
    name2 = env["installer"].snapshot()
    assert env["installer"].latest_backup_name() == name2


def test_rejects_world_path_traversal(installer_env) -> None:
    env = installer_env
    with pytest.raises(FileNotFoundError):
        env["installer"].status("../BedrockLevel")


def test_bundled_resolves_pack_source_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "data" / "worlds" / "BedrockLevel").mkdir(parents=True)
    (project / ".env").write_text("LEVEL_NAME=BedrockLevel\n", encoding="utf-8")
    installer = TelemetryPackInstaller.bundled(project)
    assert installer.source.name == "behavior_pack"

import json
import sqlite3
import stat
import tarfile
from pathlib import Path

import pytest

from minecraft_manager.operations.backup import BackupService
from tests.conftest import FakeConsole


@pytest.fixture
def backup_env(tmp_path: Path):
    root = tmp_path
    project = root / "minecraft-bedrock"
    world = project / "data" / "worlds" / "BedrockLevel"
    world.mkdir(parents=True)
    (world / "level.dat").write_bytes(b"original-world")
    (project / "data" / "server.properties").write_text("level-name=BedrockLevel\n")
    (project / ".env").write_text("LEVEL_NAME=BedrockLevel\n")
    database = root / "data" / "manager.db"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE marker(value TEXT)")
        connection.execute("INSERT INTO marker VALUES('original')")
        connection.execute("PRAGMA user_version=1")
    console = FakeConsole()
    running = [True]
    service = BackupService(
        database,
        project,
        root / "backups",
        console,  # type: ignore[arg-type]
        lambda: running[0],
    )
    return {"root": root, "project": project, "world": world, "database": database,
            "console": console, "running": running, "service": service}


def test_creates_verifiable_coordinated_backup_and_resumes_saves(backup_env) -> None:
    env = backup_env
    result = env["service"].create()
    assert result["ok"]
    assert env["console"].commands[0] == ["save", "hold"]
    assert env["console"].commands[-1] == ["save", "resume"]
    identifier = str(result["id"])
    assert env["service"].list()[0]["id"] == identifier
    manifest = json.loads((env["root"] / "backups" / identifier / "manifest.json").read_text())
    assert manifest["world"] == "BedrockLevel"
    assert manifest["database_schema"] == 1
    assert stat.S_IMODE((env["root"] / "backups" / identifier).stat().st_mode) == 0o750
    assert stat.S_IMODE((env["root"] / "backups" / identifier / "manifest.json").stat().st_mode) == 0o640
    with tarfile.open(env["root"] / "backups" / identifier / "configuration.tar.gz") as archive:
        assert ".env" in archive.getnames()
        assert "data/server.properties" in archive.getnames()


def test_detects_corrupted_artifact(backup_env) -> None:
    env = backup_env
    identifier = str(env["service"].create()["id"])
    with (env["root"] / "backups" / identifier / "world.tar.gz").open("ab") as stream:
        stream.write(b"corruption")
    with pytest.raises(ValueError, match="checksum"):
        env["service"].verify(identifier)


def test_restore_refuses_while_bedrock_is_running(backup_env) -> None:
    env = backup_env
    identifier = str(env["service"].create()["id"])
    with pytest.raises(RuntimeError, match="stop the Bedrock"):
        env["service"].restore(identifier, confirmed=True)


def test_offline_restore_replaces_world_and_database_with_recovery_copy(backup_env) -> None:
    env = backup_env
    identifier = str(env["service"].create()["id"])
    (env["world"] / "level.dat").write_bytes(b"changed-world")
    with sqlite3.connect(env["database"]) as connection:
        connection.execute("UPDATE marker SET value='changed'")
    env["running"][0] = False

    result = env["service"].restore(identifier, confirmed=True)

    assert (env["world"] / "level.dat").read_bytes() == b"original-world"
    with sqlite3.connect(env["database"]) as connection:
        assert connection.execute("SELECT value FROM marker").fetchone()[0] == "original"
    assert Path(str(result["recovery"]), "manager.db").is_file()


def test_restore_requires_explicit_confirmation(backup_env) -> None:
    env = backup_env
    identifier = str(env["service"].create()["id"])
    env["running"][0] = False
    with pytest.raises(ValueError, match="confirmation"):
        env["service"].restore(identifier)


def test_prune_is_dry_run_until_confirmed(backup_env) -> None:
    env = backup_env
    env["service"].create()
    env["service"].create()
    preview = env["service"].prune(1)
    assert preview["dry_run"]
    assert len(preview["candidates"]) == 1
    assert len(env["service"].list()) == 2
    applied = env["service"].prune(1, confirmed=True)
    assert len(applied["deleted"]) == 1
    assert len(env["service"].list()) == 1

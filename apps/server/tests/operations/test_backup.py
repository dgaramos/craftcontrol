import json
import sqlite3
import stat
import tarfile
from pathlib import Path

import pytest

from controlplane.operations.backup import BackupService
from fakes import FakeConsole


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


def test_backup_sqlite_paths_are_opened_through_the_injected_factory(backup_env) -> None:
    """Backup creation measures every SQLite connection it opens."""
    from controlplane.core.sqlite import sqlite_diagnostics

    env = backup_env
    opened: list[Path] = []

    def connect(path: Path) -> sqlite3.Connection:
        opened.append(path)
        return sqlite3.connect(path)

    service = BackupService(
        env["database"],
        env["project"],
        env["root"] / "backups",
        env["console"],  # type: ignore[arg-type]
        lambda: env["running"][0],
        sqlite_connect=connect,
    )

    before = int(sqlite_diagnostics()["connections"])
    service.create()

    assert len(opened) == 4
    assert opened[0] == env["database"]
    assert int(sqlite_diagnostics()["connections"]) == before + 4


def test_backup_records_locked_database_failures(backup_env) -> None:
    """A locked backup verification connection contributes to diagnostics."""
    from controlplane.core.sqlite import sqlite_diagnostics

    env = backup_env
    identifier = str(env["service"].create()["id"])
    before = int(sqlite_diagnostics()["contention_failures"])

    def locked_connect(_: Path) -> sqlite3.Connection:
        raise sqlite3.OperationalError("database is locked")

    service = BackupService(
        env["database"],
        env["project"],
        env["root"] / "backups",
        env["console"],  # type: ignore[arg-type]
        lambda: env["running"][0],
        sqlite_connect=locked_connect,
    )

    with pytest.raises(sqlite3.OperationalError, match="locked"):
        service.verify(identifier)

    assert int(sqlite_diagnostics()["contention_failures"]) == before + 1


def test_backup_records_locked_database_operation_failures(backup_env) -> None:
    """A lock raised after connection setup is counted and closes the connection."""
    from controlplane.core.sqlite import sqlite_diagnostics

    env = backup_env
    identifier = str(env["service"].create()["id"])
    before = int(sqlite_diagnostics()["contention_failures"])

    class LockedConnection:
        closed = False

        def __enter__(self) -> "LockedConnection":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def execute(self, _: str) -> None:
            raise sqlite3.OperationalError("database is locked")

        def close(self) -> None:
            self.closed = True

    connection = LockedConnection()

    def connect(_: Path) -> sqlite3.Connection:
        return connection  # type: ignore[return-value]

    service = BackupService(
        env["database"],
        env["project"],
        env["root"] / "backups",
        env["console"],  # type: ignore[arg-type]
        lambda: env["running"][0],
        sqlite_connect=connect,
    )

    with pytest.raises(sqlite3.OperationalError, match="locked"):
        service.verify(identifier)

    assert connection.closed
    assert int(sqlite_diagnostics()["contention_failures"]) == before + 1


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


def test_prune_rejects_keep_less_than_one(backup_env) -> None:
    env = backup_env
    import pytest
    with pytest.raises(ValueError, match="keep must be at least 1"):
        env["service"].prune(0)


def test_list_skips_non_directory_entries(backup_env) -> None:
    """list() ignores files without a manifest.json and non-directory entries."""
    env = backup_env
    env["service"].create()
    # Create a stray file (not a directory) inside backup_root
    stray = env["root"] / "backups" / "not-a-directory"
    stray.write_text("garbage")
    # Create a directory without a manifest
    no_manifest = env["root"] / "backups" / "no-manifest"
    no_manifest.mkdir()
    results = env["service"].list()
    ids = [r["id"] for r in results]
    assert "not-a-directory" not in ids
    assert "no-manifest" not in ids


def test_list_handles_corrupt_manifest(backup_env) -> None:
    """list() appends {invalid: True} entries when manifest JSON is unreadable."""
    env = backup_env
    identifier = str(env["service"].create()["id"])
    # Corrupt the manifest
    (env["root"] / "backups" / identifier / "manifest.json").write_text("NOT_JSON")
    results = env["service"].list()
    entry = next(r for r in results if r["id"] == identifier)
    assert entry.get("invalid") is True


def test_verify_rejects_wrong_format_version(backup_env) -> None:
    """verify() raises when FORMAT_VERSION in manifest does not match."""
    import pytest
    env = backup_env
    identifier = str(env["service"].create()["id"])
    manifest_path = env["root"] / "backups" / identifier / "manifest.json"
    data = json.loads(manifest_path.read_text())
    data["format"] = 999
    manifest_path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unsupported backup format"):
        env["service"].verify(identifier)


def test_backup_directory_rejects_invalid_identifier(backup_env) -> None:
    """_backup_directory raises ValueError for identifiers with path separators."""
    import pytest
    with pytest.raises(ValueError, match="invalid backup identifier"):
        env = backup_env
        env["service"].verify("../../etc/passwd")


def test_backup_directory_rejects_missing_identifier(backup_env) -> None:
    """_backup_directory raises FileNotFoundError for non-existent backups."""
    import pytest
    with pytest.raises(FileNotFoundError):
        env = backup_env
        env["service"].verify("nonexistent-backup-id")


def test_world_directory_rejects_path_outside_worlds(backup_env) -> None:
    """_world_directory raises ValueError for worlds that escape the worlds dir."""
    import pytest
    with pytest.raises(ValueError, match="existing direct child"):
        env = backup_env
        env["service"].create(world="../escape")


def test_configured_world_falls_back_to_server_properties(backup_env) -> None:
    """_configured_world reads level-name from server.properties when .env is absent."""
    env = backup_env
    # Add a second world directory so the single-directory fallback cannot fire;
    # the only way to select the correct world is to read server.properties.
    (env["project"] / "data" / "worlds" / "OtherLevel").mkdir()
    # Remove LEVEL_NAME from .env so it falls through to server.properties
    (env["project"] / ".env").unlink()
    result = env["service"].create()
    assert result["ok"]


def test_configured_world_uses_single_directory_as_fallback(backup_env) -> None:
    """_configured_world returns the sole world dir when no config files exist."""
    env = backup_env
    (env["project"] / ".env").unlink()
    (env["project"] / "data" / "server.properties").unlink()
    result = env["service"].create()
    assert result["ok"]


def test_docker_container_running_returns_false_when_docker_unavailable(
    monkeypatch,
) -> None:
    """docker_container_running returns False when docker binary is not found."""
    import subprocess
    import controlplane.operations.backup as backup_mod

    def _raise(*args, **kwargs):
        raise FileNotFoundError("docker: command not found")

    monkeypatch.setattr(subprocess, "run", _raise)
    result = backup_mod.docker_container_running("any-container")
    assert result is False

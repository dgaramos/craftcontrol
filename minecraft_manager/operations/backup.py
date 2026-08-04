from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import time
from typing import Callable

from ..ports import ServerConsole


class BackupService:
    FORMAT_VERSION = 1
    CONFIG_PATHS = (
        ".env",
        "docker-compose.yml",
        "data/server.properties",
        "data/permissions.json",
        "data/allowlist.json",
        "data/whitelist.json",
        "data/behavior_packs",
    )

    def __init__(
        self,
        database: Path,
        project: Path,
        backup_root: Path,
        console: ServerConsole,
        server_running: Callable[[], bool],
    ) -> None:
        self.database = database.resolve()
        self.project = project.resolve()
        self.backup_root = backup_root.resolve()
        self.console = console
        self.server_running = server_running

    def create(self, world: str | None = None) -> dict[str, object]:
        world_dir = self._world_directory(world)
        self.backup_root.mkdir(parents=True, exist_ok=True)
        identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        destination = self.backup_root / identifier
        held = False
        with tempfile.TemporaryDirectory(prefix=f".{identifier}-", dir=self.backup_root) as temporary:
            staging = Path(temporary)
            try:
                if self.server_running():
                    self.console.send(["save", "hold"])
                    held = True
                    self._wait_until_ready()
                self._backup_database(staging / "manager.db")
                self._archive(staging / "world.tar.gz", ((world_dir, f"worlds/{world_dir.name}"),))
                configuration = tuple(
                    (path, path.relative_to(self.project).as_posix())
                    for relative in self.CONFIG_PATHS
                    if (path := self.project / relative).exists()
                )
                self._archive(staging / "configuration.tar.gz", configuration)
                manifest = self._manifest(identifier, world_dir.name, staging)
                (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
                os.replace(staging, destination)
                self._normalize_permissions(destination)
            finally:
                if held:
                    self.console.send(["save", "resume"])
        return self.verify(destination.name)

    def list(self) -> list[dict[str, object]]:
        if not self.backup_root.exists():
            return []
        results = []
        for path in sorted(self.backup_root.iterdir(), reverse=True):
            manifest = path / "manifest.json"
            if not path.is_dir() or not manifest.is_file():
                continue
            try:
                payload = json.loads(manifest.read_text())
                results.append({
                    "id": path.name,
                    "created_at": payload.get("created_at"),
                    "world": payload.get("world"),
                    "format": payload.get("format"),
                })
            except (OSError, ValueError):
                results.append({"id": path.name, "invalid": True})
        return results

    def verify(self, identifier: str) -> dict[str, object]:
        directory = self._backup_directory(identifier)
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest.get("format") != self.FORMAT_VERSION:
            raise ValueError("unsupported backup format")
        for name, metadata in manifest.get("files", {}).items():
            path = directory / name
            if not path.is_file() or path.stat().st_size != metadata["size"] or self._sha256(path) != metadata["sha256"]:
                raise ValueError(f"backup checksum mismatch: {name}")
        with sqlite3.connect(directory / "manager.db") as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"backup database integrity failed: {integrity}")
        for name in ("world.tar.gz", "configuration.tar.gz"):
            with tarfile.open(directory / name, "r:gz") as archive:
                if any(member.name.startswith("/") or ".." in Path(member.name).parts for member in archive.getmembers()):
                    raise ValueError(f"unsafe archive member in {name}")
        return {"ok": True, "id": directory.name, "manifest": manifest}

    def prune(self, keep: int, confirmed: bool = False) -> dict[str, object]:
        if keep < 1:
            raise ValueError("keep must be at least 1")
        candidates = [str(item["id"]) for item in self.list()[keep:] if not item.get("invalid")]
        if not confirmed:
            return {"ok": True, "deleted": [], "candidates": candidates, "dry_run": True}
        deleted = []
        for identifier in candidates:
            directory = self._backup_directory(identifier)
            shutil.rmtree(directory)
            deleted.append(identifier)
        return {"ok": True, "deleted": deleted, "candidates": [], "dry_run": False}

    def restore(self, identifier: str, confirmed: bool = False) -> dict[str, object]:
        if not confirmed:
            raise ValueError("restore requires explicit confirmation")
        if self.server_running():
            raise RuntimeError("stop the Bedrock server before restore")
        verified = self.verify(identifier)
        directory = self._backup_directory(identifier)
        world_name = str(verified["manifest"]["world"])
        world_target = self.project / "data" / "worlds" / world_name
        recovery_root = self.backup_root / "pre-restore" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        recovery_root.mkdir(parents=True, exist_ok=False)
        self._backup_database(recovery_root / "manager.db")
        if world_target.exists():
            self._archive(recovery_root / "world.tar.gz", ((world_target, f"worlds/{world_name}"),))
        self._normalize_permissions(recovery_root)

        with tempfile.TemporaryDirectory(prefix=".restore-", dir=self.project / "data") as temporary:
            staging = Path(temporary)
            self._extract(directory / "world.tar.gz", staging)
            restored_world = staging / "worlds" / world_name
            if not restored_world.is_dir():
                raise ValueError("backup does not contain the expected world")
            old_world = recovery_root / "replaced-world"
            if world_target.exists():
                os.replace(world_target, old_world)
            os.replace(restored_world, world_target)

        database_staging = self.database.with_name(f".{self.database.name}.restore")
        shutil.copy2(directory / "manager.db", database_staging)
        os.replace(database_staging, self.database)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(f"{self.database}{suffix}")
            if sidecar.exists():
                sidecar.unlink()
        return {"ok": True, "id": identifier, "world": world_name, "recovery": str(recovery_root)}

    def _world_directory(self, world: str | None) -> Path:
        worlds = (self.project / "data" / "worlds").resolve()
        if world is None:
            world = self._configured_world()
        candidate = (worlds / world).resolve()
        if candidate.parent != worlds or not candidate.is_dir():
            raise ValueError("world must be an existing direct child of data/worlds")
        return candidate

    def _configured_world(self) -> str:
        env_file = self.project / ".env"
        if env_file.exists():
            for line in env_file.read_text(errors="replace").splitlines():
                if line.startswith("LEVEL_NAME="):
                    return line.split("=", 1)[1].strip().strip('"\'')
        properties = self.project / "data" / "server.properties"
        if properties.exists():
            for line in properties.read_text(errors="replace").splitlines():
                if line.startswith("level-name="):
                    return line.split("=", 1)[1].strip()
        directories = [path for path in (self.project / "data" / "worlds").iterdir() if path.is_dir()]
        if len(directories) == 1:
            return directories[0].name
        raise ValueError("unable to determine active world; pass --world")

    def _wait_until_ready(self) -> None:
        for _ in range(10):
            output = self.console.send_and_read(["save", "query"])
            lowered = output.casefold()
            if "ready" in lowered or "files are now" in lowered or "prontos" in lowered:
                return
            time.sleep(1)
        raise RuntimeError("Bedrock did not confirm save hold readiness")

    def _backup_database(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database) as source, sqlite3.connect(destination) as target:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite backup integrity check failed")

    @staticmethod
    def _archive(destination: Path, entries: tuple[tuple[Path, str], ...]) -> None:
        with tarfile.open(destination, "w:gz") as archive:
            for source, name in entries:
                archive.add(source, arcname=name, recursive=True)

    @staticmethod
    def _extract(archive_path: Path, destination: Path) -> None:
        with tarfile.open(archive_path, "r:gz") as archive:
            archive.extractall(destination, filter="data")

    def _manifest(self, identifier: str, world: str, staging: Path) -> dict[str, object]:
        files = {}
        for name in ("manager.db", "world.tar.gz", "configuration.tar.gz"):
            path = staging / name
            files[name] = {"size": path.stat().st_size, "sha256": self._sha256(path)}
        with sqlite3.connect(staging / "manager.db") as connection:
            schema = int(connection.execute("PRAGMA user_version").fetchone()[0])
        return {
            "format": self.FORMAT_VERSION,
            "id": identifier,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "world": world,
            "database_schema": schema,
            "files": files,
        }

    def _backup_directory(self, identifier: str) -> Path:
        if not identifier or Path(identifier).name != identifier:
            raise ValueError("invalid backup identifier")
        directory = (self.backup_root / identifier).resolve()
        if directory.parent != self.backup_root or not directory.is_dir():
            raise FileNotFoundError(identifier)
        return directory

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _normalize_permissions(self, root: Path) -> None:
        """Keep sensitive artifacts private but manageable by the host data owner."""
        owner = self.database.parent.stat()
        for directory, names, files in os.walk(root):
            current = Path(directory)
            os.chown(current, owner.st_uid, owner.st_gid)
            current.chmod(0o750)
            for name in files:
                path = current / name
                os.chown(path, owner.st_uid, owner.st_gid)
                path.chmod(0o640)


def docker_container_running(container: str) -> bool:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", container],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from ..server.files import ServerFiles


PACK_ID = "8c916948-76c6-4aa5-91e0-97671dfd3830"
PACK_DIRECTORY = "craftcontrol-telemetry"
LEGACY_DIRECTORY = "minecraft-bedrock-telemetry"


@dataclass(frozen=True)
class TelemetryPackStatus:
    world: str
    source_version: str
    installed_version: str | None
    enabled_version: str | None
    installed: bool
    enabled: bool
    upgrade_available: bool
    legacy_directory: bool
    restart_required: bool | None
    installed_updated_at: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TelemetryPackInstaller:
    def __init__(self, project: Path, source: Path) -> None:
        self.project = project.resolve()
        self.data = self.project / "data"
        self.source = source.resolve()
        self.manifest = self._read_manifest(self.source / "manifest.json")
        if self.manifest["header"].get("uuid") != PACK_ID:
            raise ValueError("Telemetry pack UUID does not match CraftControl's allowlist")
        self.version = self._version(self.manifest["header"].get("version"))

    @classmethod
    def bundled(cls, project: Path) -> "TelemetryPackInstaller":
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / "packs" / "telemetry" / "behavior_pack"
            if candidate.is_dir():
                return cls(project, candidate)
        raise FileNotFoundError("Telemetry behavior pack not found relative to installer")

    def status(self, world: str | None = None) -> TelemetryPackStatus:
        world_name, world_directory = self._world(world)
        installed_manifest = self._optional_manifest(self._destination / "manifest.json")
        installed_version = self._version(installed_manifest["header"].get("version")) if installed_manifest else None
        enabled_entry = next((item for item in self._read_associations(world_directory) if item.get("pack_id") == PACK_ID), None)
        enabled_version = self._version(enabled_entry.get("version")) if enabled_entry else None
        installed = installed_manifest is not None
        enabled = enabled_entry is not None
        return TelemetryPackStatus(
            world=world_name,
            source_version=self.version,
            installed_version=installed_version,
            enabled_version=enabled_version,
            installed=installed,
            enabled=enabled,
            upgrade_available=installed_version != self.version or enabled_version != self.version,
            legacy_directory=self._legacy_destination.exists(),
            restart_required=None,
            installed_updated_at=(self._destination / "manifest.json").stat().st_mtime if installed else None,
        )

    def install(self, world: str | None = None) -> dict[str, Any]:
        world_name, world_directory = self._world(world)
        before = self.status(world_name)
        if before.installed_version == self.version and before.enabled_version == self.version and not before.legacy_directory:
            return {"changed": False, "action": "install", "status": before.to_dict(), "backup": None, "restart_required": False}
        backup = self._backup(world_name, world_directory)
        self._packs_directory.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{PACK_DIRECTORY}.", dir=self._packs_directory))
        try:
            shutil.copytree(self.source, staging, dirs_exist_ok=True)
            self._normalize_permissions(staging)
            if self._destination.exists():
                shutil.rmtree(self._destination)
            os.replace(staging, self._destination)
            self._write_associations(world_directory, self._with_pack(self._read_associations(world_directory)))
            if self._legacy_destination.exists():
                shutil.rmtree(self._legacy_destination)
        except Exception:
            if staging.exists():
                shutil.rmtree(staging)
            self._restore_backup(backup)
            raise
        return {"changed": True, "action": "install", "status": self.status(world_name).to_dict(), "backup": backup.name, "restart_required": True}

    def disable(self, world: str | None = None) -> dict[str, Any]:
        world_name, world_directory = self._world(world)
        associations = self._read_associations(world_directory)
        if not any(item.get("pack_id") == PACK_ID for item in associations):
            return {"changed": False, "action": "disable", "status": self.status(world_name).to_dict(), "backup": None, "restart_required": False}
        backup = self._backup(world_name, world_directory)
        self._write_associations(world_directory, [item for item in associations if item.get("pack_id") != PACK_ID])
        return {"changed": True, "action": "disable", "status": self.status(world_name).to_dict(), "backup": backup.name, "restart_required": True}

    def remove(self, world: str | None = None) -> dict[str, Any]:
        world_name, world_directory = self._world(world)
        before = self.status(world_name)
        if not before.installed and not before.enabled and not before.legacy_directory:
            return {"changed": False, "action": "remove", "status": before.to_dict(), "backup": None, "restart_required": False}
        backup = self._backup(world_name, world_directory)
        self._write_associations(world_directory, [item for item in self._read_associations(world_directory) if item.get("pack_id") != PACK_ID])
        for destination in (self._destination, self._legacy_destination):
            if destination.exists():
                shutil.rmtree(destination)
        return {"changed": True, "action": "remove", "status": self.status(world_name).to_dict(), "backup": backup.name, "restart_required": True}

    def snapshot(self, world: str | None = None) -> str:
        """Create a recovery copy of the current installed state and return the backup name."""
        world_name, world_directory = self._world(world)
        backup = self._backup(world_name, world_directory)
        return backup.name

    def rollback(self, backup_name: str | None = None) -> dict[str, Any]:
        backups = sorted((item for item in self._backup_root.glob("*") if item.is_dir()), reverse=True)
        backup = self._backup_root / backup_name if backup_name else (backups[0] if backups else None)
        if backup is None or not backup.is_dir() or backup.parent != self._backup_root:
            raise FileNotFoundError("Telemetry pack backup not found")
        metadata = self._restore_backup(backup)
        return {"changed": True, "action": "rollback", "backup": backup.name, "status": self.status(metadata["world"]).to_dict(), "restart_required": True}

    @property
    def _packs_directory(self) -> Path:
        return self.data / "behavior_packs"

    @property
    def _destination(self) -> Path:
        return self._packs_directory / PACK_DIRECTORY

    @property
    def _legacy_destination(self) -> Path:
        return self._packs_directory / LEGACY_DIRECTORY

    @property
    def _backup_root(self) -> Path:
        root = self.project / "backups" / "craftcontrol-telemetry"
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()

    def _world(self, explicit: str | None) -> tuple[str, Path]:
        worlds = (self.data / "worlds").resolve()
        candidates: list[str] = []
        if explicit:
            candidates.append(explicit)
        else:
            files = ServerFiles(self.project / ".env", self.data / "server.properties")
            _, environment = files.read_env()
            properties = files.read_properties()
            candidates.extend(value for value in (environment.get("LEVEL_NAME"), properties.get("level-name")) if value)
            if worlds.is_dir():
                candidates.extend(item.name for item in worlds.iterdir() if item.is_dir())
        for name in dict.fromkeys(candidates):
            if not name or Path(name).name != name:
                continue
            directory = (worlds / name).resolve()
            if directory.parent == worlds and directory.is_dir():
                return name, directory
        raise FileNotFoundError("No valid Bedrock world directory was found")

    def _backup(self, world: str, world_directory: Path) -> Path:
        identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup = self._backup_root / identifier
        backup.mkdir()
        association = world_directory / "world_behavior_packs.json"
        metadata = {"world": world, "association_existed": association.exists(), "packs": []}
        if association.exists():
            shutil.copy2(association, backup / "world_behavior_packs.json")
        pack_backup = backup / "packs"
        for destination in (self._destination, self._legacy_destination):
            if destination.exists():
                pack_backup.mkdir(exist_ok=True)
                shutil.copytree(destination, pack_backup / destination.name)
                metadata["packs"].append(destination.name)
        (backup / "backup.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return backup

    def _restore_backup(self, backup: Path) -> dict[str, Any]:
        backup = backup.resolve()
        if backup.parent != self._backup_root:
            raise ValueError("Backup path escapes the telemetry backup directory")
        metadata = json.loads((backup / "backup.json").read_text(encoding="utf-8"))
        _, world_directory = self._world(metadata["world"])
        association = world_directory / "world_behavior_packs.json"
        if metadata["association_existed"]:
            shutil.copy2(backup / "world_behavior_packs.json", association)
        elif association.exists():
            association.unlink()
        for destination in (self._destination, self._legacy_destination):
            if destination.exists():
                shutil.rmtree(destination)
        for name in metadata.get("packs", []):
            if name not in {PACK_DIRECTORY, LEGACY_DIRECTORY}:
                raise ValueError("Backup contains an unexpected pack directory")
            self._packs_directory.mkdir(parents=True, exist_ok=True)
            shutil.copytree(backup / "packs" / name, self._packs_directory / name)
        return metadata

    def _read_associations(self, world_directory: Path) -> list[dict[str, Any]]:
        path = world_directory / "world_behavior_packs.json"
        if not path.exists():
            return []
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ValueError("world_behavior_packs.json must contain a JSON array")
        return value

    def _write_associations(self, world_directory: Path, associations: list[dict[str, Any]]) -> None:
        path = world_directory / "world_behavior_packs.json"
        descriptor, temporary = tempfile.mkstemp(prefix=".world_behavior_packs.", dir=world_directory, text=True)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(associations, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.chmod(temporary, 0o644)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _with_pack(self, associations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = [item for item in associations if item.get("pack_id") != PACK_ID]
        result.append({"pack_id": PACK_ID, "version": list(self.manifest["header"]["version"])})
        return result

    @staticmethod
    def _normalize_permissions(root: Path) -> None:
        for directory, directories, files in os.walk(root):
            os.chmod(directory, 0o755)
            for name in directories:
                os.chmod(Path(directory) / name, 0o755)
            for name in files:
                os.chmod(Path(directory) / name, 0o644)

    @staticmethod
    def _read_manifest(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise FileNotFoundError(f"Telemetry pack manifest not found: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("header"), dict):
            raise ValueError("Telemetry pack manifest is invalid")
        return value

    @classmethod
    def _optional_manifest(cls, path: Path) -> dict[str, Any] | None:
        return cls._read_manifest(path) if path.is_file() else None

    @staticmethod
    def _version(value: Any) -> str:
        if not isinstance(value, list) or len(value) != 3 or not all(isinstance(part, int) and part >= 0 for part in value):
            raise ValueError("Telemetry pack version must contain three non-negative integers")
        return ".".join(str(part) for part in value)

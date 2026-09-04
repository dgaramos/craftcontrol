"""TDD: audit writes for BackupService actions.

Criteria:
- Happy path: create succeeds -> audit record with action "backup.created"
- Happy path: restore succeeds -> audit record with action "backup.restored"
- Happy path: prune (confirmed) -> audit record with action "backup.pruned"
- Edge case: metadata contains no host paths or secrets
- Edge case: audit_service=None does not raise
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.audit.service import AuditService
from src.operations.backup import BackupService

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fakes import FakeAuditPort, FakeConsole


def _make_backup_env(tmp_path: Path):
    project = tmp_path / "project"
    backup_root = tmp_path / "backups"
    world = project / "data" / "worlds" / "TestWorld"
    world.mkdir(parents=True)
    (project / ".env").write_text("LEVEL_NAME=TestWorld\n", encoding="utf-8")
    project.mkdir(parents=True, exist_ok=True)
    backup_root.mkdir(parents=True, exist_ok=True)
    database = project / "manager.db"
    database.write_bytes(b"")
    return project, backup_root, database


def _make_service(tmp_path, audit_port=None):
    project, backup_root, database = _make_backup_env(tmp_path)
    console = FakeConsole()
    port = audit_port if audit_port is not None else FakeAuditPort()
    audit = AuditService(port)
    service = BackupService(
        database=database,
        project=project,
        backup_root=backup_root,
        console=console,
        server_running=lambda: False,
        audit_service=audit,
    )
    return service, port, project, backup_root


def _make_service_no_audit(tmp_path):
    project, backup_root, database = _make_backup_env(tmp_path)
    return BackupService(
        database=database,
        project=project,
        backup_root=backup_root,
        console=FakeConsole(),
        server_running=lambda: False,
    )


class TestBackupAudit:
    def test_create_writes_audit_record(self, tmp_path: Path) -> None:
        """Happy path: create writes a backup.created audit record."""
        port = FakeAuditPort()
        service, _, _, _ = _make_service(tmp_path, port)
        service.create()
        assert any(r["action"] == "backup.created" for r in port.records), port.records

    def test_restore_writes_audit_record(self, tmp_path: Path) -> None:
        """Happy path: restore writes a backup.restored audit record."""
        port = FakeAuditPort()
        service, _, _project, _backup_root = _make_service(tmp_path, port)
        # Create a backup first so we have something to restore from
        result = service.create()
        identifier = result["id"]
        # Restore requires server not running — already False
        service.restore(identifier, confirmed=True)
        assert any(r["action"] == "backup.restored" for r in port.records), port.records

    def test_prune_confirmed_writes_audit_record(self, tmp_path: Path) -> None:
        """Happy path: confirmed prune writes a backup.pruned record."""
        port = FakeAuditPort()
        service, _, _, _ = _make_service(tmp_path, port)
        service.create()
        service.create()  # two backups so keep=1 deletes one
        service.prune(keep=1, confirmed=True)
        assert any(r["action"] == "backup.pruned" for r in port.records), port.records

    def test_prune_dry_run_does_not_write_audit_record(self, tmp_path: Path) -> None:
        """Edge case: dry-run prune (confirmed=False) must not write an audit record."""
        port = FakeAuditPort()
        service, _, _, _ = _make_service(tmp_path, port)
        service.create()
        service.create()
        port.records.clear()
        service.prune(keep=1, confirmed=False)
        assert not any(r["action"] == "backup.pruned" for r in port.records), port.records

    def test_backup_audit_metadata_does_not_expose_paths_or_secrets(self, tmp_path: Path) -> None:
        """Edge case: metadata must not contain host paths or secret content."""
        port = FakeAuditPort()
        service, _, _, _ = _make_service(tmp_path, port)
        service.create()
        created = next(r for r in port.records if r["action"] == "backup.created")
        metadata_str = json.dumps(created["metadata"])
        assert str(tmp_path) not in metadata_str, "host path leaked into metadata"
        assert ".env" not in metadata_str, ".env referenced in metadata"
        assert "manager.db" not in metadata_str, "database path in metadata"

    def test_no_audit_service_create_does_not_raise(self, tmp_path: Path) -> None:
        """Edge case: omitting audit_service on create must not raise."""
        service = _make_service_no_audit(tmp_path)
        service.create()

    def test_no_audit_service_restore_does_not_raise(self, tmp_path: Path) -> None:
        """Edge case: omitting audit_service on restore must not raise."""
        service = _make_service_no_audit(tmp_path)
        result = service.create()
        service.restore(result["id"], confirmed=True)

    def test_no_audit_service_prune_does_not_raise(self, tmp_path: Path) -> None:
        """Edge case: omitting audit_service on prune must not raise."""
        service = _make_service_no_audit(tmp_path)
        service.create()
        service.create()
        service.prune(keep=1, confirmed=True)

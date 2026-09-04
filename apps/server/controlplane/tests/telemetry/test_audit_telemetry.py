"""TDD: audit writes for TelemetryPackInstaller actions.

Criteria:
- Happy path: install -> audit record with action "telemetry.installed"
- Happy path: disable -> audit record with action "telemetry.disabled"
- Happy path: remove -> audit record with action "telemetry.removed"
- Edge case: audit_service=None does not raise
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

import pytest

from src.audit.service import AuditService
from src.telemetry.installer import PACK_ID, TelemetryPackInstaller

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fakes import FakeAuditPort


def _make_installer_env(tmp_path: Path, audit_port=None):
    project = tmp_path / "project"
    source = tmp_path / "source"
    world = project / "data" / "worlds" / "BedrockLevel"
    world.mkdir(parents=True)
    (project / ".env").write_text("LEVEL_NAME=BedrockLevel\n", encoding="utf-8")
    source.mkdir()
    (source / "scripts").mkdir()
    (source / "scripts" / "main.js").write_text("// pack\n", encoding="utf-8")
    (source / "manifest.json").write_text(json.dumps({
        "format_version": 2,
        "header": {"name": "CraftControl Telemetry Pack", "uuid": PACK_ID, "version": [0, 2, 0]},
    }), encoding="utf-8")
    port = audit_port if audit_port is not None else FakeAuditPort()
    audit = AuditService(port)
    installer = TelemetryPackInstaller(project, source, audit_service=audit)
    return installer, port


def _make_installer_no_audit(tmp_path: Path):
    project = tmp_path / "project"
    source = tmp_path / "source"
    world = project / "data" / "worlds" / "BedrockLevel"
    world.mkdir(parents=True)
    (project / ".env").write_text("LEVEL_NAME=BedrockLevel\n", encoding="utf-8")
    source.mkdir()
    (source / "scripts").mkdir()
    (source / "scripts" / "main.js").write_text("// pack\n", encoding="utf-8")
    (source / "manifest.json").write_text(json.dumps({
        "format_version": 2,
        "header": {"name": "CraftControl Telemetry Pack", "uuid": PACK_ID, "version": [0, 2, 0]},
    }), encoding="utf-8")
    return TelemetryPackInstaller(project, source)


class TestTelemetryPackAudit:
    def test_install_writes_audit_record(self, tmp_path: Path) -> None:
        """Happy path: install writes a telemetry.installed audit record."""
        port = FakeAuditPort()
        installer, _ = _make_installer_env(tmp_path, port)
        installer.install()
        assert any(r["action"] == "telemetry.installed" for r in port.records), port.records

    def test_disable_writes_audit_record(self, tmp_path: Path) -> None:
        """Happy path: disable writes a telemetry.disabled audit record."""
        port = FakeAuditPort()
        installer, _ = _make_installer_env(tmp_path, port)
        installer.install()
        port.records.clear()
        installer.disable()
        assert any(r["action"] == "telemetry.disabled" for r in port.records), port.records

    def test_remove_writes_audit_record(self, tmp_path: Path) -> None:
        """Happy path: remove writes a telemetry.removed audit record."""
        port = FakeAuditPort()
        installer, _ = _make_installer_env(tmp_path, port)
        installer.install()
        port.records.clear()
        installer.remove()
        assert any(r["action"] == "telemetry.removed" for r in port.records), port.records

    def test_no_audit_service_install_does_not_raise(self, tmp_path: Path) -> None:
        """Edge case: omitting audit_service on install must not raise."""
        installer = _make_installer_no_audit(tmp_path)
        installer.install()

    def test_no_audit_service_disable_does_not_raise(self, tmp_path: Path) -> None:
        """Edge case: omitting audit_service on disable must not raise."""
        installer = _make_installer_no_audit(tmp_path)
        installer.install()
        installer.disable()

    def test_no_audit_service_remove_does_not_raise(self, tmp_path: Path) -> None:
        """Edge case: omitting audit_service on remove must not raise."""
        installer = _make_installer_no_audit(tmp_path)
        installer.install()
        installer.remove()

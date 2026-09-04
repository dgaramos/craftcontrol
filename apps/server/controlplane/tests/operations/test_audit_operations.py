"""TDD: audit writes for ServerOperationService terminal states.

Criteria:
- Happy path: CONFIRMED operation → audit record with action "operation.confirmed"
- Failure path: FAILED operation → audit record with action "operation.failed"
- Edge case: audit_service=None does not raise
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.audit.service import AuditService
from src.operations.lifecycle import OperationState
from src.operations.service import ServerOperationService
from conftest import make_operation_db, make_operation_service, wait_for_terminal
from fakes import FakeAuditPort


class InlineThread:
    """Runs a background-operation target synchronously."""

    def __init__(self, *, target, args, **_kwargs) -> None:
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


def _make_service_with_audit(
    tmp_path: Path,
    audit_port: FakeAuditPort | None = None,
    confirmed_property_value: str = "MyServer",
):
    from unittest.mock import MagicMock
    from src.operations.repository import SQLiteOperationRepository

    port = audit_port if audit_port is not None else FakeAuditPort()
    audit = AuditService(port)

    docker = MagicMock()
    docker.status.return_value = {"state": "running", "online": True}
    docker.execute.return_value = None
    broker = MagicMock()
    configuration = MagicMock()
    # read_properties must return the same value sent so verification confirms.
    configuration.read_properties.return_value = {"server-name": confirmed_property_value}

    return ServerOperationService(
        operation_repository=SQLiteOperationRepository(make_operation_db(tmp_path)),
        docker=docker,
        broker=broker,
        configuration=configuration,
        thread_factory=InlineThread,
        server_id="test-server",
        health_timeout=1,
        restart_timeout=180,
        audit_service=audit,
    ), port


class TestServerOperationServiceAudit:
    def test_confirmed_operation_writes_audit_record(self, tmp_path: Path) -> None:
        """Happy path: a CONFIRMED operation writes an audit record."""
        port = FakeAuditPort()
        service, _ = _make_service_with_audit(tmp_path, port)
        service.apply_restart_required({"SERVER_NAME": "MyServer"}, lambda: None)
        assert any(r["action"] == "operation.confirmed" for r in port.records), port.records

    def test_failed_operation_writes_audit_record(self, tmp_path: Path) -> None:
        """Failure path: a FAILED operation writes an audit record."""
        port = FakeAuditPort()
        service, _ = _make_service_with_audit(tmp_path, port)

        def bad_apply():
            raise RuntimeError("disk full")

        service.apply_restart_required({"SERVER_NAME": "MyServer"}, bad_apply)
        assert any(r["action"] == "operation.failed" for r in port.records), port.records

    def test_no_audit_service_does_not_raise(self, tmp_path: Path) -> None:
        """Edge case: omitting audit_service must not raise."""
        service = make_operation_service(tmp_path, thread_factory=InlineThread)
        service.apply_restart_required({"SERVER_NAME": "MyServer"}, lambda: None)

    def test_audit_metadata_does_not_expose_setting_values(self, tmp_path: Path) -> None:
        """Edge case: metadata must only contain setting keys, not values."""
        port = FakeAuditPort()
        service, _ = _make_service_with_audit(tmp_path, port)
        service, port2 = _make_service_with_audit(tmp_path, port, confirmed_property_value="SuperSecret")
        service.apply_restart_required({"SERVER_NAME": "SuperSecret"}, lambda: None)
        confirmed = next((r for r in port2.records if r["action"] == "operation.confirmed"), None)
        assert confirmed is not None
        # "changes" should list keys, not contain the value "SuperSecret"
        metadata = confirmed["metadata"]
        assert "changes" in metadata
        assert "SuperSecret" not in str(metadata["changes"])

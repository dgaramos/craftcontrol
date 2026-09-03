"""Tests for audit records emitted by privileged ManagerService mutations.

TDD: Red tests written before implementation code.

Each test group covers:
- Happy path: a successful mutation emits an audit record with the correct fields.
- Failure path: an invalid/disallowed call emits a failure/denied audit record.
- Edge case: audit_service=None does not break the mutation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.audit.service import AuditService
from src.core.events import EventBroker
from src.core.repository import StateRepository
from src.players import PlayerService, SQLitePlayerRepository
from src.runtime import ManagerService
from src.runtime.reconciliation import ReconciliationService
from src.server import WorldService
from src.server.files import ServerFiles
from src.telemetry.repository import SQLiteTelemetryRepository
from src.telemetry.service import TelemetryService
from conftest import make_operation_db
from fakes import FakeBedrock, FakeDocker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeAuditPort:
    """Minimal in-memory AuditPort for injection into tests."""

    def __init__(self) -> None:
        self.written: list[dict[str, Any]] = []

    def write(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        result: str,
        metadata: dict[str, Any],
    ) -> None:
        self.written.append(
            {"actor": actor, "action": action, "target": target, "result": result, "metadata": metadata}
        )

    def query(self, *, page: int, page_size: int, actor: str | None = None, action: str | None = None) -> dict:
        return {"records": [], "total": 0, "page": page, "page_size": page_size, "pages": 0}


def _make_manager(tmp_path: Path, *, audit_port: FakeAuditPort | None = None) -> tuple[ManagerService, FakeAuditPort]:
    db_path = make_operation_db(tmp_path)
    repo = StateRepository(db_path)
    repo.initialize()
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties")
    bedrock = FakeBedrock()
    docker = FakeDocker()
    broker = EventBroker(repo)
    player_repo = SQLitePlayerRepository(db_path)
    player_service = PlayerService(player_repo, files, bedrock, broker)  # type: ignore[arg-type]
    telemetry_service = TelemetryService(SQLiteTelemetryRepository(db_path), broker)
    world_service = WorldService(bedrock, broker)  # type: ignore[arg-type]
    reconciliation_service = ReconciliationService(
        repository=repo,
        files=files,
        bedrock=bedrock,  # type: ignore[arg-type]
        broker=broker,
        player_service=player_service,
        telemetry_service=telemetry_service,
    )
    port = audit_port if audit_port is not None else FakeAuditPort()
    audit_service = AuditService(port)
    manager = ManagerService(
        repo,
        files,
        bedrock,  # type: ignore[arg-type]
        docker,  # type: ignore[arg-type]
        broker=broker,
        player_service=player_service,
        telemetry_service=telemetry_service,
        world_service=world_service,
        reconciliation_service=reconciliation_service,
        audit_service=audit_service,
    )
    return manager, port


# ---------------------------------------------------------------------------
# set_gamerule
# ---------------------------------------------------------------------------

class TestManagerAuditOnGamerule:
    def test_success_emits_audit_record(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        manager.set_gamerule("showcoordinates", "true", actor="alice")
        assert len(port.written) == 1
        rec = port.written[0]
        assert rec["action"] == "server.gamerule.changed"
        assert rec["target"] == "showcoordinates"
        assert rec["result"] == "success"
        assert rec["actor"] == "alice"

    def test_invalid_rule_emits_failure_audit(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        with pytest.raises(KeyError):
            manager.set_gamerule("unknownRule", "true", actor="alice")
        assert len(port.written) == 1
        rec = port.written[0]
        assert rec["action"] == "server.gamerule.changed"
        assert rec["result"] in {"failure", "denied"}

    def test_no_audit_service_does_not_raise(self, tmp_path: Path) -> None:
        manager, _ = _make_manager(tmp_path)
        manager.audit_service = None
        # Should not raise even without audit_service
        manager.set_gamerule("showcoordinates", "false")


# ---------------------------------------------------------------------------
# save_settings
# ---------------------------------------------------------------------------

class TestManagerAuditOnSettingsChange:
    def test_success_emits_audit_record(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        manager.save_settings({"MAX_PLAYERS": "10"}, actor="alice")
        assert len(port.written) == 1
        rec = port.written[0]
        assert rec["action"] == "server.settings.changed"
        assert rec["result"] == "success"
        assert rec["actor"] == "alice"

    def test_invalid_payload_emits_failure_audit(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        with pytest.raises((TypeError, ValueError)):
            manager.save_settings("not-a-dict", actor="alice")
        assert len(port.written) == 1
        assert port.written[0]["result"] == "failure"

    def test_no_valid_settings_emits_failure_audit(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        with pytest.raises(ValueError):
            manager.save_settings({"unknown-key": "x"}, actor="alice")
        assert len(port.written) == 1
        assert port.written[0]["result"] == "failure"


# ---------------------------------------------------------------------------
# run_world_action
# ---------------------------------------------------------------------------

class TestManagerAuditOnWorldAction:
    def test_success_emits_audit_record(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        # Pick any valid world action
        valid_action = next(iter(manager.WORLD_ACTIONS))
        manager.run_world_action(valid_action, actor="alice")
        assert len(port.written) == 1
        rec = port.written[0]
        assert rec["action"] == "world.action"
        assert rec["target"] == valid_action
        assert rec["result"] == "success"
        assert rec["actor"] == "alice"

    def test_invalid_action_emits_failure_audit(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        with pytest.raises(KeyError):
            manager.run_world_action("not-a-real-action", actor="alice")
        assert len(port.written) == 1
        assert port.written[0]["result"] in {"failure", "denied"}

    def test_no_audit_service_does_not_raise(self, tmp_path: Path) -> None:
        manager, _ = _make_manager(tmp_path)
        manager.audit_service = None
        valid_action = next(iter(manager.WORLD_ACTIONS))
        manager.run_world_action(valid_action)


# ---------------------------------------------------------------------------
# time_action
# ---------------------------------------------------------------------------

class TestManagerAuditOnTimeAction:
    def test_success_emits_audit_record(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        manager.time_action("query", {"value": "daytime"}, actor="alice")
        assert len(port.written) == 1
        rec = port.written[0]
        assert rec["action"] == "world.time.action"
        assert rec["target"] == "query"
        assert rec["result"] == "success"
        assert rec["actor"] == "alice"

    def test_invalid_action_emits_failure_audit(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        with pytest.raises((KeyError, ValueError)):
            manager.time_action("not-valid", {}, actor="alice")
        assert len(port.written) == 1
        assert port.written[0]["result"] in {"failure", "denied"}


# ---------------------------------------------------------------------------
# set_player_operator
# ---------------------------------------------------------------------------

class TestManagerAuditOnPlayerOperator:
    def test_success_emits_audit_record(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        manager.set_player_operator("Steve", True, actor="alice")
        assert len(port.written) == 1
        rec = port.written[0]
        assert rec["action"] == "players.operator.changed"
        assert rec["target"] == "Steve"
        assert rec["result"] == "success"
        assert rec["actor"] == "alice"
        assert rec["metadata"].get("enabled") is True

    def test_disable_operator_audit_records_enabled_false(self, tmp_path: Path) -> None:
        manager, port = _make_manager(tmp_path)
        manager.set_player_operator("Steve", False, actor="alice")
        assert port.written[0]["metadata"].get("enabled") is False

    def test_no_audit_service_does_not_raise(self, tmp_path: Path) -> None:
        manager, _ = _make_manager(tmp_path)
        manager.audit_service = None
        manager.set_player_operator("Steve", True)

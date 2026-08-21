"""Tests for the server-operation lifecycle, persistence, and service.

Covers:
- lifecycle.py  (contract / data model)
- repository.py (SQLite persistence)
- service.py    (orchestration and reconciliation)
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minecraft_manager.operations.lifecycle import (
    OperationStage,
    OperationState,
    ServerOperation,
    StageResult,
)
from minecraft_manager.operations.repository import SQLiteOperationRepository
from minecraft_manager.operations.service import (
    ConflictingOperationError,
    ServerOperationService,
)
from minecraft_manager.migrations import run_migrations
import sqlite3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_db(tmp_path: Path) -> Path:
    db = tmp_path / "state.db"
    with sqlite3.connect(db) as conn:
        run_migrations(conn)
    return db


def make_repo(tmp_path: Path) -> SQLiteOperationRepository:
    return SQLiteOperationRepository(make_db(tmp_path))


def make_service(
    tmp_path: Path,
    docker: MagicMock | None = None,
    broker: MagicMock | None = None,
    health_timeout: int = 1,
) -> ServerOperationService:
    if docker is None:
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.return_value = None
    if broker is None:
        broker = MagicMock()
    return ServerOperationService(
        operation_repository=make_repo(tmp_path),
        docker=docker,
        broker=broker,
        server_id="test-server",
        health_timeout=health_timeout,
    )


# ---------------------------------------------------------------------------
# Lifecycle model tests
# ---------------------------------------------------------------------------


class TestServerOperationContract:
    def test_create_produces_pending_operation(self):
        op = ServerOperation.create("srv", {"MAX_PLAYERS": "20"})
        assert op.state == OperationState.PENDING
        assert op.server_id == "srv"
        assert len(op.stages) == len(OperationStage.ordered())
        assert all(s.result == StageResult.PENDING for s in op.stages)

    def test_start_transitions_to_running(self):
        op = ServerOperation.create("srv", {})
        op.start()
        assert op.state == OperationState.RUNNING

    def test_complete_stage_sets_evidence(self):
        op = ServerOperation.create("srv", {})
        op.start()
        op.begin_stage(OperationStage.REVIEW)
        op.complete_stage(OperationStage.REVIEW, evidence={"changes": ["MAX_PLAYERS"]})
        record = next(s for s in op.stages if s.stage == OperationStage.REVIEW)
        assert record.result == StageResult.COMPLETED
        assert record.evidence["changes"] == ["MAX_PLAYERS"]

    def test_fail_stage_marks_operation_failed(self):
        op = ServerOperation.create("srv", {})
        op.start()
        op.begin_stage(OperationStage.RESTART)
        op.fail_stage(OperationStage.RESTART, "container conflict")
        assert op.state == OperationState.FAILED
        assert op.terminal_error == "container conflict"
        assert op.state.is_terminal

    def test_confirm_marks_operation_confirmed(self):
        op = ServerOperation.create("srv", {})
        op.start()
        op.confirm(evidence={"confirmed_at": 123.0})
        assert op.state == OperationState.CONFIRMED
        assert op.state.is_terminal

    def test_diverge_marks_operation_divergent(self):
        op = ServerOperation.create("srv", {})
        op.start()
        op.diverge("config mismatch", observation={"expected": "20", "actual": "10"})
        assert op.state == OperationState.DIVERGENT
        assert op.state.is_terminal

    def test_skip_stage_records_reason(self):
        op = ServerOperation.create("srv", {})
        op.start()
        op.skip_stage(OperationStage.BACKUP_VERIFY, reason="no_backup_required")
        record = next(s for s in op.stages if s.stage == OperationStage.BACKUP_VERIFY)
        assert record.result == StageResult.SKIPPED
        assert record.evidence["skip_reason"] == "no_backup_required"

    def test_roundtrip_serialisation(self):
        op = ServerOperation.create("srv", {"X": "1"}, correlation_id="abc")
        op.start()
        op.begin_stage(OperationStage.REVIEW)
        op.complete_stage(OperationStage.REVIEW, evidence={"changes": ["X"]})
        restored = ServerOperation.from_dict(op.as_dict())
        assert restored.operation_id == op.operation_id
        assert restored.state == op.state
        assert restored.correlation_id == "abc"
        review = next(s for s in restored.stages if s.stage == OperationStage.REVIEW)
        assert review.result == StageResult.COMPLETED

    def test_active_stage_property(self):
        op = ServerOperation.create("srv", {})
        op.start()
        op.begin_stage(OperationStage.PREPARE)
        assert op.active_stage is not None
        assert op.active_stage.stage == OperationStage.PREPARE

    def test_failed_stage_property(self):
        op = ServerOperation.create("srv", {})
        op.start()
        op.begin_stage(OperationStage.RESTART)
        op.fail_stage(OperationStage.RESTART, "boom")
        assert op.failed_stage is not None
        assert op.failed_stage.stage == OperationStage.RESTART


# ---------------------------------------------------------------------------
# Repository tests
# ---------------------------------------------------------------------------


class TestSQLiteOperationRepository:
    def test_save_and_get(self, tmp_path: Path):
        repo = make_repo(tmp_path)
        op = ServerOperation.create("srv", {"K": "V"})
        repo.save(op)
        loaded = repo.get(op.operation_id)
        assert loaded is not None
        assert loaded.operation_id == op.operation_id
        assert loaded.state == OperationState.PENDING
        assert loaded.requested_changes == {"K": "V"}
        assert len(loaded.stages) == len(OperationStage.ordered())

    def test_get_latest(self, tmp_path: Path):
        repo = make_repo(tmp_path)
        op1 = ServerOperation.create("srv", {})
        op2 = ServerOperation.create("srv", {})
        op2.created_at = op1.created_at + 1
        repo.save(op1)
        repo.save(op2)
        latest = repo.get_latest("srv")
        assert latest is not None
        assert latest.operation_id == op2.operation_id

    def test_get_active_excludes_terminal(self, tmp_path: Path):
        repo = make_repo(tmp_path)
        op = ServerOperation.create("srv", {})
        op.start()
        op.confirm()
        repo.save(op)
        assert repo.get_active("srv") is None

    def test_get_active_returns_running(self, tmp_path: Path):
        repo = make_repo(tmp_path)
        op = ServerOperation.create("srv", {})
        op.start()
        repo.save(op)
        active = repo.get_active("srv")
        assert active is not None
        assert active.operation_id == op.operation_id

    def test_update_stage_persists_without_full_save(self, tmp_path: Path):
        repo = make_repo(tmp_path)
        op = ServerOperation.create("srv", {})
        op.start()
        repo.save(op)
        op.begin_stage(OperationStage.REVIEW)
        repo.update_stage(op, OperationStage.REVIEW)
        loaded = repo.get(op.operation_id)
        assert loaded is not None
        review = next(s for s in loaded.stages if s.stage == OperationStage.REVIEW)
        assert review.result == StageResult.RUNNING

    def test_list_recent(self, tmp_path: Path):
        repo = make_repo(tmp_path)
        for i in range(3):
            op = ServerOperation.create("srv", {})
            op.created_at = float(i)
            repo.save(op)
        ops = repo.list_recent("srv", limit=2)
        assert len(ops) == 2

    def test_returns_none_for_missing(self, tmp_path: Path):
        repo = make_repo(tmp_path)
        assert repo.get("nonexistent") is None
        assert repo.get_latest("absent") is None
        assert repo.get_active("absent") is None

    def test_idempotent_upsert(self, tmp_path: Path):
        repo = make_repo(tmp_path)
        op = ServerOperation.create("srv", {})
        repo.save(op)
        op.start()
        repo.save(op)
        loaded = repo.get(op.operation_id)
        assert loaded is not None
        assert loaded.state == OperationState.RUNNING


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


class TestServerOperationService:
    def test_apply_creates_operation_and_runs_apply_fn(self, tmp_path: Path):
        service = make_service(tmp_path)
        applied = []

        def apply_fn():
            applied.append(True)

        op = service.apply_restart_required({"X": "1"}, apply_fn)
        assert op.operation_id
        assert op.state in {OperationState.PENDING, OperationState.RUNNING}
        # Wait for background thread
        time.sleep(2)
        assert len(applied) == 1
        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.CONFIRMED

    def test_rejects_concurrent_operation(self, tmp_path: Path):
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        # Make docker.execute block so the first operation stays running
        barrier = threading.Event()

        def slow_execute(action):
            barrier.wait(timeout=5)

        docker.execute.side_effect = slow_execute
        service = make_service(tmp_path, docker=docker, health_timeout=1)

        def apply_fn():
            pass

        service.apply_restart_required({"X": "1"}, apply_fn)
        time.sleep(0.2)  # Let the operation start
        with pytest.raises(ConflictingOperationError):
            service.apply_restart_required({"Y": "2"}, apply_fn)
        barrier.set()

    def test_operation_fails_when_apply_fn_raises(self, tmp_path: Path):
        service = make_service(tmp_path)

        def bad_apply():
            raise RuntimeError("disk full")

        op = service.apply_restart_required({"X": "1"}, bad_apply)
        time.sleep(1)
        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.FAILED
        assert "disk full" in (refreshed.terminal_error or "")

    def test_operation_fails_when_docker_execute_raises(self, tmp_path: Path):
        docker = MagicMock()
        docker.status.return_value = {"state": "stopped", "online": False}
        docker.execute.side_effect = RuntimeError("container conflict")
        service = make_service(tmp_path, docker=docker, health_timeout=1)
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(1)
        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.FAILED

    def test_operation_fails_when_health_wait_times_out(self, tmp_path: Path):
        docker = MagicMock()
        # Container stays offline
        docker.status.return_value = {"state": "stopped", "online": False}
        docker.execute.return_value = None
        service = make_service(tmp_path, docker=docker, health_timeout=1)
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(2)
        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.FAILED
        failed = refreshed.failed_stage
        assert failed is not None
        assert failed.stage == OperationStage.HEALTH_WAIT

    def test_broker_publishes_on_each_stage(self, tmp_path: Path):
        broker = MagicMock()
        service = make_service(tmp_path, broker=broker, health_timeout=1)
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(2)
        assert broker.publish.call_count >= 3

    def test_get_latest_returns_most_recent(self, tmp_path: Path):
        service = make_service(tmp_path, health_timeout=1)
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(2)
        latest = service.get_latest()
        assert latest is not None
        assert latest.operation_id == op.operation_id

    def test_request_reconciliation_updates_observation(self, tmp_path: Path):
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.return_value = None
        service = make_service(tmp_path, docker=docker, health_timeout=1)
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(2)
        refreshed = service.request_reconciliation(op.operation_id)
        assert refreshed is not None
        assert "container_state" in refreshed.observation

    def test_request_reconciliation_returns_none_for_unknown(self, tmp_path: Path):
        service = make_service(tmp_path)
        assert service.request_reconciliation("nonexistent") is None

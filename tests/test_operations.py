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


class InlineThread:
    """Runs a background-operation target synchronously in focused tests."""

    def __init__(self, *, target, args, **_kwargs) -> None:
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


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
    configuration: MagicMock | None = None,
    health_timeout: int = 1,
    thread_factory=threading.Thread,
) -> ServerOperationService:
    if docker is None:
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.return_value = None
    if broker is None:
        broker = MagicMock()
    if configuration is None:
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "1"}
    return ServerOperationService(
        operation_repository=make_repo(tmp_path),
        docker=docker,
        broker=broker,
        configuration=configuration,
        thread_factory=thread_factory,
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
    def test_operation_confirms_only_when_effective_configuration_matches(self, tmp_path: Path):
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "20"}
        service = make_service(
            tmp_path,
            docker=docker,
            configuration=configuration,
            thread_factory=InlineThread,
        )

        operation = service.apply_restart_required({"MAX_PLAYERS": "20"}, lambda: None)

        assert operation.state == OperationState.CONFIRMED
        verify = next(stage for stage in operation.stages if stage.stage == OperationStage.VERIFY)
        assert verify.evidence["differences"] == []
        assert operation.observation["observed_settings"] == {"max-players": "20"}

    def test_operation_becomes_divergent_when_effective_configuration_differs(self, tmp_path: Path):
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "10"}
        service = make_service(
            tmp_path,
            docker=docker,
            configuration=configuration,
            thread_factory=InlineThread,
        )

        operation = service.apply_restart_required({"MAX_PLAYERS": "20"}, lambda: None)

        assert operation.state == OperationState.DIVERGENT
        assert operation.observation["differences"] == [
            {"property": "max-players", "expected": "20", "observed": "10"}
        ]
        assert operation.active_stage is None

    def test_operation_fails_when_bedrock_becomes_unhealthy_during_verification(self, tmp_path: Path):
        docker = MagicMock()
        docker.status.side_effect = [
            {"state": "running", "online": True},
            {"state": "stopped", "online": False},
        ]
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "20"}
        service = make_service(
            tmp_path, docker=docker, configuration=configuration, thread_factory=InlineThread
        )

        operation = service.apply_restart_required({"MAX_PLAYERS": "20"}, lambda: None)

        assert operation.state == OperationState.FAILED
        assert operation.failed_stage is not None
        assert operation.failed_stage.stage == OperationStage.VERIFY

    def test_operation_normalizes_valid_settings_before_verification(self, tmp_path: Path):
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "20"}
        service = make_service(tmp_path, configuration=configuration, thread_factory=InlineThread)

        operation = service.apply_restart_required({"MAX_PLAYERS": 20}, lambda: None)

        assert operation.state == OperationState.CONFIRMED
        assert operation.requested_changes == {"MAX_PLAYERS": "20"}

    def test_operation_records_each_invalid_setting_during_review(self, tmp_path: Path):
        service = make_service(tmp_path, thread_factory=InlineThread)

        operation = service.apply_restart_required(
            {"MAX_PLAYERS": 101, "DIFFICULTY": "nightmare"}, lambda: None
        )

        review = next(stage for stage in operation.stages if stage.stage == OperationStage.REVIEW)
        assert operation.state == OperationState.FAILED
        assert review.evidence["invalid_settings"] == {
            "MAX_PLAYERS": "valor fora do intervalo",
            "DIFFICULTY": "opção inválida",
        }

    def test_operation_fails_before_apply_when_a_setting_cannot_be_verified(self, tmp_path: Path):
        service = make_service(tmp_path, thread_factory=InlineThread)
        applied = []

        operation = service.apply_restart_required({"UNSUPPORTED_SETTING": "value"}, lambda: applied.append(True))

        assert operation.state == OperationState.FAILED
        assert applied == []
        review = next(stage for stage in operation.stages if stage.stage == OperationStage.REVIEW)
        assert review.evidence["unverifiable_settings"] == ["UNSUPPORTED_SETTING"]

    def test_apply_creates_operation_and_runs_apply_fn(self, tmp_path: Path):
        service = make_service(tmp_path)
        applied = []

        def apply_fn():
            applied.append(True)

        op = service.apply_restart_required({"MAX_PLAYERS": "1"}, apply_fn)
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

        service.apply_restart_required({"MAX_PLAYERS": "1"}, apply_fn)
        time.sleep(0.2)  # Let the operation start
        with pytest.raises(ConflictingOperationError):
            service.apply_restart_required({"MAX_PLAYERS": "2"}, apply_fn)
        barrier.set()

    def test_operation_fails_when_apply_fn_raises(self, tmp_path: Path):
        service = make_service(tmp_path)

        def bad_apply():
            raise RuntimeError("disk full")

        op = service.apply_restart_required({"MAX_PLAYERS": "1"}, bad_apply)
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

    def test_get_active_returns_none_when_no_active(self, tmp_path: Path):
        service = make_service(tmp_path)
        assert service.get_active() is None

    def test_list_recent_returns_operations(self, tmp_path: Path):
        service = make_service(tmp_path, health_timeout=1)
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(2)
        results = service.list_recent(limit=5)
        assert len(results) >= 1
        assert any(r.operation_id == op.operation_id for r in results)

    def test_observe_container_error_branch(self, tmp_path: Path):
        """_observe_container catches docker.status() exceptions and returns error dict."""
        docker = MagicMock()
        docker.status.side_effect = RuntimeError("docker daemon unavailable")
        docker.execute.return_value = None
        broker = MagicMock()
        service = make_service(tmp_path, docker=docker, broker=broker, health_timeout=1)
        # Trigger the error branch via apply which calls _observe_container during RESTART failure
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(2)
        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        # Operation fails because health wait uses _observe_container which returns online=False
        assert refreshed.state == OperationState.FAILED
        # Confirm failure occurred specifically in the HEALTH_WAIT stage, not in an
        # outer handler that would mask the error origin.
        failed = refreshed.failed_stage
        assert failed is not None and failed.stage == OperationStage.HEALTH_WAIT

    def test_unexpected_exception_in_run_marks_operation_failed(self, tmp_path: Path):
        """Outer except in _run catches unexpected failures from repo operations."""
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.return_value = None
        broker = MagicMock()

        repo = make_repo(tmp_path)
        original_update = repo.update_stage

        def flaky_update_stage(operation, stage):
            # Raise on PREPARE to exercise the outer _run except handler without
            # relying on a fragile call-count that breaks when the stage sequence
            # changes.
            if stage == OperationStage.PREPARE:
                raise RuntimeError("unexpected disk error")
            return original_update(operation, stage)

        repo.update_stage = flaky_update_stage  # type: ignore[method-assign]
        service = ServerOperationService(
            operation_repository=repo,
            docker=docker,
            broker=broker,
            configuration=MagicMock(),
            thread_factory=threading.Thread,
            server_id="test-server",
            health_timeout=1,
        )
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(1)
        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.FAILED
        assert "internal error" in (refreshed.terminal_error or "")

    def test_publish_exception_is_swallowed(self, tmp_path: Path):
        """_publish swallows broker exceptions without failing the operation."""
        broker = MagicMock()
        broker.publish.side_effect = RuntimeError("broker unavailable")
        service = make_service(tmp_path, broker=broker, health_timeout=1)
        op = service.apply_restart_required({}, lambda: None)
        time.sleep(2)
        # Operation still reaches terminal state despite broker failures
        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state.is_terminal

    def test_reconcile_startup_orphan(self, tmp_path: Path):
        """On startup, active operations from a previous process are failed."""
        db = make_db(tmp_path)
        repo = SQLiteOperationRepository(db)
        orphan = ServerOperation.create("test-server", {"X": "1"})
        orphan.start()
        # Simulate a stale orphan: backdate updated_at beyond the staleness threshold
        # so _reconcile_startup_orphans treats it as abandoned rather than still-running.
        orphan.updated_at -= 60
        repo.save(orphan)
        # Verify orphan is active before we create the service
        assert repo.get_active("test-server") is not None

        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        broker = MagicMock()
        # Creating the service triggers _reconcile_startup_orphans
        ServerOperationService(
            operation_repository=repo,
            docker=docker,
            broker=broker,
            configuration=MagicMock(),
            thread_factory=threading.Thread,
            server_id="test-server",
            health_timeout=1,
        )
        # The orphan should now be in a terminal state
        reconciled = repo.get(orphan.operation_id)
        assert reconciled is not None
        assert reconciled.state == OperationState.FAILED
        assert "abandoned" in (reconciled.terminal_error or "")

    def test_reconcile_startup_orphan_with_active_stage(self, tmp_path: Path):
        """Orphan with an active (RUNNING) stage uses that stage for fail_stage."""
        db = make_db(tmp_path)
        repo = SQLiteOperationRepository(db)
        orphan = ServerOperation.create("test-server", {})
        orphan.start()
        orphan.begin_stage(OperationStage.RESTART)
        # Backdate updated_at so the staleness guard treats this as a true orphan.
        orphan.updated_at -= 60
        repo.save(orphan)

        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        broker = MagicMock()
        ServerOperationService(
            operation_repository=repo,
            docker=docker,
            broker=broker,
            configuration=MagicMock(),
            thread_factory=threading.Thread,
            server_id="test-server",
            health_timeout=1,
        )
        reconciled = repo.get(orphan.operation_id)
        assert reconciled is not None
        assert reconciled.state == OperationState.FAILED

    def test_reconcile_startup_orphan_skips_recent_operations(self, tmp_path: Path):
        """Recently-updated operations are left untouched to avoid racing a live worker."""
        db = make_db(tmp_path)
        repo = SQLiteOperationRepository(db)
        orphan = ServerOperation.create("test-server", {})
        orphan.start()
        # updated_at is fresh (now) — staleness guard must keep it as RUNNING.
        repo.save(orphan)

        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        broker = MagicMock()
        ServerOperationService(
            operation_repository=repo,
            docker=docker,
            broker=broker,
            configuration=MagicMock(),
            thread_factory=threading.Thread,
            server_id="test-server",
            health_timeout=1,
        )
        untouched = repo.get(orphan.operation_id)
        assert untouched is not None
        assert untouched.state == OperationState.RUNNING


# ---------------------------------------------------------------------------
# Lifecycle edge-case tests
# ---------------------------------------------------------------------------


class TestLifecycleEdgeCases:
    def test_index_of_returns_correct_position(self):
        assert OperationStage.index_of(OperationStage.REVIEW) == 0
        assert OperationStage.index_of(OperationStage.CONFIRM) == len(OperationStage.ordered()) - 1

    def test_begin_stage_with_evidence(self):
        op = ServerOperation.create("srv", {})
        op.start()
        op.begin_stage(OperationStage.REVIEW, evidence={"hint": "value"})
        record = next(s for s in op.stages if s.stage == OperationStage.REVIEW)
        assert record.evidence["hint"] == "value"

    def test_stage_raises_keyerror_for_stage_not_in_list(self):
        op = ServerOperation.create("srv", {})
        # Clear stages to force the KeyError path
        op.stages = []
        with pytest.raises(KeyError):
            op._stage(OperationStage.REVIEW)

    def test_assert_state_raises_on_wrong_state(self):
        op = ServerOperation.create("srv", {})
        # Operation is PENDING; calling start() again should raise because
        # start() asserts PENDING and transitions, so call confirm() which asserts RUNNING
        with pytest.raises(ValueError, match="Cannot transition"):
            op.confirm()

    def test_active_stage_returns_none_when_no_running_stage(self):
        op = ServerOperation.create("srv", {})
        # All stages are PENDING — none is RUNNING
        assert op.active_stage is None

    def test_failed_stage_returns_none_when_no_failed_stage(self):
        op = ServerOperation.create("srv", {})
        assert op.failed_stage is None


# ---------------------------------------------------------------------------
# Repository edge-case tests
# ---------------------------------------------------------------------------


class TestRepositoryEdgeCases:
    def test_update_stage_returns_early_for_missing_stage(self, tmp_path: Path):
        """update_stage is a no-op when the stage is not found in operation.stages."""
        repo = make_repo(tmp_path)
        op = ServerOperation.create("srv", {})
        op.start()
        repo.save(op)
        # Replace stages list with an empty list so the stage look-up finds nothing
        op.stages = []
        # Should not raise; just return early
        repo.update_stage(op, OperationStage.REVIEW)


# ---------------------------------------------------------------------------
# Issue #194 — failure recovery and reconciliation
# ---------------------------------------------------------------------------


class TestRecoveryAndReconciliation:
    def test_reconciliation_confirms_when_server_is_online_and_config_matches(self, tmp_path: Path):
        """request_reconciliation transitions FAILED → CONFIRMED when config matches."""
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.side_effect = RuntimeError("container conflict")
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "20"}
        service = make_service(tmp_path, docker=docker, configuration=configuration, health_timeout=1)
        op = service.apply_restart_required({"MAX_PLAYERS": "20"}, lambda: None)
        time.sleep(2)
        failed = service.get_operation(op.operation_id)
        assert failed is not None and failed.state == OperationState.FAILED

        # Now fix docker so reconciliation sees the server online
        docker.status.side_effect = None
        docker.status.return_value = {"state": "running", "online": True}
        reconciled = service.request_reconciliation(op.operation_id)
        assert reconciled is not None
        assert reconciled.state == OperationState.CONFIRMED

    def test_reconciliation_marks_divergent_when_config_differs(self, tmp_path: Path):
        """request_reconciliation marks FAILED → DIVERGENT when server online but config differs."""
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.side_effect = RuntimeError("conflict")
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "10"}
        service = make_service(tmp_path, docker=docker, configuration=configuration, health_timeout=1)
        op = service.apply_restart_required({"MAX_PLAYERS": "20"}, lambda: None)
        time.sleep(2)
        failed = service.get_operation(op.operation_id)
        assert failed is not None and failed.state == OperationState.FAILED

        docker.status.side_effect = None
        docker.status.return_value = {"state": "running", "online": True}
        reconciled = service.request_reconciliation(op.operation_id)
        assert reconciled is not None
        assert reconciled.state == OperationState.DIVERGENT

    def test_reconciliation_skips_running_operations(self, tmp_path: Path):
        """request_reconciliation does not alter non-terminal operations."""
        service = make_service(tmp_path)
        op = ServerOperation.create("test-server", {})
        op.start()
        service._repo.save(op)
        result = service.request_reconciliation(op.operation_id)
        assert result is not None
        assert result.state == OperationState.RUNNING

    def test_reconciliation_returns_none_for_unknown(self, tmp_path: Path):
        service = make_service(tmp_path)
        assert service.request_reconciliation("nonexistent-id") is None

    def test_retry_creates_linked_operation(self, tmp_path: Path):
        """retry_operation returns a new operation linked to the original via parent_operation_id."""
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.side_effect = RuntimeError("conflict")
        service = make_service(tmp_path, docker=docker, health_timeout=1)
        op = service.apply_restart_required({"MAX_PLAYERS": "20"}, lambda: None)
        time.sleep(2)
        original = service.get_operation(op.operation_id)
        assert original is not None and original.state == OperationState.FAILED

        docker.execute.side_effect = None
        docker.status.return_value = {"state": "running", "online": True}
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "20"}
        service._configuration = configuration

        retry = service.retry_operation(op.operation_id, lambda: None)
        assert retry.parent_operation_id == op.operation_id
        assert retry.requested_changes == {"MAX_PLAYERS": "20"}
        # Original must be untouched
        still_original = service.get_operation(op.operation_id)
        assert still_original is not None
        assert still_original.state == OperationState.FAILED

    def test_retry_raises_for_unknown_operation(self, tmp_path: Path):
        service = make_service(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            service.retry_operation("nonexistent", lambda: None)

    def test_retry_raises_for_confirmed_operation(self, tmp_path: Path):
        """retry_operation rejects CONFIRMED operations — only FAILED/DIVERGENT are retryable."""
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "20"}
        service = make_service(tmp_path, docker=docker, configuration=configuration, thread_factory=InlineThread)
        op = service.apply_restart_required({"MAX_PLAYERS": "20"}, lambda: None)
        assert op.state == OperationState.CONFIRMED
        with pytest.raises(ValueError, match="confirmed"):
            service.retry_operation(op.operation_id, lambda: None)

    def test_retry_raises_conflict_when_another_operation_active(self, tmp_path: Path):
        """retry_operation raises ConflictingOperationError when another operation is running."""
        docker = MagicMock()
        docker.status.return_value = {"state": "running", "online": True}
        docker.execute.side_effect = RuntimeError("conflict")
        service = make_service(tmp_path, docker=docker, health_timeout=1)
        op = service.apply_restart_required({"MAX_PLAYERS": "20"}, lambda: None)
        time.sleep(2)
        original = service.get_operation(op.operation_id)
        assert original is not None and original.state == OperationState.FAILED

        # Create another active operation directly
        active = ServerOperation.create("test-server", {})
        active.start()
        service._repo.save(active)

        with pytest.raises(ConflictingOperationError):
            service.retry_operation(op.operation_id, lambda: None)

    def test_parent_operation_id_survives_roundtrip(self, tmp_path: Path):
        """parent_operation_id is persisted and restored correctly."""
        repo = make_repo(tmp_path)
        origin = ServerOperation.create("srv", {})
        repo.save(origin)
        child = ServerOperation.create("srv", {}, parent_operation_id=origin.operation_id)
        repo.save(child)
        loaded = repo.get(child.operation_id)
        assert loaded is not None
        assert loaded.parent_operation_id == origin.operation_id

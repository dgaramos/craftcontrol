"""Tests for SQLiteOperationRepository.

Covers:
- create_operation stores a PENDING record and rejects duplicate IDs
- advance_stage opens stages, promotes PENDING → IN_PROGRESS, is idempotent
- complete_stage closes open stages and rejects unknown/already-closed stages
- transition_state moves the record to any non-terminal state and to all four
  terminal states; rejects transitions out of terminal states
- get_operation returns None for missing IDs
- list_operations returns records newest-first
- JSON columns (stage_log, intended_state, observed_state, divergence_detail,
  error_detail) round-trip correctly
- Terminal states record completed_at automatically
- Migration 5 creates the server_operations table
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

import pytest

from minecraft_manager.migrations import run_migrations
from minecraft_manager.operations.repository import (
    InvalidStateTransitionError,
    OperationNotFoundError,
    SQLiteOperationRepository,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "manager.db"
    with sqlite3.connect(path) as conn:
        run_migrations(conn)
    return path


@pytest.fixture
def repo(db_path: Path) -> SQLiteOperationRepository:
    return SQLiteOperationRepository(db_path)


def _new_id() -> str:
    return str(uuid.uuid4())


_ALL_STAGES = [
    "REVIEW", "BACKUP_VERIFICATION", "PREPARATION",
    "RESTART", "HEALTH_WAIT", "VERIFICATION", "CONFIRMATION",
]


def _run_all_stages(repo: SQLiteOperationRepository, oid: str) -> None:
    """Advance and complete every stage in lifecycle order."""
    t = time.time()
    for i, stage in enumerate(_ALL_STAGES):
        repo.advance_stage(oid, stage, started_at=t + i * 0.001)
        repo.complete_stage(oid, stage, outcome="ok", completed_at=t + i * 0.001 + 0.0005)


def _run_stages_through(repo: SQLiteOperationRepository, oid: str, last: str) -> None:
    """Advance and complete stages up to and including *last*."""
    t = time.time()
    for i, stage in enumerate(_ALL_STAGES):
        repo.advance_stage(oid, stage, started_at=t + i * 0.001)
        repo.complete_stage(oid, stage, outcome="ok", completed_at=t + i * 0.001 + 0.0005)
        if stage == last:
            break


# ---------------------------------------------------------------------------
# create_operation
# ---------------------------------------------------------------------------

class TestCreateOperation:
    def test_returns_pending_record(self, repo: SQLiteOperationRepository) -> None:
        op = repo.create_operation(
            operation_id=_new_id(),
            operation_type="server_settings_update",
            initiated_by="alice",
            intended_state={"difficulty": "hard"},
        )
        assert op["state"] == "PENDING"
        assert op["operation_type"] == "server_settings_update"
        assert op["initiated_by"] == "alice"
        assert op["intended_state"] == {"difficulty": "hard"}
        assert op["stage_log"] == []
        assert op["current_stage"] is None
        assert op["completed_at"] is None

    def test_rejects_duplicate_id(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        with pytest.raises(ValueError, match="already exists"):
            repo.create_operation(oid, "server_settings_update", "bob", {})

    def test_rejects_invalid_operation_type(self, repo: SQLiteOperationRepository) -> None:
        with pytest.raises(ValueError, match="unknown operation_type"):
            repo.create_operation(_new_id(), "not_a_real_type", "alice", {})


# ---------------------------------------------------------------------------
# get_operation / list_operations
# ---------------------------------------------------------------------------

class TestQueries:
    def test_get_returns_none_for_unknown_id(self, repo: SQLiteOperationRepository) -> None:
        assert repo.get_operation(_new_id()) is None

    def test_list_operations_empty(self, repo: SQLiteOperationRepository) -> None:
        assert repo.list_operations() == []

    def test_list_operations_newest_first(self, repo: SQLiteOperationRepository) -> None:
        ids = []
        for _ in range(3):
            oid = _new_id()
            ids.append(oid)
            repo.create_operation(oid, "server_settings_update", "alice", {})
            time.sleep(0.01)
        result = repo.list_operations()
        assert [r["operation_id"] for r in result] == list(reversed(ids))

    def test_list_operations_respects_limit(self, repo: SQLiteOperationRepository) -> None:
        for _ in range(5):
            repo.create_operation(_new_id(), "server_settings_update", "alice", {})
        assert len(repo.list_operations(limit=3)) == 3

    def test_list_operations_rejects_negative_limit(self, repo: SQLiteOperationRepository) -> None:
        with pytest.raises(ValueError, match="limit must be between"):
            repo.list_operations(limit=-1)

    def test_list_operations_rejects_zero_limit(self, repo: SQLiteOperationRepository) -> None:
        with pytest.raises(ValueError, match="limit must be between"):
            repo.list_operations(limit=0)

    def test_list_operations_rejects_overlarge_limit(self, repo: SQLiteOperationRepository) -> None:
        with pytest.raises(ValueError, match="limit must be between"):
            repo.list_operations(limit=201)


# ---------------------------------------------------------------------------
# advance_stage
# ---------------------------------------------------------------------------

class TestAdvanceStage:
    def test_first_stage_transitions_pending_to_in_progress(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        op = repo.get_operation(oid)
        assert op["state"] == "IN_PROGRESS"
        assert op["current_stage"] == "REVIEW"
        assert len(op["stage_log"]) == 1
        assert op["stage_log"][0]["stage"] == "REVIEW"
        assert op["stage_log"][0]["outcome"] is None

    def test_subsequent_stages_stay_in_progress(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        repo.advance_stage(oid, "BACKUP_VERIFICATION", started_at=time.time())
        op = repo.get_operation(oid)
        assert op["state"] == "IN_PROGRESS"
        assert op["current_stage"] == "BACKUP_VERIFICATION"
        assert len(op["stage_log"]) == 2

    def test_idempotent_for_same_stage(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        t = time.time()
        repo.advance_stage(oid, "REVIEW", started_at=t)
        repo.advance_stage(oid, "REVIEW", started_at=t + 1)  # should be silently ignored
        op = repo.get_operation(oid)
        assert len(op["stage_log"]) == 1

    def test_raises_for_terminal_operation(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.transition_state(oid, "CANCELLED", updated_at=time.time())
        with pytest.raises(InvalidStateTransitionError):
            repo.advance_stage(oid, "REVIEW", started_at=time.time())

    def test_raises_for_unknown_stage(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        with pytest.raises(ValueError, match="unknown stage"):
            repo.advance_stage(oid, "BOGUS_STAGE", started_at=time.time())


# ---------------------------------------------------------------------------
# complete_stage
# ---------------------------------------------------------------------------

class TestCompleteStage:
    def test_closes_open_stage(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        t = time.time()
        repo.advance_stage(oid, "REVIEW", started_at=t)
        repo.complete_stage(oid, "REVIEW", outcome="ok", completed_at=t + 1, detail="passed")
        op = repo.get_operation(oid)
        entry = op["stage_log"][0]
        assert entry["outcome"] == "ok"
        assert entry["detail"] == "passed"
        assert entry["completed_at"] == pytest.approx(t + 1)

    def test_raises_for_missing_open_stage(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        with pytest.raises(InvalidStateTransitionError):
            repo.complete_stage(oid, "BACKUP_VERIFICATION", outcome="ok", completed_at=time.time())

    def test_raises_for_terminal_operation(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        repo.transition_state(oid, "FAILED", updated_at=time.time(), error_detail={"code": "x", "message": "y", "stage": "REVIEW"})
        with pytest.raises(InvalidStateTransitionError):
            repo.complete_stage(oid, "REVIEW", outcome="error", completed_at=time.time())

    def test_raises_for_invalid_outcome(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        with pytest.raises(ValueError, match="unknown outcome"):
            repo.complete_stage(oid, "REVIEW", outcome="bad", completed_at=time.time())

    def test_idempotent_for_repeated_completion_with_same_values(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        t = time.time()
        repo.advance_stage(oid, "REVIEW", started_at=t)
        repo.complete_stage(oid, "REVIEW", outcome="ok", completed_at=t + 1, detail="passed")
        # Replaying with identical values must not raise.
        repo.complete_stage(oid, "REVIEW", outcome="ok", completed_at=t + 2, detail="passed")
        op = repo.get_operation(oid)
        assert op["stage_log"][0]["outcome"] == "ok"

    def test_raises_for_repeated_completion_with_different_outcome(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        t = time.time()
        repo.advance_stage(oid, "REVIEW", started_at=t)
        repo.complete_stage(oid, "REVIEW", outcome="ok", completed_at=t + 1)
        with pytest.raises(InvalidStateTransitionError):
            repo.complete_stage(oid, "REVIEW", outcome="error", completed_at=t + 2)


# ---------------------------------------------------------------------------
# transition_state
# ---------------------------------------------------------------------------

class TestTransitionState:
    def test_applied_sets_completed_at(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        _run_all_stages(repo, oid)
        t = time.time()
        repo.transition_state(oid, "APPLIED", updated_at=t)
        op = repo.get_operation(oid)
        assert op["state"] == "APPLIED"
        assert op["completed_at"] is not None
        assert op["current_stage"] is None

    def test_divergent_sets_completed_at(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        _run_stages_through(repo, oid, "VERIFICATION")
        t = time.time()
        repo.transition_state(oid, "DIVERGENT", updated_at=t)
        op = repo.get_operation(oid)
        assert op["state"] == "DIVERGENT"
        assert op["completed_at"] is not None
        assert op["current_stage"] is None

    def test_failed_sets_completed_at(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        t = time.time()
        repo.transition_state(oid, "FAILED", updated_at=t)
        op = repo.get_operation(oid)
        assert op["state"] == "FAILED"
        assert op["completed_at"] is not None
        assert op["current_stage"] is None

    def test_cancelled_from_pending_sets_completed_at(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        t = time.time()
        repo.transition_state(oid, "CANCELLED", updated_at=t)
        op = repo.get_operation(oid)
        assert op["state"] == "CANCELLED"
        assert op["completed_at"] is not None
        assert op["current_stage"] is None

    def test_terminal_rejects_further_transitions(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        _run_all_stages(repo, oid)
        repo.transition_state(oid, "APPLIED", updated_at=time.time())
        with pytest.raises(InvalidStateTransitionError):
            repo.transition_state(oid, "FAILED", updated_at=time.time())

    def test_raises_for_unknown_state(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        with pytest.raises(ValueError, match="unknown state"):
            repo.transition_state(oid, "NOPE", updated_at=time.time())

    def test_raises_for_unknown_current_stage(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        with pytest.raises(ValueError, match="unknown stage"):
            repo.transition_state(oid, "IN_PROGRESS", updated_at=time.time(), current_stage="BOGUS_STAGE")

    def test_raises_for_unknown_operation(self, repo: SQLiteOperationRepository) -> None:
        with pytest.raises(OperationNotFoundError):
            repo.transition_state(_new_id(), "APPLIED", updated_at=time.time())

    def test_divergent_stores_detail(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        _run_stages_through(repo, oid, "VERIFICATION")
        detail = [{"field": "difficulty", "intended": "hard", "observed": "normal"}]
        repo.transition_state(
            oid,
            "DIVERGENT",
            updated_at=time.time(),
            divergence_detail=detail,
            observed_state={"difficulty": "normal"},
        )
        op = repo.get_operation(oid)
        assert op["divergence_detail"] == detail
        assert op["observed_state"] == {"difficulty": "normal"}

    def test_failed_stores_error_detail(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        error = {"code": "executor_timeout", "message": "timed out", "stage": "RESTART"}
        repo.transition_state(oid, "FAILED", updated_at=time.time(), error_detail=error)
        op = repo.get_operation(oid)
        assert op["error_detail"] == error

    def test_executor_ref_is_stored(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        _run_all_stages(repo, oid)
        repo.transition_state(oid, "APPLIED", updated_at=time.time(), executor_ref="compose:restart:abc123")
        op = repo.get_operation(oid)
        assert op["executor_ref"] == "compose:restart:abc123"

    def test_raises_for_invalid_transition_pending_to_applied(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        with pytest.raises(InvalidStateTransitionError, match="not permitted"):
            repo.transition_state(oid, "APPLIED", updated_at=time.time())

    def test_raises_for_invalid_transition_pending_to_divergent(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        with pytest.raises(InvalidStateTransitionError, match="not permitted"):
            repo.transition_state(oid, "DIVERGENT", updated_at=time.time())

    def test_raises_for_cancelled_after_restart_begins(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        for stage in ["REVIEW", "BACKUP_VERIFICATION", "PREPARATION", "RESTART"]:
            repo.advance_stage(oid, stage, started_at=time.time())
        with pytest.raises(InvalidStateTransitionError, match="cannot be cancelled"):
            repo.transition_state(oid, "CANCELLED", updated_at=time.time())

    def test_raises_for_applied_without_confirmation(self, repo: SQLiteOperationRepository) -> None:
        # APPLIED requires CONFIRMATION to be completed; only running through VERIFICATION is not enough.
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        _run_stages_through(repo, oid, "VERIFICATION")
        with pytest.raises(InvalidStateTransitionError, match=r"requires.*CONFIRMATION"):
            repo.transition_state(oid, "APPLIED", updated_at=time.time())

    def test_raises_for_divergent_without_verification(self, repo: SQLiteOperationRepository) -> None:
        # DIVERGENT requires VERIFICATION to be completed; stopping after HEALTH_WAIT is not enough.
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        _run_stages_through(repo, oid, "HEALTH_WAIT")
        with pytest.raises(InvalidStateTransitionError, match=r"requires.*VERIFICATION"):
            repo.transition_state(oid, "DIVERGENT", updated_at=time.time())

    def test_raises_for_applied_after_review_only(self, repo: SQLiteOperationRepository) -> None:
        # Regression guard: confirm REVIEW alone is never sufficient for APPLIED.
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        with pytest.raises(InvalidStateTransitionError, match=r"requires.*CONFIRMATION"):
            repo.transition_state(oid, "APPLIED", updated_at=time.time())

    def test_in_progress_rejects_when_no_stage_started(self, repo: SQLiteOperationRepository) -> None:
        # Transition to IN_PROGRESS is invalid when stage_log is empty (no stage ever started).
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        with pytest.raises(InvalidStateTransitionError, match="at least one started stage"):
            repo.transition_state(oid, "IN_PROGRESS", updated_at=time.time(), current_stage="REVIEW")

    def test_in_progress_rejects_when_current_stage_differs_from_last_started(
        self, db_path: Path, repo: SQLiteOperationRepository
    ) -> None:
        # Inject a PENDING operation with two stage_log entries so the last started
        # stage is BACKUP_VERIFICATION. Passing REVIEW as current_stage must be rejected.
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        t = time.time()
        stage_log = json.dumps([
            {"stage": "REVIEW", "started_at": t, "completed_at": None, "outcome": None, "detail": None},
            {"stage": "BACKUP_VERIFICATION", "started_at": t + 0.001, "completed_at": None, "outcome": None, "detail": None},
        ])
        # Keep state as PENDING so the PENDING → IN_PROGRESS transition is valid.
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE server_operations SET stage_log=? WHERE operation_id=?",
                (stage_log, oid),
            )
        with pytest.raises(InvalidStateTransitionError, match="last started stage"):
            repo.transition_state(oid, "IN_PROGRESS", updated_at=time.time(), current_stage="REVIEW")


class TestAdvanceStageOrdering:
    def test_raises_when_first_stage_is_not_review(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        with pytest.raises(InvalidStateTransitionError, match="expected next stage"):
            repo.advance_stage(oid, "RESTART", started_at=time.time())

    def test_raises_when_stage_skips_ahead(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        repo.advance_stage(oid, "REVIEW", started_at=time.time())
        with pytest.raises(InvalidStateTransitionError, match="expected next stage"):
            repo.advance_stage(oid, "PREPARATION", started_at=time.time())

    def test_sequential_stages_are_accepted(self, repo: SQLiteOperationRepository) -> None:
        oid = _new_id()
        repo.create_operation(oid, "server_settings_update", "alice", {})
        for stage in ["REVIEW", "BACKUP_VERIFICATION", "PREPARATION", "RESTART"]:
            repo.advance_stage(oid, stage, started_at=time.time())
        op = repo.get_operation(oid)
        assert op["current_stage"] == "RESTART"


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class TestMigration:
    def test_migration_creates_server_operations_table(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "server_operations" in tables

    def test_migration_schema_version_is_five(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 5

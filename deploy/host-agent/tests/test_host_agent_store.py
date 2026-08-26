"""Tests for OperationRecord and OperationStore."""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
import sys
import tempfile

_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(_AGENT_DIR) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(_AGENT_DIR))

import store as st


def _op_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Operation store eviction
# ---------------------------------------------------------------------------

class TestOperationStoreEviction:
    def test_create_and_get(self) -> None:
        s = st.OperationStore()
        op_id = _op_id()
        rec = s.create(op_id)
        assert rec is not None
        assert s.get(op_id) is rec

    def test_create_duplicate_returns_none(self) -> None:
        s = st.OperationStore()
        op_id = _op_id()
        s.create(op_id)
        assert s.create(op_id) is None

    def test_evict_expired_removes_old_completed(self) -> None:
        completed_at = 1000.0
        now = completed_at + st.RESULT_RETENTION_SECONDS + 1
        s = st.OperationStore(time_func=lambda: now)
        op_id = _op_id()
        s.create(op_id)
        s.update(op_id, status="done", completed_at=completed_at)
        s.evict_expired()
        assert s.get(op_id) is None

    def test_evict_does_not_remove_recent_completed(self) -> None:
        completed_at = 1000.0
        now = completed_at + 1
        s = st.OperationStore(time_func=lambda: now)
        op_id = _op_id()
        s.create(op_id)
        s.update(op_id, status="done", completed_at=completed_at)
        s.evict_expired()
        assert s.get(op_id) is not None

    def test_evict_does_not_remove_running(self) -> None:
        s = st.OperationStore(time_func=lambda: 999999.0)
        op_id = _op_id()
        s.create(op_id)
        s.evict_expired()
        assert s.get(op_id) is not None


# ---------------------------------------------------------------------------
# SQLite persistence
# ---------------------------------------------------------------------------

class TestSQLitePersistence:
    def _db_store(self, tmp_path: Path, **kwargs) -> st.OperationStore:
        db = str(tmp_path / "test.db")
        return st.OperationStore(db_path=db, **kwargs)

    def test_record_survives_store_reload(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        op_id = _op_id()

        s1 = st.OperationStore(db_path=db)
        s1.create(op_id)
        s1.update(op_id, status="done", outcome="ok", completed_at=time.monotonic())

        s2 = st.OperationStore(db_path=db)
        rec = s2.get(op_id)
        assert rec is not None
        assert rec.status == "done"
        assert rec.outcome == "ok"

    def test_crash_recovery_marks_running_as_failed(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        op_id = _op_id()

        # Simulate a crash: create a running record and never mark it done.
        s1 = st.OperationStore(db_path=db)
        s1.create(op_id)
        # Record remains "running" in DB.
        # Close by letting s1 go out of scope; reload in a new store.

        s2 = st.OperationStore(db_path=db)
        rec = s2.get(op_id)
        assert rec is not None
        assert rec.status == "done"
        assert rec.outcome == "error"
        assert rec.error_code == "CRASH_RECOVERY"
        assert rec.completed_at is not None

    def test_crash_recovery_does_not_alter_completed_records(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        op_id = _op_id()

        s1 = st.OperationStore(db_path=db)
        s1.create(op_id)
        s1.update(op_id, status="done", outcome="ok", completed_at=1.0)

        s2 = st.OperationStore(db_path=db)
        rec = s2.get(op_id)
        assert rec is not None
        assert rec.outcome == "ok"

    def test_ttl_eviction_removes_from_sqlite(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        completed_at = 1000.0
        now = completed_at + st.RESULT_RETENTION_SECONDS + 1
        op_id = _op_id()

        s1 = st.OperationStore(db_path=db)
        s1.create(op_id)
        s1.update(op_id, status="done", completed_at=completed_at)
        s1.evict_expired()  # in-memory only at this point

        # Reload: if SQLite row was deleted, crash-recovery won't see it.
        s2 = st.OperationStore(db_path=db, time_func=lambda: now)
        s2.evict_expired()
        assert s2.get(op_id) is None

    def test_evict_expired_removes_from_sqlite(self, tmp_path: Path) -> None:
        """Evicted records are gone from SQLite so they are absent on reload."""
        db = str(tmp_path / "test.db")
        completed_at = 500.0
        now = completed_at + st.RESULT_RETENTION_SECONDS + 1
        op_id = _op_id()

        s1 = st.OperationStore(db_path=db, time_func=lambda: now)
        s1.create(op_id)
        s1.update(op_id, status="done", completed_at=completed_at)
        s1.evict_expired()

        import sqlite3
        conn = sqlite3.connect(db)
        cur = conn.execute(
            "SELECT COUNT(*) FROM operations WHERE operation_id = ?", (op_id,)
        )
        count = cur.fetchone()[0]
        conn.close()
        assert count == 0

    def test_health_reached_bool_roundtrip(self, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        op_id = _op_id()

        s1 = st.OperationStore(db_path=db)
        s1.create(op_id)
        s1.update(op_id, status="done", outcome="ok", health_reached=True, completed_at=1.0)

        s2 = st.OperationStore(db_path=db)
        rec = s2.get(op_id)
        assert rec is not None
        assert rec.health_reached is True

    def test_host_agent_db_env_var(self, tmp_path: Path, monkeypatch) -> None:
        """HOST_AGENT_DB is wired through _load_config."""
        # Import agent from the agent directory
        import importlib
        import sys

        db_path = str(tmp_path / "env-test.db")
        monkeypatch.setenv("HOST_AGENT_DB", db_path)

        # Reload agent module to pick up env change
        agent_dir = str(_AGENT_DIR)
        if agent_dir not in sys.path:
            sys.path.insert(0, agent_dir)

        import importlib
        import agent as ag
        importlib.reload(ag)

        config = ag._load_config()
        assert config["db"] == db_path

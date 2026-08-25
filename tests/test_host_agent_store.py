"""Tests for OperationRecord and OperationStore."""
from __future__ import annotations

import time
import uuid

import sys
import os

_AGENT_DIR = os.path.join(os.path.dirname(__file__), "..", "deploy", "host-agent")
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_AGENT_DIR))

import store as st  # noqa: E402


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

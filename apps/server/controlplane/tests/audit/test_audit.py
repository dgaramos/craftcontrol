"""Tests for the audit module — model, repository, and service.

TDD: Red tests written before implementation.
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from src.audit.model import AuditRecord
from src.audit.repository import SQLiteAuditRepository
from src.audit.service import AuditService
from conftest import make_operation_db
from factories import audit_record


def _db(tmp_path: Path) -> Path:
    """Create a migrated test database and return its path."""
    return make_operation_db(tmp_path, "test.db")


# ---------------------------------------------------------------------------
# AuditRecord model
# ---------------------------------------------------------------------------

class TestAuditRecord:
    def test_fields_are_accessible(self) -> None:
        record = audit_record(id=1, occurred_at=1_000_000.0, metadata={"ip": "127.0.0.1"})
        assert record.id == 1
        assert record.occurred_at == 1_000_000.0
        assert record.actor == "alice"
        assert record.action == "auth.login"
        assert record.target == "alice"
        assert record.result == "success"
        assert record.metadata == {"ip": "127.0.0.1"}

    def test_actor_and_target_may_be_none(self) -> None:
        record = audit_record(id=2, occurred_at=1_000_001.0, actor=None, target=None, result="denied")
        assert record.actor is None
        assert record.target is None


# ---------------------------------------------------------------------------
# SQLiteAuditRepository — write
# ---------------------------------------------------------------------------

class TestSQLiteAuditRepositoryWrite:
    def test_write_persists_all_fields(self, tmp_path: Path) -> None:
        repo = SQLiteAuditRepository(_db(tmp_path), time_fn=lambda: 1_000_000.0)
        repo.write(
            actor="alice",
            action="auth.login",
            target="alice",
            result="success",
            metadata={"ip": "127.0.0.1"},
        )
        conn = sqlite3.connect(tmp_path / "test.db")
        row = conn.execute(
            "SELECT occurred_at, actor_identity, action, target, result, details FROM audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 1_000_000.0
        assert row[1] == "alice"
        assert row[2] == "auth.login"
        assert row[3] == "alice"
        assert row[4] == "success"
        import json
        assert json.loads(row[5]) == {"ip": "127.0.0.1"}

    def test_write_allows_null_actor_and_target(self, tmp_path: Path) -> None:
        repo = SQLiteAuditRepository(_db(tmp_path), time_fn=lambda: 2_000_000.0)
        repo.write(actor=None, action="auth.login", target=None, result="denied", metadata={})
        conn = sqlite3.connect(tmp_path / "test.db")
        row = conn.execute(
            "SELECT actor_identity, target FROM audit_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert row[0] is None
        assert row[1] is None

    def test_metadata_must_not_contain_secrets(self, tmp_path: Path) -> None:
        """write() strips known secret keys from metadata before persistence."""
        repo = SQLiteAuditRepository(_db(tmp_path), time_fn=lambda: 3_000_000.0)
        repo.write(
            actor="alice",
            action="auth.password_changed",
            target="alice",
            result="success",
            metadata={"password": "s3cr3t", "token": "abc", "password_hash": "xyz", "ip": "127.0.0.1"},
        )
        conn = sqlite3.connect(tmp_path / "test.db")
        row = conn.execute("SELECT details FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        import json
        stored = json.loads(row[0])
        assert "password" not in stored
        assert "token" not in stored
        assert "password_hash" not in stored
        assert stored.get("ip") == "127.0.0.1"


# ---------------------------------------------------------------------------
# SQLiteAuditRepository — query
# ---------------------------------------------------------------------------

class TestSQLiteAuditRepositoryQuery:
    def _seed(self, path: Path, count: int) -> None:
        conn = sqlite3.connect(path)
        for i in range(count):
            conn.execute(
                "INSERT INTO audit_log(occurred_at, actor_identity, action, target, result, details) VALUES(?,?,?,?,?,?)",
                (float(i + 1), "alice" if i % 2 == 0 else "bob", "auth.login", "alice", "success", "{}"),
            )
        conn.commit()
        conn.close()

    def test_empty_database_returns_empty_page(self, tmp_path: Path) -> None:
        repo = SQLiteAuditRepository(_db(tmp_path))
        result = repo.query(page=1, page_size=20)
        assert result["records"] == []
        assert result["total"] == 0
        assert result["page"] == 1
        assert result["page_size"] == 20
        assert result["pages"] == 0

    def test_query_returns_newest_first(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        self._seed(db, 3)
        repo = SQLiteAuditRepository(db)
        result = repo.query(page=1, page_size=10)
        records = result["records"]
        assert len(records) == 3
        # newest first
        assert records[0].occurred_at > records[1].occurred_at > records[2].occurred_at

    def test_pagination_is_deterministic(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        self._seed(db, 5)
        repo = SQLiteAuditRepository(db)
        page1 = repo.query(page=1, page_size=3)
        page2 = repo.query(page=2, page_size=3)
        assert len(page1["records"]) == 3
        assert len(page2["records"]) == 2
        assert page1["total"] == 5
        assert page1["pages"] == 2
        # no overlap
        ids1 = {r.id for r in page1["records"]}
        ids2 = {r.id for r in page2["records"]}
        assert not ids1 & ids2

    def test_filter_by_actor(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        self._seed(db, 6)  # alice: 0,2,4 → 3 rows; bob: 1,3,5 → 3 rows
        repo = SQLiteAuditRepository(db)
        result = repo.query(page=1, page_size=10, actor="alice")
        actors = {r.actor for r in result["records"]}
        assert actors == {"alice"}
        assert result["total"] == 3

    def test_filter_by_action(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO audit_log(occurred_at,actor_identity,action,target,result,details) VALUES(?,?,?,?,?,?)",
            (1.0, "alice", "auth.login", "alice", "success", "{}"),
        )
        conn.execute(
            "INSERT INTO audit_log(occurred_at,actor_identity,action,target,result,details) VALUES(?,?,?,?,?,?)",
            (2.0, "alice", "auth.password_changed", "alice", "success", "{}"),
        )
        conn.commit()
        conn.close()
        repo = SQLiteAuditRepository(db)
        result = repo.query(page=1, page_size=10, action="auth.login")
        assert result["total"] == 1
        assert result["records"][0].action == "auth.login"

    def test_records_are_audit_record_instances(self, tmp_path: Path) -> None:
        db = _db(tmp_path)
        self._seed(db, 2)
        repo = SQLiteAuditRepository(db)
        result = repo.query(page=1, page_size=10)
        assert all(isinstance(r, AuditRecord) for r in result["records"])


# ---------------------------------------------------------------------------
# AuditService
# ---------------------------------------------------------------------------

class FakeAuditPort:
    def __init__(self) -> None:
        self.written: list[dict] = []
        self._records: list[AuditRecord] = []

    def write(self, *, actor: str | None, action: str, target: str | None, result: str, metadata: dict) -> None:
        self.written.append({"actor": actor, "action": action, "target": target, "result": result, "metadata": metadata})

    def query(self, *, page: int, page_size: int, actor: str | None = None, action: str | None = None) -> dict:
        return {"records": self._records, "total": len(self._records), "page": page, "page_size": page_size, "pages": 1}


class TestAuditService:
    def test_write_delegates_to_port(self) -> None:
        port = FakeAuditPort()
        service = AuditService(port)
        service.write(actor="alice", action="auth.login", target="alice", result="success", metadata={"ip": "127.0.0.1"})
        assert len(port.written) == 1
        assert port.written[0]["action"] == "auth.login"

    def test_query_delegates_to_port(self) -> None:
        port = FakeAuditPort()
        port._records = [
            audit_record()
        ]
        service = AuditService(port)
        result = service.query(page=1, page_size=20)
        assert result["total"] == 1
        assert result["records"][0].action == "auth.login"

    def test_write_accepts_none_actor_and_target(self) -> None:
        port = FakeAuditPort()
        service = AuditService(port)
        service.write(actor=None, action="auth.login", target=None, result="denied", metadata={})
        assert port.written[0]["actor"] is None
        assert port.written[0]["target"] is None

    def test_write_without_metadata_defaults_to_empty_dict(self) -> None:
        port = FakeAuditPort()
        service = AuditService(port)
        service.write(actor="alice", action="auth.login", target="alice", result="success")
        assert port.written[0]["metadata"] == {}

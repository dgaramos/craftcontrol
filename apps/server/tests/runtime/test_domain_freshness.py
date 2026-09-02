"""Tests for SQLiteTelemetryRepository.domain_freshness and ManagerService.diagnostics domains."""
from __future__ import annotations

from pathlib import Path

import pytest

from minecraft_manager.core.repository import StateRepository
from minecraft_manager.telemetry.repository import SQLiteTelemetryRepository

DOMAINS = {"settings", "gamerules", "players", "server", "telemetry"}
STALE_THRESHOLD = 1200


def _fresh_repo(tmp_path: Path) -> SQLiteTelemetryRepository:
    path = tmp_path / "state.db"
    repo = StateRepository(path)
    repo.initialize()
    return SQLiteTelemetryRepository(path)


# ---------------------------------------------------------------------------
# 1. Never observed — observed_at==0 for every domain
# ---------------------------------------------------------------------------


def test_domain_freshness_never_observed(tmp_path: Path) -> None:
    repo = _fresh_repo(tmp_path)

    freshness = repo.domain_freshness()

    for name in DOMAINS:
        entry = freshness[name]
        assert entry["observed_at"] is None, f"{name}.observed_at should be None when never observed"
        assert entry["age_seconds"] is None, f"{name}.age_seconds should be None when never observed"
        assert entry["stale"] is True, f"{name}.stale should be True when never observed"


# ---------------------------------------------------------------------------
# 2. Fresh domain — observed 60 seconds ago
# ---------------------------------------------------------------------------


def test_domain_freshness_fresh(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    repo_state = StateRepository(path)
    repo_state.initialize()

    observed = 1_000_000.0
    now = observed + 60.0

    repo_state.store("settings", {"level-name": "Bedrock level"}, "test")
    # Patch observed_at directly in state table so we control the time precisely
    import sqlite3
    with sqlite3.connect(str(path)) as con:
        con.execute("UPDATE state SET updated_at=? WHERE kind='settings'", (observed,))

    repo = SQLiteTelemetryRepository(path)
    freshness = repo.domain_freshness(time_fn=lambda: now)

    entry = freshness["settings"]
    assert entry["observed_at"] == pytest.approx(observed)
    assert entry["age_seconds"] == pytest.approx(60.0, abs=1.0)
    assert entry["stale"] is False


# ---------------------------------------------------------------------------
# 3. Stale domain — observed 1201 seconds ago
# ---------------------------------------------------------------------------


def test_domain_freshness_stale(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    repo_state = StateRepository(path)
    repo_state.initialize()

    observed = 1_000_000.0
    now = observed + STALE_THRESHOLD + 1  # 1201 seconds later

    repo_state.store("gamerules", {"keepInventory": "false"}, "test")
    import sqlite3
    with sqlite3.connect(str(path)) as con:
        con.execute("UPDATE state SET updated_at=? WHERE kind='gamerules'", (observed,))

    repo = SQLiteTelemetryRepository(path)
    freshness = repo.domain_freshness(time_fn=lambda: now)

    entry = freshness["gamerules"]
    assert entry["stale"] is True
    assert entry["age_seconds"] == pytest.approx(STALE_THRESHOLD + 1, abs=1.0)


# ---------------------------------------------------------------------------
# 4. time_fn is injectable — output is deterministic
# ---------------------------------------------------------------------------


def test_domain_freshness_time_injectable(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    repo_state = StateRepository(path)
    repo_state.initialize()

    observed = 5_000_000.0
    fake_now = observed + 100.0

    repo_state.store("server", {"online": "2"}, "test")
    import sqlite3
    with sqlite3.connect(str(path)) as con:
        con.execute("UPDATE state SET updated_at=? WHERE kind='server'", (observed,))

    repo = SQLiteTelemetryRepository(path)
    result_a = repo.domain_freshness(time_fn=lambda: fake_now)
    result_b = repo.domain_freshness(time_fn=lambda: fake_now)

    assert result_a["server"]["age_seconds"] == result_b["server"]["age_seconds"]
    assert result_a["server"]["age_seconds"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# 5. ManagerService.diagnostics() exposes "domains"
# ---------------------------------------------------------------------------


def test_diagnostics_includes_domains(tmp_path: Path) -> None:
    from minecraft_manager.core.events import EventBroker
    from minecraft_manager.server.files import ServerFiles
    from minecraft_manager.core.repository import StateRepository
    from minecraft_manager.server import WorldService
    from minecraft_manager.runtime import ManagerService
    from minecraft_manager.telemetry.repository import SQLiteTelemetryRepository
    from minecraft_manager.telemetry.service import TelemetryService

    from fakes import FakeBedrock, FakeDocker

    db_path = tmp_path / "state.db"
    repo = StateRepository(db_path)
    repo.initialize()
    broker = EventBroker(repo)
    telemetry_repo = SQLiteTelemetryRepository(db_path)
    telemetry_service = TelemetryService(telemetry_repo, broker)
    files = ServerFiles(tmp_path / ".env", tmp_path / "server.properties")
    bedrock = FakeBedrock()
    docker = FakeDocker()

    class _FakeReconciliation:
        refreshing = False
        def diagnostics(self): return {"refreshing": False, "pending_gamerule_refreshes": 0, "gamerule_worker_running": False, "snapshot_running": False, "reconciliation": {}}
        def start(self): pass
        def refresh(self, reason=""): pass
        def refresh_async(self, reason=""): pass

    class _FakePlayerService:
        def state(self): return {}

    world_service = WorldService(bedrock, broker)  # type: ignore[arg-type]
    service = ManagerService(
        repo, files, bedrock, docker, broker=broker,  # type: ignore[arg-type]
        player_service=_FakePlayerService(),  # type: ignore[arg-type]
        telemetry_service=telemetry_service,
        world_service=world_service,
        reconciliation_service=_FakeReconciliation(),  # type: ignore[arg-type]
    )

    diagnostics = service.diagnostics()

    assert "domains" in diagnostics, "diagnostics() must include 'domains'"
    domains = diagnostics["domains"]
    for name in DOMAINS:
        assert name in domains, f"domains must contain '{name}'"
        entry = domains[name]
        assert "observed_at" in entry
        assert "age_seconds" in entry
        assert "stale" in entry

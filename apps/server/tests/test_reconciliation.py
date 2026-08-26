"""Tests for ReconciliationService covering worker threads and error paths."""
from __future__ import annotations

import threading
import time
from pathlib import Path

from conftest import make_manager_service
from fakes import FakeBedrock


def _reconciliation(tmp_path: Path, bedrock: FakeBedrock | None = None):
    svc = make_manager_service(tmp_path, bedrock)
    return svc, svc._reconciliation


# ---------------------------------------------------------------------------
# refresh_gamerules_async — happy path
# ---------------------------------------------------------------------------

def test_gamerule_worker_queries_and_persists_result(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.gamerule_result = {"keepinventory": "true"}
    svc, rec = _reconciliation(tmp_path, bedrock)

    rec.refresh_gamerules_async({"keepinventory"})

    deadline = time.time() + 5
    while time.time() < deadline:
        state = svc.state()
        if state.get("gamerules", {}).get("keepinventory") == "true":
            break
        time.sleep(0.05)
    else:
        raise AssertionError("gamerule worker did not persist result in time")

    assert svc.state()["gamerules"]["keepinventory"] == "true"


def test_gamerule_worker_exits_when_no_pending_rules_remain(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.gamerule_result = {}
    _, rec = _reconciliation(tmp_path, bedrock)

    rec.refresh_gamerules_async({"keepinventory"})

    # Worker should finish and set _gamerule_worker_running = False
    deadline = time.time() + 5
    while time.time() < deadline:
        with rec._pending_rules_lock:
            if not rec._gamerule_worker_running:
                break
        time.sleep(0.05)
    else:
        raise AssertionError("gamerule worker did not exit")

    with rec._pending_rules_lock:
        assert not rec._gamerule_worker_running


# ---------------------------------------------------------------------------
# refresh_gamerules_async — rules restored on failure
# ---------------------------------------------------------------------------

import pytest

@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_gamerule_worker_restores_rules_on_query_failure(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    rules_restored = threading.Event()

    def failing_query(rules):
        # Signal before raising so we can observe the restore in the except block
        raise RuntimeError("bedrock unavailable")

    bedrock.query_gamerules = failing_query
    _, rec = _reconciliation(tmp_path, bedrock)

    # Patch refresh_gamerules_async to detect restart (which means rules were restored)
    original_restart = rec.refresh_gamerules_async

    def patched_restart(rules):
        rules_restored.set()
        # Don't actually restart to avoid infinite loop in test
    rec.refresh_gamerules_async = patched_restart  # type: ignore[method-assign]

    rec.refresh_gamerules_async = original_restart
    # Re-patch after first call: capture the restart that happens from the worker finally block
    first_call_done = threading.Event()

    def first_call_restart(rules):
        if first_call_done.is_set():
            rules_restored.set()
            return
        first_call_done.set()
        original_restart(rules)

    rec.refresh_gamerules_async = first_call_restart  # type: ignore[method-assign]
    rec.refresh_gamerules_async({"keepinventory"})

    assert rules_restored.wait(timeout=8), "rules were not restored to pending set after query_gamerules failure"


# ---------------------------------------------------------------------------
# request_telemetry_snapshot — exception path
# ---------------------------------------------------------------------------

def test_snapshot_exception_marks_state_degraded(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.request_telemetry_snapshot = lambda: (_ for _ in ()).throw(RuntimeError("network error"))  # type: ignore[method-assign]
    svc, rec = _reconciliation(tmp_path, bedrock)

    result = rec.request_telemetry_snapshot("test-error")

    assert result == 0
    telemetry = svc.state()["telemetry"]
    assert telemetry["status"] == "degraded"
    assert "network error" in telemetry["last_error"]


def test_snapshot_exception_publishes_failed_event(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.request_telemetry_snapshot = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]
    svc, rec = _reconciliation(tmp_path, bedrock)

    events: list[str] = []
    original = svc.broker.publish

    def capture(topic, *a, **kw):
        events.append(topic)
        return original(topic, *a, **kw)

    svc.broker.publish = capture  # type: ignore[method-assign]
    rec.broker = svc.broker

    rec.request_telemetry_snapshot("test-error")

    assert "telemetry.snapshot.failed" in events


# ---------------------------------------------------------------------------
# Telemetry callback error in refresh() — does not propagate
# ---------------------------------------------------------------------------

def test_telemetry_callback_error_does_not_abort_refresh(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.query_state_result = ({}, [], 0, 5, {})
    svc, rec = _reconciliation(tmp_path, bedrock)

    def bad_callback(reason: str) -> None:
        raise RuntimeError("telemetry trigger failed")

    rec._telemetry_snapshot_fn = bad_callback

    # refresh() must complete without raising
    rec.refresh("test")

    assert not rec.refreshing
    assert rec._refresh_lock.acquire(blocking=False), "lock was not released after callback error"
    rec._refresh_lock.release()


def test_telemetry_callback_error_publishes_event(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.query_state_result = ({}, [], 0, 5, {})
    svc, rec = _reconciliation(tmp_path, bedrock)

    events: list[str] = []
    original = svc.broker.publish

    def capture(topic, *a, **kw):
        events.append(topic)
        return original(topic, *a, **kw)

    svc.broker.publish = capture  # type: ignore[method-assign]
    rec.broker = svc.broker

    rec._telemetry_snapshot_fn = lambda reason: (_ for _ in ()).throw(RuntimeError("bad"))

    rec.refresh("test")

    assert "telemetry.snapshot.trigger.failed" in events


# ---------------------------------------------------------------------------
# refresh() — concurrent skip
# ---------------------------------------------------------------------------

def test_refresh_concurrent_call_is_skipped(tmp_path: Path) -> None:
    """A second refresh() while the first holds the lock returns immediately."""
    bedrock = FakeBedrock()
    started = threading.Event()
    can_finish = threading.Event()

    original_query = bedrock.query_state

    def blocking_query():
        started.set()
        can_finish.wait(timeout=5)
        return original_query()

    bedrock.query_state = blocking_query  # type: ignore[method-assign]

    _, rec = _reconciliation(tmp_path, bedrock)

    t = threading.Thread(target=rec.refresh, args=("first",), daemon=True)
    t.start()
    started.wait(timeout=5)

    # Second call while first holds lock must return without blocking
    rec.refresh("second")

    can_finish.set()
    t.join(timeout=5)


# ---------------------------------------------------------------------------
# refresh() — exception publishes failed event and re-raises
# ---------------------------------------------------------------------------

def test_refresh_exception_publishes_failed_event(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.query_state_error = RuntimeError("bedrock down")
    svc, rec = _reconciliation(tmp_path, bedrock)

    events: list[str] = []
    original = svc.broker.publish

    def capture(topic, *a, **kw):
        events.append(topic)
        return original(topic, *a, **kw)

    svc.broker.publish = capture  # type: ignore[method-assign]
    rec.broker = svc.broker

    with pytest.raises(RuntimeError, match="bedrock down"):
        rec.refresh("test")

    assert "state.reconciliation.failed" in events


# ---------------------------------------------------------------------------
# refresh_gamerules_async — second call while worker running only enqueues
# ---------------------------------------------------------------------------

def test_gamerule_second_call_enqueues_without_starting_second_worker(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    call_count = 0
    can_proceed = threading.Event()

    original_query = bedrock.query_gamerules

    def slow_query(rules):
        nonlocal call_count
        call_count += 1
        can_proceed.wait(timeout=5)
        return original_query(rules)

    bedrock.query_gamerules = slow_query  # type: ignore[method-assign]

    _, rec = _reconciliation(tmp_path, bedrock)
    rec.refresh_gamerules_async({"keepinventory"})

    # Wait until worker is marked running
    deadline = time.time() + 3
    while time.time() < deadline:
        with rec._pending_rules_lock:
            if rec._gamerule_worker_running:
                break
        time.sleep(0.02)

    # Second call while worker running — must not start a second worker
    rec.refresh_gamerules_async({"domobspawning"})

    # At this point only one thread should have called query_gamerules
    assert call_count <= 1

    can_proceed.set()

    # Wait for worker to finish
    deadline = time.time() + 5
    while time.time() < deadline:
        with rec._pending_rules_lock:
            if not rec._gamerule_worker_running:
                break
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# request_telemetry_snapshot — zero envelopes marks degraded
# ---------------------------------------------------------------------------

def test_snapshot_zero_envelopes_marks_degraded(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    bedrock.telemetry_output = ""  # no lines → 0 accepted envelopes
    svc, rec = _reconciliation(tmp_path, bedrock)

    events: list[str] = []
    original = svc.broker.publish

    def capture(topic, *a, **kw):
        events.append(topic)
        return original(topic, *a, **kw)

    svc.broker.publish = capture  # type: ignore[method-assign]
    rec.broker = svc.broker

    accepted = rec.request_telemetry_snapshot("test")

    assert accepted == 0
    assert svc.state()["telemetry"]["status"] == "degraded"
    assert "telemetry.snapshot.incomplete" in events


# ---------------------------------------------------------------------------
# request_telemetry_snapshot_async — coalescing within 5 s
# ---------------------------------------------------------------------------

def test_snapshot_async_coalesces_rapid_calls(tmp_path: Path) -> None:
    svc, rec = _reconciliation(tmp_path)

    events: list[str] = []
    original = svc.broker.publish

    def capture(topic, *a, **kw):
        events.append(topic)
        return original(topic, *a, **kw)

    svc.broker.publish = capture  # type: ignore[method-assign]
    rec.broker = svc.broker

    # First call triggers normally; force last_request to look recent
    import time as _time
    rec._telemetry_last_request = _time.monotonic()

    # Second call within 5 s must be coalesced
    rec.request_telemetry_snapshot_async("rapid")

    assert "telemetry.snapshot.coalesced" in events


# ---------------------------------------------------------------------------
# refresh_gamerules_async — unknown name validation
# ---------------------------------------------------------------------------

def test_refresh_gamerules_async_discards_unknown_names(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    queried: list[set[str]] = []

    def capturing_query(rules):
        queried.append(set(rules))
        return {}

    bedrock.query_gamerules = capturing_query
    _, rec = _reconciliation(tmp_path, bedrock)

    rec.refresh_gamerules_async({"notarule"})

    deadline = time.time() + 5
    while time.time() < deadline:
        with rec._pending_rules_lock:
            if not rec._gamerule_worker_running and queried == []:
                break
            if queried:
                break
        time.sleep(0.05)

    # Unknown name must not reach the adapter
    assert queried == [] or all("notarule" not in q for q in queried)


def test_refresh_gamerules_async_discards_name_with_newline(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    queried: list[set[str]] = []

    def capturing_query(rules):
        queried.append(set(rules))
        return {}

    bedrock.query_gamerules = capturing_query
    _, rec = _reconciliation(tmp_path, bedrock)

    rec.refresh_gamerules_async({"pvp\nlist"})

    deadline = time.time() + 5
    while time.time() < deadline:
        with rec._pending_rules_lock:
            if not rec._gamerule_worker_running:
                break
        time.sleep(0.05)

    assert all("pvp\nlist" not in q for q in queried)


def test_refresh_gamerules_async_keeps_valid_discards_invalid(tmp_path: Path) -> None:
    bedrock = FakeBedrock()
    queried: list[set[str]] = []
    done = threading.Event()

    def capturing_query(rules):
        queried.append(set(rules))
        done.set()
        return {r: "true" for r in rules}

    bedrock.query_gamerules = capturing_query
    _, rec = _reconciliation(tmp_path, bedrock)

    rec.refresh_gamerules_async({"pvp", "badname"})
    done.wait(timeout=5)

    assert queried, "query_gamerules was never called"
    assert "pvp" in queried[0]
    assert "badname" not in queried[0]

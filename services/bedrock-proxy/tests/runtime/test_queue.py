"""Tests for queue_worker.OperationQueue.

Covers:
- Sequential execution with workers=1
- 503 rejection when the queue is at capacity
- GET /v1/health includes queue_depth and worker_count
- HOST_AGENT_WORKERS / HOST_AGENT_QUEUE_SIZE env var wiring
"""
from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from http.server import HTTPServer
from typing import Any
from unittest.mock import MagicMock

import pytest

from helpers import make_executor  # noqa: F401

from src.runtime.queue_worker import OperationQueue
from src.store.store import OperationStore
from src.http.router import build_handler_class


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop_subprocess(*args: Any, **kwargs: Any) -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = ""
    m.stderr = ""
    return m


def _make_fake_executor(barrier: threading.Barrier | None = None, calls: list | None = None):
    """Return a fake executor that optionally synchronises via a barrier."""

    class FakeExecutor:
        def run(self, record, store, intended_state, health_timeout, restart_timeout):
            if calls is not None:
                calls.append(record.operation_id)
            if barrier is not None:
                barrier.wait()  # both arrive here; caller controls release

    return FakeExecutor()


def _make_store(tmp_path) -> OperationStore:
    return OperationStore(db_path=str(tmp_path / "ops.db"))


# ---------------------------------------------------------------------------
# Unit: OperationQueue
# ---------------------------------------------------------------------------

class TestOperationQueueEnqueue:
    def test_enqueue_accepted_returns_true(self, tmp_path):
        executor = _make_fake_executor()
        q = OperationQueue(executor, workers=1, queue_size=4)
        q.start()
        store = _make_store(tmp_path)
        record = store.create("op-1")
        assert record is not None
        result = q.enqueue(record, store, {}, 120, 60)
        assert result is True

    def test_enqueue_rejected_when_full(self, tmp_path):
        """Queue of size 1 with a blocking worker: second enqueue must be rejected."""
        gate = threading.Event()

        class BlockingExecutor:
            def run(self, record, store, intended_state, health_timeout, restart_timeout):
                gate.wait(timeout=10)

        executor = BlockingExecutor()
        q = OperationQueue(executor, workers=1, queue_size=1)
        q.start()
        store = _make_store(tmp_path)

        # Fill the worker (it starts processing immediately, so enqueue a second
        # one to occupy the single queue slot).
        r1 = store.create("op-fill-worker")
        r2 = store.create("op-fill-queue")
        r3 = store.create("op-overflow")

        q.enqueue(r1, store, {}, 120, 60)
        # Give the worker a moment to pick r1 up and free the queue slot.
        time.sleep(0.05)
        q.enqueue(r2, store, {}, 120, 60)

        # Now the slot is taken; r3 must be rejected.
        result = q.enqueue(r3, store, {}, 120, 60)
        gate.set()  # unblock worker
        assert result is False

    def test_worker_count_property(self):
        executor = _make_fake_executor()
        q = OperationQueue(executor, workers=3, queue_size=8)
        assert q.worker_count == 3

    def test_queue_depth_decreases_after_processing(self, tmp_path):
        done = threading.Event()

        class SlowExecutor:
            def run(self, record, store, intended_state, health_timeout, restart_timeout):
                done.set()

        executor = SlowExecutor()
        q = OperationQueue(executor, workers=1, queue_size=8)
        q.start()
        store = _make_store(tmp_path)
        record = store.create("op-depth")
        assert record is not None
        q.enqueue(record, store, {}, 120, 60)
        done.wait(timeout=5)
        # After done.set() the worker has finished; depth should be 0.
        assert q.queue_depth == 0


class TestOperationQueueSequential:
    def test_single_worker_executes_sequentially(self, tmp_path):
        """With workers=1, ops must start in order and not overlap."""
        order: list[str] = []
        lock = threading.Lock()
        active: list[str] = []
        overlap_detected = False

        class OrderedExecutor:
            def run(self, record, store, intended_state, health_timeout, restart_timeout):
                nonlocal overlap_detected
                with lock:
                    active.append(record.operation_id)
                    if len(active) > 1:
                        overlap_detected = True
                time.sleep(0.02)
                with lock:
                    active.remove(record.operation_id)
                    order.append(record.operation_id)

        executor = OrderedExecutor()
        q = OperationQueue(executor, workers=1, queue_size=8)
        q.start()
        store = _make_store(tmp_path)

        r1 = store.create("op-seq-1")
        r2 = store.create("op-seq-2")
        assert r1 is not None
        assert r2 is not None
        q.enqueue(r1, store, {}, 120, 60)
        q.enqueue(r2, store, {}, 120, 60)

        # Wait for both to complete.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(order) < 2:
            time.sleep(0.01)

        assert len(order) == 2
        assert not overlap_detected


class TestEnvVarWiring:
    def test_workers_env_var(self, monkeypatch):
        monkeypatch.setenv("HOST_AGENT_WORKERS", "3")
        monkeypatch.setenv("HOST_AGENT_QUEUE_SIZE", "16")
        executor = _make_fake_executor()
        q = OperationQueue(executor)
        assert q.worker_count == 3
        assert q._queue.maxsize == 16

    def test_invalid_workers_raises(self):
        with pytest.raises(ValueError):
            OperationQueue(_make_fake_executor(), workers=0, queue_size=8)

    def test_invalid_queue_size_raises(self):
        with pytest.raises(ValueError):
            OperationQueue(_make_fake_executor(), workers=1, queue_size=0)


# ---------------------------------------------------------------------------
# Integration: HTTP endpoint
# ---------------------------------------------------------------------------

def _start_test_server(tmp_path, executor=None, workers=1, queue_size=8):
    """Start a test HTTPServer with the full handler stack; return (server, thread, conn_factory)."""
    if executor is None:
        executor = _make_fake_executor()

    store = _make_store(tmp_path)
    op_queue = OperationQueue(executor, workers=workers, queue_size=queue_size)
    op_queue.start()

    from src.adapters.docker import DockerContainerStatus
    status_checker = DockerContainerStatus(subprocess_run=_noop_subprocess)

    handler_class = build_handler_class(
        "test-token",
        store,
        executor,  # type: ignore[arg-type]
        status_checker,
        "minecraft-server",
        op_queue,
    )
    server = HTTPServer(("127.0.0.1", 0), handler_class)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server, t, port, store, op_queue


class TestHealthEndpointQueueFields:
    def test_health_includes_queue_fields(self, tmp_path):
        server, _, port, store, op_queue = _start_test_server(tmp_path, workers=2, queue_size=5)
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", "/v1/health")
            resp = conn.getresponse()
            body = json.loads(resp.read())
            assert resp.status == 200
            assert body["queue_depth"] == 0
            assert body["worker_count"] == 2
        finally:
            server.shutdown()


class TestHTTP503OnFullQueue:
    def test_returns_503_when_queue_full(self, tmp_path):
        gate = threading.Event()

        class BlockingExecutor:
            def run(self, record, store, intended_state, health_timeout, restart_timeout):
                gate.wait(timeout=10)

        server, _, port, store, op_queue = _start_test_server(
            tmp_path, executor=BlockingExecutor(), workers=1, queue_size=1
        )
        try:
            conn = HTTPConnection("127.0.0.1", port, timeout=5)
            headers = {"Authorization": "Bearer test-token", "Content-Type": "application/json"}

            def _execute(op_id):
                body = json.dumps({
                    "operation_id": op_id,
                    "intended_state": {},
                }).encode()
                c = HTTPConnection("127.0.0.1", port, timeout=5)
                c.request("POST", "/v1/execute", body, headers)
                return c.getresponse()

            # First operation occupies the worker.
            r1 = _execute("op-block-worker")
            assert r1.status == 202
            r1.read()
            time.sleep(0.05)  # let worker pick it up

            # Second fills the queue slot.
            r2 = _execute("op-fill-slot")
            assert r2.status == 202
            r2.read()

            # Third must be rejected with 503.
            r3 = _execute("op-overflow")
            body3 = json.loads(r3.read())
            assert r3.status == 503
            assert body3["error"] == "queue_full"
        finally:
            gate.set()
            server.shutdown()

"""Bounded operation queue with a fixed worker pool for the host agent.

Workers consume ``_QueuedOperation`` items from a ``queue.Queue`` one at a time,
ensuring that a single worker never picks up a new operation until the current
one reaches a terminal state (``completed`` or ``failed``).

Environment variables
---------------------
HOST_AGENT_WORKERS      Number of worker threads.  Default: 1.
HOST_AGENT_QUEUE_SIZE   Maximum items the queue holds before rejecting.  Default: 8.
"""
from __future__ import annotations

import logging
import os
import queue
import threading
from dataclasses import dataclass
from typing import Any

from src.runtime.operations import OperationExecutor
from src.store.store import OperationRecord, OperationStore

logger = logging.getLogger("bedrock-proxy.queue")

WORKERS_DEFAULT = 1
QUEUE_SIZE_DEFAULT = 8


@dataclass
class _QueuedOperation:
    record: OperationRecord
    store: OperationStore
    intended_state: dict[str, Any]
    health_timeout: int
    restart_timeout: int


class OperationQueue:
    """Bounded FIFO queue consumed by a fixed-size worker pool.

    Parameters
    ----------
    executor:
        ``OperationExecutor`` instance that carries out each operation.
    workers:
        Number of worker threads to start.  Defaults to the
        ``HOST_AGENT_WORKERS`` env var, falling back to ``WORKERS_DEFAULT``.
    queue_size:
        Maximum number of pending items.  Defaults to the
        ``HOST_AGENT_QUEUE_SIZE`` env var, falling back to ``QUEUE_SIZE_DEFAULT``.
    """

    def __init__(
        self,
        executor: OperationExecutor,
        *,
        workers: int | None = None,
        queue_size: int | None = None,
    ) -> None:
        if workers is None:
            workers = int(os.environ.get("HOST_AGENT_WORKERS", WORKERS_DEFAULT))
        if queue_size is None:
            queue_size = int(os.environ.get("HOST_AGENT_QUEUE_SIZE", QUEUE_SIZE_DEFAULT))

        if workers < 1:
            raise ValueError(f"HOST_AGENT_WORKERS must be >= 1, got {workers}")
        if queue_size < 1:
            raise ValueError(f"HOST_AGENT_QUEUE_SIZE must be >= 1, got {queue_size}")

        self._executor = executor
        self._worker_count = workers
        self._queue: queue.Queue[_QueuedOperation] = queue.Queue(maxsize=queue_size)
        self._threads: list[threading.Thread] = []
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the worker threads.  Call once at server start-up."""
        if self._started:
            return
        self._started = True
        for i in range(self._worker_count):
            t = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"op-worker-{i}",
            )
            t.start()
            self._threads.append(t)
        logger.info(
            "Operation queue started: workers=%d queue_size=%d",
            self._worker_count,
            self._queue.maxsize,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        record: OperationRecord,
        store: OperationStore,
        intended_state: dict[str, Any],
        health_timeout: int,
        restart_timeout: int,
    ) -> bool:
        """Place an operation on the queue.

        Returns ``True`` if accepted, ``False`` if the queue is full.
        """
        item = _QueuedOperation(
            record=record,
            store=store,
            intended_state=intended_state,
            health_timeout=health_timeout,
            restart_timeout=restart_timeout,
        )
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            logger.warning(
                "Queue full (%d slots): rejected operation %s",
                self._queue.maxsize,
                record.operation_id,
            )
            return False
        logger.info(
            "Enqueued operation %s (depth=%d)",
            record.operation_id,
            self._queue.qsize(),
        )
        return True

    @property
    def queue_depth(self) -> int:
        """Approximate number of items currently waiting in the queue."""
        return self._queue.qsize()

    @property
    def worker_count(self) -> int:
        """Number of worker threads configured for this queue."""
        return self._worker_count

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                self._executor.run(
                    item.record,
                    item.store,
                    item.intended_state,
                    item.health_timeout,
                    item.restart_timeout,
                )
            except Exception:
                logger.exception(
                    "Unhandled error in worker processing operation %s",
                    item.record.operation_id,
                )
            finally:
                self._queue.task_done()

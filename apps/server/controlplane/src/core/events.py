from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import time
from typing import Any, Iterator

from ..ports import EventStore

MAX_SSE_CONNECTIONS = 240


class StreamCapacityError(RuntimeError):
    """Raised before a stream can consume capacity reserved for HTTP requests."""


@dataclass(frozen=True)
class Event:
    id: int
    topic: str
    timestamp: float
    source: str
    payload: dict[str, Any]


class EventBroker:
    """Persist and fan out operational events to bounded SSE subscribers."""

    def __init__(self, repository: EventStore, heartbeat_seconds: float = 20, max_stream_connections: int = MAX_SSE_CONNECTIONS) -> None:
        """Create a broker with a bounded stream pool and idle heartbeat."""
        self.repository = repository
        self._heartbeat_seconds = heartbeat_seconds
        self._max_stream_connections = max_stream_connections
        self._subscribers: set[queue.Queue[Event]] = set()
        self._lock = threading.Lock()
        self._topic_counts: dict[str, int] = {}
        self._active_stream_connections = 0
        self._stream_connections = 0
        self._stream_reconnections: int = 0

    def publish(self, topic: str, source: str, payload: dict[str, Any] | None = None) -> Event:
        """Persist an event and offer it to every currently live subscriber."""
        payload = payload or {}
        timestamp = time.time()
        event_id = self.repository.record_event(topic, source, payload)
        event = Event(event_id, topic, timestamp, source, payload)
        with self._lock:
            self._topic_counts[topic] = self._topic_counts.get(topic, 0) + 1
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                pass
        return event

    def diagnostics(self) -> dict[str, Any]:
        """Return process-local counters without exposing subscriber payloads."""
        with self._lock:
            return {
                "events_by_topic": dict(sorted(self._topic_counts.items())),
                "sse_connections": self._active_stream_connections,
                "sse_connections_total": self._stream_connections,
                "sse_reconnections": self._stream_reconnections,
            }

    def stream(self, after_id: int = 0) -> Iterator[Event | None]:
        """Reserve one SSE slot and return its replaying event iterator."""
        with self._lock:
            if self._active_stream_connections >= self._max_stream_connections:
                raise StreamCapacityError("SSE connection capacity reached")
            self._active_stream_connections += 1
            self._stream_connections += 1
            if after_id > 0:
                self._stream_reconnections += 1
        return self._stream(after_id)

    def _stream(self, after_id: int) -> Iterator[Event | None]:
        """Yield replay and live events, releasing the reserved slot on close."""
        try:
            for saved in self.repository.events_after(after_id):
                yield Event(saved["id"], saved["topic"], saved["timestamp"], saved["source"], saved["payload"])
            subscriber: queue.Queue[Event] = queue.Queue(maxsize=100)
            with self._lock:
                self._subscribers.add(subscriber)
            while True:
                try:
                    yield subscriber.get(timeout=self._heartbeat_seconds)
                except queue.Empty:
                    yield None
        finally:
            with self._lock:
                self._active_stream_connections -= 1
                if "subscriber" in locals():
                    self._subscribers.discard(subscriber)

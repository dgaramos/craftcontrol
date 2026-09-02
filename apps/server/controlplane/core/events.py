from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import time
from typing import Any, Iterator

from ..ports import EventStore


@dataclass(frozen=True)
class Event:
    id: int
    topic: str
    timestamp: float
    source: str
    payload: dict[str, Any]


class EventBroker:
    def __init__(self, repository: EventStore) -> None:
        self.repository = repository
        self._subscribers: set[queue.Queue[Event]] = set()
        self._lock = threading.Lock()
        self._topic_counts: dict[str, int] = {}
        self._active_stream_connections = 0
        self._stream_connections = 0
        self._stream_reconnections: int = 0

    def publish(self, topic: str, source: str, payload: dict[str, Any] | None = None) -> Event:
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
        with self._lock:
            return {
                "events_by_topic": dict(sorted(self._topic_counts.items())),
                "sse_connections": self._active_stream_connections,
                "sse_connections_total": self._stream_connections,
                "sse_reconnections": self._stream_reconnections,
            }

    def stream(self, after_id: int = 0) -> Iterator[Event | None]:
        with self._lock:
            self._active_stream_connections += 1
            self._stream_connections += 1
            if after_id > 0:
                self._stream_reconnections += 1
        try:
            for saved in self.repository.events_after(after_id):
                yield Event(saved["id"], saved["topic"], saved["timestamp"], saved["source"], saved["payload"])
            subscriber: queue.Queue[Event] = queue.Queue(maxsize=100)
            with self._lock:
                self._subscribers.add(subscriber)
            while True:
                try:
                    yield subscriber.get(timeout=20)
                except queue.Empty:
                    yield None
        finally:
            with self._lock:
                self._active_stream_connections -= 1
                if "subscriber" in locals():
                    self._subscribers.discard(subscriber)

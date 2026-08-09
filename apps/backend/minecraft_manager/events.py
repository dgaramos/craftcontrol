from __future__ import annotations

from dataclasses import dataclass
import queue
import threading
import time
from typing import Any, Iterator

from .ports import EventStore


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

    def publish(self, topic: str, source: str, payload: dict[str, Any] | None = None) -> Event:
        payload = payload or {}
        timestamp = time.time()
        event_id = self.repository.record_event(topic, source, payload)
        event = Event(event_id, topic, timestamp, source, payload)
        with self._lock:
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                pass
        return event

    def stream(self, after_id: int = 0) -> Iterator[Event | None]:
        for saved in self.repository.events_after(after_id):
            yield Event(saved["id"], saved["topic"], saved["timestamp"], saved["source"], saved["payload"])
        subscriber: queue.Queue[Event] = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.add(subscriber)
        try:
            while True:
                try:
                    yield subscriber.get(timeout=20)
                except queue.Empty:
                    yield None
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)

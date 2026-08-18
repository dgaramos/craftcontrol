"""Tests for EventBroker — publish, stream replay, live subscription, and cleanup."""
from __future__ import annotations

import queue
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from minecraft_manager.events import Event, EventBroker


@pytest.fixture
def store() -> MagicMock:
    mock = MagicMock()
    mock.record_event.return_value = 1
    mock.events_after.return_value = []
    return mock


@pytest.fixture
def broker(store: MagicMock) -> EventBroker:
    return EventBroker(store)


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------

def test_publish_records_event_and_returns_event_object(broker: EventBroker, store: MagicMock) -> None:
    event = broker.publish("state.changed", "test", {"domains": ["server"]})
    store.record_event.assert_called_once_with("state.changed", "test", {"domains": ["server"]})
    assert event.topic == "state.changed"
    assert event.source == "test"
    assert event.payload == {"domains": ["server"]}
    assert event.id == 1


def test_publish_uses_empty_payload_when_none_given(broker: EventBroker, store: MagicMock) -> None:
    event = broker.publish("ping", "system")
    assert event.payload == {}
    store.record_event.assert_called_once_with("ping", "system", {})


def test_publish_delivers_to_active_subscriber(broker: EventBroker) -> None:
    received: list[Event] = []
    done = threading.Event()

    def consume():
        for item in broker.stream(after_id=0):
            if item is not None:
                received.append(item)
                break
        done.set()

    t = threading.Thread(target=consume, daemon=True)
    t.start()
    # Poll under lock until the subscriber is registered inside stream()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        with broker._lock:
            if broker._subscribers:
                break
        time.sleep(0.001)
    broker.publish("player.join", "bedrock-log", {"player": "VonCrush"})
    assert done.wait(timeout=3), "Consumer did not receive event in time"
    try:
        assert len(received) == 1
        assert received[0].topic == "player.join"
    finally:
        t.join(timeout=3)


def test_publish_skips_full_subscriber_queue(broker: EventBroker) -> None:
    full_q: queue.Queue[Event] = queue.Queue(maxsize=1)
    dummy_event = Event(0, "fill", 0.0, "test", {})
    full_q.put_nowait(dummy_event)
    with broker._lock:
        broker._subscribers.add(full_q)
    # Should not raise even though the queue is full
    broker.publish("overflow", "test")
    with broker._lock:
        broker._subscribers.discard(full_q)


# ---------------------------------------------------------------------------
# stream — replay from history
# ---------------------------------------------------------------------------

def test_stream_replays_saved_events_before_live(broker: EventBroker, store: MagicMock) -> None:
    store.events_after.return_value = [
        {"id": 1, "topic": "state.changed", "timestamp": 1000.0, "source": "test", "payload": {}},
        {"id": 2, "topic": "player.join", "timestamp": 1001.0, "source": "bedrock-log", "payload": {"player": "VonCrush"}},
    ]
    gen = broker.stream(after_id=0)
    first = next(gen)
    second = next(gen)
    assert first.id == 1
    assert first.topic == "state.changed"
    assert second.id == 2
    assert second.topic == "player.join"
    store.events_after.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# stream — subscriber lifecycle
# ---------------------------------------------------------------------------

def test_stream_registers_and_removes_subscriber(broker: EventBroker) -> None:
    assert len(broker._subscribers) == 0
    registered = threading.Event()
    closed = threading.Event()

    def consume():
        gen = broker.stream(after_id=0)
        # Signal once we've passed history replay and are waiting for live events
        registered.set()
        # Pull one item (will block until broker publishes or timeout)
        try:
            next(gen)
        except StopIteration:
            pass
        finally:
            gen.close()
            closed.set()

    t = threading.Thread(target=consume, daemon=True)
    t.start()
    registered.wait(timeout=3)
    # At this point stream() may still be setting up — check under lock
    with broker._lock:
        count = len(broker._subscribers)
    # Push an event to unblock the consumer
    broker.publish("ping", "test")
    closed.wait(timeout=3)
    t.join(timeout=3)
    assert count == 1
    assert len(broker._subscribers) == 0


def test_stream_yields_none_on_timeout(broker: EventBroker) -> None:
    """Stream yields None when no event arrives within the timeout window."""
    # Patch the queue timeout to 0 so it fires immediately
    original_queue = queue.Queue

    class ImmediateTimeoutQueue(original_queue):
        def get(self, block=True, timeout=None):
            raise queue.Empty

    import unittest.mock as mock
    with mock.patch("minecraft_manager.core.events.queue.Queue", ImmediateTimeoutQueue):
        broker2 = EventBroker(broker.repository)
        gen = broker2.stream(after_id=0)
        item = next(gen)
        gen.close()
    assert item is None

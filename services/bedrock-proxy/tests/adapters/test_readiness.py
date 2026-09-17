"""Tests for the transport-aware Bedrock readiness probe."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.readiness import (
    SERVER_STARTED_MARKER,
    TRANSPORT_NETHERNET,
    TRANSPORT_RAKNET,
    TransportAwareHealthProbe,
    read_transport,
)
from helpers import FakeLogReader


def _write_properties(data_dir: Path, transport: str | None) -> None:
    lines = ["server-port=19132\n"]
    if transport is not None:
        lines.append(f"transport={transport}\n")
    (data_dir / "server.properties").write_text("".join(lines), encoding="utf-8")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay


def _probe(
    data_dir: Path,
    log_reader: FakeLogReader,
    clock: FakeClock,
    raknet_result: bool = True,
) -> tuple[TransportAwareHealthProbe, list[tuple[str, int, int]]]:
    calls: list[tuple[str, int, int]] = []

    def raknet_wait(host: str, port: int, timeout_seconds: int) -> bool:
        calls.append((host, port, timeout_seconds))
        return raknet_result

    probe = TransportAwareHealthProbe(
        str(data_dir),
        "bedrock",
        log_reader,
        raknet_wait=raknet_wait,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    return probe, calls


class TestReadTransport:
    def test_reads_nethernet_from_properties(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "NetherNet")
        assert read_transport(str(tmp_path)) == TRANSPORT_NETHERNET

    def test_defaults_to_raknet_when_key_or_file_is_missing(self, tmp_path: Path) -> None:
        assert read_transport(str(tmp_path)) == TRANSPORT_RAKNET
        _write_properties(tmp_path, None)
        assert read_transport(str(tmp_path)) == TRANSPORT_RAKNET

    def test_unreadable_file_defaults_to_raknet(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "nethernet")

        def read_text(path: Path, **kwargs: object) -> str:
            raise OSError("permission denied")

        assert read_transport(str(tmp_path), read_text=read_text) == TRANSPORT_RAKNET

    def test_unknown_transport_is_returned_verbatim(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "quic")
        assert read_transport(str(tmp_path)) == "quic"


class TestTransportAwareHealthProbe:
    def test_raknet_transport_delegates_to_the_udp_ping(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "raknet")
        reader = FakeLogReader(started_at="2026-09-17T17:29:10Z", logs=f"[INFO] {SERVER_STARTED_MARKER}\n")
        probe, calls = _probe(tmp_path, reader, FakeClock(), raknet_result=True)
        assert probe.wait("127.0.0.1", 19132, 30) is True
        assert calls == [("127.0.0.1", 19132, 30)]
        assert reader.logs_calls == []

    def test_raknet_transport_never_accepts_log_evidence_without_a_pong(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, None)
        reader = FakeLogReader(started_at="2026-09-17T17:29:10Z", logs=f"[INFO] {SERVER_STARTED_MARKER}\n")
        probe, calls = _probe(tmp_path, reader, FakeClock(), raknet_result=False)
        assert probe.wait("127.0.0.1", 19132, 30) is False
        assert len(calls) == 1

    def test_nethernet_transport_is_ready_when_the_current_boot_logged_server_started(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "nethernet")
        reader = FakeLogReader(
            started_at="2026-09-17T17:29:10Z",
            logs=f"[2026-09-17 14:29:24:667 INFO] {SERVER_STARTED_MARKER}\n",
        )
        probe, calls = _probe(tmp_path, reader, FakeClock())
        assert probe.wait("127.0.0.1", 19132, 30) is True
        assert calls == []
        assert reader.logs_calls == [("bedrock", "2026-09-17T17:29:10Z")]

    def test_nethernet_transport_retries_with_backoff_until_the_marker_appears(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "nethernet")
        clock = FakeClock()
        reader = FakeLogReader(
            started_at="2026-09-17T17:29:10Z",
            logs=["", "[INFO] Starting Server\n", f"[INFO] Starting Server\n[INFO] {SERVER_STARTED_MARKER}\n"],
        )
        probe, _ = _probe(tmp_path, reader, clock)
        assert probe.wait("127.0.0.1", 19132, 60) is True
        assert clock.sleeps == [1, 2]

    def test_nethernet_transport_times_out_without_the_marker(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "nethernet")
        clock = FakeClock()
        reader = FakeLogReader(started_at="2026-09-17T17:29:10Z", logs="[INFO] Starting Server\n")
        probe, _ = _probe(tmp_path, reader, clock)
        assert probe.wait("127.0.0.1", 19132, 5) is False
        assert clock.now <= 5
        assert clock.sleeps == [1, 2, 2]

    def test_nethernet_transport_is_not_ready_without_a_current_boot_reference(self, tmp_path: Path) -> None:
        # Without StartedAt the previous boot's marker cannot be excluded, so the
        # probe must not claim readiness from stale evidence.
        _write_properties(tmp_path, "nethernet")
        reader = FakeLogReader(started_at=None, logs=f"[INFO] {SERVER_STARTED_MARKER}\n")
        probe, _ = _probe(tmp_path, reader, FakeClock())
        assert probe.wait("127.0.0.1", 19132, 3) is False
        assert reader.logs_calls == []

    def test_nethernet_transport_treats_log_reader_errors_as_not_ready(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "nethernet")
        reader = FakeLogReader(started_at="2026-09-17T17:29:10Z", logs=OSError("docker unavailable"))
        probe, _ = _probe(tmp_path, reader, FakeClock())
        assert probe.wait("127.0.0.1", 19132, 3) is False

    def test_unsupported_transport_is_never_reported_healthy(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "quic")
        clock = FakeClock()
        reader = FakeLogReader(started_at="2026-09-17T17:29:10Z", logs=f"[INFO] {SERVER_STARTED_MARKER}\n")
        probe, calls = _probe(tmp_path, reader, clock, raknet_result=True)
        assert probe.wait("127.0.0.1", 19132, 30) is False
        assert calls == []
        assert reader.logs_calls == []
        assert clock.sleeps == []

    def test_transport_is_read_on_every_wait(self, tmp_path: Path) -> None:
        # PREPARE may rewrite server.properties between operations; the probe
        # must follow the file rather than a value cached at startup.
        _write_properties(tmp_path, "raknet")
        reader = FakeLogReader(started_at="2026-09-17T17:29:10Z", logs=f"[INFO] {SERVER_STARTED_MARKER}\n")
        probe, calls = _probe(tmp_path, reader, FakeClock(), raknet_result=False)
        assert probe.wait("127.0.0.1", 19132, 3) is False
        _write_properties(tmp_path, "nethernet")
        assert probe.wait("127.0.0.1", 19132, 3) is True
        assert len(calls) == 1


@pytest.mark.parametrize("value", ["raknet", "nethernet"])
def test_transport_constants_match_bedrock_property_values(value: str) -> None:
    assert value in {TRANSPORT_RAKNET, TRANSPORT_NETHERNET}

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

    def test_ignores_comments_blank_lines_and_malformed_entries(self, tmp_path: Path) -> None:
        (tmp_path / "server.properties").write_text(
            "# transport=nethernet\n\nnot a property\ntransport = NetherNet\n",
            encoding="utf-8",
        )
        assert read_transport(str(tmp_path)) == TRANSPORT_NETHERNET

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

    def test_nethernet_transport_gives_up_when_the_deadline_passes_during_a_log_check(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "nethernet")
        clock = FakeClock()

        class SlowLogReader(FakeLogReader):
            def logs_since(self, container: str, since: str, *, timeout_seconds: float | None = None) -> str:
                clock.now += 10  # the docker call itself consumed the remaining budget
                return super().logs_since(container, since, timeout_seconds=timeout_seconds)

        reader = SlowLogReader(started_at="2026-09-17T17:29:10Z", logs="[INFO] Starting Server\n")
        probe, _ = _probe(tmp_path, reader, clock)
        assert probe.wait("127.0.0.1", 19132, 5) is False
        assert clock.sleeps == []

    def test_nethernet_transport_bounds_every_docker_call_by_the_remaining_budget(self, tmp_path: Path) -> None:
        # HEALTH_WAIT owns the deadline: each docker call may use at most what is
        # left, so a slow daemon can never hold the single worker past it.
        _write_properties(tmp_path, "nethernet")
        clock = FakeClock()

        class SlowLogReader(FakeLogReader):
            def started_at(self, container: str, *, timeout_seconds: float | None = None) -> str | None:
                clock.now += 3  # docker inspect consumed part of the budget
                return super().started_at(container, timeout_seconds=timeout_seconds)

        reader = SlowLogReader(started_at="2026-09-17T17:29:10Z", logs=["", f"[INFO] {SERVER_STARTED_MARKER}\n"])
        probe, _ = _probe(tmp_path, reader, clock)
        assert probe.wait("127.0.0.1", 19132, 20) is True
        # attempt 1: inspect gets 20s, logs gets 17s; sleep 1s; attempt 2 at t=4:
        # inspect gets 16s, logs gets 13s.
        assert reader.timeouts == [20, 17, 16, 13]
        assert clock.sleeps == [1]

    def test_nethernet_transport_skips_the_log_read_when_inspect_exhausts_the_budget(self, tmp_path: Path) -> None:
        _write_properties(tmp_path, "nethernet")
        clock = FakeClock()

        class SlowLogReader(FakeLogReader):
            def started_at(self, container: str, *, timeout_seconds: float | None = None) -> str | None:
                clock.now += 10
                return super().started_at(container, timeout_seconds=timeout_seconds)

        reader = SlowLogReader(started_at="2026-09-17T17:29:10Z", logs=f"[INFO] {SERVER_STARTED_MARKER}\n")
        probe, _ = _probe(tmp_path, reader, clock)
        assert probe.wait("127.0.0.1", 19132, 5) is False
        assert reader.logs_calls == []
        assert clock.sleeps == []

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

"""Tests for the RakNet health-probe adapter."""
from __future__ import annotations

import struct

from adapters.raknet import _build_unconnected_ping, _next_probe_delay, _validate_pong, _wait_for_health


_MAGIC = bytes([0x00, 0xFF, 0xFF, 0x00, 0xFE, 0xFE, 0xFE, 0xFE, 0xFD, 0xFD, 0xFD, 0xFD, 0x12, 0x34, 0x56, 0x78])


def _valid_pong() -> bytes:
    return b"\x1c" + struct.pack(">Q", 0) + struct.pack(">Q", 42) + _MAGIC + b"\x00\x00"


class TestRakNetProbe:
    def test_validates_pong_magic_and_header(self) -> None:
        assert _validate_pong(_valid_pong()) is True
        assert _validate_pong(b"\x01" + _valid_pong()[1:]) is False
        assert _validate_pong(b"\x1c" * 10) is False

    def test_builds_expected_ping_packet(self) -> None:
        ping = _build_unconnected_ping()
        assert len(ping) == 33
        assert ping[0] == 0x01
        assert ping[9:25] == _MAGIC

    def test_backoff_caps_at_ten_seconds(self) -> None:
        delay = 1.0
        delays = []
        for _ in range(6):
            delays.append(delay)
            delay = _next_probe_delay(delay)
        assert delays == [1.0, 2.0, 4.0, 8.0, 10, 10]

    def test_wait_retries_with_injected_probe_and_clock(self) -> None:
        now = [0.0]
        sleeps: list[float] = []
        attempts = [0]

        def probe(*args: object) -> bool:
            attempts[0] += 1
            return attempts[0] == 2

        def sleep(delay: float) -> None:
            sleeps.append(delay)
            now[0] += delay

        assert _wait_for_health("127.0.0.1", 19132, 5, probe=probe, monotonic=lambda: now[0], sleep=sleep) is True
        assert sleeps == [1]

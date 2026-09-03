"""RakNet UDP health probe — concrete HealthProbe adapter."""
from __future__ import annotations

import socket
import struct
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.ports import HealthProbe

# RakNet constants (also re-exported for callers that need them directly).
RAKNET_MAGIC = bytes([
    0x00, 0xFF, 0xFF, 0x00, 0xFE, 0xFE, 0xFE, 0xFE,
    0xFD, 0xFD, 0xFD, 0xFD, 0x12, 0x34, 0x56, 0x78,
])
PROBE_READ_TIMEOUT_SECONDS = 2
PROBE_INITIAL_INTERVAL_SECONDS = 1
PROBE_MAX_INTERVAL_SECONDS = 10


def _build_unconnected_ping() -> bytes:
    """Build a 33-byte RakNet unconnected ping datagram."""
    packet_id = b'\x01'
    timestamp = struct.pack('>Q', int(time.monotonic() * 1000))
    client_guid = struct.pack('>Q', uuid.uuid4().int & 0xFFFFFFFFFFFFFFFF)
    return packet_id + timestamp + RAKNET_MAGIC + client_guid


def _validate_pong(data: bytes) -> bool:
    """Return True if data is a valid RakNet ID_UNCONNECTED_PONG."""
    if len(data) < 35:
        return False
    if data[0] != 0x1C:
        return False
    # magic is at bytes 17-32 (inclusive)
    if data[17:33] != RAKNET_MAGIC:
        return False
    return True


def _probe_bedrock(host: str, port: int, timeout: float) -> bool:
    """Send one unconnected ping and return True on valid pong."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(_build_unconnected_ping(), (host, port))
            data, _ = sock.recvfrom(4096)
            return _validate_pong(data)
        finally:
            sock.close()
    except OSError:
        return False


def _next_probe_delay(previous_delay: float) -> float:
    """Return the capped exponential delay before the next health probe."""
    return min(previous_delay * 2, PROBE_MAX_INTERVAL_SECONDS)


def _wait_for_health(
    host: str,
    port: int,
    timeout_seconds: int,
    *,
    probe: Callable[[str, int, float], bool] | None = None,
    monotonic: Callable[[], float] | None = None,
    sleep: Callable[[float], None] | None = None,
) -> bool:
    """Poll Bedrock with capped exponential backoff until the deadline.

    The first probe is immediate. Failed probes wait 1s, 2s, 4s, 8s, then at
    most 10s between attempts. The requested operation deadline remains the
    authority; neither a probe nor a sleep can extend it.
    """
    probe = probe or _probe_bedrock
    monotonic = monotonic or time.monotonic
    sleep = sleep or time.sleep
    deadline = monotonic() + timeout_seconds
    delay = PROBE_INITIAL_INTERVAL_SECONDS
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        if probe(host, port, min(PROBE_READ_TIMEOUT_SECONDS, remaining)):
            return True
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleep(min(delay, remaining))
        delay = _next_probe_delay(delay)
    return False


class RakNetHealthProbe:
    """HealthProbe adapter: polls via RakNet UDP unconnected ping."""

    def wait(self, host: str, port: int, timeout_seconds: int) -> bool:  # noqa: D102
        return _wait_for_health(host, port, timeout_seconds)


if TYPE_CHECKING:
    # Static check: RakNetHealthProbe must satisfy the HealthProbe Protocol.
    _: HealthProbe = RakNetHealthProbe()

"""RakNet UDP health probe — concrete HealthProbe adapter."""
from __future__ import annotations

import socket
import struct
import time
import uuid

from ports import HealthProbe

# RakNet constants (also re-exported for callers that need them directly).
RAKNET_MAGIC = bytes([
    0x00, 0xFF, 0xFF, 0x00, 0xFE, 0xFE, 0xFE, 0xFE,
    0xFD, 0xFD, 0xFD, 0xFD, 0x12, 0x34, 0x56, 0x78,
])
PROBE_READ_TIMEOUT_SECONDS = 2
PROBE_INTERVAL_SECONDS = 5


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


def _wait_for_health(host: str, port: int, timeout_seconds: int) -> bool:
    """Poll the Bedrock health probe. Returns True if healthy within timeout."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _probe_bedrock(host, port, PROBE_READ_TIMEOUT_SECONDS):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(PROBE_INTERVAL_SECONDS, remaining))
    return False


class RakNetHealthProbe:
    """HealthProbe adapter: polls via RakNet UDP unconnected ping."""

    def wait(self, host: str, port: int, timeout_seconds: int) -> bool:  # noqa: D102
        return _wait_for_health(host, port, timeout_seconds)


# Satisfy the structural Protocol check at import time.
_: HealthProbe = RakNetHealthProbe()

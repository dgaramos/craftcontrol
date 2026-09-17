"""Transport-aware Bedrock readiness probe — concrete HealthProbe adapter.

Bedrock Dedicated Server 1.26.50+ selects its network transport through the
``transport`` key in ``server.properties``:

* ``raknet`` — the classic UDP transport. Readiness is proven by a RakNet
  unconnected pong on ``server-port`` (see ``raknet.py``).
* ``nethernet`` — the WebRTC-based transport. The server no longer answers
  RakNet pings (nothing listens on ``server-port``), so readiness is proven by
  the ``Server started.`` console marker emitted by the current container
  boot. Logs are scoped to the container's ``StartedAt`` timestamp so a marker
  from a previous boot is never accepted.

Any other transport value is unsupported: the probe never reports it healthy,
because it has no way to verify the server actually speaks a compatible
protocol.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from src.adapters.raknet import (
    PROBE_INITIAL_INTERVAL_SECONDS,
    _next_probe_delay,
    _wait_for_health,
)
from src.ports import ContainerLogReader, HealthProbe

logger = logging.getLogger("bedrock-proxy")

TRANSPORT_RAKNET = "raknet"
TRANSPORT_NETHERNET = "nethernet"
SUPPORTED_TRANSPORTS = frozenset({TRANSPORT_RAKNET, TRANSPORT_NETHERNET})
# Bedrock prints "[<timestamp> INFO] Server started." once the world is loaded
# and the network transport is accepting connections, on every transport.
SERVER_STARTED_MARKER = "Server started."


def read_transport(
    bedrock_data: str,
    read_text: Callable[..., str] | None = None,
) -> str:
    """Return the ``transport`` value from server.properties, lowercased.

    Defaults to ``raknet`` when the file or key is missing or unreadable,
    which preserves the pre-1.26.50 behaviour for existing deployments.
    """
    read_text = read_text or (lambda p, **kw: p.read_text(**kw))
    props_file = Path(bedrock_data) / "server.properties"
    try:
        raw = read_text(props_file, encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read %s (%s); assuming transport=%s", props_file, exc, TRANSPORT_RAKNET)
        return TRANSPORT_RAKNET
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "transport":
            return value.strip().lower() or TRANSPORT_RAKNET
    return TRANSPORT_RAKNET


class TransportAwareHealthProbe:
    """HealthProbe adapter that selects the readiness strategy per transport."""

    def __init__(
        self,
        bedrock_data: str,
        container: str,
        log_reader: ContainerLogReader,
        *,
        raknet_wait: Callable[[str, int, int], bool] | None = None,
        read_text: Callable[..., str] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._bedrock_data = bedrock_data
        self.container = container
        self._logs = log_reader
        self._raknet_wait = raknet_wait or _wait_for_health
        self._read_text = read_text
        self._monotonic = monotonic or time.monotonic
        self._sleep = sleep or time.sleep

    def wait(self, host: str, port: int, timeout_seconds: int) -> bool:  # noqa: D102
        transport = read_transport(self._bedrock_data, read_text=self._read_text)
        if transport == TRANSPORT_RAKNET:
            return self._raknet_wait(host, port, timeout_seconds)
        if transport == TRANSPORT_NETHERNET:
            return self._wait_for_nethernet(timeout_seconds)
        logger.error(
            "Unsupported Bedrock transport %r; readiness cannot be verified (supported: %s)",
            transport, ", ".join(sorted(SUPPORTED_TRANSPORTS)),
        )
        return False

    def _wait_for_nethernet(self, timeout_seconds: int) -> bool:
        """Poll the current boot's console log for the started marker."""
        deadline = self._monotonic() + timeout_seconds
        delay: float = PROBE_INITIAL_INTERVAL_SECONDS
        while True:
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return False
            if self._current_boot_started():
                return True
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return False
            self._sleep(min(delay, remaining))
            delay = _next_probe_delay(delay)

    def _current_boot_started(self) -> bool:
        since = self._logs.started_at(self.container)
        if not since:
            logger.warning("Container %s has no StartedAt timestamp; cannot scope readiness evidence", self.container)
            return False
        try:
            text = self._logs.logs_since(self.container, since)
        except OSError as exc:
            logger.warning("Cannot read logs for %s: %s", self.container, exc)
            return False
        return SERVER_STARTED_MARKER in text


if TYPE_CHECKING:  # pragma: no cover
    _: HealthProbe = TransportAwareHealthProbe.__new__(TransportAwareHealthProbe)

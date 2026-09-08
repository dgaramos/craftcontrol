"""Opt-in telemetry metrics — the manager's half of the contract.

``docs/telemetry-metrics.md`` decides what the pack may collect; this module
owns the manager-side allowlist of metric names and the shape of the state the
pack reports back. Nothing here talks to the console or the database.
"""

from __future__ import annotations

import json
import re
from typing import Any

#: Every metric the manager may switch. A name outside this set is refused
#: before anything reaches the Bedrock console.
METRICS = ("itemUse", "blockInteractions", "entityInteractions", "containerInteractions")


#: A Minecraft namespaced identifier, the only shape an opt-in metric map may
#: use as a key. Player-authored text carries capitals, spaces or formatting
#: codes and cannot match, which is what keeps a custom name out of the data.
NAMESPACED_IDENTIFIER = re.compile(r"^[a-z0-9_]+:[a-z0-9_./-]+$")
IDENTIFIER_MAX_LENGTH = 112


def is_metric_key(value: Any) -> bool:
    """Return whether a value may be stored as a metric map key."""
    return (
        isinstance(value, str)
        and len(value) <= IDENTIFIER_MAX_LENGTH
        and bool(NAMESPACED_IDENTIFIER.match(value))
    )


class UnknownMetric(ValueError):
    """Raised for a metric name outside the allowlist."""

    def __init__(self, metric: Any) -> None:
        super().__init__(f"Métrica de telemetria desconhecida: {metric}")
        self.metric = metric


def validate(metric: Any) -> str:
    """Return the metric name, or refuse it."""
    if not isinstance(metric, str) or metric not in METRICS:
        raise UnknownMetric(metric)
    return metric


def normalize(value: Any) -> dict[str, bool]:
    """Read a reported metric map, defaulting anything unrecognized to off.

    A metric the pack does not report is *not enabled*: an older pack, a
    truncated payload or a corrupt property must never read as opted in.
    """
    source = value if isinstance(value, dict) else {}
    return {metric: source.get(metric) is True for metric in METRICS}


def loads(raw: Any) -> dict[str, bool]:
    """Read the metric map persisted in the telemetry state table."""
    try:
        return normalize(json.loads(raw) if isinstance(raw, str) and raw else None)
    except ValueError:
        return normalize(None)


def dumps(value: Any) -> str:
    return json.dumps(normalize(value), sort_keys=True)

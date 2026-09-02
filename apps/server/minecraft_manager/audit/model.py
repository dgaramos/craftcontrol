"""Sanitized audit-record domain model.

An AuditRecord captures the five W's of an administrative action:

- who acted (actor)
- what action was taken (action)
- on whom or what (target)
- with what outcome (result)
- when (occurred_at)
- with what sanitized context (metadata)

INVARIANT: ``metadata`` must never contain credentials, tokens, password
hashes, session identifiers, XUIDs, or any other secret material.  The
repository layer enforces this by stripping known secret keys before
persistence; callers must not rely on the repository as the sole guard.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuditRecord:
    """Immutable, sanitized audit record."""

    id: int
    occurred_at: float
    actor: str | None
    action: str
    target: str | None
    result: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

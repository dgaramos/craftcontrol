"""AuditService — application-layer facade over the AuditPort.

Thin orchestration class; keeps the HTTP layer and other services
decoupled from the persistence adapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..ports import AuditPort


class AuditService:
    """Coordinates audit writes and queries through the AuditPort boundary."""

    def __init__(self, port: "AuditPort") -> None:
        self._port = port

    def write(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        result: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a sanitized audit record through the port."""
        self._port.write(
            actor=actor,
            action=action,
            target=target,
            result=result,
            metadata=metadata or {},
        )

    def query(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        actor: str | None = None,
        action: str | None = None,
    ) -> dict[str, Any]:
        """Return a paginated page of audit records."""
        return self._port.query(
            page=page,
            page_size=page_size,
            actor=actor,
            action=action,
        )

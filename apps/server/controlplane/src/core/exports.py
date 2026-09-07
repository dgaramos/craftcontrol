"""Serialization and bounds shared by every export resource.

Implements the format-neutral half of ``docs/exports.md``: the manifest, the
JSON and CSV representations, and the two ceilings. Resource-specific reads live
in the module that owns the data, so this one stays free of domain knowledge.
"""

from __future__ import annotations

import csv
import io
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

EXPORT_SCHEMA_VERSION = 1
ROW_LIMIT = 10_000
BYTE_LIMIT = 5 * 1024 * 1024
FORMATS = ("json", "csv")


class ExportTooLarge(Exception):
    """Raised when an export exceeds a ceiling and must be refused whole."""

    def __init__(self, limit: str, measured: int, allowed: int) -> None:
        super().__init__(f"export exceeds the {limit} limit ({measured} > {allowed})")
        self.limit = limit
        self.measured = measured
        self.allowed = allowed


def calendar_timezone_name() -> str:
    """Return the IANA name used to bucket calendar days.

    Mirrors ``players.sqlite.calendar_timezone``; the manifest records it so a
    stored file stays interpretable after the deployment's ``TZ`` changes.
    """
    return os.environ.get("TZ", "America/Sao_Paulo")


def rfc3339(value: float | int | None) -> str:
    """Render an instant for CSV, where an epoch number is unreadable."""
    if value is None:
        return ""
    return datetime.fromtimestamp(float(value), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_name(resource: str, extension: str, now: float | None = None) -> str:
    stamp = datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc)
    return f"craftcontrol-{resource}-{stamp.strftime('%Y%m%dT%H%M%SZ')}.{extension}"


def flatten(record: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested values into dotted column names for CSV."""
    flat: dict[str, Any] = {}
    for key, value in record.items():
        column = f"{prefix}{key}"
        if isinstance(value, Mapping):
            flat.update(flatten(value, f"{column}."))
        elif isinstance(value, (list, tuple)):
            flat[column] = " ".join(str(item) for item in value)
        else:
            flat[column] = value
    return flat


@dataclass(frozen=True)
class Manifest:
    """What a payload contains, so a stored file can be read years later."""

    resource: str
    format: str
    filters: dict[str, Any]
    row_count: int
    generated_at: float
    timezone: str = ""
    export_schema_version: int = EXPORT_SCHEMA_VERSION
    row_limit: int = ROW_LIMIT
    truncated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "export_schema_version": self.export_schema_version,
            "resource": self.resource,
            "format": self.format,
            "filters": dict(self.filters),
            "generated_at": self.generated_at,
            "row_count": self.row_count,
            "timezone": self.timezone or calendar_timezone_name(),
            "row_limit": self.row_limit,
            "truncated": self.truncated,
        }


def enforce_row_limit(count: int, allowed: int = ROW_LIMIT) -> None:
    """Refuse before serializing when the record ceiling is already exceeded."""
    if count > allowed:
        raise ExportTooLarge("record", count, allowed)


def _measured(payload: str, allowed: int) -> str:
    """Return the payload, or refuse it, measured as the bytes that would be sent."""
    size = len(payload.encode("utf-8"))
    if size > allowed:
        raise ExportTooLarge("byte", size, allowed)
    return payload


def serialize_json(manifest: Manifest, records: list[Mapping[str, Any]], allowed: int = BYTE_LIMIT) -> str:
    """Serialize the complete object, then measure it. Never partial."""
    payload = json.dumps(
        {"manifest": manifest.as_dict(), "records": [dict(record) for record in records]},
        ensure_ascii=False,
    )
    return _measured(payload, allowed)


def serialize_csv(
    records: Iterable[Mapping[str, Any]],
    columns: list[str],
    allowed: int = BYTE_LIMIT,
) -> str:
    """Serialize RFC 4180 CSV with a stable column order and LF endings."""
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for record in records:
        flat = flatten(record)
        writer.writerow({column: _cell(flat.get(column)) for column in columns})
    return _measured(buffer.getvalue(), allowed)


def _cell(value: Any) -> str:
    """Render one CSV cell; a null is empty, never the string ``null``."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)

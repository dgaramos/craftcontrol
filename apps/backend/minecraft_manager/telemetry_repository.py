"""Telemetry persistence adapter over the shared SQLite database."""

from __future__ import annotations

from typing import Any

from .repository import StateRepository


class SQLiteTelemetryRepository:
    def __init__(self, database: StateRepository) -> None:
        self.database = database

    def snapshot(self, refreshing: bool = False) -> dict[str, Any]:
        return self.database.snapshot(refreshing)

    def store(self, kind: str, values: dict[str, str], source: str) -> None:
        self.database.store(kind, values, source)

    def ingest_telemetry(self, envelope: dict[str, Any]) -> tuple[bool, list[str]]:
        return self.database.ingest_telemetry(envelope)

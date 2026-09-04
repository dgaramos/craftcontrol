"""Fake infrastructure objects shared across the backend test suite."""
from __future__ import annotations

import json


class FakeBedrock:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []
        self.telemetry_output: str | None = None
        self.query_state_result: tuple = ({}, [], 0, 0, {})
        self.query_state_error: Exception | None = None
        self.gamerule_result: dict = {}

    def send(self, parts: list[str]) -> None:
        self.commands.append(parts)

    def send_and_read(self, parts: list[str]) -> str:
        self.commands.append(parts)
        return "The time is 34"

    def set_operator(self, player: str, enabled: bool) -> None:
        self.commands.append(["op" if enabled else "deop", player])

    def query_state(self) -> tuple:
        if self.query_state_error is not None:
            raise self.query_state_error
        return self.query_state_result

    def query_gamerules(self, rules: set) -> dict:
        return self.gamerule_result

    def request_telemetry_snapshot(self) -> str:
        if self.telemetry_output is not None:
            return self.telemetry_output
        payloads = (
            {"schema": 1, "sequence": 12, "type": "snapshot.started", "timestamp": 1, "player": None, "data": {"players": 0}},
            {"schema": 1, "sequence": 12, "type": "snapshot.finished", "timestamp": 1, "player": None, "data": {}},
        )
        return "\n".join(f"[Scripting] [BEDROCK_TELEMETRY] {json.dumps(payload)}" for payload in payloads)


class FakeDocker:
    def __init__(self) -> None:
        self.actions: list[str] = []
        self._status: dict = {"status": "running"}

    def status(self) -> dict:
        return self._status

    def execute(self, action: str) -> None:
        self.actions.append(action)


class FakeRuntime:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True


class FakeAuditPort:
    """Minimal in-memory AuditPort for injection into tests."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def write(
        self,
        *,
        actor: str | None,
        action: str,
        target: str | None,
        result: str,
        metadata: dict,
    ) -> None:
        self.records.append(
            {"actor": actor, "action": action, "target": target, "result": result, "metadata": metadata}
        )

    def query(self, *, page: int, page_size: int, actor=None, action=None) -> dict:
        return {"records": self.records, "total": len(self.records), "page": page, "page_size": page_size, "pages": 1}


class FakeConsole:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def send(self, parts: list[str]) -> None:
        self.commands.append(parts)

    def send_and_read(self, parts: list[str]) -> str:
        self.commands.append(parts)
        return "Data saved. Files are now ready to be copied."

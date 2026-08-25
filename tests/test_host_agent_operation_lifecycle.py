"""Integration tests: HostAgentContainerOperations as the ContainerOperations adapter.

Covers the three acceptance criteria from issue #232:
- AC1: Agent unreachable → FAILED terminal state with user-readable error (no host internals).
- AC2: Agent returns 5xx → FAILED terminal state; error evidence contains no host internals.
- AC3: FAILED operation caused by agent unavailability → reconciliation re-observes and
       updates state correctly when the agent becomes available again.

These tests wire the real HostAgentContainerOperations (backed by a fake _HttpClient) into a
ServerOperationService with an SQLite repository so the full lifecycle executes end-to-end.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import minecraft_manager.host_agent as _host_agent_module
from minecraft_manager.host_agent import HostAgentContainerOperations
from minecraft_manager.migrations import run_migrations
from minecraft_manager.operations.lifecycle import OperationStage, OperationState
from minecraft_manager.operations.repository import SQLiteOperationRepository
from minecraft_manager.operations.service import ServerOperationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_TOKEN = "test-secret-token-abcdef1234567890"  # noqa: S105
OP_ID = "11111111-1111-1111-1111-111111111111"

_HOST_INTERNALS = [
    "host-gateway",
    "7890",
    "/run/secrets",
    VALID_TOKEN,
]


def _contains_host_internal(text: str) -> bool:
    """Return True if *text* exposes any configured host internal."""
    return any(internal in text for internal in _HOST_INTERNALS)


def _make_http_client(responses: list[tuple[int, dict[str, Any]] | Exception]) -> MagicMock:
    """Return a fake _HttpClient that yields responses or raises exceptions in sequence."""
    mock = MagicMock()
    mock.request.side_effect = responses
    return mock


def _make_adapter(client: MagicMock) -> HostAgentContainerOperations:
    """Wrap a fake _HttpClient in a HostAgentContainerOperations with test credentials."""
    return HostAgentContainerOperations(
        "http://host-gateway:7890",
        VALID_TOKEN,
        http_client=client,
    )


def _make_db(tmp_path: Path) -> Path:
    """Create and migrate an SQLite database in *tmp_path* and return its path."""
    db = tmp_path / "state.db"
    with sqlite3.connect(db) as conn:
        run_migrations(conn)
    return db


def _make_service(
    tmp_path: Path,
    adapter: HostAgentContainerOperations,
    configuration: MagicMock | None = None,
) -> ServerOperationService:
    """Wire adapter and a fresh SQLite repository into a ServerOperationService."""
    broker = MagicMock()
    if configuration is None:
        configuration = MagicMock()
        configuration.read_properties.return_value = {}
    return ServerOperationService(
        operation_repository=SQLiteOperationRepository(_make_db(tmp_path)),
        docker=adapter,
        broker=broker,
        configuration=configuration,
        thread_factory=threading.Thread,
        server_id="test-server",
        health_timeout=1,
    )


def _wait_for_terminal(
    service: ServerOperationService,
    operation_id: str,
    timeout: float = 10.0,
) -> None:
    """Poll until *operation_id* reaches a terminal state or *timeout* seconds elapse."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        op = service.get_operation(operation_id)
        if op is not None and op.state.is_terminal:
            return
        time.sleep(0.05)
    raise AssertionError(f"Operation {operation_id} did not reach terminal state before timeout")


# ---------------------------------------------------------------------------
# AC1: Agent unreachable → FAILED with user-readable error, no host internals
# ---------------------------------------------------------------------------

class TestAgentUnreachable:
    """AC1: Given the agent is unreachable, the operation fails with FAILED terminal state
    and a user-readable error that does not expose host internals."""

    def test_connection_refused_produces_failed_operation(self, tmp_path: Path) -> None:
        """ConnectionRefusedError (pre-delivery) → FAILED operation."""
        client = MagicMock()
        client.request.side_effect = ConnectionRefusedError("connection refused")
        # status() is also called; agent unreachable → offline
        adapter = _make_adapter(client)
        service = _make_service(tmp_path, adapter)

        op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
        _wait_for_terminal(service, op.operation_id)

        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.FAILED

    def test_connection_refused_error_is_user_readable(self, tmp_path: Path) -> None:
        """Error message is human-readable and contains no host internals."""
        client = MagicMock()
        client.request.side_effect = ConnectionRefusedError("connection refused")
        adapter = _make_adapter(client)
        service = _make_service(tmp_path, adapter)

        op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
        _wait_for_terminal(service, op.operation_id)

        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        error = refreshed.terminal_error or ""
        # Must be non-empty and contain at least one readable word.
        assert error
        # Must not expose host internals.
        assert not _contains_host_internal(error), (
            f"terminal_error exposes host internals: {error!r}"
        )

    def test_connect_timeout_produces_failed_operation(self, tmp_path: Path) -> None:
        """TimeoutError (pre-delivery) → FAILED operation without host internals."""
        client = MagicMock()
        client.request.side_effect = TimeoutError("timed out")
        adapter = _make_adapter(client)
        service = _make_service(tmp_path, adapter)

        op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
        _wait_for_terminal(service, op.operation_id)

        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.FAILED
        error = refreshed.terminal_error or ""
        assert error
        assert not _contains_host_internal(error), (
            f"terminal_error exposes host internals: {error!r}"
        )

    def test_failed_stage_is_restart(self, tmp_path: Path) -> None:
        """Pre-delivery failures are recorded at the RESTART stage in the service lifecycle."""
        client = MagicMock()
        client.request.side_effect = ConnectionRefusedError("connection refused")
        adapter = _make_adapter(client)
        service = _make_service(tmp_path, adapter)

        op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
        _wait_for_terminal(service, op.operation_id)

        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        failed = refreshed.failed_stage
        assert failed is not None
        assert failed.stage == OperationStage.RESTART


# ---------------------------------------------------------------------------
# AC2: 5xx response → FAILED, no host internals in evidence
# ---------------------------------------------------------------------------

class TestAgentFiveXxResponse:
    """AC2: Given the agent returns a 5xx response, the error evidence is recorded
    without exposing host internals.

    The adapter's post-delivery recovery polls have a 5 s delay between attempts.
    All tests in this class patch that delay to 0 so the test suite runs fast.
    """

    def _make_5xx_client_that_exhausts_recovery(self) -> MagicMock:
        """Build a fake client that drives the full 5xx-exhaustion path.

        Call sequence expected by the adapter and service:
          1. POST /v1/execute              → 500  (delivery fails; enters recovery)
          2. GET /v1/status  (poll 1)      → 500  (recovery attempt 1 fails)
          3. GET /v1/status  (poll 2)      → 500  (recovery attempt 2 fails)
          4. GET /v1/status  (poll 3)      → 500  (recovery exhausted; RESTART fails)
          5. GET /v1/health  (status() via _observe_container after RESTART failure) → 503

        Each call is validated against the expected method and URL. Any call
        beyond position 5 raises AssertionError so unexpected extra requests
        surface as an explicit test failure rather than a silent fallback.
        """
        base = "http://host-gateway:7890"
        scripted: list[tuple[str, str, tuple[int, dict[str, Any]] | Exception]] = [
            ("POST", f"{base}/v1/execute",  (500, {"error": "internal_server_error"})),
            ("GET",  f"{base}/v1/status",   (500, {"error": "internal_server_error"})),
            ("GET",  f"{base}/v1/status",   (500, {"error": "internal_server_error"})),
            ("GET",  f"{base}/v1/status",   (500, {"error": "internal_server_error"})),
            ("GET",  f"{base}/v1/health",   (503, {})),
        ]
        iterator = iter(scripted)

        def _side_effect(method: str, url: str, **_kwargs: object) -> tuple[int, dict[str, Any]]:
            try:
                exp_method, exp_url_prefix, response = next(iterator)
            except StopIteration:
                raise AssertionError(
                    f"Unexpected extra call: {method} {url}"
                ) from None
            assert method == exp_method, f"Expected {exp_method}, got {method} ({url})"
            assert url.startswith(exp_url_prefix), (
                f"Expected URL starting with {exp_url_prefix!r}, got {url!r}"
            )
            if isinstance(response, Exception):
                raise response
            return response

        mock = MagicMock()
        mock.request.side_effect = _side_effect
        return mock

    def test_5xx_produces_failed_operation(self, tmp_path: Path) -> None:
        """5xx from POST /v1/execute that exhausts recovery → FAILED."""
        client = self._make_5xx_client_that_exhausts_recovery()
        adapter = _make_adapter(client)
        service = _make_service(tmp_path, adapter)

        with patch.object(_host_agent_module, "_POST_DELIVERY_RETRY_INTERVAL_SECONDS", 0):
            op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
            _wait_for_terminal(service, op.operation_id)

        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.FAILED

    def test_5xx_error_contains_no_host_internals(self, tmp_path: Path) -> None:
        """terminal_error and stage evidence from a 5xx failure expose no host internals."""
        client = self._make_5xx_client_that_exhausts_recovery()
        adapter = _make_adapter(client)
        service = _make_service(tmp_path, adapter)

        with patch.object(_host_agent_module, "_POST_DELIVERY_RETRY_INTERVAL_SECONDS", 0):
            op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
            _wait_for_terminal(service, op.operation_id)

        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None

        error = refreshed.terminal_error or ""
        assert not _contains_host_internal(error), (
            f"terminal_error exposes host internals: {error!r}"
        )

        # Check stage error messages and evidence as well.
        for stage in refreshed.stages:
            for value in (stage.error or "", str(stage.result or {}), str(stage.evidence or {})):
                assert not _contains_host_internal(value), (
                    f"Stage {stage.stage} evidence exposes host internals: {value!r}"
                )

    def test_5xx_then_recovery_success_confirms_operation(self, tmp_path: Path) -> None:
        """POST 5xx followed by a successful recovery poll → operation CONFIRMED.

        HTTP call sequence inside the adapter and service:
          1. POST /v1/execute → 500      (post-delivery ambiguous → _poll_with_recovery)
          2. GET /v1/status  → 200 done ok  (recovery succeeds → execute() returns normally)
          3. GET /v1/health  → 200       (service HEALTH_WAIT: status() → online=True)
          4. GET /v1/health  → 200       (_verify_configuration calls _observe_container again)
        """
        ok_response: tuple[int, dict[str, Any]] = (
            200,
            {
                "status": "done",
                "outcome": "ok",
                "executor_ref": "ref-123",
                "health_reached": True,
                "failed_stage": None,
                "detail": "ok",
                "error_code": None,
                "exception_type": None,
            },
        )
        health_ok: tuple[int, dict[str, Any]] = (200, {"status": "ok", "version": "0.1.0"})
        responses: list[tuple[int, dict[str, Any]] | Exception] = [
            (500, {"error": "transient"}),  # POST /v1/execute
            ok_response,                     # recovery poll
            health_ok,                       # HEALTH_WAIT: status() → online=True
            health_ok,                       # VERIFY: _observe_container in _verify_configuration
        ]
        client = _make_http_client(responses)
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "5"}
        adapter = _make_adapter(client)

        broker = MagicMock()
        service = ServerOperationService(
            operation_repository=SQLiteOperationRepository(_make_db(tmp_path)),
            docker=adapter,
            broker=broker,
            configuration=configuration,
            thread_factory=threading.Thread,
            server_id="test-server",
            health_timeout=5,
        )

        with patch.object(_host_agent_module, "_POST_DELIVERY_RETRY_INTERVAL_SECONDS", 0):
            op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
            _wait_for_terminal(service, op.operation_id)

        refreshed = service.get_operation(op.operation_id)
        assert refreshed is not None
        assert refreshed.state == OperationState.CONFIRMED


# ---------------------------------------------------------------------------
# AC3: Reconciliation after agent-unavailability failure
# ---------------------------------------------------------------------------

class TestReconciliationAfterAgentUnavailability:
    """AC3: Given a FAILED operation caused by agent unavailability, when the user
    requests reconciliation, the system re-observes through the agent and updates
    the state correctly."""

    def test_reconciliation_confirms_when_agent_recovers_and_config_matches(
        self, tmp_path: Path
    ) -> None:
        """After FAILED (agent down), reconciliation → CONFIRMED when agent is back and config matches."""
        # Phase 1: agent is unavailable; operation fails.
        client = MagicMock()
        client.request.side_effect = ConnectionRefusedError("connection refused")
        adapter = _make_adapter(client)
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "5"}
        service = _make_service(tmp_path, adapter, configuration=configuration)

        op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
        _wait_for_terminal(service, op.operation_id)

        failed = service.get_operation(op.operation_id)
        assert failed is not None and failed.state == OperationState.FAILED

        # Phase 2: agent recovers; reconciliation re-observes.
        # status() is now called successfully → online=True.
        client.request.side_effect = None
        client.request.return_value = (200, {"status": "ok", "version": "0.1.0"})

        reconciled = service.request_reconciliation(op.operation_id)
        assert reconciled is not None
        assert reconciled.state == OperationState.CONFIRMED

    def test_reconciliation_stays_failed_when_agent_remains_unavailable(
        self, tmp_path: Path
    ) -> None:
        """After FAILED (agent down), reconciliation keeps FAILED when agent is still down."""
        client = MagicMock()
        client.request.side_effect = ConnectionRefusedError("connection refused")
        adapter = _make_adapter(client)
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "5"}
        service = _make_service(tmp_path, adapter, configuration=configuration)

        op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
        _wait_for_terminal(service, op.operation_id)

        failed = service.get_operation(op.operation_id)
        assert failed is not None and failed.state == OperationState.FAILED

        # Agent is still unreachable during reconciliation.
        # status() raises OSError → _observe_container returns online=False.
        client.request.side_effect = ConnectionRefusedError("still down")

        reconciled = service.request_reconciliation(op.operation_id)
        assert reconciled is not None
        # State should remain FAILED — server offline, no verifiable configuration to confirm.
        assert reconciled.state == OperationState.FAILED

    def test_reconciliation_marks_divergent_when_agent_recovers_and_config_differs(
        self, tmp_path: Path
    ) -> None:
        """After FAILED (agent down), reconciliation → DIVERGENT when config does not match."""
        client = MagicMock()
        client.request.side_effect = ConnectionRefusedError("connection refused")
        adapter = _make_adapter(client)
        # Requested MAX_PLAYERS=5 but server reports max-players=10 → divergent.
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "10"}
        service = _make_service(tmp_path, adapter, configuration=configuration)

        op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
        _wait_for_terminal(service, op.operation_id)

        failed = service.get_operation(op.operation_id)
        assert failed is not None and failed.state == OperationState.FAILED

        # Agent recovers.
        client.request.side_effect = None
        client.request.return_value = (200, {"status": "ok", "version": "0.1.0"})

        reconciled = service.request_reconciliation(op.operation_id)
        assert reconciled is not None
        assert reconciled.state == OperationState.DIVERGENT

    def test_reconciliation_updates_observation_with_agent_state(
        self, tmp_path: Path
    ) -> None:
        """Reconciliation records the re-observed agent state in the operation observation."""
        client = MagicMock()
        client.request.side_effect = ConnectionRefusedError("connection refused")
        adapter = _make_adapter(client)
        configuration = MagicMock()
        configuration.read_properties.return_value = {"max-players": "5"}
        service = _make_service(tmp_path, adapter, configuration=configuration)

        op = service.apply_restart_required({"MAX_PLAYERS": "5"}, lambda: None)
        _wait_for_terminal(service, op.operation_id)

        # Agent recovers.
        client.request.side_effect = None
        client.request.return_value = (200, {"status": "ok", "version": "0.1.0"})

        reconciled = service.request_reconciliation(op.operation_id)
        assert reconciled is not None
        # The observation must record the reconciled container state.
        assert "container_state" in reconciled.observation

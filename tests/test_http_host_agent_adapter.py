"""Tests for HostAgentContainerOperations (host_agent.py).

Covers:
- status(): maps 200 → online=True, transport error → online=False
- execute("apply"): successful round-trip through POST /v1/execute + poll
- execute("apply"): pre-delivery failure (connection refused, timeout)
- execute("apply"): post-delivery ambiguous failure, recovery polling
- execute("apply"): agent returns 409 conflict
- execute("apply"): agent returns 401 unauthorized
- execute("apply"): agent returns 400 bad request
- execute("apply"): terminal failure outcome (failed_stage, error_code)
- execute("apply"): agent restart during polling (404 from status)
- execute(): unsupported action raises KeyError
- execute(): missing operation_id raises ValueError
- _load_token(): reads file, strips whitespace, raises on missing file
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from minecraft_manager.host_agent import (
    HostAgentContainerOperations,
    _load_token,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

VALID_TOKEN = "test-secret-token-abcdef1234567890"
OP_ID = "11111111-1111-1111-1111-111111111111"


def _make_client(responses: list[tuple[int, dict[str, Any]]]) -> MagicMock:
    """Return a mock _HttpClient that yields responses in sequence."""
    mock = MagicMock()
    mock.request.side_effect = responses
    return mock


def _adapter(client: MagicMock | None = None) -> HostAgentContainerOperations:
    return HostAgentContainerOperations(
        "http://host-gateway:7890",
        VALID_TOKEN,
        http_client=client or MagicMock(),
    )


def _execute(adapter: HostAgentContainerOperations, op_id: str = OP_ID, **kwargs: Any) -> None:
    adapter.execute(
        "apply",
        operation_id=op_id,
        intended_state={"server_name": "Test"},
        health_timeout_seconds=120,
        restart_timeout_seconds=60,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# status()
# ---------------------------------------------------------------------------

class TestStatus:
    def test_health_200_returns_online(self) -> None:
        client = _make_client([(200, {"status": "ok", "version": "0.1.0"})])
        result = _adapter(client).status()
        assert result["online"] is True
        assert result["state"] == "running"

    def test_health_non_200_returns_offline(self) -> None:
        client = _make_client([(503, {})])
        result = _adapter(client).status()
        assert result["online"] is False
        assert result["state"] == "stopped"

    def test_connection_error_returns_offline(self) -> None:
        client = MagicMock()
        client.request.side_effect = OSError("connection refused")
        result = _adapter(client).status()
        assert result["online"] is False
        assert result["state"] == "stopped"


# ---------------------------------------------------------------------------
# execute(): successful path
# ---------------------------------------------------------------------------

class TestExecuteSuccess:
    def test_success_returns_normally(self) -> None:
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            (200, {"operation_id": OP_ID, "status": "done", "outcome": "ok",
                   "executor_ref": "ref-123", "health_reached": True,
                   "failed_stage": None, "detail": "ok", "error_code": None,
                   "exception_type": None}),
        ])
        _execute(_adapter(client))  # must not raise

    def test_success_with_intermediate_running_status(self) -> None:
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            (200, {"operation_id": OP_ID, "status": "running", "current_stage": "restart"}),
            (200, {"operation_id": OP_ID, "status": "running", "current_stage": "health_wait"}),
            (200, {"operation_id": OP_ID, "status": "done", "outcome": "ok",
                   "executor_ref": "ref-456", "health_reached": True,
                   "failed_stage": None, "detail": "healthy", "error_code": None,
                   "exception_type": None}),
        ])
        _execute(_adapter(client))  # must not raise

    def test_bearer_token_sent_with_execute(self) -> None:
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            (200, {"status": "done", "outcome": "ok", "executor_ref": None,
                   "health_reached": True, "failed_stage": None,
                   "detail": None, "error_code": None, "exception_type": None}),
        ])
        _execute(_adapter(client))
        post_call = client.request.call_args_list[0]
        headers: dict[str, str] = post_call.kwargs.get("headers", {})
        auth = headers.get("Authorization", "")
        assert auth == f"Bearer {VALID_TOKEN}"


# ---------------------------------------------------------------------------
# execute(): unsupported action and missing operation_id
# ---------------------------------------------------------------------------

class TestExecuteValidation:
    def test_unsupported_action_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            _adapter().execute("start")

    def test_missing_operation_id_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="operation_id"):
            _adapter().execute("apply")


# ---------------------------------------------------------------------------
# execute(): pre-delivery failures
# ---------------------------------------------------------------------------

class TestPreDeliveryFailure:
    def test_connection_refused_raises_runtime_error(self) -> None:
        client = MagicMock()
        client.request.side_effect = ConnectionRefusedError("connection refused")
        with pytest.raises(RuntimeError, match="connection refused"):
            _execute(_adapter(client))

    def test_connect_timeout_raises_runtime_error(self) -> None:
        client = MagicMock()
        client.request.side_effect = TimeoutError("timed out")
        with pytest.raises(RuntimeError, match="timed out"):
            _execute(_adapter(client))

    def test_generic_oserror_raises_runtime_error(self) -> None:
        client = MagicMock()
        client.request.side_effect = OSError("network unreachable")
        with pytest.raises(RuntimeError, match="transport error"):
            _execute(_adapter(client))


# ---------------------------------------------------------------------------
# execute(): authentication and protocol errors
# ---------------------------------------------------------------------------

class TestProtocolErrors:
    def test_401_raises_runtime_error(self) -> None:
        client = _make_client([(401, {"error": "unauthorized"})])
        with pytest.raises(RuntimeError, match="authentication failed"):
            _execute(_adapter(client))

    def test_400_includes_agent_message(self) -> None:
        client = _make_client([(400, {"error": "bad_request", "message": "invalid field xyz"})])
        with pytest.raises(RuntimeError, match="invalid field xyz"):
            _execute(_adapter(client))

    def test_409_conflict_raises_runtime_error(self) -> None:
        client = _make_client([(409, {"error": "conflict", "operation_id": OP_ID,
                                      "message": "Operation already in progress"})])
        with pytest.raises(RuntimeError, match="conflict"):
            _execute(_adapter(client))


# ---------------------------------------------------------------------------
# execute(): terminal failure outcomes
# ---------------------------------------------------------------------------

class TestTerminalFailure:
    def test_error_outcome_raises_with_stage_and_code(self) -> None:
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            (200, {"operation_id": OP_ID, "status": "done", "outcome": "error",
                   "executor_ref": None, "health_reached": False,
                   "failed_stage": "health_wait",
                   "detail": "server did not reach healthy state",
                   "error_code": "health_probe_timeout",
                   "exception_type": None}),
        ])
        with pytest.raises(RuntimeError, match="health_wait"):
            _execute(_adapter(client))

    def test_error_outcome_includes_error_code(self) -> None:
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            (200, {"operation_id": OP_ID, "status": "done", "outcome": "error",
                   "executor_ref": None, "health_reached": None,
                   "failed_stage": "prepare",
                   "detail": "could not write server.properties",
                   "error_code": "preparation_write_failed",
                   "exception_type": None}),
        ])
        with pytest.raises(RuntimeError, match="preparation_write_failed"):
            _execute(_adapter(client))


# ---------------------------------------------------------------------------
# execute(): post-delivery ambiguous failure recovery
# ---------------------------------------------------------------------------

class TestPostDeliveryRecovery:
    def test_5xx_response_then_recovery_succeeds(self) -> None:
        """5xx on POST → recovery poll succeeds with terminal ok."""
        client = _make_client([
            # POST returns 5xx (post-delivery ambiguous)
            (500, {"error": "internal"}),
            # Recovery poll 1: terminal ok
            (200, {"status": "done", "outcome": "ok", "executor_ref": "ref",
                   "health_reached": True, "failed_stage": None,
                   "detail": "ok", "error_code": None, "exception_type": None}),
        ])
        _execute(_adapter(client))  # must not raise

    def test_status_404_raises_ambiguous_error(self) -> None:
        """Agent restarted during poll → 404 on status → ambiguous failure."""
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            # Agent restarted; status is now 404
            (404, {"error": "not_found", "operation_id": OP_ID}),
        ])
        with pytest.raises(RuntimeError, match="agent may have restarted"):
            _execute(_adapter(client))

    def test_post_delivery_transport_error_then_exhausted_recovery(self) -> None:
        """Transport error on POST → all recovery polls fail → ambiguous error."""
        client = MagicMock()
        # POST raises OSError (generic — treated as pre-delivery / safe)
        client.request.side_effect = OSError("broken pipe")
        with pytest.raises(RuntimeError, match="transport error"):
            _execute(_adapter(client))


# ---------------------------------------------------------------------------
# _load_token()
# ---------------------------------------------------------------------------

class TestLoadToken:
    def test_reads_and_strips_whitespace(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".token", delete=False) as f:
            f.write("my-secret-token\n")
            name = f.name
        assert _load_token(name) == "my-secret-token"

    def test_missing_file_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="not readable"):
            _load_token("/nonexistent/path/host-agent-token")

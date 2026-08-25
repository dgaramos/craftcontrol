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
- execute(): unsupported action raises RuntimeError
- execute(): missing operation_id raises ValueError
- execute(): None intended_state defaults to empty dict
- execute(): OSError during status polling triggers recovery
- execute(): unexpected status code during polling triggers recovery
- execute(): recovery: "running" response returns to normal polling
- execute(): recovery: OSError on all attempts raises ambiguous error
- _UrllibClient.request(): successful response
- _UrllibClient.request(): HTTPError returns (code, body)
- _UrllibClient.request(): URLError with OSError reason re-raises reason
- _UrllibClient.request(): URLError with non-OSError reason raises OSError
- _load_token(): reads file, strips whitespace, raises on missing file
"""
from __future__ import annotations

import io
import json
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from minecraft_manager.host_agent import (
    HostAgentContainerOperations,
    _UrllibClient,
    _load_token,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

VALID_TOKEN = "test-secret-token-abcdef1234567890"  # noqa: S105
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
    def test_unsupported_action_raises_runtime_error(self) -> None:
        with pytest.raises(RuntimeError, match="does not support action"):
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

    def test_pre_delivery_transport_error_raises_runtime_error(self) -> None:
        """OSError on POST (pre-delivery) → RuntimeError with 'transport error'; no recovery poll."""
        client = MagicMock()
        # POST raises OSError (generic — treated as pre-delivery / safe)
        client.request.side_effect = OSError("broken pipe")
        with pytest.raises(RuntimeError, match="transport error"):
            _execute(_adapter(client))


# ---------------------------------------------------------------------------
# execute(): additional branch coverage
# ---------------------------------------------------------------------------

class TestExecuteBranchCoverage:
    def test_none_intended_state_defaults_to_empty_dict(self) -> None:
        """intended_state=None should be replaced with {} and restart_timeout_seconds defaults to 60."""
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            (200, {"status": "done", "outcome": "ok", "executor_ref": "r",
                   "health_reached": True, "failed_stage": None,
                   "detail": "ok", "error_code": None, "exception_type": None}),
        ])
        adapter = _adapter(client)
        # Should not raise even though intended_state is None
        adapter.execute("apply", operation_id=OP_ID, intended_state=None)
        # Inspect the POST payload: intended_state must be {} and restart_timeout_seconds must be 60
        post_call = client.request.call_args_list[0]
        sent_body: dict[str, Any] = json.loads(post_call.kwargs["body"])
        assert sent_body["intended_state"] == {}
        assert sent_body["restart_timeout_seconds"] == 60

    def test_oserror_during_status_poll_enters_recovery(self) -> None:
        """OSError on GET /v1/status during _poll_until_done enters recovery."""
        client = MagicMock()
        # POST 202 accepted, then GET /v1/status raises OSError, then recovery
        # poll also fails -> ambiguous error
        client.request.side_effect = [
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            # OSError during _poll_until_done triggers recovery
            OSError("connection reset"),
            # All 3 _poll_with_recovery attempts also fail
            OSError("connection reset"),
            OSError("connection reset"),
            OSError("connection reset"),
        ]
        with pytest.raises(RuntimeError, match="ambiguous"):
            _execute(_adapter(client))

    def test_unexpected_status_code_during_poll_enters_recovery(self) -> None:
        """503 on GET /v1/status during _poll_until_done enters recovery."""
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            # Unexpected status code during polling
            (503, {"error": "overloaded"}),
            # Recovery poll: done ok
            (200, {"status": "done", "outcome": "ok", "executor_ref": "r",
                   "health_reached": True, "failed_stage": None,
                   "detail": "ok", "error_code": None, "exception_type": None}),
        ])
        _execute(_adapter(client))  # must not raise

    def test_recovery_running_returns_to_normal_poll(self) -> None:
        """'running' response in _poll_with_recovery returns to _poll_until_done."""
        client = _make_client([
            # POST 5xx -> recovery
            (500, {}),
            # Recovery poll: still running -> back to _poll_until_done
            (200, {"status": "running"}),
            # Normal poll: done ok
            (200, {"status": "done", "outcome": "ok", "executor_ref": "r",
                   "health_reached": True, "failed_stage": None,
                   "detail": "ok", "error_code": None, "exception_type": None}),
        ])
        _execute(_adapter(client))  # must not raise

    def test_recovery_oserror_all_attempts_exhausted(self) -> None:
        """All _poll_with_recovery attempts fail with OSError -> ambiguous error."""
        client = MagicMock()
        client.request.side_effect = [
            # POST 5xx triggers recovery
            (500, {}),
            # All 3 recovery poll attempts fail
            OSError("broken"),
            OSError("broken"),
            OSError("broken"),
        ]
        with pytest.raises(RuntimeError, match="ambiguous"):
            _execute(_adapter(client))


# ---------------------------------------------------------------------------
# _UrllibClient.request()
# ---------------------------------------------------------------------------

def _make_resp_opener(
    status: int,
    body: dict[str, Any] | None = None,
    raw: bytes | None = None,
) -> tuple[Any, MagicMock]:
    """Return (opener_callable, request_capture) that yields a fake HTTP response.

    The opener captures the ``urllib.request.Request`` object passed to it so
    tests can inspect headers without patching the global.
    """
    if raw is None:
        raw = json.dumps(body or {}).encode()
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = raw
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    captured: list[Any] = []

    def opener(req: Any, *, timeout: float = 30.0) -> Any:  # noqa: ARG001
        captured.append(req)
        return resp

    capture = MagicMock()
    capture.side_effect = opener
    capture.captured = captured  # type: ignore[attr-defined]
    return capture, resp


def _make_exc_opener(exc: Exception) -> Any:
    """Return an opener callable that raises *exc*."""
    def opener(req: Any, *, timeout: float = 30.0) -> Any:  # noqa: ARG001
        raise exc
    return opener


class TestUrllibClient:
    def test_successful_get_returns_status_and_json(self) -> None:
        opener, _ = _make_resp_opener(200, {"ok": True})
        code, body = _UrllibClient(opener=opener).request("GET", "http://host/v1/health")
        assert code == 200
        assert body == {"ok": True}

    def test_http_error_returns_code_and_parsed_body(self) -> None:
        raw = json.dumps({"message": "not found"}).encode()
        exc = urllib.error.HTTPError(
            url="http://host/v1/health",
            code=404,
            msg="Not Found",
            hdrs=MagicMock(),  # type: ignore[arg-type]
            fp=io.BytesIO(raw),
        )
        code, body = _UrllibClient(opener=_make_exc_opener(exc)).request(
            "GET", "http://host/v1/health"
        )
        assert code == 404
        assert body == {"message": "not found"}

    def test_http_error_with_invalid_json_returns_empty_body(self) -> None:
        exc = urllib.error.HTTPError(
            url="http://host/v1/health",
            code=502,
            msg="Bad Gateway",
            hdrs=MagicMock(),  # type: ignore[arg-type]
            fp=io.BytesIO(b"<html>bad gateway</html>"),
        )
        code, body = _UrllibClient(opener=_make_exc_opener(exc)).request(
            "GET", "http://host/v1/health"
        )
        assert code == 502
        assert body == {}

    def test_url_error_with_oserror_reason_reraises_reason(self) -> None:
        inner = ConnectionRefusedError(111, "Connection refused")
        exc = urllib.error.URLError(reason=inner)
        with pytest.raises(ConnectionRefusedError):
            _UrllibClient(opener=_make_exc_opener(exc)).request(
                "GET", "http://host/v1/health"
            )

    def test_url_error_with_timeout_reason_reraises_timeout(self) -> None:
        inner = TimeoutError("timed out")
        exc = urllib.error.URLError(reason=inner)
        with pytest.raises(TimeoutError):
            _UrllibClient(opener=_make_exc_opener(exc)).request(
                "GET", "http://host/v1/health"
            )

    def test_url_error_with_non_oserror_reason_raises_oserror(self) -> None:
        exc = urllib.error.URLError(reason="unknown reason")
        with pytest.raises(OSError):
            _UrllibClient(opener=_make_exc_opener(exc)).request(
                "GET", "http://host/v1/health"
            )

    def test_request_with_headers_passes_them(self) -> None:
        opener, _ = _make_resp_opener(200, {"ok": True})
        _UrllibClient(opener=opener).request(
            "GET",
            "http://host/v1/health",
            headers={"Authorization": "Bearer tok"},
        )
        assert opener.called
        captured_req = opener.captured[0]
        assert captured_req.get_header("Authorization") == "Bearer tok"

    def test_empty_response_body_returns_empty_dict(self) -> None:
        opener, _ = _make_resp_opener(200, raw=b"")
        code, body = _UrllibClient(opener=opener).request("GET", "http://host/v1/health")
        assert code == 200
        assert body == {}


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

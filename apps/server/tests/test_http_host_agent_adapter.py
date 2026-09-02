"""Tests for HostAgentContainerOperations (host_agent.py).

Covers:
- status(): maps bedrock_running=true → online=True, agent-alive-but-bedrock-stopped → online=False, transport error → online=False
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

import ast
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
    ReadTimeoutError,
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


def _adapter(
    client: MagicMock | None = None,
    retry_interval: float = 0.0,
) -> HostAgentContainerOperations:
    return HostAgentContainerOperations(
        "http://host-gateway:7890",
        VALID_TOKEN,
        http_client=client or MagicMock(),
        retry_interval=retry_interval,
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
    def test_bedrock_running_true_returns_online(self) -> None:
        """bedrock_running=true in /v1/bedrock/status body → online."""
        client = _make_client([(200, {"bedrock_running": True})])
        result = _adapter(client).status()
        assert result["online"] is True
        assert result["state"] == "running"

    def test_bedrock_running_false_returns_offline(self) -> None:
        """Agent alive but bedrock_running=false → offline (the key fix for #299/#296)."""
        client = _make_client([(200, {"bedrock_running": False})])
        result = _adapter(client).status()
        assert result["online"] is False
        assert result["state"] == "stopped"

    def test_non_200_returns_offline(self) -> None:
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

    def test_status_uses_server_name_in_container_field(self) -> None:
        """container field reflects the configured server_name, not 'host-agent'."""
        client = _make_client([(200, {"bedrock_running": True})])
        adapter = HostAgentContainerOperations(
            "http://host-gateway:7890",
            VALID_TOKEN,
            http_client=client,
            server_name="my-bedrock",
        )
        result = adapter.status()
        assert result["container"] == "my-bedrock"

    def test_status_sends_bearer_token(self) -> None:
        """status() authenticates with the agent token."""
        client = _make_client([(200, {"bedrock_running": True})])
        _adapter(client).status()
        _, kwargs = client.request.call_args
        assert kwargs["headers"]["Authorization"] == f"Bearer {VALID_TOKEN}"

    def test_status_queries_bedrock_status_endpoint(self) -> None:
        """status() must call /v1/bedrock/status, not /v1/health."""
        client = _make_client([(200, {"bedrock_running": True})])
        _adapter(client).status()
        args, _ = client.request.call_args
        assert args[1].endswith("/v1/bedrock/status")


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
# execute(): read-phase timeout routes to recovery polling
# ---------------------------------------------------------------------------

class TestReadPhaseTimeout:
    """A ReadTimeoutError on POST /v1/execute triggers _poll_with_recovery."""

    def test_read_timeout_on_post_triggers_recovery_poll_done(self) -> None:
        """ReadTimeoutError on POST → recovery poll returns done/ok → no error raised."""
        client = MagicMock()
        # POST raises ReadTimeoutError; subsequent recovery status poll returns done/ok.
        client.request.side_effect = [
            ReadTimeoutError("read body timed out"),
            (200, {"status": "done", "outcome": "ok", "executor_ref": "r1"}),
        ]
        # Should not raise — recovery poll resolves successfully.
        _execute(_adapter(client))

    def test_read_timeout_on_post_does_not_raise_pre_delivery_error(self) -> None:
        """ReadTimeoutError on POST must not surface as a pre-delivery connect-timeout error."""
        client = MagicMock()
        client.request.side_effect = [
            ReadTimeoutError("read body timed out"),
            (200, {"status": "done", "outcome": "ok", "executor_ref": "r2"}),
        ]
        # Must not raise RuntimeError("connection timed out").
        _execute(_adapter(client))

    def test_read_timeout_on_post_triggers_recovery_poll_failure(self) -> None:
        """ReadTimeoutError on POST → recovery exhausted → RuntimeError with ambiguous message."""
        client = MagicMock()
        client.request.side_effect = [
            ReadTimeoutError("read body timed out"),
            OSError("conn reset"),
            OSError("conn reset"),
            OSError("conn reset"),
        ]
        with pytest.raises(RuntimeError, match="ambiguous"):
            _execute(_adapter(client, retry_interval=0.0))

    def test_read_timeout_is_subclass_of_timeout_error(self) -> None:
        """ReadTimeoutError must be catchable as TimeoutError."""
        exc = ReadTimeoutError("read timed out")
        assert isinstance(exc, TimeoutError)

    def test_connect_timeout_still_raises_pre_delivery_error(self) -> None:
        """A plain TimeoutError (connect phase) must still raise pre-delivery RuntimeError."""
        client = MagicMock()
        client.request.side_effect = TimeoutError("connect timed out")
        with pytest.raises(RuntimeError, match="timed out"):
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

    def test_recovery_running_then_500_then_done_no_recursion(self) -> None:
        """Alternating 500/running does not recurse: polling loop resumes after each recovery."""
        # Sequence: POST 202 → poll 500 (→ recovery: running) → poll 500 (→ recovery: running)
        # → poll done ok.  Previously this would cause mutual recursion; now the
        # outer loop in _poll_until_done simply continues after _poll_with_recovery
        # returns True.
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            # First poll: unexpected 500 → recovery
            (500, {"error": "transient"}),
            # Recovery attempt 1: still running → caller resumes loop
            (200, {"status": "running"}),
            # Second poll: another 500 → recovery
            (500, {"error": "transient"}),
            # Recovery attempt 1: still running → caller resumes loop again
            (200, {"status": "running"}),
            # Third poll: terminal ok
            (200, {"status": "done", "outcome": "ok", "executor_ref": "r",
                   "health_reached": True, "failed_stage": None,
                   "detail": "ok", "error_code": None, "exception_type": None}),
        ])
        _execute(_adapter(client))  # must not raise and must not RecursionError

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

    def test_read_body_timeout_raises_read_timeout_error(self) -> None:
        """TimeoutError during resp.read() must be converted to ReadTimeoutError."""
        resp = MagicMock()
        resp.status = 200
        resp.read.side_effect = TimeoutError("read timed out")
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)

        def opener(req: Any, *, timeout: float = 30.0) -> Any:  # noqa: ARG001
            return resp

        with pytest.raises(ReadTimeoutError):
            _UrllibClient(opener=opener).request("POST", "http://host/v1/execute")

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


# ---------------------------------------------------------------------------
# execute(): intended_state key translation (uppercase schema → agent field)
# ---------------------------------------------------------------------------

class TestIntendedStateKeyTranslation:
    """GAMEMODE and other uppercase schema keys must be translated to agent field names."""

    def _execute_with_state(
        self,
        intended_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Post an execute call and return the parsed payload sent to the agent."""
        client = _make_client([
            (202, {"operation_id": OP_ID, "status": "accepted"}),
            (200, {"status": "done", "outcome": "ok", "executor_ref": None,
                   "health_reached": True, "failed_stage": None,
                   "detail": "ok", "error_code": None, "exception_type": None}),
        ])
        _adapter(client).execute(
            "apply",
            operation_id=OP_ID,
            intended_state=intended_state,
        )
        post_call = client.request.call_args_list[0]
        import json as _json
        return _json.loads(post_call.kwargs["body"])["intended_state"]

    def test_gamemode_uppercase_is_translated_to_lowercase(self) -> None:
        """GAMEMODE (backend schema key) must become gamemode in the agent payload."""
        sent = self._execute_with_state({"GAMEMODE": "survival"})
        assert "gamemode" in sent
        assert "GAMEMODE" not in sent
        assert sent["gamemode"] == "survival"

    def test_difficulty_uppercase_is_translated(self) -> None:
        sent = self._execute_with_state({"DIFFICULTY": "hard"})
        assert "difficulty" in sent
        assert "DIFFICULTY" not in sent

    def test_server_name_uppercase_is_translated(self) -> None:
        sent = self._execute_with_state({"SERVER_NAME": "My Server"})
        assert "server_name" in sent
        assert "SERVER_NAME" not in sent

    def test_server_port_v6_maps_to_server_portv6(self) -> None:
        """SERVER_PORT_V6 → server-portv6 (properties) → server_portv6 (agent field)."""
        sent = self._execute_with_state({"SERVER_PORT_V6": 19133})
        assert "server_portv6" in sent
        assert "SERVER_PORT_V6" not in sent

    def test_lowercase_keys_are_preserved_unchanged(self) -> None:
        """Keys already in agent format must survive the translation unchanged."""
        sent = self._execute_with_state({"server_name": "Direct"})
        assert sent["server_name"] == "Direct"

    def test_creative_gamemode_value_is_preserved(self) -> None:
        sent = self._execute_with_state({"GAMEMODE": "creative"})
        assert sent["gamemode"] == "creative"

    def test_adventure_gamemode_value_is_preserved(self) -> None:
        sent = self._execute_with_state({"GAMEMODE": "adventure"})
        assert sent["gamemode"] == "adventure"

    def test_conflicting_aliases_uppercase_first_raises_value_error(self) -> None:
        """GAMEMODE=survival then gamemode=creative → conflict → ValueError before payload."""
        from minecraft_manager.host_agent import _translate_intended_state
        with pytest.raises(ValueError, match="conflicting"):
            _translate_intended_state({"GAMEMODE": "survival", "gamemode": "creative"})

    def test_conflicting_aliases_lowercase_first_raises_value_error(self) -> None:
        """gamemode=creative then GAMEMODE=survival → conflict → ValueError before payload."""
        from minecraft_manager.host_agent import _translate_intended_state
        with pytest.raises(ValueError, match="conflicting"):
            _translate_intended_state({"gamemode": "creative", "GAMEMODE": "survival"})

    def test_duplicate_aliases_same_value_collapsed(self) -> None:
        """GAMEMODE=survival and gamemode=survival → same value → collapsed to one entry."""
        from minecraft_manager.host_agent import _translate_intended_state
        result = _translate_intended_state({"GAMEMODE": "survival", "gamemode": "survival"})
        assert result == {"gamemode": "survival"}

    def test_every_restart_required_setting_has_a_host_agent_field(self) -> None:
        """Every UI setting must translate to the host agent's canonical contract."""
        from minecraft_manager.host_agent import _translate_intended_state
        from minecraft_manager.core.schema import PROPERTY_NAMES, SETTINGS

        translated = _translate_intended_state({key: "value" for key in SETTINGS})
        agent_operations = Path(__file__).parents[3] / "services" / "host-agent" / "operations.py"
        module = ast.parse(agent_operations.read_text())
        values = {}
        for node in module.body:
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {"_INTENDED_STATE_FIELDS", "_FIELD_MAP"}:
                    value = node.value
                    if (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name)
                        and value.func.id == "frozenset"
                    ):
                        value = value.args[0]
                    values[target.id] = ast.literal_eval(value)
        agent_fields = values["_INTENDED_STATE_FIELDS"]
        agent_field_map = values["_FIELD_MAP"]

        assert set(translated) <= agent_fields
        assert set(translated) <= set(agent_field_map)
        for schema_field, property_name in PROPERTY_NAMES.items():
            agent_field = property_name.replace("-", "_")
            assert _translate_intended_state({schema_field: "value"}) == {agent_field: "value"}
            assert agent_field_map[agent_field] == property_name

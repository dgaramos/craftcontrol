"""Tests for AgentHandler, build_handler_class, and authentication."""
from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
import proxy.http.handler as hd
import proxy.http.router as rt
import proxy.store.store as st
from proxy.runtime.operations import OperationExecutor
from helpers import execute_request, fake_run, make_executor as _make_executor_base, operation_id


def _make_status_checker(running: bool = True) -> Any:
    """Return a mock ContainerStatusChecker."""
    mock = MagicMock()
    mock.is_running.return_value = running
    return mock


VALID_TOKEN = "test-secret-token-abcdef1234567890"

_op_id = operation_id


def _make_store() -> st.OperationStore:
    return st.OperationStore()


def _make_executor(subprocess_run: Any = None) -> OperationExecutor:
    """Build an executor with a per-call temporary directory for isolation."""
    return _make_executor_base(subprocess_run=subprocess_run)


def _handler_class(
    token: str = VALID_TOKEN,
    store: st.OperationStore | None = None,
    executor: OperationExecutor | None = None,
    status_checker: Any = None,
    bedrock_container_name: str = "minecraft-server",
) -> type:
    store = store or _make_store()
    executor = executor or _make_executor()
    checker = status_checker if status_checker is not None else _make_status_checker()
    return rt.build_handler_class(token, store, executor, checker, bedrock_container_name)


class FakeRequest:
    def __init__(self, method: str, path: str, body: bytes = b"", headers: dict[str, str] | None = None) -> None:
        hdrs = {"Content-Length": str(len(body))}
        if headers:
            hdrs.update(headers)
        header_lines = "".join(f"{k}: {v}\r\n" for k, v in hdrs.items())
        raw = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n{header_lines}\r\n".encode() + body
        self._file = BytesIO(raw)

    def makefile(self, mode: str) -> Any:
        return self._file


def _call_handler(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = VALID_TOKEN,
    store: st.OperationStore | None = None,
    executor: OperationExecutor | None = None,
    extra_headers: dict[str, str] | None = None,
    status_checker: Any = None,
    bedrock_container_name: str = "minecraft-server",
) -> tuple[int, dict[str, Any]]:
    raw_body = json.dumps(body).encode() if body is not None else b""
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)

    request = FakeRequest(method, path, raw_body, headers)
    response_buf = BytesIO()

    HandlerClass = _handler_class(
        store=store,
        executor=executor,
        status_checker=status_checker,
        bedrock_container_name=bedrock_container_name,
    )

    class CapturingSocket:
        def makefile(self, mode: str, bufsize: int = -1) -> Any:
            if "w" in mode:
                return response_buf
            return request.makefile(mode)

        def sendall(self, data: bytes) -> None:
            response_buf.write(data)

        def settimeout(self, timeout: Any) -> None:
            pass

        def setsockopt(self, *args: Any) -> None:
            pass

        def getsockname(self) -> tuple:
            return ("127.0.0.1", 7890)

        def getpeername(self) -> tuple:
            return ("127.0.0.1", 55000)

    server_mock = MagicMock()
    handler = HandlerClass.__new__(HandlerClass)
    handler.request = CapturingSocket()
    handler.client_address = ("127.0.0.1", 55000)
    handler.server = server_mock
    handler.setup()
    handler.handle()

    response_buf.seek(0)
    raw_response = response_buf.read().decode()

    lines = raw_response.split("\r\n")
    status_code = int(lines[0].split(" ")[1])

    body_start = raw_response.find("\r\n\r\n")
    if body_start == -1:
        return status_code, {}
    json_body = raw_response[body_start + 4:]
    try:
        parsed_body = json.loads(json_body)
    except json.JSONDecodeError:
        parsed_body = {"_raw": json_body}

    return status_code, parsed_body


def _post_raw(raw_body: bytes, content_length_override: str | None = None) -> tuple[int, dict[str, Any]]:
    headers: dict[str, str] = {"Authorization": f"Bearer {VALID_TOKEN}"}
    if content_length_override is not None:
        headers["Content-Length"] = content_length_override
    else:
        headers["Content-Length"] = str(len(raw_body))

    hdrs_text = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    raw_request = f"POST /v1/execute HTTP/1.1\r\nHost: localhost\r\n{hdrs_text}\r\n".encode() + raw_body
    request_file = BytesIO(raw_request)

    response_buf = BytesIO()

    class CapturingSocket:
        def makefile(self, mode: str, bufsize: int = -1) -> Any:
            if "w" in mode:
                return response_buf
            return request_file

        def sendall(self, data: bytes) -> None:
            response_buf.write(data)

        def settimeout(self, timeout: Any) -> None:
            pass

        def setsockopt(self, *args: Any) -> None:
            pass

        def getsockname(self) -> tuple:
            return ("127.0.0.1", 7890)

        def getpeername(self) -> tuple:
            return ("127.0.0.1", 55000)

    HandlerClass = _handler_class()
    handler = HandlerClass.__new__(HandlerClass)
    handler.request = CapturingSocket()
    handler.client_address = ("127.0.0.1", 55000)
    handler.server = MagicMock()
    handler.setup()
    handler.handle()

    response_buf.seek(0)
    raw_response = response_buf.read().decode()
    lines = raw_response.split("\r\n")
    status_code = int(lines[0].split(" ")[1])
    body_start = raw_response.find("\r\n\r\n")
    json_body_parsed: dict[str, Any] = {}
    if body_start != -1:
        try:
            json_body_parsed = json.loads(raw_response[body_start + 4:])
        except json.JSONDecodeError:
            pass
    return status_code, json_body_parsed


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200_without_auth(self) -> None:
        status, body = _call_handler("GET", "/v1/health", token=None)
        assert status == 200
        assert body["status"] == "ok"
        assert "version" in body

    def test_health_ignores_auth_header(self) -> None:
        status, body = _call_handler("GET", "/v1/health", token="wrong-token")
        assert status == 200


# ---------------------------------------------------------------------------
# GET /v1/bedrock/status
# ---------------------------------------------------------------------------

class TestBedrockStatusEndpoint:
    def test_bedrock_running_true(self) -> None:
        checker = _make_status_checker(running=True)
        status, body = _call_handler("GET", "/v1/bedrock/status", status_checker=checker)
        assert status == 200
        assert body["bedrock_running"] is True

    def test_bedrock_running_false(self) -> None:
        checker = _make_status_checker(running=False)
        status, body = _call_handler("GET", "/v1/bedrock/status", status_checker=checker)
        assert status == 200
        assert body["bedrock_running"] is False

    def test_requires_auth(self) -> None:
        status, body = _call_handler("GET", "/v1/bedrock/status", token=None)
        assert status == 401
        assert body["error"] == "unauthorized"

    def test_wrong_token_returns_401(self) -> None:
        status, _ = _call_handler("GET", "/v1/bedrock/status", token="wrong-token")
        assert status == 401

    def test_passes_container_name_to_checker(self) -> None:
        checker = _make_status_checker(running=True)
        _call_handler("GET", "/v1/bedrock/status", status_checker=checker, bedrock_container_name="my-bedrock")
        checker.is_running.assert_called_once_with("my-bedrock")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestAuthentication:
    def test_missing_auth_header_returns_401(self) -> None:
        status, body = _call_handler("GET", "/v1/status/some-id", token=None)
        assert status == 401
        assert body["error"] == "unauthorized"

    def test_wrong_token_returns_401(self) -> None:
        status, body = _call_handler("GET", "/v1/status/some-id", token="wrong-token")
        assert status == 401

    def test_correct_token_passes(self) -> None:
        store = _make_store()
        status, body = _call_handler("GET", f"/v1/status/{operation_id()}", token=VALID_TOKEN, store=store)
        assert status == 404

    def test_bearer_prefix_required(self) -> None:
        status, body = _call_handler("GET", "/v1/status/x", token=None,
                                     extra_headers={"Authorization": VALID_TOKEN})
        assert status == 401


# ---------------------------------------------------------------------------
# POST /v1/execute validation
# ---------------------------------------------------------------------------

class TestExecuteValidation:
    def _execute(self, body: dict, **kwargs: Any) -> tuple[int, dict]:
        return _call_handler("POST", "/v1/execute", body=body, **kwargs)

    def test_missing_operation_id_returns_400(self) -> None:
        status, body = self._execute({"intended_state": {}})
        assert status == 400
        assert "operation_id" in body["message"].lower()

    def test_missing_intended_state_returns_400(self) -> None:
        status, body = self._execute({"operation_id": _op_id()})
        assert status == 400
        assert "intended_state" in body["message"].lower()

    def test_unknown_intended_state_field_returns_400(self) -> None:
        status, body = self._execute({"operation_id": _op_id(), "intended_state": {"unknown_field": "x"}})
        assert status == 400
        assert "unknown_field" in body["message"]

    def test_health_timeout_too_low_returns_400(self) -> None:
        status, body = self._execute({
            "operation_id": _op_id(),
            "intended_state": {},
            "health_timeout_seconds": 5,
        })
        assert status == 400

    def test_health_timeout_too_high_returns_400(self) -> None:
        status, body = self._execute({
            "operation_id": _op_id(),
            "intended_state": {},
            "health_timeout_seconds": 601,
        })
        assert status == 400

    def test_restart_timeout_too_low_returns_400(self) -> None:
        status, body = self._execute({
            "operation_id": _op_id(),
            "intended_state": {},
            "restart_timeout_seconds": 5,
        })
        assert status == 400

    def test_restart_timeout_too_high_returns_400(self) -> None:
        status, body = self._execute({
            "operation_id": _op_id(),
            "intended_state": {},
            "restart_timeout_seconds": 301,
        })
        assert status == 400

    def test_valid_request_returns_202(self) -> None:
        executor = _make_executor(subprocess_run=fake_run())
        store = _make_store()
        status, body = self._execute(
            execute_request({"server_name": "Test"}),
            store=store,
            executor=executor,
        )
        assert status == 202
        assert body["status"] == "accepted"

    def test_valid_request_default_timeouts(self) -> None:
        executor = _make_executor(subprocess_run=fake_run())
        store = _make_store()
        status, _ = self._execute(
            execute_request(),
            store=store,
            executor=executor,
        )
        assert status == 202


# ---------------------------------------------------------------------------
# Idempotency and conflict
# ---------------------------------------------------------------------------

class TestExecuteIdempotency:
    def test_duplicate_in_flight_returns_409(self) -> None:
        store = _make_store()
        op_id = _op_id()
        rec = store.create(op_id)
        assert rec is not None

        status, body = _call_handler("POST", "/v1/execute",
                                     body={"operation_id": op_id, "intended_state": {}},
                                     store=store)
        assert status == 409
        assert body["error"] == "conflict"

    def test_duplicate_completed_returns_202(self) -> None:
        store = _make_store()
        op_id = _op_id()
        rec = store.create(op_id)
        assert rec is not None
        store.update(op_id, status="done", outcome="ok", completed_at=time.time())

        status, body = _call_handler("POST", "/v1/execute",
                                     body={"operation_id": op_id, "intended_state": {}},
                                     store=store)
        assert status == 202
        assert body["status"] == "accepted"


# ---------------------------------------------------------------------------
# GET /v1/status
# ---------------------------------------------------------------------------

class TestStatus:
    def test_unknown_operation_returns_404(self) -> None:
        store = _make_store()
        status, body = _call_handler("GET", f"/v1/status/{_op_id()}", store=store)
        assert status == 404
        assert body["error"] == "not_found"

    def test_running_operation(self) -> None:
        store = _make_store()
        op_id = _op_id()
        store.create(op_id)

        status, body = _call_handler("GET", f"/v1/status/{op_id}", store=store)
        assert status == 200
        assert body["status"] == "running"
        assert "current_stage" in body

    def test_done_ok_operation(self) -> None:
        store = _make_store()
        op_id = _op_id()
        store.create(op_id)
        store.update(op_id,
                     status="done",
                     outcome="ok",
                     executor_ref="ref-123",
                     health_reached=True,
                     failed_stage=None,
                     detail="ok",
                     error_code=None,
                     exception_type=None,
                     completed_at=time.time())

        status, body = _call_handler("GET", f"/v1/status/{op_id}", store=store)
        assert status == 200
        assert body["status"] == "done"
        assert body["outcome"] == "ok"
        assert body["health_reached"] is True
        assert body["failed_stage"] is None

    def test_done_error_operation(self) -> None:
        store = _make_store()
        op_id = _op_id()
        store.create(op_id)
        store.update(op_id,
                     status="done",
                     outcome="error",
                     executor_ref=None,
                     health_reached=False,
                     failed_stage="health_wait",
                     detail="timed out",
                     error_code="health_probe_timeout",
                     exception_type=None,
                     completed_at=time.time())

        status, body = _call_handler("GET", f"/v1/status/{op_id}", store=store)
        assert status == 200
        assert body["outcome"] == "error"
        assert body["failed_stage"] == "health_wait"
        assert body["error_code"] == "health_probe_timeout"


# ---------------------------------------------------------------------------
# Unknown paths
# ---------------------------------------------------------------------------

class TestUnknownPaths:
    def test_unknown_get_returns_404(self) -> None:
        status, body = _call_handler("GET", "/v1/unknown")
        assert status == 404

    def test_unknown_post_returns_404(self) -> None:
        status, body = _call_handler("POST", "/v1/unknown", body={})
        assert status == 404


# ---------------------------------------------------------------------------
# _read_json_body hardening
# ---------------------------------------------------------------------------

class TestReadJsonBodyHardening:
    def test_invalid_content_length_returns_400(self) -> None:
        status, body = _post_raw(b'{"operation_id":"x"}', content_length_override="abc")
        assert status == 400
        assert "Content-Length" in body.get("message", "")

    def test_negative_content_length_returns_400(self) -> None:
        status, body = _post_raw(b'{"operation_id":"x"}', content_length_override="-1")
        assert status == 400

    def test_body_too_large_returns_400(self) -> None:
        oversized = str(hd.MAX_BODY_BYTES + 1)
        status, body = _post_raw(b'{"operation_id":"x"}', content_length_override=oversized)
        assert status == 400

    def test_non_dict_json_body_returns_400(self) -> None:
        status, body = _post_raw(b'["not", "an", "object"]')
        assert status == 400
        assert "object" in body.get("message", "").lower()


# ---------------------------------------------------------------------------
# intended_state value validation
# ---------------------------------------------------------------------------

class TestIntendedStateValueValidation:
    def _execute(self, intended_state: dict) -> tuple[int, dict]:
        return _call_handler(
            "POST", "/v1/execute",
            body={"operation_id": _op_id(), "intended_state": intended_state},
        )

    def test_newline_in_server_name_returns_400(self) -> None:
        status, body = self._execute({"server_name": "evil\nallow-cheats=true"})
        assert status == 400
        assert "newline" in body.get("message", "").lower()

    def test_invalid_difficulty_enum_returns_400(self) -> None:
        status, body = self._execute({"difficulty": "godmode"})
        assert status == 400
        assert "difficulty" in body.get("message", "")

    def test_valid_difficulty_accepted(self) -> None:
        executor = _make_executor(subprocess_run=fake_run())
        store = _make_store()
        status, body = _call_handler(
            "POST", "/v1/execute",
            body={"operation_id": _op_id(), "intended_state": {"difficulty": "hard"}},
            store=store,
            executor=executor,
        )
        assert status == 202

    def test_non_bool_for_bool_field_returns_400(self) -> None:
        status, body = self._execute({"online_mode": "yes"})
        assert status == 400
        assert "boolean" in body.get("message", "").lower()

    def test_non_int_for_int_field_returns_400(self) -> None:
        status, body = self._execute({"max_players": "ten"})
        assert status == 400
        assert "integer" in body.get("message", "").lower()

    def test_server_port_out_of_range_returns_400(self) -> None:
        status, body = self._execute({"server_port": 65536})
        assert status == 400
        assert "65535" in body.get("message", "")

    def test_server_portv6_zero_returns_400(self) -> None:
        status, body = self._execute({"server_portv6": 0})
        assert status == 400
        assert "65535" in body.get("message", "")

    def test_server_port_valid_boundary_accepted(self) -> None:
        executor = _make_executor(subprocess_run=fake_run())
        store = _make_store()
        status, _ = _call_handler(
            "POST", "/v1/execute",
            body={"operation_id": _op_id(), "intended_state": {"server_port": 65535}},
            store=store,
            executor=executor,
        )
        assert status == 202


# ---------------------------------------------------------------------------
# execute(): gamemode field — acceptance and validation
# ---------------------------------------------------------------------------

class TestGamemodeField:
    """gamemode is an accepted intended_state field with a Bedrock-constrained value set."""

    def _execute(self, intended_state: dict) -> tuple[int, dict]:
        return _call_handler(
            "POST", "/v1/execute",
            body={"operation_id": _op_id(), "intended_state": intended_state},
        )

    def test_survival_gamemode_accepted(self) -> None:
        status, _ = self._execute({"gamemode": "survival"})
        assert status == 202

    def test_creative_gamemode_accepted(self) -> None:
        status, _ = self._execute({"gamemode": "creative"})
        assert status == 202

    def test_adventure_gamemode_accepted(self) -> None:
        status, _ = self._execute({"gamemode": "adventure"})
        assert status == 202

    def test_invalid_gamemode_returns_400(self) -> None:
        status, body = self._execute({"gamemode": "spectator"})
        assert status == 400
        assert body.get("error") == "bad_request"
        assert "gamemode" in body.get("message", "").lower()

    def test_force_gamemode_boolean_is_accepted(self) -> None:
        status, _ = self._execute({"force_gamemode": True})
        assert status == 202

    def test_force_gamemode_non_boolean_is_rejected(self) -> None:
        status, body = self._execute({"force_gamemode": "true"})
        assert status == 400
        assert "boolean" in body.get("message", "").lower()

    def test_uppercase_gamemode_key_rejected_as_unrecognised(self) -> None:
        """The host agent contract uses lowercase keys; GAMEMODE must be rejected."""
        status, body = self._execute({"GAMEMODE": "survival"})
        assert status == 400
        assert "GAMEMODE" in body.get("message", "")

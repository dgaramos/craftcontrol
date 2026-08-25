"""Tests for the CraftControl host agent — bootstrap and facade layer.

Verifies that the ``agent`` module re-exports every public name consumed by
callers that do ``import agent as ha``.  Focused behavioural tests live in:

- ``test_host_agent_store.py``     — OperationRecord / OperationStore
- ``test_host_agent_executor.py``  — OperationExecutor and RakNet probe
- ``test_host_agent_handler.py``   — AgentHandler and HTTP routing
"""
from __future__ import annotations

import json
import struct
import time
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# The agent lives in deploy/host-agent/agent.py — import it directly.
import sys

_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

import agent as ha  # noqa: E402  (import after sys.path manipulation)
from operations import _build_updates
from ports import RestartTimeoutError
from helpers import make_executor as _make_executor_base, FakeProbe as _FakeProbeBase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_TOKEN = "test-secret-token-abcdef1234567890"

_RAKNET_MAGIC = bytes([0x00, 0xFF, 0xFF, 0x00, 0xFE, 0xFE, 0xFE, 0xFE,
                        0xFD, 0xFD, 0xFD, 0xFD, 0x12, 0x34, 0x56, 0x78])


def _make_valid_pong() -> bytes:
    """Build a minimal valid RakNet ID_UNCONNECTED_PONG (35 bytes)."""
    #  byte 0:    0x1C
    #  bytes 1-8: timestamp (8 bytes)
    #  bytes 9-16: server GUID (8 bytes)
    #  bytes 17-32: magic (16 bytes)
    #  bytes 33-34: padding
    header = b'\x1c'
    timestamp = struct.pack('>Q', 0)
    guid = struct.pack('>Q', 42)
    return header + timestamp + guid + _RAKNET_MAGIC + b'\x00\x00'


def _op_id() -> str:
    return str(uuid.uuid4())


def _make_store() -> ha.OperationStore:
    return ha.OperationStore()


class _FakeProbe(_FakeProbeBase):
    """Re-exported from conftest for local use in facade tests."""


def _make_executor(
    subprocess_run: Any = None,
    probe_result: bool = True,
    bedrock_data: str | None = None,
) -> ha.OperationExecutor:
    return _make_executor_base(
        subprocess_run=subprocess_run,
        probe_result=probe_result,
        bedrock_data=bedrock_data,
    )


def _handler_class(token: str = VALID_TOKEN, store: ha.OperationStore | None = None, executor: ha.OperationExecutor | None = None) -> type:
    store = store or _make_store()
    executor = executor or _make_executor()
    return ha.build_handler_class(token, store, executor)


# Minimal fake HTTP transport for unit-testing the handler without a real socket.
class FakeSocket:
    def __init__(self) -> None:
        self._buf = BytesIO()

    def makefile(self, mode: str) -> Any:
        if "w" in mode:
            return self._buf
        return BytesIO()

    def getsockname(self) -> tuple:
        return ("127.0.0.1", 7890)

    def getpeername(self) -> tuple:
        return ("127.0.0.1", 55000)


class FakeRequest:
    """Simulate an incoming HTTP request as a file-like object."""

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
    store: ha.OperationStore | None = None,
    executor: ha.OperationExecutor | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Invoke the AgentHandler directly and return (status_code, response_body)."""
    raw_body = json.dumps(body).encode() if body is not None else b""
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)

    request = FakeRequest(method, path, raw_body, headers)
    response_buf = BytesIO()

    HandlerClass = _handler_class(store=store, executor=executor)

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

    # Parse status line
    lines = raw_response.split("\r\n")
    status_code = int(lines[0].split(" ")[1])

    # Find blank line separating headers from body
    body_start = raw_response.find("\r\n\r\n")
    if body_start == -1:
        return status_code, {}
    json_body = raw_response[body_start + 4:]
    try:
        parsed_body = json.loads(json_body)
    except json.JSONDecodeError:
        parsed_body = {"_raw": json_body}

    return status_code, parsed_body


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
        status, body = _call_handler("GET", f"/v1/status/{_op_id()}", token=VALID_TOKEN, store=store)
        # 404 because op not found, but auth passed
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
        executor = _make_executor(subprocess_run=MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr="")))
        store = _make_store()
        status, body = self._execute(
            {"operation_id": _op_id(), "intended_state": {"server_name": "Test"}},
            store=store,
            executor=executor,
        )
        assert status == 202
        assert body["status"] == "accepted"

    def test_valid_request_default_timeouts(self) -> None:
        """Omitting timeout fields uses defaults (10–600 range)."""
        executor = _make_executor(subprocess_run=MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr="")))
        store = _make_store()
        status, _ = self._execute(
            {"operation_id": _op_id(), "intended_state": {}},
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
        # op is still running

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
        store.update(op_id, status="done", outcome="ok", completed_at=time.monotonic())

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
                     completed_at=time.monotonic())

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
                     completed_at=time.monotonic())

        status, body = _call_handler("GET", f"/v1/status/{op_id}", store=store)
        assert status == 200
        assert body["outcome"] == "error"
        assert body["failed_stage"] == "health_wait"
        assert body["error_code"] == "health_probe_timeout"


# ---------------------------------------------------------------------------
# RakNet probe validation — facade re-export checks
# ---------------------------------------------------------------------------

class TestRakNetProbe:
    def test_valid_pong_accepted(self) -> None:
        pong = _make_valid_pong()
        assert ha._validate_pong(pong) is True

    def test_wrong_first_byte_rejected(self) -> None:
        pong = b'\x01' + _make_valid_pong()[1:]
        assert ha._validate_pong(pong) is False

    def test_too_short_rejected(self) -> None:
        assert ha._validate_pong(b'\x1c' * 10) is False

    def test_wrong_magic_rejected(self) -> None:
        pong = _make_valid_pong()
        # Corrupt a byte in the magic field (bytes 17-32)
        mutated = bytearray(pong)
        mutated[17] = 0xFF
        assert ha._validate_pong(bytes(mutated)) is False

    def test_ping_packet_is_33_bytes(self) -> None:
        ping = ha._build_unconnected_ping()
        assert len(ping) == 33
        assert ping[0] == 0x01
        # Magic at bytes 9-24
        assert ping[9:25] == _RAKNET_MAGIC

    def test_probe_returns_false_on_no_response(self) -> None:
        # Port 19199 is almost certainly not listening in the test environment
        result = ha._probe_bedrock("127.0.0.1", 19199, timeout=0.2)
        assert result is False


# ---------------------------------------------------------------------------
# Operation store eviction
# ---------------------------------------------------------------------------

class TestOperationStoreEviction:
    def test_create_and_get(self) -> None:
        store = ha.OperationStore()
        op_id = _op_id()
        rec = store.create(op_id)
        assert rec is not None
        assert store.get(op_id) is rec

    def test_create_duplicate_returns_none(self) -> None:
        store = ha.OperationStore()
        op_id = _op_id()
        store.create(op_id)
        assert store.create(op_id) is None

    def test_evict_expired_removes_old_completed(self) -> None:
        # Completed at t=1000; clock is now at t=1000+RETENTION+1 → expired.
        completed_at = 1000.0
        now = completed_at + ha.RESULT_RETENTION_SECONDS + 1
        store = ha.OperationStore(time_func=lambda: now)
        op_id = _op_id()
        store.create(op_id)
        store.update(op_id, status="done", completed_at=completed_at)
        store.evict_expired()
        assert store.get(op_id) is None

    def test_evict_does_not_remove_recent_completed(self) -> None:
        # Completed just now; clock has not advanced past the retention window.
        completed_at = 1000.0
        now = completed_at + 1  # only 1 second later — well within retention
        store = ha.OperationStore(time_func=lambda: now)
        op_id = _op_id()
        store.create(op_id)
        store.update(op_id, status="done", completed_at=completed_at)
        store.evict_expired()
        assert store.get(op_id) is not None

    def test_evict_does_not_remove_running(self) -> None:
        store = ha.OperationStore(time_func=lambda: 999999.0)
        op_id = _op_id()
        store.create(op_id)
        # Running records have completed_at=None; eviction must ignore them.
        store.evict_expired()
        assert store.get(op_id) is not None


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

def _post_raw(raw_body: bytes, content_length_override: str | None = None) -> tuple[int, dict[str, Any]]:
    """POST /v1/execute with a raw byte body, optionally overriding Content-Length."""
    headers: dict[str, str] = {"Authorization": f"Bearer {VALID_TOKEN}"}
    if content_length_override is not None:
        headers["Content-Length"] = content_length_override
    else:
        headers["Content-Length"] = str(len(raw_body))

    hdrs_text = "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    raw_request = f"POST /v1/execute HTTP/1.1\r\nHost: localhost\r\n{hdrs_text}\r\n".encode() + raw_body
    from io import BytesIO
    request_file = BytesIO(raw_request)

    class RawFakeRequest:
        def makefile(self, mode: str) -> Any:
            return request_file

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

    from unittest.mock import MagicMock
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
    json_body: dict[str, Any] = {}
    if body_start != -1:
        try:
            json_body = json.loads(raw_response[body_start + 4:])
        except json.JSONDecodeError:
            pass
    return status_code, json_body


class TestReadJsonBodyHardening:
    def test_invalid_content_length_returns_400(self) -> None:
        status, body = _post_raw(b'{"operation_id":"x"}', content_length_override="abc")
        assert status == 400
        assert "Content-Length" in body.get("message", "")

    def test_negative_content_length_returns_400(self) -> None:
        status, body = _post_raw(b'{"operation_id":"x"}', content_length_override="-1")
        assert status == 400

    def test_body_too_large_returns_400(self) -> None:
        oversized = str(ha.MAX_BODY_BYTES + 1)
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
        # Validation happens before the thread starts; 202 means the value passed.
        executor = _make_executor(subprocess_run=MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr="")))
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
        executor = _make_executor(subprocess_run=MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr="")))
        store = _make_store()
        status, _ = _call_handler(
            "POST", "/v1/execute",
            body={"operation_id": _op_id(), "intended_state": {"server_port": 65535}},
            store=store,
            executor=executor,
        )
        assert status == 202


# ---------------------------------------------------------------------------
# agent.py: _load_token and _load_config coverage
# ---------------------------------------------------------------------------

class TestAgentBootstrap:
    def test_load_token_reads_file(self, tmp_path: Path) -> None:
        secret = tmp_path / "token"
        secret.write_text("  my-secret-token  \n")
        token = ha._load_token(str(secret))
        assert token == "my-secret-token"

    def test_load_token_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="Cannot read"):
            ha._load_token(str(tmp_path / "nonexistent"))

    def test_load_token_raises_on_empty_file(self, tmp_path: Path) -> None:
        secret = tmp_path / "token"
        secret.write_text("   \n")
        with pytest.raises(RuntimeError, match="empty"):
            ha._load_token(str(secret))

    def test_load_config_returns_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in [
            "HOST_AGENT_BIND",
            "HOST_AGENT_SECRET_FILE",
            "HOST_AGENT_COMPOSE_PROJECT",
            "HOST_AGENT_COMPOSE_FILE",
            "HOST_AGENT_BEDROCK_DATA",
        ]:
            monkeypatch.delenv(var, raising=False)
        config = ha._load_config()
        assert config["bind"] == ha.BIND_DEFAULT
        assert config["secret_file"] == ha.SECRET_FILE_DEFAULT
        assert config["compose_project"] == ha.COMPOSE_PROJECT_DEFAULT
        assert config["compose_file"] == ha.COMPOSE_FILE_DEFAULT
        assert config["bedrock_data"] == ha.BEDROCK_DATA_DEFAULT

    def test_load_config_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST_AGENT_BIND", "127.0.0.1:9999")
        monkeypatch.setenv("HOST_AGENT_COMPOSE_PROJECT", "my-project")
        config = ha._load_config()
        assert config["bind"] == "127.0.0.1:9999"
        assert config["compose_project"] == "my-project"

    def test_run_starts_and_stops(self, tmp_path: Path) -> None:
        """ha.run must build adapters, start the server, and stop on KeyboardInterrupt."""
        import threading
        from http.server import HTTPServer
        from unittest.mock import patch

        secret = tmp_path / "token"
        secret.write_text("test-token\n")
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": str(tmp_path),
        }

        results: list[str] = []

        class _StopAfterStart(HTTPServer):
            def serve_forever(self, *args: object, **kwargs: object) -> None:
                results.append("started")
                raise KeyboardInterrupt

        with patch("agent.HTTPServer", _StopAfterStart):
            ha.run(bind="127.0.0.1:0", token="tok", config=config)

        assert results == ["started"]


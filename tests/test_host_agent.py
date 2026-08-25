"""Tests for the CraftControl host agent.

Covers:
- Authentication (valid token, missing token, wrong token)
- POST /v1/execute: validation, conflict, idempotent replay, accepted response
- GET /v1/status/{operation_id}: running, done (ok), done (error), not found
- GET /v1/health: unauthenticated, returns version
- Executor stages: prepare (writes server.properties), restart (docker compose),
  health_wait (UDP probe)
- Error paths: prepare failure, restart failure, restart timeout, health timeout
- RakNet probe validation
"""
from __future__ import annotations

import json
import struct
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import HTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# The agent lives in deploy/host-agent/agent.py — import it directly.
import sys, os

_AGENT_DIR = os.path.join(os.path.dirname(__file__), "..", "deploy", "host-agent")
if _AGENT_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_AGENT_DIR))

import agent as ha  # noqa: E402  (import after sys.path manipulation)


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


def _make_executor(subprocess_run: Any = None) -> ha.OperationExecutor:
    config = {
        "compose_project": "minecraft-bedrock",
        "compose_file": "/opt/craftcontrol/docker-compose.yml",
        "bedrock_data": "/tmp/bedrock-test",
    }
    return ha.OperationExecutor(config, subprocess_run=subprocess_run)


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
# Executor: prepare stage
# ---------------------------------------------------------------------------

class TestExecutorPrepare:
    def _run_prepare(self, intended_state: dict, data_dir: Path) -> None:
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/docker-compose.yml",
            "bedrock_data": str(data_dir),
        }
        executor = ha.OperationExecutor(config)
        executor._prepare(intended_state)

    def test_writes_server_properties(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self._run_prepare({"server_name": "My Server", "max_players": 10}, data_dir)
            content = (data_dir / "server.properties").read_text()
            assert "server-name=My Server" in content
            assert "max-players=10" in content

    def test_empty_intended_state_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self._run_prepare({}, data_dir)
            assert not (data_dir / "server.properties").exists()

    def test_missing_data_dir_raises(self) -> None:
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": "/nonexistent/path/bedrock",
        }
        executor = ha.OperationExecutor(config)
        with pytest.raises(RuntimeError, match="not found"):
            executor._prepare({"server_name": "Test"})


# ---------------------------------------------------------------------------
# Executor: restart stage
# ---------------------------------------------------------------------------

class TestExecutorRestart:
    def _make_executor_with_mock(self, returncode: int = 0, stderr: str = "") -> tuple[ha.OperationExecutor, MagicMock]:
        mock_run = MagicMock(return_value=MagicMock(returncode=returncode, stdout="", stderr=stderr))
        config = {
            "compose_project": "minecraft-bedrock",
            "compose_file": "/opt/craftcontrol/docker-compose.yml",
            "bedrock_data": "/tmp/bedrock",
        }
        executor = ha.OperationExecutor(config, subprocess_run=mock_run)
        return executor, mock_run

    def test_successful_restart_returns_ref(self) -> None:
        executor, mock_run = self._make_executor_with_mock()
        ref = executor._restart(60)
        assert "minecraft-bedrock" in ref
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "docker" in cmd
        assert "compose" in cmd
        assert "restart" in cmd

    def test_non_zero_exit_raises(self) -> None:
        executor, _ = self._make_executor_with_mock(returncode=1, stderr="compose error")
        with pytest.raises(RuntimeError, match="compose error"):
            executor._restart(60)

    def test_timeout_propagates(self) -> None:
        mock_run = MagicMock(side_effect=subprocess.TimeoutExpired(["docker"], 60))
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": "/tmp/bd",
        }
        executor = ha.OperationExecutor(config, subprocess_run=mock_run)
        with pytest.raises(subprocess.TimeoutExpired):
            executor._restart(60)


# ---------------------------------------------------------------------------
# Executor: full run integration
# ---------------------------------------------------------------------------

class TestExecutorRun:
    def _run_executor(self, subprocess_run: Any, probe_result: bool, data_dir: Path) -> ha.OperationRecord:
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": str(data_dir),
        }
        executor = ha.OperationExecutor(config, subprocess_run=subprocess_run)
        store = ha.OperationStore()
        op_id = _op_id()
        record = store.create(op_id)
        assert record is not None

        with patch("agent._wait_for_health", return_value=probe_result):
            executor.run(record, store, {"server_name": "Test"}, 10, 30)

        return store.get(op_id)  # type: ignore[return-value]

    def test_success_path(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        with tempfile.TemporaryDirectory() as tmp:
            rec = self._run_executor(mock_run, probe_result=True, data_dir=Path(tmp))
        assert rec.status == "done"
        assert rec.outcome == "ok"
        assert rec.health_reached is True
        assert rec.failed_stage is None
        assert rec.error_code is None

    def test_prepare_failure(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        # Use a non-existent bedrock data dir to trigger prepare failure
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": "/nonexistent/bedrock",
        }
        executor = ha.OperationExecutor(config, subprocess_run=mock_run)
        store = ha.OperationStore()
        op_id = _op_id()
        record = store.create(op_id)
        assert record is not None

        executor.run(record, store, {"server_name": "X"}, 10, 30)

        rec = store.get(op_id)
        assert rec is not None
        assert rec.outcome == "error"
        assert rec.failed_stage == "prepare"
        assert rec.error_code == "preparation_write_failed"

    def test_restart_failure(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="compose error"))
        with tempfile.TemporaryDirectory() as tmp:
            rec = self._run_executor(mock_run, probe_result=False, data_dir=Path(tmp))
        assert rec.outcome == "error"
        assert rec.failed_stage == "restart"
        assert rec.error_code == "restart_command_failed"

    def test_restart_timeout(self) -> None:
        mock_run = MagicMock(side_effect=subprocess.TimeoutExpired(["docker"], 30))
        with tempfile.TemporaryDirectory() as tmp:
            rec = self._run_executor(mock_run, probe_result=False, data_dir=Path(tmp))
        assert rec.outcome == "error"
        assert rec.failed_stage == "restart"
        assert rec.error_code == "restart_timeout"

    def test_health_probe_timeout(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        with tempfile.TemporaryDirectory() as tmp:
            rec = self._run_executor(mock_run, probe_result=False, data_dir=Path(tmp))
        assert rec.outcome == "error"
        assert rec.failed_stage == "health_wait"
        assert rec.error_code == "health_probe_timeout"
        assert rec.health_reached is False


# ---------------------------------------------------------------------------
# RakNet probe validation
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
# Executor: health_wait exception handling
# ---------------------------------------------------------------------------

class TestExecutorRunHealthWaitException:
    def test_invalid_server_port_causes_health_wait_error(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        with tempfile.TemporaryDirectory() as tmp:
            config = {
                "compose_project": "mc",
                "compose_file": "/tmp/dc.yml",
                "bedrock_data": tmp,
            }
            executor = ha.OperationExecutor(config, subprocess_run=mock_run)
            store = ha.OperationStore()
            op_id = _op_id()
            record = store.create(op_id)
            assert record is not None
            executor.run(record, store, {"server_port": "not-a-number"}, 10, 30)
        rec = store.get(op_id)
        assert rec is not None
        assert rec.outcome == "error"
        assert rec.failed_stage == "health_wait"
        assert rec.error_code == "health_wait_error"
        assert rec.completed_at is not None


# ---------------------------------------------------------------------------
# Executor: merge-write server.properties
# ---------------------------------------------------------------------------

class TestExecutorPrepareMerge:
    def _run_prepare(self, intended_state: dict, data_dir: Path) -> None:
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/docker-compose.yml",
            "bedrock_data": str(data_dir),
        }
        executor = ha.OperationExecutor(config)
        executor._prepare(intended_state)

    def test_existing_keys_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            props = data_dir / "server.properties"
            props.write_text("level-name=MyWorld\nserver-port=19132\n")
            self._run_prepare({"server_name": "Updated"}, data_dir)
            content = props.read_text()
            assert "level-name=MyWorld" in content
            assert "server-port=19132" in content
            assert "server-name=Updated" in content

    def test_existing_key_updated_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            props = data_dir / "server.properties"
            props.write_text("server-name=OldName\nmax-players=10\n")
            self._run_prepare({"server_name": "NewName"}, data_dir)
            content = props.read_text()
            assert content.count("server-name=") == 1
            assert "server-name=NewName" in content
            assert "max-players=10" in content

    def test_boolean_rendered_as_lowercase_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self._run_prepare({"allow_cheats": True}, data_dir)
            content = (data_dir / "server.properties").read_text()
            assert "allow-cheats=true" in content

    def test_comments_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            props = data_dir / "server.properties"
            props.write_text("# Generated by Bedrock\nserver-name=Old\n")
            self._run_prepare({"server_name": "New"}, data_dir)
            content = props.read_text()
            assert "# Generated by Bedrock" in content
            assert "server-name=New" in content

    def test_read_oserror_raises_runtime_error(self) -> None:
        """If the existing server.properties cannot be read, _prepare must abort."""
        from unittest.mock import patch, MagicMock
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            props = data_dir / "server.properties"
            props.write_text("server-name=Original\n")
            with patch.object(Path, "read_text", side_effect=OSError("permission denied")):
                with pytest.raises(RuntimeError, match="data loss"):
                    self._run_prepare({"server_name": "Hacked"}, data_dir)
            # Original file must be untouched
            assert "server-name=Original" in props.read_text()

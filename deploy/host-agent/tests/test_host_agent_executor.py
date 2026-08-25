"""Tests for OperationExecutor and RakNet probe functions."""
from __future__ import annotations

import struct
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import sys

_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(_AGENT_DIR) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(_AGENT_DIR))

import executor as ex
import store as st


_RAKNET_MAGIC = bytes([0x00, 0xFF, 0xFF, 0x00, 0xFE, 0xFE, 0xFE, 0xFE,
                        0xFD, 0xFD, 0xFD, 0xFD, 0x12, 0x34, 0x56, 0x78])


def _op_id() -> str:
    return str(uuid.uuid4())


def _make_valid_pong() -> bytes:
    header = b'\x1c'
    timestamp = struct.pack('>Q', 0)
    guid = struct.pack('>Q', 42)
    return header + timestamp + guid + _RAKNET_MAGIC + b'\x00\x00'


# ---------------------------------------------------------------------------
# RakNet probe validation
# ---------------------------------------------------------------------------

class TestRakNetProbe:
    def test_valid_pong_accepted(self) -> None:
        pong = _make_valid_pong()
        assert ex._validate_pong(pong) is True

    def test_wrong_first_byte_rejected(self) -> None:
        pong = b'\x01' + _make_valid_pong()[1:]
        assert ex._validate_pong(pong) is False

    def test_too_short_rejected(self) -> None:
        assert ex._validate_pong(b'\x1c' * 10) is False

    def test_wrong_magic_rejected(self) -> None:
        pong = _make_valid_pong()
        mutated = bytearray(pong)
        mutated[17] = 0xFF
        assert ex._validate_pong(bytes(mutated)) is False

    def test_ping_packet_is_33_bytes(self) -> None:
        ping = ex._build_unconnected_ping()
        assert len(ping) == 33
        assert ping[0] == 0x01
        assert ping[9:25] == _RAKNET_MAGIC

    def test_probe_returns_false_on_no_response(self) -> None:
        result = ex._probe_bedrock("127.0.0.1", 19199, timeout=0.2)
        assert result is False


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
        executor = ex.OperationExecutor(config)
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
        executor = ex.OperationExecutor(config)
        with pytest.raises(RuntimeError, match="not found"):
            executor._prepare({"server_name": "Test"})


# ---------------------------------------------------------------------------
# Executor: restart stage
# ---------------------------------------------------------------------------

class TestExecutorRestart:
    def _make_executor_with_mock(self, returncode: int = 0, stderr: str = "") -> tuple[ex.OperationExecutor, MagicMock]:
        mock_run = MagicMock(return_value=MagicMock(returncode=returncode, stdout="", stderr=stderr))
        config = {
            "compose_project": "minecraft-bedrock",
            "compose_file": "/opt/craftcontrol/docker-compose.yml",
            "bedrock_data": "/tmp/bedrock",
        }
        executor = ex.OperationExecutor(config, subprocess_run=mock_run)
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
        executor = ex.OperationExecutor(config, subprocess_run=mock_run)
        with pytest.raises(subprocess.TimeoutExpired):
            executor._restart(60)


# ---------------------------------------------------------------------------
# Executor: full run integration
# ---------------------------------------------------------------------------

class TestExecutorRun:
    def _run_executor(self, subprocess_run: Any, probe_result: bool, data_dir: Path) -> st.OperationRecord:
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": str(data_dir),
        }
        executor = ex.OperationExecutor(
            config,
            subprocess_run=subprocess_run,
            wait_for_health=lambda host, port, timeout: probe_result,
        )
        store = st.OperationStore()
        op_id = _op_id()
        record = store.create(op_id)
        assert record is not None

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
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": "/nonexistent/bedrock",
        }
        executor = ex.OperationExecutor(config, subprocess_run=mock_run)
        store = st.OperationStore()
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
            executor = ex.OperationExecutor(config, subprocess_run=mock_run)
            store = st.OperationStore()
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
        executor = ex.OperationExecutor(config)
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
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            props = data_dir / "server.properties"
            props.write_text("server-name=Original\n")

            def _failing_reader(path: Path, **kwargs: object) -> str:
                raise OSError("permission denied")

            config = {
                "compose_project": "mc",
                "compose_file": "/tmp/docker-compose.yml",
                "bedrock_data": str(data_dir),
            }
            executor = ex.OperationExecutor(config, read_text=_failing_reader)
            with pytest.raises(RuntimeError, match="data loss"):
                executor._prepare({"server_name": "Hacked"})
            assert "server-name=Original" in props.read_text()

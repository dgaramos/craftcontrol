"""Tests for OperationExecutor (operations layer) and RakNet probe (adapter)."""
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

import store as st
from adapters.docker import DockerComposeRunner
from adapters.filesystem import BedrockFileSystem
from adapters.raknet import _build_unconnected_ping, _probe_bedrock, _validate_pong
from operations import OperationExecutor, _build_updates
from ports import RestartTimeoutError


_RAKNET_MAGIC = bytes([0x00, 0xFF, 0xFF, 0x00, 0xFE, 0xFE, 0xFE, 0xFE,
                        0xFD, 0xFD, 0xFD, 0xFD, 0x12, 0x34, 0x56, 0x78])


def _op_id() -> str:
    return str(uuid.uuid4())


def _make_valid_pong() -> bytes:
    header = b'\x1c'
    timestamp = struct.pack('>Q', 0)
    guid = struct.pack('>Q', 42)
    return header + timestamp + guid + _RAKNET_MAGIC + b'\x00\x00'


class _FakeProbe:
    def __init__(self, result: bool = True) -> None:
        self._result = result

    def wait(self, host: str, port: int, timeout_seconds: int) -> bool:
        return self._result


def _make_executor(
    subprocess_run: Any = None,
    probe_result: bool = True,
    bedrock_data: str = "/tmp/bedrock-test",
) -> OperationExecutor:
    config = {
        "compose_project": "mc",
        "compose_file": "/tmp/docker-compose.yml",
        "bedrock_data": bedrock_data,
    }
    runner = DockerComposeRunner(config, subprocess_run=subprocess_run)
    fs = BedrockFileSystem(bedrock_data)
    probe = _FakeProbe(probe_result)
    return OperationExecutor(runner, fs, probe)


# ---------------------------------------------------------------------------
# RakNet probe validation
# ---------------------------------------------------------------------------

class TestRakNetProbe:
    def test_valid_pong_accepted(self) -> None:
        pong = _make_valid_pong()
        assert _validate_pong(pong) is True

    def test_wrong_first_byte_rejected(self) -> None:
        pong = b'\x01' + _make_valid_pong()[1:]
        assert _validate_pong(pong) is False

    def test_too_short_rejected(self) -> None:
        assert _validate_pong(b'\x1c' * 10) is False

    def test_wrong_magic_rejected(self) -> None:
        pong = _make_valid_pong()
        mutated = bytearray(pong)
        mutated[17] = 0xFF
        assert _validate_pong(bytes(mutated)) is False

    def test_ping_packet_is_33_bytes(self) -> None:
        ping = _build_unconnected_ping()
        assert len(ping) == 33
        assert ping[0] == 0x01
        assert ping[9:25] == _RAKNET_MAGIC

    def test_probe_returns_false_on_no_response(self) -> None:
        result = _probe_bedrock("127.0.0.1", 19199, timeout=0.2)
        assert result is False


# ---------------------------------------------------------------------------
# BedrockFileSystem: write_server_properties
# ---------------------------------------------------------------------------

class TestBedrockFileSystemWrite:
    def test_writes_server_properties(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            fs = BedrockFileSystem(str(data_dir))
            updates = _build_updates({"server_name": "My Server", "max_players": 10})
            fs.write_server_properties(updates)
            content = (data_dir / "server.properties").read_text()
            assert "server-name=My Server" in content
            assert "max-players=10" in content

    def test_empty_updates_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            fs = BedrockFileSystem(str(data_dir))
            fs.write_server_properties({})
            assert not (data_dir / "server.properties").exists()

    def test_missing_data_dir_raises(self) -> None:
        fs = BedrockFileSystem("/nonexistent/path/bedrock")
        with pytest.raises(RuntimeError, match="not found"):
            fs.write_server_properties({"server-name": "Test"})


# ---------------------------------------------------------------------------
# DockerComposeRunner: restart
# ---------------------------------------------------------------------------

class TestDockerComposeRunnerRestart:
    _CONFIG = {
        "compose_project": "minecraft-bedrock",
        "compose_file": "/opt/craftcontrol/docker-compose.yml",
        "bedrock_data": "/tmp/bedrock",
    }

    def test_successful_restart_returns_ref(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        runner = DockerComposeRunner(self._CONFIG, subprocess_run=mock_run)
        ref = runner.restart(60)
        assert "minecraft-bedrock" in ref
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "docker" in cmd
        assert "compose" in cmd
        assert "restart" in cmd

    def test_non_zero_exit_raises(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="compose error"))
        runner = DockerComposeRunner(self._CONFIG, subprocess_run=mock_run)
        with pytest.raises(RuntimeError, match="compose error"):
            runner.restart(60)

    def test_timeout_raises_restart_timeout_error(self) -> None:
        mock_run = MagicMock(side_effect=subprocess.TimeoutExpired(["docker"], 60))
        runner = DockerComposeRunner(
            {"compose_project": "mc", "compose_file": "/tmp/dc.yml", "bedrock_data": "/tmp/bd"},
            subprocess_run=mock_run,
        )
        with pytest.raises(RestartTimeoutError):
            runner.restart(60)


# ---------------------------------------------------------------------------
# OperationExecutor: full run integration
# ---------------------------------------------------------------------------

class TestOperationExecutorRun:
    def _run_executor(self, subprocess_run: Any, probe_result: bool, data_dir: Path) -> st.OperationRecord:
        executor = _make_executor(
            subprocess_run=subprocess_run,
            probe_result=probe_result,
            bedrock_data=str(data_dir),
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
        executor = _make_executor(
            subprocess_run=mock_run,
            probe_result=False,
            bedrock_data="/nonexistent/bedrock",
        )
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
# OperationExecutor: health_wait exception handling
# ---------------------------------------------------------------------------

class TestOperationExecutorRunHealthWaitException:
    def test_invalid_server_port_causes_health_wait_error(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        with tempfile.TemporaryDirectory() as tmp:
            executor = _make_executor(
                subprocess_run=mock_run,
                probe_result=True,
                bedrock_data=tmp,
            )
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
# BedrockFileSystem: merge-write server.properties
# ---------------------------------------------------------------------------

class TestBedrockFileSystemMerge:
    def _run_prepare(self, intended_state: dict, data_dir: Path) -> None:
        fs = BedrockFileSystem(str(data_dir))
        updates = _build_updates(intended_state)
        fs.write_server_properties(updates)

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

            fs = BedrockFileSystem(str(data_dir), read_text=_failing_reader)
            with pytest.raises(RuntimeError, match="data loss"):
                fs.write_server_properties({"server-name": "Hacked"})
            assert "server-name=Original" in props.read_text()

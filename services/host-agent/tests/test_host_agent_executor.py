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
from adapters.docker import DockerComposeRunner, DockerContainerStatus
from adapters.filesystem import BedrockFileSystem
from adapters.raknet import (
    _build_unconnected_ping,
    _next_probe_delay,
    _probe_bedrock,
    _validate_pong,
    _wait_for_health,
    RakNetHealthProbe,
)
from operations import OperationExecutor, _build_updates
from ports import ContainerRunner, FileSystem, HealthProbe, RestartTimeoutError
from helpers import make_executor as _make_executor, FakeProbe as _FakeProbe


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

    def test_configured_service_used_in_command_and_ref(self) -> None:
        """compose_service from config must appear in the restart command and the returned ref."""
        config = {
            "compose_project": "minecraft-bedrock",
            "compose_file": "/opt/craftcontrol/docker-compose.yml",
            "compose_service": "minecraft-bedrock",
            "bedrock_data": "/tmp/bedrock",
        }
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        runner = DockerComposeRunner(config, subprocess_run=mock_run)
        ref = runner.restart(60)
        cmd = mock_run.call_args[0][0]
        assert "minecraft-bedrock" in cmd
        assert cmd[-1] == "minecraft-bedrock"
        assert "minecraft-bedrock_restart_" in ref

    def test_default_service_used_when_compose_service_absent(self) -> None:
        """When compose_service is absent the default 'minecraft-server' is used."""
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": "/tmp/bd",
        }
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        runner = DockerComposeRunner(config, subprocess_run=mock_run)
        ref = runner.restart(60)
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == "minecraft-server"
        assert "minecraft-server_restart_" in ref


# ---------------------------------------------------------------------------
# DockerContainerStatus: is_running
# ---------------------------------------------------------------------------

class TestDockerContainerStatus:
    def test_running_container_returns_true(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="true\n"))
        checker = DockerContainerStatus(subprocess_run=mock_run)
        assert checker.is_running("minecraft-server") is True

    def test_stopped_container_returns_false(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="false\n"))
        checker = DockerContainerStatus(subprocess_run=mock_run)
        assert checker.is_running("minecraft-server") is False

    def test_nonzero_exit_returns_false(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
        checker = DockerContainerStatus(subprocess_run=mock_run)
        assert checker.is_running("minecraft-server") is False

    def test_timeout_returns_false(self) -> None:
        mock_run = MagicMock(side_effect=subprocess.TimeoutExpired(["docker"], 10))
        checker = DockerContainerStatus(subprocess_run=mock_run)
        assert checker.is_running("minecraft-server") is False

    def test_os_error_returns_false(self) -> None:
        mock_run = MagicMock(side_effect=OSError("docker not found"))
        checker = DockerContainerStatus(subprocess_run=mock_run)
        assert checker.is_running("minecraft-server") is False


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


# ---------------------------------------------------------------------------
# BedrockFileSystem: write error paths and mode preservation
# ---------------------------------------------------------------------------

class TestBedrockFileSystemWriteErrors:
    def test_preserves_existing_file_identity_and_mode(self) -> None:
        """Updates must retain the Bedrock runtime's inode and file mode."""
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            props = data_dir / "server.properties"
            props.write_text("server-name=Old\n")
            props.chmod(0o600)
            original_stat = props.stat()
            fs = BedrockFileSystem(str(data_dir))
            fs.write_server_properties({"server-name": "New"})
            assert "server-name=New" in props.read_text()
            assert oct(props.stat().st_mode)[-3:] == "600"
            assert props.stat().st_ino == original_stat.st_ino
            assert props.stat().st_uid == original_stat.st_uid
            assert props.stat().st_gid == original_stat.st_gid

    def test_write_oserror_raises_runtime_error(self) -> None:
        """An OSError during the tmp-file write must surface as RuntimeError."""
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            fs = BedrockFileSystem(str(data_dir))
            # Patch Path.write_text to fail after the file-list is built.
            original_write_text = Path.write_text

            call_count = [0]

            def _failing_write(self_path: Path, *args: object, **kwargs: object) -> None:
                if self_path.suffix == ".tmp":
                    call_count[0] += 1
                    raise OSError("disk full")
                return original_write_text(self_path, *args, **kwargs)

            with patch.object(Path, "write_text", _failing_write):
                with pytest.raises(RuntimeError, match="Failed to write"):
                    fs.write_server_properties({"server-name": "X"})

    def test_tmp_unlink_oserror_is_swallowed(self) -> None:
        """An OSError from tmp_file.unlink must not shadow the original write error."""
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            fs = BedrockFileSystem(str(data_dir))
            original_write_text = Path.write_text
            original_unlink = Path.unlink

            def _fail_write(self_path: Path, *args: object, **kwargs: object) -> None:
                if self_path.suffix == ".tmp":
                    raise OSError("disk full")
                return original_write_text(self_path, *args, **kwargs)

            def _fail_unlink(self_path: Path, *args: object, **kwargs: object) -> None:
                raise OSError("cannot unlink")

            with patch.object(Path, "write_text", _fail_write):
                with patch.object(Path, "unlink", _fail_unlink):
                    with pytest.raises(RuntimeError, match="Failed to write"):
                        fs.write_server_properties({"server-name": "X"})


# ---------------------------------------------------------------------------
# RakNet: _wait_for_health loop branches
# ---------------------------------------------------------------------------

class TestWaitForHealth:
    def test_backoff_doubles_and_stops_at_ten_seconds(self) -> None:
        delay = 1.0
        delays = []
        for _ in range(6):
            delays.append(delay)
            delay = _next_probe_delay(delay)
        assert delays == [1.0, 2.0, 4.0, 8.0, 10, 10]

    def test_returns_true_immediately_on_first_probe(self) -> None:
        """If the first probe succeeds _wait_for_health returns True."""
        result = _wait_for_health("127.0.0.1", 19132, 5, probe=lambda *_: True)
        assert result is True

    def test_returns_false_when_timeout_expires(self) -> None:
        """With a 0-second timeout the loop exits without a successful probe."""
        result = _wait_for_health("127.0.0.1", 19199, 0)
        assert result is False

    def test_sleeps_and_retries(self) -> None:
        """The loop uses the first backoff delay before the second probe."""
        call_count = [0]
        sleeps: list[float] = []

        def _probe(host: str, port: int, timeout: float) -> bool:
            call_count[0] += 1
            return call_count[0] >= 2

        result = _wait_for_health("127.0.0.1", 19132, 5, probe=_probe, sleep=sleeps.append)
        assert result is True
        assert call_count[0] == 2
        assert sleeps == [1]

    def test_backoff_never_sleeps_past_health_deadline(self) -> None:
        now = [0.0]
        sleeps: list[float] = []

        def _sleep(delay: float) -> None:
            sleeps.append(delay)
            now[0] += delay

        result = _wait_for_health(
            "127.0.0.1", 19132, 5,
            probe=lambda *_: False,
            monotonic=lambda: now[0],
            sleep=_sleep,
        )

        assert result is False
        assert sleeps == [1, 2, 2]
        assert now[0] == 5

    def test_raknet_health_probe_wait_delegates(self) -> None:
        """RakNetHealthProbe.wait must delegate to _wait_for_health."""
        with patch("adapters.raknet._wait_for_health", return_value=True) as mock_wfh:
            probe = RakNetHealthProbe()
            result = probe.wait("127.0.0.1", 19132, 10)
        assert result is True
        mock_wfh.assert_called_once_with("127.0.0.1", 19132, 10)

    def test_probe_returns_true_on_valid_pong(self) -> None:
        """_probe_bedrock returns True when the socket receives a valid pong."""
        valid_pong = _make_valid_pong()

        class _FakeSocket:
            def settimeout(self, t: float) -> None:
                pass

            def sendto(self, data: bytes, addr: tuple) -> None:
                pass

            def recvfrom(self, bufsize: int) -> tuple:
                return valid_pong, ("127.0.0.1", 19132)

            def close(self) -> None:
                pass

        with patch("adapters.raknet.socket.socket", return_value=_FakeSocket()):
            result = _probe_bedrock("127.0.0.1", 19132, 0.5)
        assert result is True


# ---------------------------------------------------------------------------
# ports.py: Protocol stub method coverage
# ---------------------------------------------------------------------------

class TestProtocolStubs:
    def test_container_runner_stub_is_callable(self) -> None:
        """The Protocol stub body must be executable for coverage."""
        result = ContainerRunner.restart(None, 0)  # type: ignore[arg-type]
        assert result is None

    def test_file_system_stub_is_callable(self) -> None:
        result = FileSystem.write_server_properties(None, {})  # type: ignore[arg-type]
        assert result is None

    def test_health_probe_stub_is_callable(self) -> None:
        result = HealthProbe.wait(None, "", 0, 0)  # type: ignore[arg-type]
        assert result is None


# ---------------------------------------------------------------------------
# operations.py: empty intended_state skips write
# ---------------------------------------------------------------------------

class TestGamemodeIntendedState:
    """gamemode in intended_state must be written to server.properties."""

    def _run_with_gamemode(self, gamemode: str) -> tuple[str, str]:
        """Run an operation with the given gamemode and return (outcome, properties_content)."""
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        with tempfile.TemporaryDirectory() as tmp:
            executor = _make_executor(subprocess_run=mock_run, probe_result=True, bedrock_data=tmp)
            store = st.OperationStore()
            op_id = _op_id()
            record = store.create(op_id)
            assert record is not None
            executor.run(record, store, {"gamemode": gamemode}, 10, 30)
            rec = store.get(op_id)
            assert rec is not None
            content = (Path(tmp) / "server.properties").read_text()
            return rec.outcome, content

    def test_gamemode_survival_written_to_server_properties(self) -> None:
        outcome, content = self._run_with_gamemode("survival")
        assert outcome == "ok"
        assert "gamemode=survival" in content

    def test_gamemode_creative_written_to_server_properties(self) -> None:
        outcome, content = self._run_with_gamemode("creative")
        assert outcome == "ok"
        assert "gamemode=creative" in content

    def test_gamemode_adventure_written_to_server_properties(self) -> None:
        outcome, content = self._run_with_gamemode("adventure")
        assert outcome == "ok"
        assert "gamemode=adventure" in content

    def test_force_gamemode_written_to_server_properties(self) -> None:
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        with tempfile.TemporaryDirectory() as tmp:
            executor = _make_executor(subprocess_run=mock_run, probe_result=True, bedrock_data=tmp)
            store = st.OperationStore()
            record = store.create(_op_id())
            assert record is not None
            executor.run(record, store, {"force_gamemode": True}, 10, 30)
            completed = store.get(record.operation_id)
            assert completed is not None
            assert completed.outcome == "ok"
            content = (Path(tmp) / "server.properties").read_text()
        assert "force-gamemode=true" in content


class TestOperationExecutorEmptyState:
    def test_empty_intended_state_skips_write_and_succeeds(self) -> None:
        """When intended_state is empty the prepare stage logs and continues."""
        mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
        with tempfile.TemporaryDirectory() as tmp:
            executor = _make_executor(subprocess_run=mock_run, probe_result=True, bedrock_data=tmp)
            store = st.OperationStore()
            op_id = _op_id()
            record = store.create(op_id)
            assert record is not None
            executor.run(record, store, {}, 10, 30)
        rec = store.get(op_id)
        assert rec is not None
        assert rec.outcome == "ok"
        assert rec.failed_stage is None

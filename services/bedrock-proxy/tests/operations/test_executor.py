"""Tests for the operation orchestration use case."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import proxy.store.store as st
from helpers import fake_run, make_executor, operation_id


class TestOperationExecutorRun:
    def _run(self, subprocess_run: Any, probe_result: bool, data_dir: Path) -> st.OperationRecord:
        executor = make_executor(subprocess_run=subprocess_run, probe_result=probe_result, bedrock_data=str(data_dir))
        store = st.OperationStore()
        record = store.create(operation_id())
        assert record is not None
        executor.run(record, store, {"server_name": "Test"}, 10, 30)
        result = store.get(record.operation_id)
        assert result is not None
        return result

    def test_success_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = self._run(fake_run(), True, Path(tmp))
        assert record.status == "done"
        assert record.outcome == "ok"
        assert record.health_reached is True

    def test_prepare_failure(self) -> None:
        executor = make_executor(subprocess_run=fake_run(), bedrock_data="/nonexistent/bedrock")
        store = st.OperationStore()
        record = store.create(operation_id())
        assert record is not None
        executor.run(record, store, {"server_name": "X"}, 10, 30)
        assert record.failed_stage == "prepare"
        assert record.error_code == "preparation_write_failed"

    def test_restart_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = self._run(fake_run(returncode=1, stderr="compose error"), False, Path(tmp))
        assert record.failed_stage == "restart"
        assert record.error_code == "restart_command_failed"

    def test_restart_timeout(self) -> None:
        runner = MagicMock(side_effect=subprocess.TimeoutExpired(["docker"], 30))
        with tempfile.TemporaryDirectory() as tmp:
            record = self._run(runner, False, Path(tmp))
        assert record.failed_stage == "restart"
        assert record.error_code == "restart_timeout"

    def test_health_probe_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = self._run(fake_run(), False, Path(tmp))
        assert record.failed_stage == "health_wait"
        assert record.error_code == "health_probe_timeout"

    def test_invalid_server_port_is_health_wait_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = make_executor(subprocess_run=fake_run(), bedrock_data=tmp)
            store = st.OperationStore()
            record = store.create(operation_id())
            assert record is not None
            executor.run(record, store, {"server_port": "not-a-number"}, 10, 30)
        assert record.failed_stage == "health_wait"
        assert record.error_code == "health_wait_error"


class TestOperationIntendedState:
    def test_gamemode_is_written_to_properties(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = make_executor(subprocess_run=fake_run(), bedrock_data=tmp)
            store = st.OperationStore()
            record = store.create(operation_id())
            assert record is not None
            executor.run(record, store, {"gamemode": "creative"}, 10, 30)
            content = (Path(tmp) / "server.properties").read_text()
        assert record.outcome == "ok"
        assert "gamemode=creative" in content

    def test_empty_intended_state_succeeds_without_properties_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            executor = make_executor(subprocess_run=fake_run(), bedrock_data=tmp)
            store = st.OperationStore()
            record = store.create(operation_id())
            assert record is not None
            executor.run(record, store, {}, 10, 30)
            properties_exists = (Path(tmp) / "server.properties").exists()
        assert record.outcome == "ok"
        assert not properties_exists

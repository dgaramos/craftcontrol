"""Tests for the Bedrock filesystem adapter."""
from __future__ import annotations

from pathlib import Path

import pytest

from proxy.adapters.filesystem import BedrockFileSystem
from proxy.runtime.operations import _build_updates


class TestBedrockFileSystem:
    def test_writes_new_server_properties(self, tmp_path: Path) -> None:
        filesystem = BedrockFileSystem(str(tmp_path))
        filesystem.write_server_properties(_build_updates({"server_name": "My Server", "max_players": 10}))
        content = (tmp_path / "server.properties").read_text()
        assert "server-name=My Server" in content
        assert "max-players=10" in content

    def test_preserves_existing_file_identity_and_mode(self, tmp_path: Path) -> None:
        properties = tmp_path / "server.properties"
        properties.write_text("# Generated\nserver-name=Old\nlevel-name=World\n")
        properties.chmod(0o600)
        original = properties.stat()
        BedrockFileSystem(str(tmp_path)).write_server_properties({"server-name": "New"})
        assert "server-name=New" in properties.read_text()
        assert "level-name=World" in properties.read_text()
        assert properties.stat().st_ino == original.st_ino
        assert oct(properties.stat().st_mode)[-3:] == "600"

    def test_empty_updates_do_not_write(self, tmp_path: Path) -> None:
        BedrockFileSystem(str(tmp_path)).write_server_properties({})
        assert not (tmp_path / "server.properties").exists()

    def test_missing_data_dir_raises(self) -> None:
        with pytest.raises(RuntimeError, match="not found"):
            BedrockFileSystem("/nonexistent/path/bedrock").write_server_properties({"server-name": "Test"})

    def test_read_failure_preserves_original_file(self, tmp_path: Path) -> None:
        properties = tmp_path / "server.properties"
        properties.write_text("server-name=Original\n")

        def failing_read(path: Path, **kwargs: object) -> str:
            raise OSError("permission denied")

        filesystem = BedrockFileSystem(str(tmp_path), read_text=failing_read)
        with pytest.raises(RuntimeError, match="data loss"):
            filesystem.write_server_properties({"server-name": "Hacked"})
        assert properties.read_text() == "server-name=Original\n"

    def test_new_file_write_failure_uses_injected_write_text(self, tmp_path: Path) -> None:
        def failing_write(path: Path, text: str, **kwargs: object) -> None:
            raise OSError("disk full")

        filesystem = BedrockFileSystem(str(tmp_path), write_text=failing_write)
        with pytest.raises(RuntimeError, match="Failed to write"):
            filesystem.write_server_properties({"server-name": "X"})

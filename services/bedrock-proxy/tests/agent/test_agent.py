"""Tests for the host-agent bootstrap and composition facade."""
from __future__ import annotations

from pathlib import Path
import pytest

import agent as ha


class TestAgentBootstrap:
    def test_load_token_reads_file(self, tmp_path: Path) -> None:
        secret = tmp_path / "token"
        secret.write_text("  my-secret-token  \n")
        assert ha._load_token(str(secret)) == "my-secret-token"

    def test_load_token_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="Cannot read"):
            ha._load_token(str(tmp_path / "nonexistent"))

    def test_load_token_raises_on_empty_file(self, tmp_path: Path) -> None:
        secret = tmp_path / "token"
        secret.write_text("   \n")
        with pytest.raises(RuntimeError, match="empty"):
            ha._load_token(str(secret))

    def test_load_config_returns_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for var in ["HOST_AGENT_BIND", "HOST_AGENT_SECRET_FILE", "HOST_AGENT_COMPOSE_PROJECT", "HOST_AGENT_COMPOSE_FILE", "HOST_AGENT_BEDROCK_DATA"]:
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

    def test_load_config_compose_service_empty_string_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST_AGENT_COMPOSE_SERVICE", "")
        assert ha._load_config()["compose_service"] == ha.COMPOSE_SERVICE_DEFAULT

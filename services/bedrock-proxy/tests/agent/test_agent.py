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
        for var in ha.CANONICAL_ENVIRONMENT_VARIABLES | ha.LEGACY_ENVIRONMENT_VARIABLES:
            monkeypatch.delenv(var, raising=False)
        config = ha._load_config()
        assert config["bind"] == ha.BIND_DEFAULT
        assert config["secret_file"] == ha.SECRET_FILE_DEFAULT
        assert config["compose_project"] == ha.COMPOSE_PROJECT_DEFAULT
        assert config["compose_file"] == ha.COMPOSE_FILE_DEFAULT
        assert config["bedrock_data"] == ha.BEDROCK_DATA_DEFAULT

    def test_load_config_reads_canonical_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BEDROCK_PROXY_BIND", "127.0.0.1:9999")
        monkeypatch.setenv("BEDROCK_PROXY_COMPOSE_PROJECT", "my-project")
        config = ha._load_config()
        assert config["bind"] == "127.0.0.1:9999"
        assert config["compose_project"] == "my-project"

    def test_load_config_accepts_legacy_env_vars_with_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("HOST_AGENT_BIND", "127.0.0.1:9999")
        assert ha._load_config()["bind"] == "127.0.0.1:9999"
        assert "HOST_AGENT_BIND is deprecated; use BEDROCK_PROXY_BIND" in caplog.text

    def test_load_config_prefers_canonical_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOST_AGENT_BIND", "127.0.0.1:9999")
        monkeypatch.setenv("BEDROCK_PROXY_BIND", "127.0.0.1:7890")
        assert ha._load_config()["bind"] == "127.0.0.1:7890"

    def test_load_config_compose_service_empty_string_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BEDROCK_PROXY_COMPOSE_SERVICE", "")
        assert ha._load_config()["compose_service"] == ha.COMPOSE_SERVICE_DEFAULT

    def test_systemd_environment_keys_are_consumed_by_agent(self) -> None:
        unit = (
            Path(__file__).parents[4]
            / "deploy"
            / "bedrock-proxy"
            / "systemd"
            / "craftcontrol-bedrock-proxy.service"
        )
        keys = {
            line.removeprefix("Environment=").split("=", 1)[0]
            for line in unit.read_text().splitlines()
            if line.startswith("Environment=")
        }
        assert keys
        assert keys <= ha.CANONICAL_ENVIRONMENT_VARIABLES


class TestAgentComposition:
    def test_run_wires_the_transport_aware_probe(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.adapters.readiness import TransportAwareHealthProbe

        captured: dict[str, object] = {}

        class FakeServer:
            def __init__(self, address: tuple[str, int], handler_class: type) -> None:
                captured["address"] = address
                captured["handler_class"] = handler_class

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

        monkeypatch.setattr(ha, "HTTPServer", FakeServer)
        config = {
            "compose_project": "mc",
            "compose_file": "/tmp/dc.yml",
            "bedrock_data": str(tmp_path),
            "bedrock_container": "bedrock",
            "db": ":memory:",
            "workers": "1",
            "queue_size": "1",
        }
        ha.run(bind="127.0.0.1:0", token="t", config=config)
        executor = captured["handler_class"].executor
        assert isinstance(executor._probe, TransportAwareHealthProbe)
        assert executor._probe.container == "bedrock"

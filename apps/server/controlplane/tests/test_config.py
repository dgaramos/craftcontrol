from __future__ import annotations

import pytest

from src.core.config import Settings

PROXY_VARIABLES = (
    "URL",
    "TOKEN_FILE",
    "HEALTH_TIMEOUT_SECONDS",
    "RESTART_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def _clear_proxy_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither naming generation may leak in from the ambient environment."""
    for name in PROXY_VARIABLES:
        monkeypatch.delenv(f"BEDROCK_PROXY_{name}", raising=False)
        monkeypatch.delenv(f"HOST_AGENT_{name}", raising=False)


def test_settings_uses_default_compose_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINECRAFT_COMPOSE_PROJECT", raising=False)
    assert Settings.from_env().compose_project == "minecraft-bedrock"


def test_settings_uses_five_minute_host_agent_health_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOST_AGENT_HEALTH_TIMEOUT_SECONDS", raising=False)
    assert Settings.from_env().host_agent_health_timeout_seconds == 300


def test_settings_accepts_host_agent_health_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST_AGENT_HEALTH_TIMEOUT_SECONDS", "420")
    assert Settings.from_env().host_agent_health_timeout_seconds == 420


def test_settings_uses_three_minute_host_agent_restart_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOST_AGENT_RESTART_TIMEOUT_SECONDS", raising=False)
    assert Settings.from_env().host_agent_restart_timeout_seconds == 180


def test_settings_accepts_host_agent_restart_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST_AGENT_RESTART_TIMEOUT_SECONDS", "240")
    assert Settings.from_env().host_agent_restart_timeout_seconds == 240


@pytest.mark.parametrize("value", ["not-a-number", "9", "601"])
def test_settings_rejects_invalid_host_agent_health_timeout(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("HOST_AGENT_HEALTH_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError, match="HOST_AGENT_HEALTH_TIMEOUT_SECONDS"):
        Settings.from_env()


@pytest.mark.parametrize("value", ["not-a-number", "9", "301"])
def test_settings_rejects_invalid_host_agent_restart_timeout(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("HOST_AGENT_RESTART_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError, match="HOST_AGENT_RESTART_TIMEOUT_SECONDS"):
        Settings.from_env()


def test_settings_accepts_valid_compose_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINECRAFT_COMPOSE_PROJECT", "family-bedrock_1")
    assert Settings.from_env().compose_project == "family-bedrock_1"


@pytest.mark.parametrize("value", ["", "Minecraft", "minecraft bedrock", "minecraft/bedrock"])
def test_settings_rejects_invalid_compose_project(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("MINECRAFT_COMPOSE_PROJECT", value)
    with pytest.raises(ValueError, match="valid Docker Compose project name"):
        Settings.from_env()


def test_settings_reads_the_bedrock_proxy_variable_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """The deployed Compose file sets BEDROCK_PROXY_*; those must configure the adapter."""
    monkeypatch.setenv("BEDROCK_PROXY_URL", "http://host-gateway:7890")
    monkeypatch.setenv("BEDROCK_PROXY_TOKEN_FILE", "/run/bedrock-proxy-token")
    monkeypatch.setenv("BEDROCK_PROXY_RESTART_TIMEOUT_SECONDS", "240")
    monkeypatch.setenv("BEDROCK_PROXY_HEALTH_TIMEOUT_SECONDS", "420")
    settings = Settings.from_env()
    assert settings.host_agent_url == "http://host-gateway:7890"
    assert settings.host_agent_token_file == "/run/bedrock-proxy-token"
    assert settings.host_agent_restart_timeout_seconds == 240
    assert settings.host_agent_health_timeout_seconds == 420


def test_settings_prefers_the_bedrock_proxy_name_over_the_legacy_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOST_AGENT_URL", "http://legacy:7890")
    monkeypatch.setenv("BEDROCK_PROXY_URL", "http://host-gateway:7890")
    assert Settings.from_env().host_agent_url == "http://host-gateway:7890"


def test_settings_rejects_an_invalid_bedrock_proxy_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEDROCK_PROXY_URL", "host-gateway:7890")
    with pytest.raises(ValueError, match="BEDROCK_PROXY_URL"):
        Settings.from_env()


def test_split_compose_environment_configures_the_proxy_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard: the Compose environment must reach Settings.

    Renaming the variables in docker-compose.split.yml without renaming them
    here silently drops the backend back to direct Docker operations.
    """
    import re
    from pathlib import Path

    split = Path(__file__).resolve().parents[3].parent / "docker-compose.split.yml"
    backend = split.read_text().split("  craftcontrol-backend:", 1)[1].split("  craftcontrol-frontend:", 1)[0]
    for name, raw in re.findall(r"^      ([A-Z_]+): (.+)$", backend, re.MULTILINE):
        # Compose resolves ${VAR:-default} from the deployment .env; the
        # documented defaults are what production runs with.
        value = re.sub(r"\$\{[A-Z_]+:-([^}]*)\}", r"\1", raw.strip().strip('"'))
        monkeypatch.setenv(name, value)

    settings = Settings.from_env()
    assert settings.host_agent_url == "http://host-gateway:7890"
    assert settings.host_agent_token_file == "/run/bedrock-proxy-token"
    assert settings.host_agent_restart_timeout_seconds == 180

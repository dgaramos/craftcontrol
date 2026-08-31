from __future__ import annotations

import pytest

from minecraft_manager.config import Settings


def test_settings_uses_default_compose_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINECRAFT_COMPOSE_PROJECT", raising=False)
    assert Settings.from_env().compose_project == "minecraft-bedrock"


def test_settings_uses_five_minute_host_agent_health_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOST_AGENT_HEALTH_TIMEOUT_SECONDS", raising=False)
    assert Settings.from_env().host_agent_health_timeout_seconds == 300


def test_settings_accepts_host_agent_health_timeout_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOST_AGENT_HEALTH_TIMEOUT_SECONDS", "420")
    assert Settings.from_env().host_agent_health_timeout_seconds == 420


@pytest.mark.parametrize("value", ["not-a-number", "9", "601"])
def test_settings_rejects_invalid_host_agent_health_timeout(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("HOST_AGENT_HEALTH_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError, match="HOST_AGENT_HEALTH_TIMEOUT_SECONDS"):
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

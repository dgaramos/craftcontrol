from __future__ import annotations

import pytest

from minecraft_manager.config import Settings


def test_settings_uses_default_compose_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MINECRAFT_COMPOSE_PROJECT", raising=False)
    assert Settings.from_env().compose_project == "minecraft-bedrock"


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

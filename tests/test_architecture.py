from pathlib import Path

import pytest

from minecraft_manager import frontend_root
from minecraft_manager.events import EventBroker
from minecraft_manager.files import ServerFiles
from minecraft_manager.players import PlayerService
from minecraft_manager.repository import StateRepository


class FakeConsole:
    def __init__(self) -> None:
        self.operators: list[tuple[str, bool]] = []

    def set_operator(self, player: str, enabled: bool) -> None:
        self.operators.append((player, enabled))


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_path_resolves_in_source_and_packaged_image_layouts() -> None:
    assert frontend_root(ROOT / "apps" / "backend" / "minecraft_manager") == ROOT / "apps" / "frontend"
    assert frontend_root(Path("/app/minecraft_manager")) == Path("/app/apps/frontend")


def test_frontend_and_backend_have_explicit_application_boundaries() -> None:
    assert (ROOT / "apps" / "frontend" / "static" / "app.js").is_file()
    assert (ROOT / "apps" / "backend" / "minecraft_manager" / "composition.py").is_file()
    assert (ROOT / "minecraft_manager").resolve() == (ROOT / "apps" / "backend" / "minecraft_manager").resolve()
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "./apps/backend/minecraft_manager:/app/minecraft_manager:ro" in compose


def test_player_use_cases_accept_injected_boundary_adapters(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "manager.db")
    repository.initialize()
    console = FakeConsole()
    service = PlayerService(
        repository,
        ServerFiles(tmp_path / ".env", tmp_path / "server.properties"),
        console,  # type: ignore[arg-type]
        EventBroker(repository),
    )

    service.observe_presence("VonCrush", True, "123")
    service.set_operator("VonCrush", True)

    assert console.operators == [("VonCrush", True)]
    assert service.list_profiles()[0]["operator"]


def test_architecture_document_defines_composition_and_dependency_direction() -> None:
    document = (ROOT / "docs" / "architecture.md").read_text()
    assert "composition root" in document
    assert "Dependency direction" in document
    assert "modular monolith" in document

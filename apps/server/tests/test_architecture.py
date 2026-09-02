from pathlib import Path

import pytest

from minecraft_manager import frontend_root
from minecraft_manager.events import EventBroker
from minecraft_manager.files import ServerFiles
from minecraft_manager.players import PlayerService, SQLitePlayerRepository
from minecraft_manager.repository import StateRepository


class FakeConsole:
    def __init__(self) -> None:
        self.operators: list[tuple[str, bool]] = []

    def set_operator(self, player: str, enabled: bool) -> None:
        self.operators.append((player, enabled))


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_path_resolves_in_source_and_packaged_image_layouts() -> None:
    assert frontend_root(ROOT / "apps" / "server" / "minecraft_manager") == ROOT / "apps" / "client"
    assert frontend_root(Path("/app/minecraft_manager")) == Path("/app/apps/client")


def test_frontend_and_backend_have_explicit_application_boundaries() -> None:
    assert (ROOT / "apps" / "client" / "static" / "app.js").is_file()
    assert (ROOT / "apps" / "server" / "minecraft_manager" / "composition.py").is_file()
    assert (ROOT / "minecraft_manager").resolve() == (ROOT / "apps" / "server" / "minecraft_manager").resolve()
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "./apps/server/minecraft_manager:/app/minecraft_manager:ro" in compose


def test_player_use_cases_accept_injected_boundary_adapters(tmp_path: Path) -> None:
    db_path = tmp_path / "manager.db"
    state_repo = StateRepository(db_path)
    state_repo.initialize()
    player_repo = SQLitePlayerRepository(db_path)
    console = FakeConsole()
    service = PlayerService(
        player_repo,
        ServerFiles(tmp_path / ".env", tmp_path / "server.properties"),
        console,  # type: ignore[arg-type]
        EventBroker(state_repo),
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


def test_telemetry_compatibility_shims_are_retired() -> None:
    package = ROOT / "apps" / "server" / "minecraft_manager"
    retired = (
        "telemetry.py",
        "telemetry_service.py",
        "telemetry_repository.py",
        "telemetry_installer.py",
    )

    assert all(not (package / name).exists() for name in retired)
    assert "get_db" not in (ROOT / "docs" / "development-setup.md").read_text()

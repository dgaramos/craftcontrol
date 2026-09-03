from pathlib import Path

import pytest

from src import frontend_root
from src.core.events import EventBroker
from src.server.files import ServerFiles
from src.players import PlayerService, SQLitePlayerRepository
from src.core.repository import StateRepository


class FakeConsole:
    def __init__(self) -> None:
        self.operators: list[tuple[str, bool]] = []

    def set_operator(self, player: str, enabled: bool) -> None:
        self.operators.append((player, enabled))


ROOT = Path(__file__).resolve().parents[4]

ROOT_MODULE_ALLOWLIST = frozenset(
    {
        "__init__.py",  # Flask package bootstrap
        "cli.py",  # command-line entry point
        "composition.py",  # production composition root
        "ports.py",  # shared structural contracts
        "version.py",  # process version and startup timestamp
    }
)


def _unexpected_root_python_modules(package: Path) -> set[str]:
    return {
        path.name
        for path in package.glob("*.py")
        if path.stem.isidentifier()
    } - ROOT_MODULE_ALLOWLIST


def test_frontend_path_resolves_in_source_and_packaged_image_layouts() -> None:
    assert frontend_root(ROOT / "apps" / "server" / "controlplane") == ROOT / "apps" / "client"
    assert frontend_root(Path("/app/controlplane")) == Path("/app/apps/client")


def test_frontend_and_backend_have_explicit_application_boundaries() -> None:
    assert (ROOT / "apps" / "client" / "static" / "app.js").is_file()
    assert (ROOT / "apps" / "server" / "controlplane" / "src" / "composition.py").is_file()
    assert not (ROOT / "minecraft_manager").exists()
    assert not (ROOT / "controlplane").exists()
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "./apps/server/controlplane/src:/app/src:ro" in compose


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
    package = ROOT / "apps" / "server" / "controlplane" / "src"
    retired = (
        "bedrock.py",
        "config.py",
        "migrations.py",
        "schema.py",
        "_db.py",
        "events.py",
        "files.py",
        "telemetry.py",
        "telemetry_service.py",
        "telemetry_repository.py",
        "telemetry_installer.py",
    )

    assert all(not (package / name).exists() for name in retired)
    assert "get_db" not in (ROOT / "docs" / "development-setup.md").read_text()


def test_backend_package_root_rejects_unapproved_python_modules() -> None:
    package = ROOT / "apps" / "server" / "controlplane" / "src"

    assert _unexpected_root_python_modules(package) == set()


def test_backend_module_placement_policy_is_documented_for_agents() -> None:
    required = (
        "Backend module placement",
        "New backend implementation modules must not be created",
        "package root",
        "Compatibility facades may preserve an existing import path only",
        "core/",
        "server/",
        "players/",
        "telemetry/",
        "operations/",
        "runtime/",
        "http/",
        "auth/",
        "audit/",
        "allowlist",
        "reviewed",
    )

    for document in (ROOT / "AGENTS.md", ROOT / "CLAUDE.md"):
        content = document.read_text()
        assert all(text in content for text in required), document

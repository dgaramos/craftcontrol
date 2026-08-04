import tempfile
import unittest
from pathlib import Path

from minecraft_manager.events import EventBroker
from minecraft_manager.files import ServerFiles
from minecraft_manager.players import PlayerService
from minecraft_manager.repository import StateRepository


class FakeConsole:
    def __init__(self) -> None:
        self.operators: list[tuple[str, bool]] = []

    def set_operator(self, player: str, enabled: bool) -> None:
        self.operators.append((player, enabled))


class ArchitectureTest(unittest.TestCase):
    def test_player_use_cases_accept_injected_boundary_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = StateRepository(root / "manager.db")
            repository.initialize()
            console = FakeConsole()
            service = PlayerService(
                repository,
                ServerFiles(root / ".env", root / "server.properties"),
                console,  # type: ignore[arg-type]
                EventBroker(repository),
            )

            service.observe_presence("VonCrush", True, "123")
            service.set_operator("VonCrush", True)

            self.assertEqual(console.operators, [("VonCrush", True)])
            self.assertTrue(service.list_profiles()[0]["operator"])

    def test_architecture_document_defines_composition_and_dependency_direction(self) -> None:
        root = Path(__file__).resolve().parents[1]
        document = (root / "docs" / "architecture.md").read_text()
        self.assertIn("composition root", document)
        self.assertIn("Dependency direction", document)
        self.assertIn("modular monolith", document)

import tempfile
import unittest
from pathlib import Path

from minecraft_manager.files import ServerFiles
from minecraft_manager.repository import StateRepository
from minecraft_manager.services import ManagerService


class FakeBedrock:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def send(self, parts: list[str]) -> None:
        self.commands.append(parts)

    def send_and_read(self, parts: list[str]) -> str:
        self.commands.append(parts)
        return "The time is 34"


class FakeDocker:
    pass


class TimeActionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.bedrock = FakeBedrock()
        self.service = ManagerService(
            StateRepository(root / "state.db"),
            ServerFiles(root / ".env", root / "server.properties"),
            self.bedrock,  # type: ignore[arg-type]
            FakeDocker(),  # type: ignore[arg-type]
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_supports_every_named_time_preset(self) -> None:
        for preset in ManagerService.TIME_PRESETS:
            self.service.time_action("preset", {"value": preset})
            self.assertEqual(self.bedrock.commands[-1], ["time", "set", preset])

    def test_reset_days_sets_time_to_zero(self) -> None:
        self.service.time_action("reset-days", {})
        self.assertEqual(self.bedrock.commands[-1], ["time", "set", "0"])

    def test_rejects_exact_time_outside_one_day(self) -> None:
        with self.assertRaisesRegex(ValueError, "fora do intervalo"):
            self.service.time_action("set", {"value": 24001})

    def test_queries_day_count(self) -> None:
        result = self.service.time_action("query", {"value": "day"})
        self.assertEqual(result["value"], 34)
        self.assertEqual(self.bedrock.commands[-1], ["time", "query", "day"])

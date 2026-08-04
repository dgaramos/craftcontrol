import tempfile
import unittest
import json
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

    def set_operator(self, player: str, enabled: bool) -> None:
        self.commands.append(["op" if enabled else "deop", player])

    def request_telemetry_snapshot(self) -> str:
        payloads = (
            {"schema": 1, "sequence": 12, "type": "snapshot.started", "timestamp": 1, "player": None, "data": {"players": 0}},
            {"schema": 1, "sequence": 12, "type": "snapshot.finished", "timestamp": 1, "player": None, "data": {}},
        )
        return "\n".join(f"[Scripting] [BEDROCK_TELEMETRY] {json.dumps(payload)}" for payload in payloads)


class FakeDocker:
    pass


class TimeActionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.bedrock = FakeBedrock()
        repository = StateRepository(root / "state.db")
        repository.initialize()
        self.service = ManagerService(
            repository,
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

    def test_operator_access_can_be_enabled_and_disabled(self) -> None:
        self.service.set_player_operator("VonCrush", True)
        self.assertEqual(self.bedrock.commands[-1], ["op", "VonCrush"])
        self.assertEqual(self.service.players()[0]["name"], "VonCrush")
        self.assertTrue(self.service.players()[0]["operator"])
        self.service.set_player_operator("VonCrush", False)
        self.assertEqual(self.bedrock.commands[-1], ["deop", "VonCrush"])

    def test_player_disconnect_preserves_profile_and_closes_session(self) -> None:
        self.service.player_event("Nicole", True, "123")
        self.service.player_event("Nicole", False, "123")
        profile = self.service.players()[0]
        self.assertEqual(profile["name"], "Nicole")
        self.assertFalse(profile["online"])
        self.assertEqual(profile["sessions_count"], 1)

    def test_death_counter_is_deduplicated(self) -> None:
        self.service.player_event("Nicole", True, "123")
        raw = "[INFO] Nicole was slain by Zombie"
        self.assertTrue(self.service.player_death_event("Nicole", "was slain by Zombie", raw))
        self.assertFalse(self.service.player_death_event("Nicole", "was slain by Zombie", raw))
        self.assertEqual(self.service.players()[0]["deaths_count"], 1)

    def test_snapshot_response_is_ingested_without_log_stream(self) -> None:
        self.service.request_telemetry_snapshot_async("test")
        import time
        deadline = time.time() + 2
        while time.time() < deadline and not self.service.state().get("telemetry"):
            time.sleep(0.01)
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "connected")
        self.assertEqual(telemetry["sequence"], "12")

    def test_manual_snapshot_is_ingested_synchronously(self) -> None:
        self.assertEqual(self.service.request_telemetry_snapshot("manual"), 2)
        self.assertEqual(self.service.state()["telemetry"]["last_topic"], "snapshot.finished")

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
        self.telemetry_output: str | None = None

    def send(self, parts: list[str]) -> None:
        self.commands.append(parts)

    def send_and_read(self, parts: list[str]) -> str:
        self.commands.append(parts)
        return "The time is 34"

    def set_operator(self, player: str, enabled: bool) -> None:
        self.commands.append(["op" if enabled else "deop", player])

    def request_telemetry_snapshot(self) -> str:
        if self.telemetry_output is not None:
            return self.telemetry_output
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
        self.assertEqual(telemetry["status"], "healthy")
        self.assertEqual(telemetry["sequence"], "12")

    def test_manual_snapshot_is_ingested_synchronously(self) -> None:
        self.assertEqual(self.service.request_telemetry_snapshot("manual"), 2)
        self.assertEqual(self.service.state()["telemetry"]["last_topic"], "snapshot.finished")

    def test_empty_snapshot_response_is_degraded_instead_of_stuck_syncing(self) -> None:
        self.bedrock.telemetry_output = ""
        self.assertEqual(self.service.request_telemetry_snapshot("test-empty"), 0)
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "degraded")
        self.assertEqual(telemetry["last_error"], "snapshot returned no envelopes")

    def test_sequence_gap_degrades_and_requests_reconciliation(self) -> None:
        requested: list[str] = []
        self.service.request_telemetry_snapshot_async = requested.append  # type: ignore[method-assign]
        self.service.telemetry_event({"schema": 1, "sequence": 10, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:stone"}})
        self.service.telemetry_event({"schema": 1, "sequence": 13, "type": "block.broken", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:dirt"}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "degraded")
        self.assertEqual(telemetry["gap_count"], "1")
        self.assertEqual(telemetry["missing_events"], "2")
        self.assertEqual(telemetry["last_gap"], "11-12")
        self.assertEqual(requested, ["sequence-gap"])

    def test_snapshot_repairs_degraded_state_and_stale_delta_is_rejected(self) -> None:
        self.service.request_telemetry_snapshot_async = lambda reason: None  # type: ignore[method-assign]
        self.service.telemetry_event({"schema": 1, "sequence": 10, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
        self.service.telemetry_event({"schema": 1, "sequence": 12, "type": "block.broken", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {}})
        self.service.telemetry_event({"schema": 1, "sequence": 11, "type": "block.placed", "timestamp": 3, "player": {"name": "VonCrush"}, "data": {}})
        self.assertEqual(self.service.state()["telemetry"]["sequence"], "12")
        self.service.telemetry_event({"schema": 1, "sequence": 12, "type": "snapshot.started", "timestamp": 4, "player": None, "data": {"players": 0}})
        self.service.telemetry_event({"schema": 1, "sequence": 12, "type": "snapshot.finished", "timestamp": 5, "player": None, "data": {}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "healthy")
        self.assertEqual(telemetry["last_error"], "")
        self.assertIn("last_snapshot_at", telemetry)

    def test_pack_sequence_reset_requests_snapshot(self) -> None:
        requested: list[str] = []
        self.service.request_telemetry_snapshot_async = requested.append  # type: ignore[method-assign]
        self.service.telemetry_event({"schema": 1, "sequence": 20, "type": "block.broken", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {}})
        self.service.telemetry_event({"schema": 1, "sequence": 1, "type": "telemetry.started", "timestamp": 2, "player": None, "data": {"version": "0.2.0"}})
        telemetry = self.service.state()["telemetry"]
        self.assertEqual(telemetry["status"], "syncing")
        self.assertEqual(telemetry["reset_count"], "1")
        self.assertEqual(requested, ["pack-started"])

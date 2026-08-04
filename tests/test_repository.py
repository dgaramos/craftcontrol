import tempfile
import unittest
from pathlib import Path

from minecraft_manager.repository import StateRepository


class StateRepositoryTest(unittest.TestCase):
    def test_builds_api_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.store("settings", {"SERVER_NAME": "MalavaziRamos"}, "test")
            repository.store("server", {"online": "1", "max_players": "10"}, "test")
            repository.replace("players", {"Nicole": "online"}, "test")

            snapshot = repository.snapshot()
            self.assertEqual(snapshot["settings"]["SERVER_NAME"], "MalavaziRamos")
            self.assertEqual(snapshot["players"], ["Nicole"])
            self.assertEqual(snapshot["online"], 1)
            self.assertEqual(snapshot["max_players"], 10)
            self.assertEqual(snapshot["domains"]["settings"]["freshness"], "fresh")

    def test_records_and_replays_events(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            event_id = repository.record_event("player.connected", "test", {"player": "VonCrush"})
            events = repository.events_after(0)
            self.assertEqual(events[0]["id"], event_id)
            self.assertEqual(events[0]["topic"], "player.connected")
            self.assertEqual(events[0]["payload"]["player"], "VonCrush")

    def test_keeps_offline_player_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("VonCrush", True, "99", occurred_at=100)
            repository.observe_player("VonCrush", False, "99", occurred_at=160)
            profile = repository.player_profiles()[0]
            self.assertFalse(profile["online"])
            self.assertEqual(profile["sessions_count"], 1)
            self.assertEqual(profile["total_play_seconds"], 60)
            detail = repository.player_profile(profile["id"])
            self.assertEqual([event["topic"] for event in detail["history"]], ["player.disconnected", "player.connected"])
            self.assertEqual(detail["sessions"][0]["duration_seconds"], 60)
            self.assertFalse(detail["sessions"][0]["active"])
            self.assertEqual(detail["permission"], "member")

    def test_xuid_unifies_a_temporary_name_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("Nicole", True, occurred_at=100)
            repository.observe_player("Nicole", True, "123", occurred_at=110)
            self.assertEqual(len(repository.player_profiles()), 1)
            public_id = repository.player_profiles()[0]["id"]
            self.assertNotIn("123", public_id)
            self.assertIsNotNone(repository.player_profile(public_id))

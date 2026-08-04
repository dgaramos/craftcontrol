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

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

    def test_global_activity_is_filtered_paginated_and_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("VonCrush", True, "private-xuid")
            repository.observe_player("VonCrush", False, "private-xuid")
            repository.record_player_death(
                "VonCrush", "was slain by Zombie", "private raw log evidence", "bedrock-log", "death-1",
            )
            repository.set_player_permission("VonCrush", "operator")

            first = repository.player_activity("all", "VonCrush", "all", "", 0, 1, 2)
            self.assertEqual(first["total"], 4)
            self.assertEqual(first["pages"], 2)
            self.assertEqual(len(first["events"]), 2)
            serialized = str(first)
            self.assertNotIn("private-xuid", serialized)
            self.assertNotIn("private raw log evidence", serialized)

            deaths = repository.player_activity("deaths", "", "server", "", 0, 1, 25)
            self.assertEqual(deaths["total"], 1)
            self.assertEqual(deaths["summary"]["deaths"], 1)
            self.assertEqual(deaths["events"][0]["details"]["cause"], "was slain by Zombie")
            searched = repository.player_activity("deaths", "", "all", "zombie", 0, 1, 25)
            self.assertEqual(searched["total"], 1)

    def test_global_activity_distinguishes_structured_deaths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("Nicole", True, "456")
            repository.ingest_telemetry({
                "schema": 1, "sequence": 1, "type": "entity.died", "timestamp": 1,
                "player": {"name": "Nicole"},
                "data": {"victim": "Nicole", "killerType": "minecraft:zombie", "cause": "entityAttack"},
            })
            structured = repository.player_activity("deaths", "", "structured", "", 0, 1, 25)
            self.assertEqual(structured["total"], 1)
            self.assertEqual(structured["events"][0]["source"], "behavior-pack")
            self.assertEqual(structured["events"][0]["details"]["killer"], "minecraft:zombie")

    def test_global_activity_prefers_structured_death_without_deleting_derived_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.db"
            repository = StateRepository(path)
            repository.initialize()
            repository.observe_player("Nicole", True, "456")
            repository.record_player_death("Nicole", "died", "raw evidence", "bedrock-log", "derived")
            repository.ingest_telemetry({
                "schema": 1, "sequence": 2, "type": "entity.died", "timestamp": 1,
                "player": {"name": "Nicole"},
                "data": {"victim": "Nicole", "killerType": "minecraft:zombie", "cause": "entityAttack"},
            })
            result = repository.player_activity("deaths", "", "all", "", 0, 1, 25)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["events"][0]["source"], "behavior-pack")
            import sqlite3
            with sqlite3.connect(path) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM player_history WHERE topic='player.death'").fetchone()[0], 2)

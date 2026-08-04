import json
import tempfile
import unittest
from pathlib import Path

from minecraft_manager.repository import StateRepository
from minecraft_manager.telemetry import parse_telemetry_line


class TelemetryTest(unittest.TestCase):
    def test_parses_prefixed_content_log(self) -> None:
        payload = {"schema": 1, "sequence": 7, "type": "snapshot.finished", "timestamp": 1, "player": None, "data": {}}
        line = f"[Scripting][warning]-[BEDROCK_TELEMETRY] {json.dumps(payload)}"
        self.assertEqual(parse_telemetry_line(line), payload)

    def test_rejects_unknown_topic(self) -> None:
        line = '[BEDROCK_TELEMETRY] {"schema":1,"sequence":1,"type":"shell","player":null,"data":{}}'
        with self.assertRaisesRegex(ValueError, "topic"):
            parse_telemetry_line(line)

    def test_snapshot_is_persisted_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("VonCrush", True, "99")
            event = {"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"deaths": 3, "blocksBroken": 42}}
            self.assertEqual(repository.ingest_telemetry(event), (True, ["VonCrush"]))
            self.assertEqual(repository.ingest_telemetry(event), (False, []))
            profile = repository.player_profiles()[0]
            self.assertEqual(profile["deaths_count"], 3)
            self.assertEqual(profile["deaths_source"], "behavior-pack")
            self.assertEqual(profile["telemetry"]["blocksBroken"], 42)

    def test_telemetry_follows_profile_when_xuid_becomes_known(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            event = {"schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 1, "player": {"name": "Nicole"}, "data": {"mobKills": 9}}
            repository.ingest_telemetry(event)
            repository.observe_player("Nicole", True, "123")
            profiles = repository.player_profiles()
            self.assertEqual(len(profiles), 1)
            self.assertEqual(profiles[0]["telemetry"]["mobKills"], 9)

    def test_behavior_pack_death_is_saved_in_player_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("VonCrush", True, "99")
            repository.ingest_telemetry({"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"deaths": 0}})
            death = {"schema": 1, "sequence": 9, "type": "entity.died", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {"victim": "VonCrush", "victimType": "minecraft:player", "killer": None, "killerType": "minecraft:zombie", "projectileType": None, "cause": "entityAttack"}}
            self.assertEqual(repository.ingest_telemetry(death), (True, ["VonCrush"]))
            profile = repository.player_profile(repository.player_profiles()[0]["id"])
            deaths = [event for event in profile["history"] if event["topic"] == "player.death"]
            self.assertEqual(len(deaths), 1)
            self.assertEqual(deaths[0]["source"], "behavior-pack")
            self.assertEqual(deaths[0]["payload"]["killerType"], "minecraft:zombie")
            self.assertIsNotNone(profile["last_death_at"])

    def test_new_snapshot_at_same_sequence_replaces_authoritative_totals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            first = {"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"blocksBroken": 10}}
            second = {**first, "timestamp": 2, "data": {"blocksBroken": 15}}
            self.assertTrue(repository.ingest_telemetry(first)[0])
            self.assertTrue(repository.ingest_telemetry(second)[0])
            self.assertEqual(repository.player_profiles()[0]["telemetry"]["blocksBroken"], 15)

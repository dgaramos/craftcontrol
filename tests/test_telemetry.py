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

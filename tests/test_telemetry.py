import json
import sqlite3
from pathlib import Path

import pytest

from minecraft_manager.repository import StateRepository
from minecraft_manager.telemetry import parse_telemetry_line


def test_parses_actual_bedrock_content_log_fixture() -> None:
    fixture = Path(__file__).with_name("fixtures") / "bedrock_content_log.txt"
    envelopes = [parse_telemetry_line(line) for line in fixture.read_text().splitlines()]
    assert [item["type"] for item in envelopes if item] == [
        "telemetry.started", "snapshot.started", "snapshot.player", "snapshot.finished",
    ]


def test_parses_prefixed_content_log() -> None:
    payload = {"schema": 1, "sequence": 7, "type": "snapshot.finished", "timestamp": 1, "player": None, "data": {}}
    line = f"[Scripting][warning]-[BEDROCK_TELEMETRY] {json.dumps(payload)}"
    assert parse_telemetry_line(line) == payload


def test_rejects_unknown_topic() -> None:
    line = '[BEDROCK_TELEMETRY] {"schema":1,"sequence":1,"type":"shell","player":null,"data":{}}'
    with pytest.raises(ValueError, match="topic"):
        parse_telemetry_line(line)


def test_snapshot_is_persisted_and_deduplicated(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    repository = StateRepository(path)
    repository.initialize()
    repository.observe_player("VonCrush", True, "99")
    event = {"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"deaths": 3, "blocksBroken": 42}}
    assert repository.ingest_telemetry(event) == (True, ["VonCrush"])
    assert repository.ingest_telemetry(event) == (False, [])
    profile = repository.player_profiles()[0]
    assert profile["deaths_count"] == 3
    assert profile["deaths_source"] == "behavior-pack"
    assert profile["telemetry"]["blocksBroken"] == 42
    with sqlite3.connect(path) as connection:
        stored = json.loads(connection.execute("SELECT payload FROM telemetry_events").fetchone()[0])
    assert stored == event


def test_telemetry_follows_profile_when_xuid_becomes_known(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    event = {"schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 1, "player": {"name": "Nicole"}, "data": {"mobKills": 9}}
    repository.ingest_telemetry(event)
    repository.observe_player("Nicole", True, "123")
    profiles = repository.player_profiles()
    assert len(profiles) == 1
    assert profiles[0]["telemetry"]["mobKills"] == 9


def test_behavior_pack_death_is_saved_in_player_history(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    repository.observe_player("VonCrush", True, "99")
    repository.ingest_telemetry({"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"deaths": 0}})
    death = {"schema": 1, "sequence": 9, "type": "entity.died", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {"victim": "VonCrush", "victimType": "minecraft:player", "killer": None, "killerType": "minecraft:zombie", "projectileType": None, "cause": "entityAttack"}}
    assert repository.ingest_telemetry(death) == (True, ["VonCrush"])
    profile = repository.player_profile(repository.player_profiles()[0]["id"])
    deaths = [event for event in profile["history"] if event["topic"] == "player.death"]
    assert len(deaths) == 1
    assert deaths[0]["source"] == "behavior-pack"
    assert deaths[0]["payload"]["killerType"] == "minecraft:zombie"
    assert profile["last_death_at"] is not None


def test_respawn_and_dimension_change_are_saved_in_player_history(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    repository.observe_player("VonCrush", True, "99")
    repository.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "player.respawned", "timestamp": 1,
        "player": {"name": "VonCrush"}, "data": {},
    })
    repository.ingest_telemetry({
        "schema": 1, "sequence": 2, "type": "player.dimension.changed", "timestamp": 2,
        "player": {"name": "VonCrush"},
        "data": {"from": "minecraft:overworld", "to": "minecraft:nether"},
    })
    activity = repository.player_activity("all", "", "structured", "", 0, 1, 25)
    assert activity["summary"]["respawns"] == 1
    assert activity["summary"]["dimensions"] == 1
    dimension = next(event for event in activity["events"] if event["topic"] == "player.dimension.changed")
    assert dimension["details"]["from_dimension"] == "minecraft:overworld"
    assert dimension["details"]["to_dimension"] == "minecraft:nether"


def test_new_snapshot_at_same_sequence_replaces_authoritative_totals(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    first = {"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"blocksBroken": 10}}
    second = {**first, "timestamp": 2, "data": {"blocksBroken": 15}}
    assert repository.ingest_telemetry(first)[0]
    assert repository.ingest_telemetry(second)[0]
    assert repository.player_profiles()[0]["telemetry"]["blocksBroken"] == 15


def test_block_deltas_update_bounded_type_maps_and_are_idempotent(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    repository.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"blocksBroken": 4, "blocksPlaced": 2, "brokenByType": {"minecraft:stone": 4}, "placedByType": {}},
    })
    broken = {"schema": 1, "sequence": 2, "type": "block.broken", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:diamond_ore"}}
    placed = {"schema": 1, "sequence": 3, "type": "block.placed", "timestamp": 3, "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:oak_planks"}}
    assert repository.ingest_telemetry(broken)[0]
    assert not repository.ingest_telemetry(broken)[0]
    assert repository.ingest_telemetry(placed)[0]
    stats = repository.player_profiles()[0]["telemetry"]
    assert stats["blocksBroken"] == 5
    assert stats["brokenByType"]["minecraft:diamond_ore"] == 1
    assert stats["blocksPlaced"] == 3
    assert stats["placedByType"]["minecraft:oak_planks"] == 1


def test_batched_block_deltas_update_totals_maps_and_daily_buckets(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    repository = StateRepository(path)
    repository.initialize()
    repository.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"blocksBroken": 4, "blocksPlaced": 2, "brokenByType": {}, "placedByType": {}},
    })
    batch = {
        "schema": 1, "sequence": 2, "type": "blocks.changed", "timestamp": 2,
        "player": {"name": "VonCrush"},
        "data": {
            "broken": {"total": 3, "byType": {"minecraft:stone": 2, "minecraft:diamond_ore": 1}},
            "placed": {"total": 2, "byType": {"minecraft:oak_planks": 2}},
        },
    }
    assert repository.ingest_telemetry(batch)[0]
    assert not repository.ingest_telemetry(batch)[0]
    stats = repository.player_profiles()[0]["telemetry"]
    assert stats["blocksBroken"] == 7
    assert stats["brokenByType"]["minecraft:stone"] == 2
    assert stats["blocksPlaced"] == 4
    with sqlite3.connect(path) as connection:
        daily = connection.execute("SELECT blocks_broken,blocks_placed FROM player_daily").fetchone()
    assert daily == (3, 2)

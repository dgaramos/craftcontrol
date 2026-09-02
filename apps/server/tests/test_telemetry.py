import json
import sqlite3
from pathlib import Path

import pytest

from minecraft_manager.players.repository import SQLitePlayerRepository
from minecraft_manager.core.repository import StateRepository
from minecraft_manager.telemetry.telemetry import parse_telemetry_line
from minecraft_manager.telemetry.repository import SQLiteTelemetryRepository
from minecraft_manager.core.sqlite import sqlite_diagnostics


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "state.db"
    StateRepository(path).initialize()
    return path


@pytest.fixture
def player_repo(db_path: Path) -> SQLitePlayerRepository:
    return SQLitePlayerRepository(db_path)


@pytest.fixture
def telemetry_repo(db_path: Path) -> SQLiteTelemetryRepository:
    return SQLiteTelemetryRepository(db_path)


def test_parses_actual_bedrock_content_log_fixture() -> None:
    fixture = Path(__file__).with_name("fixtures") / "bedrock_content_log.txt"
    envelopes = [parse_telemetry_line(line) for line in fixture.read_text().splitlines()]
    assert [item["type"] for item in envelopes if item] == [
        "telemetry.started", "snapshot.started", "snapshot.player", "snapshot.finished",
    ]


def test_sqlite_diagnostics_report_connection_metrics(telemetry_repo: SQLiteTelemetryRepository) -> None:
    telemetry_repo.snapshot()
    diagnostics = sqlite_diagnostics()
    assert diagnostics["connections"] >= 1
    assert diagnostics["wait_ms_average"] >= 0
    assert diagnostics["contention_failures"] >= 0


def test_parses_prefixed_content_log() -> None:
    payload = {"schema": 1, "sequence": 7, "type": "snapshot.finished", "timestamp": 1, "player": None, "data": {}}
    line = f"[Scripting][warning]-[BEDROCK_TELEMETRY] {json.dumps(payload)}"
    assert parse_telemetry_line(line) == payload


def test_rejects_unknown_topic() -> None:
    line = '[BEDROCK_TELEMETRY] {"schema":1,"sequence":1,"type":"shell","player":null,"data":{}}'
    with pytest.raises(ValueError, match="topic"):
        parse_telemetry_line(line)


def test_snapshot_is_persisted_and_deduplicated(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
    db_path: Path,
) -> None:
    player_repo.observe_player("VonCrush", True, "99")
    event = {"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"deaths": 3, "blocksBroken": 42}}
    assert telemetry_repo.ingest_telemetry(event) == (True, ["VonCrush"])
    assert telemetry_repo.ingest_telemetry(event) == (False, [])
    profile = player_repo.player_profiles()[0]
    assert profile["deaths_count"] == 3
    assert profile["deaths_source"] == "behavior-pack"
    assert profile["telemetry"]["blocksBroken"] == 42
    with sqlite3.connect(db_path) as connection:
        stored = json.loads(connection.execute("SELECT payload FROM telemetry_events").fetchone()[0])
    assert stored == event


def test_telemetry_follows_profile_when_xuid_becomes_known(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
) -> None:
    event = {"schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 1, "player": {"name": "Nicole"}, "data": {"mobKills": 9}}
    telemetry_repo.ingest_telemetry(event)
    player_repo.observe_player("Nicole", True, "123")
    profiles = player_repo.player_profiles()
    assert len(profiles) == 1
    assert profiles[0]["telemetry"]["mobKills"] == 9


def test_behavior_pack_death_is_saved_in_player_history(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
) -> None:
    player_repo.observe_player("VonCrush", True, "99")
    telemetry_repo.ingest_telemetry({"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"deaths": 0}})
    death = {"schema": 1, "sequence": 9, "type": "entity.died", "timestamp": 2, "player": {"name": "VonCrush"}, "data": {"victim": "VonCrush", "victimType": "minecraft:player", "killer": None, "killerType": "minecraft:zombie", "projectileType": None, "cause": "entityAttack"}}
    assert telemetry_repo.ingest_telemetry(death) == (True, ["VonCrush"])
    profile = player_repo.player_profile(player_repo.player_profiles()[0]["id"])
    deaths = [event for event in profile["history"] if event["topic"] == "player.death"]
    assert len(deaths) == 1
    assert deaths[0]["source"] == "behavior-pack"
    assert deaths[0]["payload"]["killerType"] == "minecraft:zombie"
    assert profile["last_death_at"] is not None


def test_respawn_and_dimension_change_are_saved_in_player_history(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
) -> None:
    player_repo.observe_player("VonCrush", True, "99")
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "player.respawned", "timestamp": 1,
        "player": {"name": "VonCrush"}, "data": {},
    })
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 2, "type": "player.dimension.changed", "timestamp": 2,
        "player": {"name": "VonCrush"},
        "data": {"from": "minecraft:overworld", "to": "minecraft:nether"},
    })
    activity = player_repo.player_activity("all", "", "structured", "", 0, 1, 25)
    assert activity["summary"]["respawns"] == 1
    assert activity["summary"]["dimensions"] == 1
    dimension = next(event for event in activity["events"] if event["topic"] == "player.dimension.changed")
    assert dimension["details"]["from_dimension"] == "minecraft:overworld"
    assert dimension["details"]["to_dimension"] == "minecraft:nether"


def test_new_snapshot_at_same_sequence_replaces_authoritative_totals(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
) -> None:
    first = {"schema": 1, "sequence": 8, "type": "snapshot.player", "timestamp": 1, "player": {"name": "VonCrush"}, "data": {"blocksBroken": 10}}
    second = {**first, "timestamp": 2, "data": {"blocksBroken": 15}}
    assert telemetry_repo.ingest_telemetry(first)[0]
    assert telemetry_repo.ingest_telemetry(second)[0]
    assert player_repo.player_profiles()[0]["telemetry"]["blocksBroken"] == 15


@pytest.mark.parametrize("raw_suffix,match", [
    ("X" * 65537, "too large"),
    ('{"schema":2,"sequence":1,"type":"snapshot.finished","player":null,"data":{}}', "schema"),
    ('{"schema":1,"sequence":-1,"type":"snapshot.finished","player":null,"data":{}}', "sequence"),
    ('{"schema":1,"sequence":true,"type":"snapshot.finished","player":null,"data":{}}', "sequence"),
    ('{"schema":1,"sequence":"a","type":"snapshot.finished","player":null,"data":{}}', "sequence"),
    ('{"schema":1,"sequence":1,"type":"snapshot.finished","player":"notadict","data":{}}', "player"),
    ('{"schema":1,"sequence":1,"type":"snapshot.finished","player":{"name":123},"data":{}}', "player"),
    ('{"schema":1,"sequence":1,"type":"snapshot.finished","player":{"name":""},"data":{}}', "player"),
    ('{"schema":1,"sequence":1,"type":"snapshot.finished","player":{"name":"' + "a" * 33 + '"},"data":{}}', "player"),
    ('{"schema":1,"sequence":1,"type":"snapshot.finished","player":null,"data":"notadict"}', "data"),
    ('{"schema":1,"sequence":1,"type":"block.broken","player":null,"data":{}}', "topic"),
    ('{"schema":1,"sequence":1,"type":"block.placed","player":null,"data":{}}', "topic"),
])
def test_parse_telemetry_line_raises_on_invalid_payload(raw_suffix: str, match: str) -> None:
    line = f"[BEDROCK_TELEMETRY] {raw_suffix}"
    with pytest.raises(ValueError, match=match):
        parse_telemetry_line(line)


def test_parse_telemetry_line_returns_none_when_prefix_absent() -> None:
    assert parse_telemetry_line("no prefix here") is None


def test_snapshot_player_gamemode_is_stored_in_stats(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
) -> None:
    event = {
        "schema": 1, "sequence": 10, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"deaths": 0, "gameMode": "survival"},
    }
    telemetry_repo.ingest_telemetry(event)
    profile = player_repo.player_profiles()[0]
    assert profile["telemetry"]["gameMode"] == "survival"


def test_snapshot_player_without_gamemode_leaves_field_absent(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
) -> None:
    event = {
        "schema": 1, "sequence": 11, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"deaths": 0},
    }
    telemetry_repo.ingest_telemetry(event)
    profile = player_repo.player_profiles()[0]
    assert "gameMode" not in profile["telemetry"]


def test_observed_game_mode_exposed_in_player_profile(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
    db_path: Path,
) -> None:
    player_repo.observe_player("VonCrush", True, "99")
    event = {
        "schema": 1, "sequence": 12, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"deaths": 0, "gameMode": "creative"},
    }
    telemetry_repo.ingest_telemetry(event)
    profiles = player_repo.player_profiles()
    profile_id = profiles[0]["id"]
    detail = player_repo.player_profile(profile_id)
    assert detail is not None
    assert detail["observed_game_mode"] == "creative"


def test_observed_game_mode_is_null_without_telemetry(
    player_repo: SQLitePlayerRepository,
    db_path: Path,
) -> None:
    player_repo.observe_player("VonCrush", True, "99")
    profiles = player_repo.player_profiles()
    profile_id = profiles[0]["id"]
    detail = player_repo.player_profile(profile_id)
    assert detail is not None
    assert detail["observed_game_mode"] is None


def test_batched_block_deltas_update_totals_maps_and_daily_buckets(
    player_repo: SQLitePlayerRepository,
    telemetry_repo: SQLiteTelemetryRepository,
    db_path: Path,
) -> None:
    telemetry_repo.ingest_telemetry({
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
    assert telemetry_repo.ingest_telemetry(batch)[0]
    assert not telemetry_repo.ingest_telemetry(batch)[0]
    stats = player_repo.player_profiles()[0]["telemetry"]
    assert stats["blocksBroken"] == 7
    assert stats["brokenByType"]["minecraft:stone"] == 2
    assert stats["blocksPlaced"] == 4
    with sqlite3.connect(db_path) as connection:
        daily = connection.execute("SELECT blocks_broken,blocks_placed FROM player_daily").fetchone()
    assert daily == (3, 2)

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from minecraft_manager._db import open_connection, sqlite_diagnostics
from minecraft_manager.players.repository import SQLitePlayerRepository
from minecraft_manager.repository import StateRepository
from minecraft_manager.telemetry_repository import SQLiteTelemetryRepository


def _init(tmp_path: Path) -> tuple[StateRepository, SQLitePlayerRepository, SQLiteTelemetryRepository]:
    path = tmp_path / "state.db"
    repo = StateRepository(path)
    repo.initialize()
    return repo, SQLitePlayerRepository(path), SQLiteTelemetryRepository(path)


def test_builds_api_snapshot(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    repository.store("settings", {"SERVER_NAME": "MalavaziRamos"}, "test")
    repository.store("server", {"online": "1", "max_players": "10"}, "test")
    repository.replace("players", {"Nicole": "online"}, "test")

    snapshot = repository.snapshot()
    assert snapshot["settings"]["SERVER_NAME"] == "MalavaziRamos"
    assert snapshot["players"] == ["Nicole"]
    assert snapshot["online"] == 1
    assert snapshot["max_players"] == 10
    assert snapshot["domains"]["settings"]["freshness"] == "fresh"


def test_snapshot_retries_transient_sqlite_contention(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    attempts = 0

    @contextmanager
    def flaky_connection(path: Path):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise sqlite3.OperationalError("database is locked")
        with open_connection(path) as connection:
            yield connection

    repository = StateRepository(path, read_connection_factory=flaky_connection)
    repository.initialize()
    repository.store("settings", {"SERVER_NAME": "MalavaziRamos"}, "test")
    before = int(sqlite_diagnostics()["retries"])

    snapshot = repository.snapshot()

    assert snapshot["settings"]["SERVER_NAME"] == "MalavaziRamos"
    assert attempts == 2
    assert int(sqlite_diagnostics()["retries"]) == before + 1


def test_records_and_replays_events(tmp_path: Path) -> None:
    repository = StateRepository(tmp_path / "state.db")
    repository.initialize()
    event_id = repository.record_event("player.connected", "test", {"player": "VonCrush"})
    events = repository.events_after(0)
    assert events[0]["id"] == event_id
    assert events[0]["topic"] == "player.connected"
    assert events[0]["payload"]["player"] == "VonCrush"


def test_keeps_offline_player_history(tmp_path: Path) -> None:
    _, player_repo, _ = _init(tmp_path)
    player_repo.observe_player("VonCrush", True, "99", occurred_at=100)
    player_repo.observe_player("VonCrush", False, "99", occurred_at=160)
    profile = player_repo.player_profiles()[0]
    assert not profile["online"]
    assert profile["sessions_count"] == 1
    assert profile["total_play_seconds"] == 60
    detail = player_repo.player_profile(profile["id"])
    assert [event["topic"] for event in detail["history"]] == ["player.disconnected", "player.connected"]
    assert detail["sessions"][0]["duration_seconds"] == 60
    assert not detail["sessions"][0]["active"]
    assert detail["permission"] == "member"


def test_xuid_unifies_a_temporary_name_profile(tmp_path: Path) -> None:
    _, player_repo, _ = _init(tmp_path)
    player_repo.observe_player("Nicole", True, occurred_at=100)
    player_repo.observe_player("Nicole", True, "123", occurred_at=110)
    assert len(player_repo.player_profiles()) == 1
    public_id = player_repo.player_profiles()[0]["id"]
    assert "123" not in public_id
    assert player_repo.player_profile(public_id) is not None


def test_global_activity_is_filtered_paginated_and_sanitized(tmp_path: Path) -> None:
    _, player_repo, _ = _init(tmp_path)
    player_repo.observe_player("VonCrush", True, "private-xuid")
    player_repo.observe_player("VonCrush", False, "private-xuid")
    player_repo.record_player_death(
        "VonCrush", "was slain by Zombie", "private raw log evidence", "bedrock-log", "death-1",
    )
    player_repo.set_player_permission("VonCrush", "operator")

    first = player_repo.player_activity("all", "VonCrush", "all", "", 0, 1, 2)
    assert first["total"] == 4
    assert first["pages"] == 2
    assert len(first["events"]) == 2
    assert isinstance(first["first_event_at"], float)
    serialized = str(first)
    assert "private-xuid" not in serialized
    assert "private raw log evidence" not in serialized

    deaths = player_repo.player_activity("deaths", "", "server", "", 0, 1, 25)
    assert deaths["total"] == 1
    assert deaths["summary"]["deaths"] == 1
    assert deaths["events"][0]["details"]["cause"] == "was slain by Zombie"
    searched = player_repo.player_activity("deaths", "", "all", "zombie", 0, 1, 25)
    assert searched["total"] == 1


def test_global_activity_distinguishes_structured_deaths(tmp_path: Path) -> None:
    _, player_repo, telemetry_repo = _init(tmp_path)
    player_repo.observe_player("Nicole", True, "456")
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "entity.died", "timestamp": 1,
        "player": {"name": "Nicole"},
        "data": {"victim": "Nicole", "killerType": "minecraft:zombie", "cause": "entityAttack"},
    })
    structured = player_repo.player_activity("deaths", "", "structured", "", 0, 1, 25)
    assert structured["total"] == 1
    assert structured["events"][0]["source"] == "behavior-pack"
    assert structured["events"][0]["details"]["killer"] == "minecraft:zombie"


def test_global_activity_prefers_structured_death_without_deleting_derived_evidence(tmp_path: Path) -> None:
    path = tmp_path / "state.db"
    _, player_repo, telemetry_repo = _init(tmp_path)
    player_repo.observe_player("Nicole", True, "456")
    player_repo.record_player_death("Nicole", "died", "raw evidence", "bedrock-log", "derived")
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 2, "type": "entity.died", "timestamp": 1,
        "player": {"name": "Nicole"},
        "data": {"victim": "Nicole", "killerType": "minecraft:zombie", "cause": "entityAttack"},
    })
    result = player_repo.player_activity("deaths", "", "all", "", 0, 1, 25)
    assert result["total"] == 1
    assert result["events"][0]["source"] == "behavior-pack"
    with sqlite3.connect(path) as connection:
        count = connection.execute("SELECT count(*) FROM player_history WHERE topic='player.death'").fetchone()[0]
    assert count == 2


def test_rankings_combine_manager_and_telemetry_aggregates(tmp_path: Path) -> None:
    _, player_repo, telemetry_repo = _init(tmp_path)
    player_repo.observe_player("VonCrush", True, "private-ranking-xuid", occurred_at=100)
    player_repo.observe_player("VonCrush", False, "private-ranking-xuid", occurred_at=220)
    player_repo.observe_player("Nicole", True, "456", occurred_at=100)
    player_repo.observe_player("Nicole", False, "456", occurred_at=160)
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"deaths": 2, "mobKills": 8, "blocksBroken": 40, "distance": 123.5, "dimensions": {"overworld": 1, "nether": 1}},
    })
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 2,
        "player": {"name": "Nicole"},
        "data": {"deaths": 3, "mobKills": 2, "blocksBroken": 60, "distance": 80, "dimensions": {"overworld": 1}},
    })
    rankings = player_repo.player_rankings()
    assert rankings["period"] == "lifetime"
    assert rankings["metrics"]["play_time"][0]["player"]["name"] == "VonCrush"
    assert rankings["metrics"]["longest_session"][0]["value"] == 120
    assert rankings["metrics"]["deaths"][0]["player"]["name"] == "Nicole"
    assert rankings["metrics"]["blocks_broken"][0]["player"]["name"] == "Nicole"
    assert rankings["metrics"]["distance"][0]["value"] == 123.5
    assert "private-ranking-xuid" not in str(rankings)


def test_block_analytics_aggregates_types_ores_and_players(tmp_path: Path) -> None:
    _, player_repo, telemetry_repo = _init(tmp_path)
    player_repo.observe_player("VonCrush", False, "private-99")
    player_repo.observe_player("Nicole", False, "private-456")
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"blocksBroken": 5, "blocksPlaced": 4, "brokenByType": {"minecraft:diamond_ore": 3, "minecraft:iron_ore": 2}, "placedByType": {"minecraft:stone": 4}},
    })
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 2,
        "player": {"name": "Nicole"},
        "data": {"blocksBroken": 5, "blocksPlaced": 2, "brokenByType": {"minecraft:deepslate_diamond_ore": 5}, "placedByType": {"minecraft:oak_planks": 2}},
    })
    result = player_repo.block_analytics()
    assert result["totals"] == {"broken": 10, "placed": 6}
    assert result["ores"]["diamond"] == 8
    assert result["rankings"]["miners"][0]["player"]["name"] == "Nicole"
    assert result["rankings"]["builders"][0]["player"]["name"] == "VonCrush"
    assert result["rankings"]["ores"]["diamond"][0]["value"] == 5
    assert result["top_broken"][0] == {"block": "minecraft:deepslate_diamond_ore", "count": 5}
    assert "private-" not in str(result)


def test_combat_analytics_has_complete_zero_state(tmp_path: Path) -> None:
    _, player_repo, _ = _init(tmp_path)
    result = player_repo.combat_analytics()
    assert result["totals"] == {"deaths": 0, "player_kills": 0, "mob_kills": 0, "damage_dealt": 0, "damage_taken": 0}
    assert result["breakdowns"] == {"causes": [], "opponents": [], "projectiles": []}
    assert result["pvp"] == []
    assert result["players"] == []


def test_combat_analytics_aggregates_snapshots_and_structured_deaths(tmp_path: Path) -> None:
    _, player_repo, telemetry_repo = _init(tmp_path)
    player_repo.observe_player("VonCrush", True, "private-99")
    player_repo.observe_player("Nicole", True, "private-456")
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"deaths": 1, "playerKills": 2, "mobKills": 8, "damageDealt": 42.5, "damageTaken": 12, "killsByType": {"minecraft:zombie": 6, "minecraft:skeleton": 2}},
    })
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 2,
        "player": {"name": "Nicole"},
        "data": {"deaths": 3, "playerKills": 1, "mobKills": 4, "damageDealt": 20, "damageTaken": 30},
    })
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 3, "type": "entity.died", "timestamp": 3,
        "player": {"name": "Nicole"},
        "data": {"victim": "Nicole", "killer": "VonCrush", "killerType": "minecraft:player", "projectileType": "minecraft:arrow", "cause": "projectile"},
    })
    result = player_repo.combat_analytics()
    assert result["totals"]["mob_kills"] == 12
    assert result["totals"]["damage_dealt"] == 62.5
    assert result["rankings"]["player_kills"][0]["player"]["name"] == "VonCrush"
    assert result["breakdowns"]["causes"][0] == {"key": "projectile", "count": 1}
    assert result["pvp"][0]["attacker"]["name"] == "VonCrush"
    assert result["top_targets"][0] == {"target": "minecraft:zombie", "kills": 6}
    von = next(item for item in result["players"] if item["player"]["name"] == "VonCrush")
    assert von["favorite_target"]["target"] == "minecraft:zombie"
    assert "private-" not in str(result)


def test_exploration_analytics_has_complete_zero_state(tmp_path: Path) -> None:
    _, player_repo, _ = _init(tmp_path)
    result = player_repo.exploration_analytics()
    assert result["totals"] == {"distance": 0, "dimensions": 0, "dimension_visits": 0, "play_seconds": 0, "sessions": 0, "active_seconds": 0}
    assert result["dimensions"] == []
    assert result["transitions"] == []
    assert result["players"] == []


def test_exploration_analytics_combines_telemetry_and_manager_presence(tmp_path: Path) -> None:
    _, player_repo, telemetry_repo = _init(tmp_path)
    player_repo.observe_player("VonCrush", True, "private-99", occurred_at=100)
    player_repo.observe_player("VonCrush", False, "private-99", occurred_at=220)
    player_repo.observe_player("Nicole", True, "private-456", occurred_at=100)
    player_repo.observe_player("Nicole", False, "private-456", occurred_at=160)
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"},
        "data": {"distance": 120.5, "dimensions": {"minecraft:overworld": 3, "minecraft:nether": 2}, "distanceByDimension": {"minecraft:overworld": 80.5, "minecraft:nether": 40}, "activeTimeByDimension": {"minecraft:overworld": 60, "minecraft:nether": 30}, "firstDimensionVisitAt": {"minecraft:overworld": 1000000000000}, "lastDimensionVisitAt": {"minecraft:overworld": 1000000005000}},
    })
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 2,
        "player": {"name": "Nicole"},
        "data": {"distance": 80, "dimensions": {"minecraft:overworld": 1}},
    })
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 3, "type": "player.dimension.changed", "timestamp": 3,
        "player": {"name": "VonCrush"}, "data": {"from": "minecraft:overworld", "to": "minecraft:nether"},
    })
    result = player_repo.exploration_analytics()
    assert result["totals"]["distance"] == 200.5
    assert result["totals"]["play_seconds"] == 180
    assert result["totals"]["dimensions"] == 2
    assert result["dimensions"][0]["dimension"] == "minecraft:overworld"
    assert result["dimensions"][0]["visits"] == 4
    assert result["dimensions"][0]["distance"] == 80.5
    assert result["dimensions"][0]["active_seconds"] == 60
    assert result["dimensions"][0]["first_seen_at"] == 1000000000
    assert result["totals"]["active_seconds"] == 90
    assert result["rankings"]["distance"][0]["player"]["name"] == "VonCrush"
    assert result["transitions"][0]["to"] == "minecraft:nether"
    assert "private-" not in str(result)


def test_daily_analytics_records_sessions_and_incremental_telemetry(tmp_path: Path) -> None:
    _, player_repo, telemetry_repo = _init(tmp_path)
    now = time.time()
    player_repo.observe_player("VonCrush", True, "private-daily", occurred_at=now - 120)
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
        "player": {"name": "VonCrush"}, "data": {"blocksBroken": 10, "damageDealt": 5, "distance": 20},
    })
    block = {
        "schema": 1, "sequence": 2, "type": "block.broken", "timestamp": 2,
        "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:stone"},
    }
    telemetry_repo.ingest_telemetry(block)
    assert not telemetry_repo.ingest_telemetry(block)[0]
    telemetry_repo.ingest_telemetry({
        "schema": 1, "sequence": 3, "type": "snapshot.player", "timestamp": 3,
        "player": {"name": "VonCrush"}, "data": {"blocksBroken": 11, "damageDealt": 8.5, "distance": 27},
    })
    player_repo.observe_player("VonCrush", False, "private-daily", occurred_at=now)
    result = player_repo.period_analytics(7)
    assert result["period_days"] == 7
    assert result["totals"]["sessions"] == 1
    assert result["totals"]["joins"] == 1
    assert abs(result["totals"]["play_seconds"] - 120) <= 1
    assert result["totals"]["blocks_broken"] == 1
    assert result["totals"]["damage_dealt"] == 3.5
    assert result["totals"]["distance"] == 7
    assert result["rankings"]["play_seconds"][0]["player"]["name"] == "VonCrush"
    assert len(result["calendar"]) == 7
    assert len(result["heatmap"]) == 168
    assert "private-daily" not in str(result)

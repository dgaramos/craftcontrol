import tempfile
import time
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

    def test_rankings_combine_manager_and_telemetry_aggregates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("VonCrush", True, "private-ranking-xuid", occurred_at=100)
            repository.observe_player("VonCrush", False, "private-ranking-xuid", occurred_at=220)
            repository.observe_player("Nicole", True, "456", occurred_at=100)
            repository.observe_player("Nicole", False, "456", occurred_at=160)
            repository.ingest_telemetry({
                "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
                "player": {"name": "VonCrush"},
                "data": {"deaths": 2, "mobKills": 8, "blocksBroken": 40, "distance": 123.5, "dimensions": {"overworld": 1, "nether": 1}},
            })
            repository.ingest_telemetry({
                "schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 2,
                "player": {"name": "Nicole"},
                "data": {"deaths": 3, "mobKills": 2, "blocksBroken": 60, "distance": 80, "dimensions": {"overworld": 1}},
            })
            rankings = repository.player_rankings()
            self.assertEqual(rankings["period"], "lifetime")
            self.assertEqual(rankings["metrics"]["play_time"][0]["player"]["name"], "VonCrush")
            self.assertEqual(rankings["metrics"]["longest_session"][0]["value"], 120)
            self.assertEqual(rankings["metrics"]["deaths"][0]["player"]["name"], "Nicole")
            self.assertEqual(rankings["metrics"]["blocks_broken"][0]["player"]["name"], "Nicole")
            self.assertEqual(rankings["metrics"]["distance"][0]["value"], 123.5)
            self.assertNotIn("private-ranking-xuid", str(rankings))

    def test_block_analytics_aggregates_types_ores_and_players(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("VonCrush", False, "private-99")
            repository.observe_player("Nicole", False, "private-456")
            repository.ingest_telemetry({
                "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
                "player": {"name": "VonCrush"},
                "data": {"blocksBroken": 5, "blocksPlaced": 4, "brokenByType": {"minecraft:diamond_ore": 3, "minecraft:iron_ore": 2}, "placedByType": {"minecraft:stone": 4}},
            })
            repository.ingest_telemetry({
                "schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 2,
                "player": {"name": "Nicole"},
                "data": {"blocksBroken": 5, "blocksPlaced": 2, "brokenByType": {"minecraft:deepslate_diamond_ore": 5}, "placedByType": {"minecraft:oak_planks": 2}},
            })
            result = repository.block_analytics()
            self.assertEqual(result["totals"], {"broken": 10, "placed": 6})
            self.assertEqual(result["ores"]["diamond"], 8)
            self.assertEqual(result["rankings"]["miners"][0]["player"]["name"], "Nicole")
            self.assertEqual(result["rankings"]["builders"][0]["player"]["name"], "VonCrush")
            self.assertEqual(result["rankings"]["ores"]["diamond"][0]["value"], 5)
            self.assertEqual(result["top_broken"][0], {"block": "minecraft:deepslate_diamond_ore", "count": 5})
            self.assertNotIn("private-", str(result))

    def test_combat_analytics_has_complete_zero_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            result = repository.combat_analytics()
            self.assertEqual(result["totals"], {"deaths": 0, "player_kills": 0, "mob_kills": 0, "damage_dealt": 0, "damage_taken": 0})
            self.assertEqual(result["breakdowns"], {"causes": [], "opponents": [], "projectiles": []})
            self.assertEqual(result["pvp"], [])
            self.assertEqual(result["players"], [])

    def test_combat_analytics_aggregates_snapshots_and_structured_deaths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("VonCrush", True, "private-99")
            repository.observe_player("Nicole", True, "private-456")
            repository.ingest_telemetry({
                "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
                "player": {"name": "VonCrush"},
                "data": {"deaths": 1, "playerKills": 2, "mobKills": 8, "damageDealt": 42.5, "damageTaken": 12},
            })
            repository.ingest_telemetry({
                "schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 2,
                "player": {"name": "Nicole"},
                "data": {"deaths": 3, "playerKills": 1, "mobKills": 4, "damageDealt": 20, "damageTaken": 30},
            })
            repository.ingest_telemetry({
                "schema": 1, "sequence": 3, "type": "entity.died", "timestamp": 3,
                "player": {"name": "Nicole"},
                "data": {"victim": "Nicole", "killer": "VonCrush", "killerType": "minecraft:player", "projectileType": "minecraft:arrow", "cause": "projectile"},
            })
            result = repository.combat_analytics()
            self.assertEqual(result["totals"]["mob_kills"], 12)
            self.assertEqual(result["totals"]["damage_dealt"], 62.5)
            self.assertEqual(result["rankings"]["player_kills"][0]["player"]["name"], "VonCrush")
            self.assertEqual(result["breakdowns"]["causes"][0], {"key": "projectile", "count": 1})
            self.assertEqual(result["pvp"][0]["attacker"]["name"], "VonCrush")
            self.assertNotIn("private-", str(result))

    def test_exploration_analytics_has_complete_zero_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            result = repository.exploration_analytics()
            self.assertEqual(result["totals"], {"distance": 0, "dimensions": 0, "dimension_visits": 0, "play_seconds": 0, "sessions": 0})
            self.assertEqual(result["dimensions"], [])
            self.assertEqual(result["transitions"], [])
            self.assertEqual(result["players"], [])

    def test_exploration_analytics_combines_telemetry_and_manager_presence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            repository.observe_player("VonCrush", True, "private-99", occurred_at=100)
            repository.observe_player("VonCrush", False, "private-99", occurred_at=220)
            repository.observe_player("Nicole", True, "private-456", occurred_at=100)
            repository.observe_player("Nicole", False, "private-456", occurred_at=160)
            repository.ingest_telemetry({
                "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
                "player": {"name": "VonCrush"},
                "data": {"distance": 120.5, "dimensions": {"minecraft:overworld": 3, "minecraft:nether": 2}},
            })
            repository.ingest_telemetry({
                "schema": 1, "sequence": 2, "type": "snapshot.player", "timestamp": 2,
                "player": {"name": "Nicole"},
                "data": {"distance": 80, "dimensions": {"minecraft:overworld": 1}},
            })
            repository.ingest_telemetry({
                "schema": 1, "sequence": 3, "type": "player.dimension.changed", "timestamp": 3,
                "player": {"name": "VonCrush"}, "data": {"from": "minecraft:overworld", "to": "minecraft:nether"},
            })
            result = repository.exploration_analytics()
            self.assertEqual(result["totals"]["distance"], 200.5)
            self.assertEqual(result["totals"]["play_seconds"], 180)
            self.assertEqual(result["totals"]["dimensions"], 2)
            self.assertEqual(result["dimensions"][0], {"dimension": "minecraft:overworld", "visits": 4})
            self.assertEqual(result["rankings"]["distance"][0]["player"]["name"], "VonCrush")
            self.assertEqual(result["transitions"][0]["to"], "minecraft:nether")
            self.assertNotIn("private-", str(result))

    def test_daily_analytics_records_sessions_and_incremental_telemetry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = StateRepository(Path(directory) / "state.db")
            repository.initialize()
            now = time.time()
            repository.observe_player("VonCrush", True, "private-daily", occurred_at=now - 120)
            repository.ingest_telemetry({
                "schema": 1, "sequence": 1, "type": "snapshot.player", "timestamp": 1,
                "player": {"name": "VonCrush"}, "data": {"blocksBroken": 10, "damageDealt": 5, "distance": 20},
            })
            block = {
                "schema": 1, "sequence": 2, "type": "block.broken", "timestamp": 2,
                "player": {"name": "VonCrush"}, "data": {"blockType": "minecraft:stone"},
            }
            repository.ingest_telemetry(block)
            self.assertFalse(repository.ingest_telemetry(block)[0])
            repository.ingest_telemetry({
                "schema": 1, "sequence": 3, "type": "snapshot.player", "timestamp": 3,
                "player": {"name": "VonCrush"}, "data": {"blocksBroken": 11, "damageDealt": 8.5, "distance": 27},
            })
            repository.observe_player("VonCrush", False, "private-daily", occurred_at=now)
            result = repository.period_analytics(7)
            self.assertEqual(result["period_days"], 7)
            self.assertEqual(result["totals"]["sessions"], 1)
            self.assertEqual(result["totals"]["joins"], 1)
            self.assertAlmostEqual(result["totals"]["play_seconds"], 120, delta=1)
            self.assertEqual(result["totals"]["blocks_broken"], 1)
            self.assertEqual(result["totals"]["damage_dealt"], 3.5)
            self.assertEqual(result["totals"]["distance"], 7)
            self.assertEqual(result["rankings"]["play_seconds"][0]["player"]["name"], "VonCrush")
            self.assertEqual(len(result["calendar"]), 7)
            self.assertEqual(len(result["heatmap"]), 168)
            self.assertNotIn("private-daily", str(result))

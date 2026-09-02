"""Telemetry persistence — autonomous SQLite adapter.

This repository owns all SQL for telemetry ingestion and connects directly to
the database.  It does not delegate to any other repository.

Telemetry events cross the player-domain boundary: ingestion writes to
player_profiles, player_history, and player_daily in addition to its own
telemetry_events and player_telemetry tables.  The shared helpers in
minecraft_manager.core.sqlite handles those cross-table writes so the logic is not
duplicated between this repository and SQLitePlayerRepository.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..core.sqlite import (
    add_daily,
    open_connection,
    player_identity,
    record_player_history,
)


STALE_THRESHOLD_SECONDS = 1200

_ALL_DOMAINS = ("settings", "gamerules", "players", "server", "telemetry")


class SQLiteTelemetryRepository:
    """Autonomous telemetry repository backed directly by a SQLite database."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self):
        return open_connection(self.path)

    # ------------------------------------------------------------------
    # State-table helpers (store, snapshot)
    # ------------------------------------------------------------------

    def store(self, kind: str, values: dict[str, str], source: str) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO state(kind,key,value,updated_at,source,changed_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(kind,key) DO UPDATE SET value=excluded.value,"
                "updated_at=excluded.updated_at,source=excluded.source,"
                "changed_at=CASE WHEN state.value != excluded.value "
                "THEN excluded.changed_at ELSE state.changed_at END",
                [(kind, key, value, now, source, now) for key, value in values.items()],
            )

    def snapshot(self, refreshing: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {
            "settings": {}, "gamerules": {}, "players": [], "online": 0,
            "max_players": 0, "updated_at": 0, "refreshing": refreshing,
        }
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT kind,key,value,updated_at,changed_at,source FROM state"
            ).fetchall()
        domains: dict[str, dict[str, Any]] = {}
        for kind, key, value, updated_at, changed_at, source in rows:
            if kind == "players":
                result["players"].append(key)
            elif kind == "server" and key in {"online", "max_players"}:
                result[key] = int(value)
            else:
                result.setdefault(kind, {})[key] = value
            result["updated_at"] = max(result["updated_at"], updated_at)
            domain = domains.setdefault(kind, {"observed_at": 0, "changed_at": 0, "source": source})
            domain["observed_at"] = max(domain["observed_at"], updated_at)
            domain["changed_at"] = max(domain["changed_at"], changed_at or updated_at)
            domain["source"] = source
        now = time.time()
        for domain in domains.values():
            domain["freshness"] = "fresh" if now - domain["observed_at"] < STALE_THRESHOLD_SECONDS else "stale"
        result["domains"] = domains
        return result

    def domain_freshness(self, time_fn=None) -> dict[str, Any]:
        """Return freshness metadata for each tracked domain.

        For each domain in ``_ALL_DOMAINS``:
        - If the domain was never observed (``observed_at == 0`` or absent):
          ``observed_at=None``, ``age_seconds=None``, ``stale=True``.
        - Otherwise: ``age_seconds = time_fn() - observed_at``,
          ``stale = age_seconds > STALE_THRESHOLD_SECONDS``.

        ``time_fn`` defaults to ``time.time`` and is injectable for testing.
        """
        if time_fn is None:
            time_fn = time.time
        raw_domains = self.snapshot().get("domains", {})
        now = time_fn()
        result: dict[str, Any] = {}
        for name in _ALL_DOMAINS:
            raw = raw_domains.get(name)
            observed_at = raw["observed_at"] if raw else 0
            if not observed_at:
                result[name] = {"observed_at": None, "age_seconds": None, "stale": True}
            else:
                age = now - observed_at
                result[name] = {
                    "observed_at": observed_at,
                    "age_seconds": age,
                    "stale": age >= STALE_THRESHOLD_SECONDS,
                }
        return result

    # ------------------------------------------------------------------
    # Telemetry ingestion
    # ------------------------------------------------------------------

    def ingest_telemetry(self, envelope: dict[str, Any]) -> tuple[bool, list[str]]:
        sequence, topic = envelope["sequence"], envelope["type"]
        player = (envelope.get("player") or {}).get("name")
        replay_identity = (
            f":{envelope.get('timestamp', '-')}"
            if topic.startswith("snapshot.") or topic == "telemetry.started"
            else ""
        )
        key = f"{sequence}:{topic}:{player or '-'}{replay_identity}"
        now = time.time()
        changed: list[str] = []
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO telemetry_events"
                "(event_key,sequence,topic,received_at,payload) VALUES(?,?,?,?,?)",
                (key, sequence, topic, now, json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))),
            )
            if cursor.rowcount == 0:
                return False, []
            connection.execute(
                "DELETE FROM telemetry_events WHERE rowid NOT IN "
                "(SELECT rowid FROM telemetry_events ORDER BY received_at DESC LIMIT 10000)"
            )
            if topic == "snapshot.player" and player:
                identity = player_identity(connection, player)
                if not connection.execute(
                    "SELECT 1 FROM player_profiles WHERE identity=?", (identity,)
                ).fetchone():
                    connection.execute(
                        "INSERT INTO player_profiles"
                        "(identity,current_name,first_seen_at,last_seen_at) VALUES(?,?,?,?)",
                        (identity, player, now, now),
                    )
                previous = connection.execute(
                    "SELECT stats FROM player_telemetry WHERE identity=?", (identity,)
                ).fetchone()
                if previous:
                    self._apply_snapshot_daily_delta(
                        connection, identity, json.loads(previous[0]), envelope["data"], now
                    )
                connection.execute(
                    "INSERT INTO player_telemetry(identity,stats,sequence,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(identity) DO UPDATE SET stats=excluded.stats,"
                    "sequence=excluded.sequence,updated_at=excluded.updated_at",
                    (identity, json.dumps(envelope["data"], ensure_ascii=False), sequence, now),
                )
                changed.append(player)
            elif topic in {
                "blocks.changed", "player.respawned", "player.dimension.changed", "entity.died",
            }:
                changed.extend(self._apply_telemetry_delta(connection, envelope, now))
        return True, changed

    def _apply_snapshot_daily_delta(
        self,
        connection: Any,
        identity: str,
        previous: dict[str, Any],
        current: dict[str, Any],
        timestamp: float,
    ) -> None:
        fields = {
            "deaths": "deaths", "playerKills": "player_kills", "mobKills": "mob_kills",
            "blocksBroken": "blocks_broken", "blocksPlaced": "blocks_placed",
            "damageDealt": "damage_dealt", "damageTaken": "damage_taken", "distance": "distance",
        }
        deltas = {}
        for source_field, dest_field in fields.items():
            before = previous.get(source_field, 0)
            after = current.get(source_field, 0)
            if isinstance(before, (int, float)) and isinstance(after, (int, float)) and after > before:
                deltas[dest_field] = after - before
        add_daily(connection, identity, timestamp, **deltas)

    def _apply_telemetry_delta(
        self,
        connection: Any,
        envelope: dict[str, Any],
        now: float,
    ) -> list[str]:
        topic, data = envelope["type"], envelope["data"]
        names: list[str] = []
        if topic == "entity.died":
            names = [name for name in (data.get("victim"), data.get("killer")) if isinstance(name, str)]
        else:
            name = (envelope.get("player") or {}).get("name")
            names = [name] if name else []
        for name in dict.fromkeys(names):
            identity = player_identity(connection, name)
            row = connection.execute(
                "SELECT stats FROM player_telemetry WHERE identity=?", (identity,)
            ).fetchone()
            if not row:
                connection.execute(
                    "INSERT OR IGNORE INTO player_telemetry(identity,stats,sequence,updated_at) VALUES(?,?,?,?)",
                    (identity, json.dumps({}), 0, now),
                )
                row = connection.execute(
                    "SELECT stats FROM player_telemetry WHERE identity=?", (identity,)
                ).fetchone()
            if row:
                stats = json.loads(row[0])
                if topic == "blocks.changed" and name == names[0]:
                    broken = data.get("broken") if isinstance(data.get("broken"), dict) else {}
                    placed = data.get("placed") if isinstance(data.get("placed"), dict) else {}
                    broken_total = self._apply_block_batch(stats, "blocksBroken", "brokenByType", broken)
                    placed_total = self._apply_block_batch(stats, "blocksPlaced", "placedByType", placed)
                    if broken_total or placed_total:
                        add_daily(connection, identity, now, blocks_broken=broken_total, blocks_placed=placed_total)
                if topic == "entity.died" and name == data.get("victim"):
                    stats["deaths"] = int(stats.get("deaths", 0)) + 1
                    derived = connection.execute(
                        "SELECT 1 FROM player_history WHERE identity=? "
                        "AND topic='player.death' AND source!='behavior-pack' "
                        "AND occurred_at BETWEEN ? AND ? LIMIT 1",
                        (identity, now - 10, now + 10),
                    ).fetchone()
                    if not derived:
                        add_daily(connection, identity, now, deaths=1)
                if topic == "entity.died" and name == data.get("killer"):
                    key = "playerKills" if data.get("victim") else "mobKills"
                    stats[key] = int(stats.get(key, 0)) + 1
                    add_daily(
                        connection, identity, now,
                        **{"player_kills" if data.get("victim") else "mob_kills": 1},
                    )
                connection.execute(
                    "UPDATE player_telemetry SET stats=?,sequence=?,updated_at=? WHERE identity=?",
                    (json.dumps(stats), envelope["sequence"], now, identity),
                )
            if topic == "entity.died" and name == data.get("victim"):
                if not connection.execute(
                    "SELECT 1 FROM player_profiles WHERE identity=?", (identity,)
                ).fetchone():
                    connection.execute(
                        "INSERT INTO player_profiles"
                        "(identity,current_name,first_seen_at,last_seen_at) VALUES(?,?,?,?)",
                        (identity, name, now, now),
                    )
                connection.execute(
                    "UPDATE player_profiles SET last_death_at=?,last_seen_at=? WHERE identity=?",
                    (now, now, identity),
                )
                record_player_history(
                    connection, identity, "player.death", "behavior-pack", data, now,
                    f"telemetry:{envelope['sequence']}:death:{identity}",
                )
            elif topic in {"player.respawned", "player.dimension.changed"}:
                if not connection.execute(
                    "SELECT 1 FROM player_profiles WHERE identity=?", (identity,)
                ).fetchone():
                    connection.execute(
                        "INSERT INTO player_profiles"
                        "(identity,current_name,first_seen_at,last_seen_at) VALUES(?,?,?,?)",
                        (identity, name, now, now),
                    )
                connection.execute(
                    "UPDATE player_profiles SET last_seen_at=? WHERE identity=?",
                    (now, identity),
                )
                record_player_history(
                    connection, identity, topic, "behavior-pack", data, now,
                    f"telemetry:{envelope['sequence']}:{topic}:{identity}",
                )
                if topic == "player.dimension.changed":
                    add_daily(connection, identity, now, dimension_transitions=1)
        return list(dict.fromkeys(names))

    @staticmethod
    def _increment_block_map(
        stats: dict[str, Any], field: str, block_type: Any, limit: int = 128
    ) -> None:
        if (
            not isinstance(block_type, str)
            or not block_type.startswith("minecraft:")
            or len(block_type) > 112
        ):
            return
        values = stats.get(field) if isinstance(stats.get(field), dict) else {}
        values[block_type] = int(values.get(block_type, 0)) + 1
        if len(values) > limit:
            values = dict(
                sorted(values.items(), key=lambda item: (-int(item[1]), item[0]))[:limit]
            )
        stats[field] = values

    @classmethod
    def _apply_block_batch(
        cls,
        stats: dict[str, Any],
        total_field: str,
        map_field: str,
        batch: dict[str, Any],
    ) -> int:
        by_type = batch.get("byType") if isinstance(batch.get("byType"), dict) else {}
        counts = {
            block_type: int(count)
            for block_type, count in by_type.items()
            if isinstance(block_type, str) and block_type.startswith("minecraft:")
            and isinstance(count, int) and not isinstance(count, bool) and count > 0
        }
        declared = batch.get("total")
        total = (
            int(declared)
            if isinstance(declared, int) and not isinstance(declared, bool) and declared >= 0
            else sum(counts.values())
        )
        if total != sum(counts.values()):
            total = sum(counts.values())
        stats[total_field] = int(stats.get(total_field, 0)) + total
        values = stats.get(map_field) if isinstance(stats.get(map_field), dict) else {}
        for block_type, count in counts.items():
            values[block_type] = int(values.get(block_type, 0)) + count
        stats[map_field] = dict(
            sorted(values.items(), key=lambda item: (-int(item[1]), item[0]))[:128]
        )
        return total

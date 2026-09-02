"""Player persistence — autonomous SQLite adapter.

This repository owns all SQL for the player domain and connects directly to
the database.  It does not delegate to any other repository.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..core.sqlite import open_connection
from .sqlite import (
    add_daily,
    allocate_daily_play,
    calendar_timezone,
    day_key,
    player_identity,
    public_player_id,
    record_player_history,
    temporary_identity,
)


ORE_BLOCKS = {
    "diamond": {"minecraft:diamond_ore", "minecraft:deepslate_diamond_ore"},
    "iron": {"minecraft:iron_ore", "minecraft:deepslate_iron_ore"},
    "gold": {"minecraft:gold_ore", "minecraft:deepslate_gold_ore", "minecraft:nether_gold_ore"},
    "copper": {"minecraft:copper_ore", "minecraft:deepslate_copper_ore"},
    "coal": {"minecraft:coal_ore", "minecraft:deepslate_coal_ore"},
    "redstone": {"minecraft:redstone_ore", "minecraft:deepslate_redstone_ore"},
    "lapis": {"minecraft:lapis_ore", "minecraft:deepslate_lapis_ore"},
    "emerald": {"minecraft:emerald_ore", "minecraft:deepslate_emerald_ore"},
    "quartz": {"minecraft:nether_quartz_ore"},
    "ancient_debris": {"minecraft:ancient_debris"},
}


class SQLitePlayerRepository:
    """Autonomous player repository backed directly by a SQLite database."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self):
        return open_connection(self.path)

    # ------------------------------------------------------------------
    # State-table helpers (store, replace, snapshot)
    # These mirror the same-named methods on StateRepository so that the
    # PlayerStore protocol is satisfied without delegation.
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

    def replace(self, kind: str, values: dict[str, str], source: str) -> None:
        with self._connect() as connection:
            if values:
                placeholders = ",".join("?" for _ in values)
                connection.execute(
                    f"DELETE FROM state WHERE kind = ? AND key NOT IN ({placeholders})",
                    (kind, *values.keys()),
                )
            else:
                connection.execute("DELETE FROM state WHERE kind = ?", (kind,))
        self.store(kind, values, source)

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
            domain["freshness"] = "fresh" if now - domain["observed_at"] < 1200 else "stale"
        result["domains"] = domains
        return result

    # ------------------------------------------------------------------
    # Player presence
    # ------------------------------------------------------------------

    def observe_player(
        self,
        name: str,
        connected: bool,
        xuid: str = "",
        source: str = "bedrock-log",
        occurred_at: float | None = None,
    ) -> dict[str, Any]:
        now = occurred_at or time.time()
        with self._connect() as connection:
            identity = player_identity(connection, name, xuid)
            row = connection.execute(
                "SELECT online,connected_at FROM player_profiles WHERE identity=?", (identity,)
            ).fetchone()
            was_online = bool(row[0]) if row else False
            connection.execute(
                "INSERT INTO player_profiles"
                "(identity,xuid,current_name,first_seen_at,last_seen_at,online,connected_at) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(identity) DO UPDATE SET "
                "xuid=COALESCE(excluded.xuid,player_profiles.xuid),"
                "current_name=excluded.current_name,"
                "last_seen_at=excluded.last_seen_at,"
                "online=excluded.online,"
                "connected_at=CASE "
                "WHEN excluded.online=1 AND player_profiles.online=0 THEN excluded.connected_at "
                "WHEN excluded.online=0 THEN NULL "
                "ELSE player_profiles.connected_at END",
                (identity, xuid or None, name, now, now, int(connected), now if connected else None),
            )
            connection.execute(
                "INSERT INTO player_aliases(identity,name,first_seen_at,last_seen_at) VALUES(?,?,?,?) "
                "ON CONFLICT(identity,name) DO UPDATE SET last_seen_at=excluded.last_seen_at",
                (identity, name, now, now),
            )
            changed = was_online != connected
            if connected and not was_online:
                connection.execute(
                    "INSERT INTO player_sessions(identity,connected_at) VALUES(?,?)", (identity, now)
                )
                connection.execute(
                    "UPDATE player_profiles SET sessions_count=sessions_count+1 WHERE identity=?",
                    (identity,),
                )
                add_daily(connection, identity, now, sessions=1, joins=1)
            elif not connected and was_online:
                session = connection.execute(
                    "SELECT id,connected_at FROM player_sessions "
                    "WHERE identity=? AND disconnected_at IS NULL ORDER BY id DESC LIMIT 1",
                    (identity,),
                ).fetchone()
                if session:
                    duration = max(0, now - float(session[1]))
                    connection.execute(
                        "UPDATE player_sessions SET disconnected_at=?,duration_seconds=?,"
                        "close_reason='disconnect' WHERE id=?",
                        (now, duration, session[0]),
                    )
                    connection.execute(
                        "UPDATE player_profiles SET total_play_seconds=total_play_seconds+? WHERE identity=?",
                        (duration, identity),
                    )
                    allocate_daily_play(connection, identity, float(session[1]), now)
            if changed:
                topic = "player.connected" if connected else "player.disconnected"
                record_player_history(connection, identity, topic, source, {"name": name}, now)
        return {"identity": identity, "changed": changed}

    def reconcile_online_players(
        self, players: list[str], xuids: dict[str, str], source: str
    ) -> None:
        now = time.time()
        online_identities: set[str] = set()
        for name in players:
            result = self.observe_player(name, True, xuids.get(name, ""), source, now)
            online_identities.add(result["identity"])
        with self._connect() as connection:
            missing = connection.execute(
                "SELECT identity,current_name FROM player_profiles WHERE online=1"
            ).fetchall()
        for identity, name in missing:
            if identity not in online_identities:
                self.observe_player(str(name), False, source=source, occurred_at=now)

    def close_online_sessions(
        self, reason: str, source: str = "docker-events"
    ) -> list[str]:
        now = time.time()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT identity,current_name,connected_at FROM player_profiles WHERE online=1"
            ).fetchall()
            for identity, name, connected_at in rows:
                duration = max(0, now - float(connected_at or now))
                connection.execute(
                    "UPDATE player_sessions SET disconnected_at=?,duration_seconds=?,"
                    "close_reason=?,inferred=1 "
                    "WHERE id=(SELECT id FROM player_sessions WHERE identity=? "
                    "AND disconnected_at IS NULL ORDER BY id DESC LIMIT 1)",
                    (now, duration, reason, identity),
                )
                allocate_daily_play(connection, identity, float(connected_at or now), now)
                connection.execute(
                    "UPDATE player_profiles SET online=0,connected_at=NULL,last_seen_at=?,"
                    "total_play_seconds=total_play_seconds+? WHERE identity=?",
                    (now, duration, identity),
                )
                record_player_history(
                    connection, identity, "player.disconnected", source,
                    {"name": name, "reason": reason, "inferred": True}, now,
                )
        return [str(row[1]) for row in rows]

    def record_player_death(
        self, name: str, cause: str, raw: str, source: str, event_key: str
    ) -> bool:
        now = time.time()
        with self._connect() as connection:
            identity = player_identity(connection, name)
            if not connection.execute(
                "SELECT 1 FROM player_profiles WHERE identity=?", (identity,)
            ).fetchone():
                connection.execute(
                    "INSERT INTO player_profiles"
                    "(identity,current_name,first_seen_at,last_seen_at,online) VALUES(?,?,?,?,0)",
                    (identity, name, now, now),
                )
            inserted = record_player_history(
                connection, identity, "player.death", source,
                {"name": name, "cause": cause, "raw": raw, "derived": True}, now, event_key,
            )
            if inserted:
                connection.execute(
                    "UPDATE player_profiles SET deaths_count=deaths_count+1,"
                    "last_death_at=?,last_seen_at=? WHERE identity=?",
                    (now, now, identity),
                )
                add_daily(connection, identity, now, deaths=1)
            return inserted

    def set_player_permission(
        self, name: str, permission: str, source: str = "manager"
    ) -> None:
        now = time.time()
        with self._connect() as connection:
            identity = player_identity(connection, name)
            existing = connection.execute(
                "SELECT permission FROM player_profiles WHERE identity=?", (identity,)
            ).fetchone()
            if not existing:
                connection.execute(
                    "INSERT INTO player_profiles"
                    "(identity,current_name,first_seen_at,last_seen_at,permission) VALUES(?,?,?,?,?)",
                    (identity, name, now, now, permission),
                )
            else:
                connection.execute(
                    "UPDATE player_profiles SET permission=? WHERE identity=?",
                    (permission, identity),
                )
            if not existing or existing[0] != permission:
                record_player_history(
                    connection, identity, "player.permission.changed", source,
                    {"name": name, "permission": permission}, now,
                )

    # ------------------------------------------------------------------
    # Read queries
    # ------------------------------------------------------------------

    def set_preferred_game_mode(self, name: str, mode: str | None) -> None:
        """Persist the operator-configured game mode preference for a player.

        ``mode=None`` clears the preference (server default applies).
        Never inferred from telemetry — exclusively panel-managed.
        """
        with self._connect() as connection:
            identity = player_identity(connection, name)
            connection.execute(
                "UPDATE player_profiles SET preferred_game_mode=? WHERE identity=?",
                (mode, identity),
            )

    def get_preferred_game_mode(self, name: str) -> str | None:
        """Return the panel-managed preferred game mode for a player, or None."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT preferred_game_mode FROM player_profiles WHERE identity=?",
                (player_identity(connection, name),),
            ).fetchone()
            return row[0] if row else None

    def player_profiles(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT identity,current_name,first_seen_at,last_seen_at,online,connected_at,"
                "sessions_count,total_play_seconds,deaths_count,last_death_at,permission,"
                "preferred_game_mode "
                "FROM player_profiles ORDER BY online DESC,last_seen_at DESC"
            ).fetchall()
            telemetry_rows = connection.execute(
                "SELECT identity,stats,updated_at FROM player_telemetry"
            ).fetchall()
        telemetry = {row[0]: (json.loads(row[1]), row[2]) for row in telemetry_rows}
        now = time.time()
        result = []
        for row in rows:
            stats, telemetry_at = telemetry.get(row[0], ({}, None))
            authoritative_deaths = stats.get("deaths") if isinstance(stats.get("deaths"), int) else None
            result.append({
                "id": public_player_id(row[0]),
                "name": row[1],
                "first_seen_at": row[2],
                "last_seen_at": row[3],
                "online": bool(row[4]),
                "connected_at": row[5],
                "sessions_count": row[6],
                "total_play_seconds": int(
                    float(row[7]) + (max(0, now - row[5]) if row[4] and row[5] else 0)
                ),
                "deaths_count": (
                    authoritative_deaths if authoritative_deaths is not None else row[8]
                ),
                "deaths_source": (
                    "behavior-pack" if authoritative_deaths is not None else "derived-log"
                ),
                "last_death_at": row[9],
                "permission": row[10],
                "operator": row[10] == "operator",
                "preferred_game_mode": row[11],
                "telemetry": stats,
                "telemetry_updated_at": telemetry_at,
            })
        return result

    def player_profile(
        self,
        public_id: str,
        history_limit: int = 100,
        session_limit: int = 50,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            identities = [
                row[0] for row in connection.execute("SELECT identity FROM player_profiles")
            ]
            identity = next(
                (value for value in identities if public_player_id(value) == public_id), None
            )
            if identity is None:
                return None
            aliases = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM player_aliases WHERE identity=? ORDER BY first_seen_at",
                    (identity,),
                )
            ]
            history = connection.execute(
                "SELECT id,topic,occurred_at,source,payload FROM player_history "
                "WHERE identity=? ORDER BY occurred_at DESC LIMIT ?",
                (identity, history_limit),
            ).fetchall()
            sessions = connection.execute(
                "SELECT id,connected_at,disconnected_at,duration_seconds,close_reason,inferred "
                "FROM player_sessions WHERE identity=? ORDER BY connected_at DESC LIMIT ?",
                (identity, session_limit),
            ).fetchall()
        profile = next(
            (item for item in self.player_profiles() if item["id"] == public_id), None
        )
        if profile is None:
            return None
        profile["aliases"] = aliases
        telemetry_stats = profile.get("telemetry") or {}
        raw_game_mode = telemetry_stats.get("gameMode")
        profile["observed_game_mode"] = raw_game_mode if isinstance(raw_game_mode, str) and raw_game_mode else None
        # preferred_game_mode is already present via player_profiles(); it is
        # panel-managed and must never be overwritten by telemetry here.
        profile["history"] = [
            {
                "id": row[0], "topic": row[1], "timestamp": row[2],
                "source": row[3], "payload": json.loads(row[4]),
            }
            for row in history
        ]
        profile["sessions"] = [
            {
                "id": row[0], "connected_at": row[1], "disconnected_at": row[2],
                "duration_seconds": int(row[3] or max(0, time.time() - row[1])),
                "close_reason": row[4], "inferred": bool(row[5]), "active": row[2] is None,
            }
            for row in sessions
        ]
        return profile

    def player_activity(
        self,
        kind: str = "all",
        player: str = "",
        source: str = "all",
        search: str = "",
        days: int = 0,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        topics = {
            "all": (
                "player.connected", "player.disconnected", "player.respawned",
                "player.dimension.changed", "player.death", "player.permission.changed",
            ),
            "deaths": ("player.death",),
            "joins": ("player.connected",),
            "leaves": ("player.disconnected",),
            "permissions": ("player.permission.changed",),
            "respawns": ("player.respawned",),
            "dimensions": ("player.dimension.changed",),
        }[kind]
        conditions = [f"h.topic IN ({','.join('?' for _ in topics)})"]
        parameters: list[Any] = list(topics)
        conditions.append(
            "(h.topic!='player.death' OR h.source='behavior-pack' OR NOT EXISTS "
            "(SELECT 1 FROM player_history structured WHERE structured.identity=h.identity "
            "AND structured.topic='player.death' AND structured.source='behavior-pack' "
            "AND abs(structured.occurred_at-h.occurred_at)<=10))"
        )
        if player:
            conditions.append(
                "(lower(p.current_name)=lower(?) OR EXISTS "
                "(SELECT 1 FROM player_aliases a WHERE a.identity=h.identity "
                "AND lower(a.name)=lower(?)))"
            )
            parameters.extend((player, player))
        if source == "structured":
            conditions.append("h.source='behavior-pack'")
        elif source == "server":
            conditions.append("h.source!='behavior-pack'")
        if search:
            conditions.append("(lower(p.current_name) LIKE ? OR lower(h.payload) LIKE ?)")
            pattern = f"%{search.casefold()}%"
            parameters.extend((pattern, pattern))
        if days:
            conditions.append("h.occurred_at>=?")
            parameters.append(time.time() - days * 86400)
        where = " AND ".join(conditions)
        offset = (page - 1) * page_size
        with self._connect() as connection:
            total = int(
                connection.execute(
                    "SELECT count(*) FROM player_history h "
                    "JOIN player_profiles p ON p.identity=h.identity "
                    f"WHERE {where}",
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                "SELECT h.id,h.topic,h.occurred_at,h.source,h.payload,h.identity,p.current_name "
                "FROM player_history h JOIN player_profiles p ON p.identity=h.identity "
                f"WHERE {where} ORDER BY h.occurred_at DESC,h.id DESC LIMIT ? OFFSET ?",
                (*parameters, page_size, offset),
            ).fetchall()
            summary_rows = connection.execute(
                "SELECT h.topic,count(*) FROM player_history h "
                "JOIN player_profiles p ON p.identity=h.identity "
                f"WHERE {where} GROUP BY h.topic",
                parameters,
            ).fetchall()
            first_event_row = connection.execute(
                "SELECT MIN(h.occurred_at) FROM player_history h "
                "JOIN player_profiles p ON p.identity=h.identity "
                "WHERE h.topic IN ("
                "'player.connected','player.disconnected','player.respawned',"
                "'player.dimension.changed','player.death','player.permission.changed')"
            ).fetchone()
        first_event_at = float(first_event_row[0]) if first_event_row and first_event_row[0] is not None else None
        events = []
        for row in rows:
            payload = json.loads(row[4])
            location = payload.get("location") if isinstance(payload.get("location"), dict) else {}
            events.append({
                "id": row[0], "topic": row[1], "timestamp": row[2], "source": row[3],
                "player": {"id": public_player_id(row[5]), "name": row[6]},
                "details": {
                    "cause": payload.get("cause"),
                    "killer": payload.get("killer") or payload.get("killerType"),
                    "projectile": payload.get("projectileType"),
                    "dimension": payload.get("dimension"),
                    "from_dimension": payload.get("from"),
                    "to_dimension": payload.get("to"),
                    "permission": payload.get("permission"),
                    "inferred": bool(payload.get("inferred")),
                    "reason": payload.get("reason"),
                    "coordinates": {
                        key: location.get(key)
                        for key in ("x", "y", "z")
                        if location.get(key) is not None
                    },
                },
            })
        counts = {row[0]: int(row[1]) for row in summary_rows}
        return {
            "events": events, "page": page, "page_size": page_size, "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
            "first_event_at": first_event_at,
            "summary": {
                "joins": counts.get("player.connected", 0),
                "leaves": counts.get("player.disconnected", 0),
                "deaths": counts.get("player.death", 0),
                "permissions": counts.get("player.permission.changed", 0),
                "respawns": counts.get("player.respawned", 0),
                "dimensions": counts.get("player.dimension.changed", 0),
            },
        }

    def player_rankings(self, limit: int = 10) -> dict[str, Any]:
        profiles = self.player_profiles()
        with self._connect() as connection:
            longest_rows = connection.execute(
                "SELECT identity,max(COALESCE(duration_seconds,? - connected_at)) "
                "FROM player_sessions GROUP BY identity",
                (time.time(),),
            ).fetchall()
        longest = {
            public_player_id(row[0]): int(max(0, row[1] or 0)) for row in longest_rows
        }
        definitions = {
            "play_time": ("manager", lambda p: int(p.get("total_play_seconds", 0))),
            "sessions": ("manager", lambda p: int(p.get("sessions_count", 0))),
            "longest_session": ("manager", lambda p: longest.get(p["id"], 0)),
            "deaths": ("mixed", lambda p: int(p.get("deaths_count", 0))),
            "player_kills": ("telemetry-pack", lambda p: int(p.get("telemetry", {}).get("playerKills", 0))),
            "mob_kills": ("telemetry-pack", lambda p: int(p.get("telemetry", {}).get("mobKills", 0))),
            "blocks_broken": ("telemetry-pack", lambda p: int(p.get("telemetry", {}).get("blocksBroken", 0))),
            "blocks_placed": ("telemetry-pack", lambda p: int(p.get("telemetry", {}).get("blocksPlaced", 0))),
            "damage_dealt": ("telemetry-pack", lambda p: float(p.get("telemetry", {}).get("damageDealt", 0))),
            "damage_taken": ("telemetry-pack", lambda p: float(p.get("telemetry", {}).get("damageTaken", 0))),
            "distance": ("telemetry-pack", lambda p: float(p.get("telemetry", {}).get("distance", 0))),
            "dimensions": ("telemetry-pack", lambda p: len(p.get("telemetry", {}).get("dimensions", {}))),
        }
        metrics: dict[str, list[dict[str, Any]]] = {}
        for key, (src, value_for) in definitions.items():
            eligible = (
                profiles if src in {"manager", "mixed"}
                else [p for p in profiles if p.get("telemetry_updated_at")]
            )
            entries = [
                {
                    "player": {"id": p["id"], "name": p["name"]},
                    "value": value_for(p),
                    "source": p.get("deaths_source", src) if key == "deaths" else src,
                    "updated_at": p.get("telemetry_updated_at") if src == "telemetry-pack" else p.get("last_seen_at"),
                }
                for p in eligible
            ]
            entries = [e for e in entries if e["value"] > 0]
            entries.sort(key=lambda e: (-e["value"], e["player"]["name"].casefold()))
            metrics[key] = entries[:limit]
        return {"generated_at": time.time(), "period": "lifetime", "metrics": metrics}

    def block_analytics(self, limit: int = 10) -> dict[str, Any]:
        profiles = [p for p in self.player_profiles() if p.get("telemetry_updated_at")]
        global_broken: dict[str, int] = {}
        global_placed: dict[str, int] = {}
        ore_totals = {ore: 0 for ore in ORE_BLOCKS}
        players = []

        def clean_map(value: Any) -> dict[str, int]:
            if not isinstance(value, dict):
                return {}
            return {
                str(k): int(c) for k, c in value.items()
                if str(k).startswith("minecraft:") and isinstance(c, (int, float)) and c > 0
            }

        def favorite(values: dict[str, int]) -> dict[str, Any] | None:
            if not values:
                return None
            block, count = min(values.items(), key=lambda item: (-item[1], item[0]))
            return {"block": block, "count": count}

        for profile in profiles:
            telemetry = profile.get("telemetry", {})
            broken = clean_map(telemetry.get("brokenByType"))
            placed = clean_map(telemetry.get("placedByType"))
            ores = {
                ore: sum(broken.get(block, 0) for block in blocks)
                for ore, blocks in ORE_BLOCKS.items()
            }
            for block, count in broken.items():
                global_broken[block] = global_broken.get(block, 0) + count
            for block, count in placed.items():
                global_placed[block] = global_placed.get(block, 0) + count
            for ore, count in ores.items():
                ore_totals[ore] += count
            players.append({
                "player": {"id": profile["id"], "name": profile["name"]},
                "blocks_broken": int(telemetry.get("blocksBroken", 0)),
                "blocks_placed": int(telemetry.get("blocksPlaced", 0)),
                "favorite_broken": favorite(broken),
                "favorite_placed": favorite(placed),
                "ores": ores,
                "updated_at": profile.get("telemetry_updated_at"),
            })

        def ranking(value_for):
            entries = [
                {"player": item["player"], "value": value_for(item), "updated_at": item["updated_at"]}
                for item in players
            ]
            entries = [e for e in entries if e["value"] > 0]
            return sorted(entries, key=lambda e: (-e["value"], e["player"]["name"].casefold()))[:limit]

        def top(values: dict[str, int]) -> list[dict[str, Any]]:
            return [
                {"block": block, "count": count}
                for block, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]
            ]

        return {
            "generated_at": time.time(), "period": "lifetime",
            "totals": {
                "broken": sum(item["blocks_broken"] for item in players),
                "placed": sum(item["blocks_placed"] for item in players),
            },
            "top_broken": top(global_broken),
            "top_placed": top(global_placed),
            "ores": ore_totals,
            "rankings": {
                "miners": ranking(lambda item: item["blocks_broken"]),
                "builders": ranking(lambda item: item["blocks_placed"]),
                "ores": {ore: ranking(lambda item, key=ore: item["ores"][key]) for ore in ORE_BLOCKS},
            },
            "players": players,
        }

    def combat_analytics(self, limit: int = 10) -> dict[str, Any]:
        profiles = self.player_profiles()
        known = {
            p["name"].casefold(): {"id": p["id"], "name": p["name"]} for p in profiles
        }
        players = []
        target_totals: dict[str, int] = {}
        for profile in profiles:
            stats = profile.get("telemetry", {}) if profile.get("telemetry_updated_at") else {}
            raw_targets = stats.get("killsByType") if isinstance(stats.get("killsByType"), dict) else {}
            targets = {
                str(name): int(count) for name, count in raw_targets.items()
                if str(name).startswith("minecraft:") and isinstance(count, (int, float)) and count > 0
            }
            for name, count in targets.items():
                target_totals[name] = target_totals.get(name, 0) + count
            favorite_target = None
            if targets:
                name, count = min(targets.items(), key=lambda item: (-item[1], item[0]))
                favorite_target = {"target": name, "kills": count}
            players.append({
                "player": {"id": profile["id"], "name": profile["name"]},
                "deaths": int(profile.get("deaths_count", 0)),
                "player_kills": int(stats.get("playerKills", 0)),
                "mob_kills": int(stats.get("mobKills", 0)),
                "damage_dealt": float(stats.get("damageDealt", 0)),
                "damage_taken": float(stats.get("damageTaken", 0)),
                "kills_by_type": targets,
                "favorite_target": favorite_target,
                "telemetry_available": bool(profile.get("telemetry_updated_at")),
                "updated_at": profile.get("telemetry_updated_at") or profile.get("last_seen_at"),
            })

        causes: dict[str, int] = {}
        opponents: dict[str, int] = {}
        projectiles: dict[str, int] = {}
        pvp: dict[tuple[str, str], int] = {}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT p.current_name,h.payload FROM player_history h "
                "JOIN player_profiles p ON p.identity=h.identity "
                "WHERE h.topic='player.death' AND h.source='behavior-pack'"
            ).fetchall()
        for victim, raw_payload in rows:
            payload = json.loads(raw_payload)
            cause = payload.get("cause")
            killer_name = payload.get("killer")
            killer_type = payload.get("killerType")
            projectile = payload.get("projectileType")
            if isinstance(cause, str) and cause:
                causes[cause] = causes.get(cause, 0) + 1
            opponent = killer_name or killer_type
            if isinstance(opponent, str) and opponent:
                opponents[opponent] = opponents.get(opponent, 0) + 1
            if isinstance(projectile, str) and projectile:
                projectiles[projectile] = projectiles.get(projectile, 0) + 1
            if isinstance(killer_name, str) and killer_name:
                pair = (killer_name, victim)
                pvp[pair] = pvp.get(pair, 0) + 1

        def ranking(field: str) -> list[dict[str, Any]]:
            entries = [
                {"player": item["player"], "value": item[field], "updated_at": item["updated_at"]}
                for item in players if item[field] > 0
            ]
            return sorted(entries, key=lambda e: (-e["value"], e["player"]["name"].casefold()))[:limit]

        def top(values: dict[str, int]) -> list[dict[str, Any]]:
            return [
                {"key": key, "count": count}
                for key, count in sorted(
                    values.items(), key=lambda item: (-item[1], item[0].casefold())
                )[:limit]
            ]

        duels = []
        for (attacker, victim), count in sorted(
            pvp.items(), key=lambda item: (-item[1], item[0][0].casefold(), item[0][1].casefold())
        )[:limit]:
            duels.append({
                "attacker": known.get(attacker.casefold(), {"id": "", "name": attacker}),
                "victim": known.get(victim.casefold(), {"id": "", "name": victim}),
                "count": count,
            })

        return {
            "generated_at": time.time(), "period": "lifetime",
            "totals": {
                "deaths": sum(item["deaths"] for item in players),
                "player_kills": sum(item["player_kills"] for item in players),
                "mob_kills": sum(item["mob_kills"] for item in players),
                "damage_dealt": round(sum(item["damage_dealt"] for item in players), 1),
                "damage_taken": round(sum(item["damage_taken"] for item in players), 1),
            },
            "breakdowns": {"causes": top(causes), "opponents": top(opponents), "projectiles": top(projectiles)},
            "top_targets": [
                {"target": key, "kills": count}
                for key, count in sorted(target_totals.items(), key=lambda item: (-item[1], item[0]))[:limit]
            ],
            "pvp": duels,
            "rankings": {field: ranking(field) for field in ("deaths", "player_kills", "mob_kills", "damage_dealt", "damage_taken")},
            "players": players,
        }

    def exploration_analytics(self, limit: int = 10) -> dict[str, Any]:
        profiles = self.player_profiles()
        players = []
        dimension_totals: dict[str, int] = {}
        dimension_distance: dict[str, float] = {}
        dimension_active: dict[str, float] = {}
        dimension_first: dict[str, float] = {}
        dimension_last: dict[str, float] = {}
        for profile in profiles:
            telemetry = profile.get("telemetry", {}) if profile.get("telemetry_updated_at") else {}
            raw_dimensions = (
                telemetry.get("dimensions") if isinstance(telemetry.get("dimensions"), dict) else {}
            )
            dimensions = {
                str(name): int(count) for name, count in raw_dimensions.items()
                if str(name).startswith("minecraft:") and isinstance(count, (int, float)) and count > 0
            }

            def numeric_map(field: str) -> dict[str, float]:
                value = telemetry.get(field) if isinstance(telemetry.get(field), dict) else {}
                return {
                    str(name): float(amount) for name, amount in value.items()
                    if str(name).startswith("minecraft:") and isinstance(amount, (int, float)) and amount >= 0
                }

            distances = numeric_map("distanceByDimension")
            active_times = numeric_map("activeTimeByDimension")
            first_visits = {
                name: value / 1000 if value > 100_000_000_000 else value
                for name, value in numeric_map("firstDimensionVisitAt").items()
            }
            last_visits = {
                name: value / 1000 if value > 100_000_000_000 else value
                for name, value in numeric_map("lastDimensionVisitAt").items()
            }
            for name, count in dimensions.items():
                dimension_totals[name] = dimension_totals.get(name, 0) + count
            for name, value in distances.items():
                dimension_distance[name] = dimension_distance.get(name, 0) + value
            for name, value in active_times.items():
                dimension_active[name] = dimension_active.get(name, 0) + value
            for name, value in first_visits.items():
                dimension_first[name] = min(dimension_first.get(name, value), value)
            for name, value in last_visits.items():
                dimension_last[name] = max(dimension_last.get(name, value), value)
            favorite = None
            candidates = set(dimensions) | set(distances) | set(active_times)
            if candidates:
                name = min(
                    candidates,
                    key=lambda item: (
                        -active_times.get(item, 0),
                        -distances.get(item, 0),
                        -dimensions.get(item, 0),
                        item,
                    ),
                )
                favorite = {
                    "dimension": name, "visits": dimensions.get(name, 0),
                    "distance": distances.get(name, 0), "active_seconds": active_times.get(name, 0),
                }
            players.append({
                "player": {"id": profile["id"], "name": profile["name"]},
                "distance": float(telemetry.get("distance", 0)),
                "dimensions": dimensions,
                "dimension_count": len(dimensions),
                "favorite_dimension": favorite,
                "distance_by_dimension": distances,
                "active_time_by_dimension": active_times,
                "active_seconds": sum(active_times.values()),
                "play_seconds": int(profile.get("total_play_seconds", 0)),
                "sessions": int(profile.get("sessions_count", 0)),
                "first_seen_at": profile.get("first_seen_at"),
                "last_seen_at": profile.get("last_seen_at"),
                "telemetry_available": bool(profile.get("telemetry_updated_at")),
                "updated_at": profile.get("telemetry_updated_at") or profile.get("last_seen_at"),
            })

        def ranking(field: str) -> list[dict[str, Any]]:
            entries = [
                {"player": item["player"], "value": item[field], "updated_at": item["updated_at"]}
                for item in players if item[field] > 0
            ]
            return sorted(entries, key=lambda e: (-e["value"], e["player"]["name"].casefold()))[:limit]

        transitions = []
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT p.identity,p.current_name,h.occurred_at,h.payload "
                "FROM player_history h JOIN player_profiles p ON p.identity=h.identity "
                "WHERE h.topic='player.dimension.changed' "
                "ORDER BY h.occurred_at DESC,h.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        for identity, name, occurred_at, raw_payload in rows:
            payload = json.loads(raw_payload)
            transitions.append({
                "player": {"id": public_player_id(identity), "name": name},
                "from": payload.get("from"),
                "to": payload.get("to"),
                "timestamp": occurred_at,
            })

        all_dimensions = set(dimension_totals) | set(dimension_distance) | set(dimension_active)
        dimension_list = [
            {
                "dimension": name,
                "visits": dimension_totals.get(name, 0),
                "distance": round(dimension_distance.get(name, 0), 1),
                "active_seconds": round(dimension_active.get(name, 0), 1),
                "first_seen_at": dimension_first.get(name),
                "last_seen_at": dimension_last.get(name),
            }
            for name in sorted(
                all_dimensions,
                key=lambda item: (
                    -dimension_active.get(item, 0),
                    -dimension_distance.get(item, 0),
                    item,
                ),
            )
        ]
        return {
            "generated_at": time.time(), "period": "lifetime",
            "totals": {
                "distance": round(sum(item["distance"] for item in players), 1),
                "dimensions": len(dimension_totals),
                "dimension_visits": sum(dimension_totals.values()),
                "play_seconds": sum(item["play_seconds"] for item in players),
                "sessions": sum(item["sessions"] for item in players),
                "active_seconds": round(sum(item["active_seconds"] for item in players), 1),
            },
            "dimensions": dimension_list,
            "transitions": transitions,
            "rankings": {
                field: ranking(field)
                for field in ("distance", "dimension_count", "play_seconds", "sessions", "active_seconds")
            },
            "players": players,
        }

    def period_analytics(self, days: int = 30, limit: int = 10) -> dict[str, Any]:
        now = time.time()
        timezone = calendar_timezone()
        today = datetime.fromtimestamp(now, timezone).date()
        dates = [(today - timedelta(days=offset)) for offset in reversed(range(days))]
        start_day, end_day = dates[0].isoformat(), dates[-1].isoformat()
        start_at = datetime.combine(dates[0], datetime.min.time(), timezone).timestamp()
        metrics = (
            "play_seconds", "sessions", "joins", "deaths", "player_kills", "mob_kills",
            "blocks_broken", "blocks_placed", "damage_dealt", "damage_taken",
            "distance", "dimension_transitions",
        )
        calendar = {
            day.isoformat(): {"day": day.isoformat(), **{metric: 0 for metric in metrics}}
            for day in dates
        }
        players: dict[str, dict[str, Any]] = {}
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT d.identity,p.current_name,d.day,d.play_seconds,d.sessions,d.joins,"
                "d.deaths,d.player_kills,d.mob_kills,d.blocks_broken,d.blocks_placed,"
                "d.damage_dealt,d.damage_taken,d.distance,d.dimension_transitions "
                "FROM player_daily d JOIN player_profiles p ON p.identity=d.identity "
                "WHERE d.day BETWEEN ? AND ?",
                (start_day, end_day),
            ).fetchall()
            active_sessions = connection.execute(
                "SELECT s.identity,p.current_name,s.connected_at "
                "FROM player_sessions s JOIN player_profiles p ON p.identity=s.identity "
                "WHERE s.disconnected_at IS NULL AND s.connected_at < ?",
                (now,),
            ).fetchall()
            heat_sessions = connection.execute(
                "SELECT connected_at,COALESCE(disconnected_at,?) FROM player_sessions "
                "WHERE connected_at < ? AND COALESCE(disconnected_at,?) > ?",
                (now, now, now, start_at),
            ).fetchall()

        for row in rows:
            identity, name, day = row[:3]
            player = players.setdefault(
                identity,
                {"player": {"id": public_player_id(identity), "name": name}, **{metric: 0 for metric in metrics}},
            )
            for index, metric in enumerate(metrics, start=3):
                value = row[index] or 0
                player[metric] += value
                calendar[day][metric] += value

        for identity, name, connected_at in active_sessions:
            player = players.setdefault(
                identity,
                {"player": {"id": public_player_id(identity), "name": name}, **{metric: 0 for metric in metrics}},
            )
            cursor = max(float(connected_at), start_at)
            while cursor < now:
                local = datetime.fromtimestamp(cursor, timezone)
                next_midnight = datetime.combine(
                    local.date() + timedelta(days=1), datetime.min.time(), timezone
                ).timestamp()
                boundary = min(now, next_midnight)
                amount = boundary - cursor
                key = local.date().isoformat()
                if key in calendar:
                    calendar[key]["play_seconds"] += amount
                    player["play_seconds"] += amount
                cursor = boundary

        heatmap = [{"weekday": weekday, "hour": hour, "seconds": 0} for weekday in range(7) for hour in range(24)]
        heatmap_index = {(item["weekday"], item["hour"]): item for item in heatmap}
        for connected_at, disconnected_at in heat_sessions:
            cursor, end = max(float(connected_at), start_at), min(float(disconnected_at), now)
            while cursor < end:
                local = datetime.fromtimestamp(cursor, timezone)
                next_hour = (
                    local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                ).timestamp()
                boundary = min(end, next_hour)
                heatmap_index[(local.weekday(), local.hour)]["seconds"] += boundary - cursor
                cursor = boundary

        player_values = list(players.values())
        rankings = {}
        for metric in metrics:
            entries = [
                {"player": item["player"], "value": round(item[metric], 1)}
                for item in player_values if item[metric] > 0
            ]
            rankings[metric] = sorted(
                entries, key=lambda e: (-e["value"], e["player"]["name"].casefold())
            )[:limit]
        days_list = list(calendar.values())
        most_active = max(days_list, key=lambda item: item["play_seconds"], default=None)
        if most_active and most_active["play_seconds"] <= 0:
            most_active = None
        return {
            "generated_at": now, "period_days": days, "timezone": str(timezone),
            "totals": {metric: round(sum(day[metric] for day in days_list), 1) for metric in metrics},
            "calendar": days_list, "heatmap": heatmap, "rankings": rankings,
            "most_active_day": most_active, "players": player_values,
        }

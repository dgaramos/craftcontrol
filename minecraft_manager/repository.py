from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
import sqlite3
import time
from typing import Any
import json
import hashlib
import logging

from .migrations import LATEST_SCHEMA_VERSION, run_migrations, schema_version


LOGGER = logging.getLogger(__name__)

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


class StateRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing_database = self.path.is_file() and self.path.stat().st_size > 0
        connection = sqlite3.connect(self.path)
        try:
            before = schema_version(connection)
            if existing_database and before < LATEST_SCHEMA_VERSION:
                self._backup_before_migration(connection, before)
            after = run_migrations(connection)
            connection.execute("PRAGMA journal_mode=WAL")
            LOGGER.info("database schema ready version=%s migrated_from=%s", after, before)
        finally:
            connection.close()

    def database_schema_version(self) -> int:
        with self._connect() as connection:
            return schema_version(connection)

    def _backup_before_migration(self, connection: sqlite3.Connection, version: int) -> Path:
        directory = self.path.parent / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{self.path.name}.pre-v{version}.bak"
        if destination.exists():
            return destination
        backup = sqlite3.connect(destination)
        try:
            connection.backup(backup)
        finally:
            backup.close()
        LOGGER.info("database migration backup created path=%s", destination)
        return destination

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def store(self, kind: str, values: dict[str, str], source: str) -> None:
        now = time.time()
        with self._connect() as connection:
            connection.executemany(
                "INSERT INTO state(kind,key,value,updated_at,source,changed_at) VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(kind,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at,"
                "source=excluded.source,changed_at=CASE WHEN state.value != excluded.value THEN excluded.changed_at ELSE state.changed_at END",
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
            rows = connection.execute("SELECT kind,key,value,updated_at,changed_at,source FROM state").fetchall()
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

    def record_event(self, topic: str, source: str, payload: dict[str, Any]) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO events(topic,created_at,source,payload) VALUES(?,?,?,?)",
                (topic, time.time(), source, json.dumps(payload, ensure_ascii=False)),
            )
            connection.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 2000)")
            return int(cursor.lastrowid)

    def events_after(self, event_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id,topic,created_at,source,payload FROM events WHERE id > ? ORDER BY id LIMIT ?",
                (event_id, limit),
            ).fetchall()
        return [{"id": row[0], "topic": row[1], "timestamp": row[2], "source": row[3], "payload": json.loads(row[4])} for row in rows]

    @staticmethod
    def _temporary_identity(name: str) -> str:
        return f"name:{name.casefold()}"

    @staticmethod
    def _public_player_id(identity: str) -> str:
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    def _player_identity(self, connection: sqlite3.Connection, name: str, xuid: str = "") -> str:
        if xuid:
            identity = f"xuid:{xuid}"
            temporary = self._temporary_identity(name)
            if temporary != identity:
                existing = connection.execute("SELECT identity FROM player_profiles WHERE identity = ?", (temporary,)).fetchone()
                target = connection.execute("SELECT identity FROM player_profiles WHERE identity = ?", (identity,)).fetchone()
                if existing and not target:
                    connection.execute("UPDATE player_profiles SET identity=?,xuid=? WHERE identity=?", (identity, xuid, temporary))
                    connection.execute("UPDATE player_aliases SET identity=? WHERE identity=?", (identity, temporary))
                    connection.execute("UPDATE player_sessions SET identity=? WHERE identity=?", (identity, temporary))
                    connection.execute("UPDATE player_history SET identity=? WHERE identity=?", (identity, temporary))
                    connection.execute("UPDATE player_telemetry SET identity=? WHERE identity=?", (identity, temporary))
            return identity
        row = connection.execute(
            "SELECT p.identity FROM player_profiles p LEFT JOIN player_aliases a ON a.identity=p.identity "
            "WHERE lower(p.current_name)=lower(?) OR lower(a.name)=lower(?) ORDER BY p.last_seen_at DESC LIMIT 1",
            (name, name),
        ).fetchone()
        return str(row[0]) if row else self._temporary_identity(name)

    def observe_player(self, name: str, connected: bool, xuid: str = "", source: str = "bedrock-log", occurred_at: float | None = None) -> dict[str, Any]:
        now = occurred_at or time.time()
        with self._connect() as connection:
            identity = self._player_identity(connection, name, xuid)
            row = connection.execute("SELECT online,connected_at FROM player_profiles WHERE identity=?", (identity,)).fetchone()
            was_online = bool(row[0]) if row else False
            connection.execute(
                "INSERT INTO player_profiles(identity,xuid,current_name,first_seen_at,last_seen_at,online,connected_at) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(identity) DO UPDATE SET "
                "xuid=COALESCE(excluded.xuid,player_profiles.xuid),current_name=excluded.current_name,"
                "last_seen_at=excluded.last_seen_at,online=excluded.online,connected_at=CASE "
                "WHEN excluded.online=1 AND player_profiles.online=0 THEN excluded.connected_at "
                "WHEN excluded.online=0 THEN NULL ELSE player_profiles.connected_at END",
                (identity, xuid or None, name, now, now, int(connected), now if connected else None),
            )
            connection.execute(
                "INSERT INTO player_aliases(identity,name,first_seen_at,last_seen_at) VALUES(?,?,?,?) "
                "ON CONFLICT(identity,name) DO UPDATE SET last_seen_at=excluded.last_seen_at",
                (identity, name, now, now),
            )
            changed = was_online != connected
            if connected and not was_online:
                connection.execute("INSERT INTO player_sessions(identity,connected_at) VALUES(?,?)", (identity, now))
                connection.execute("UPDATE player_profiles SET sessions_count=sessions_count+1 WHERE identity=?", (identity,))
            elif not connected and was_online:
                session = connection.execute(
                    "SELECT id,connected_at FROM player_sessions WHERE identity=? AND disconnected_at IS NULL ORDER BY id DESC LIMIT 1",
                    (identity,),
                ).fetchone()
                if session:
                    duration = max(0, now - float(session[1]))
                    connection.execute(
                        "UPDATE player_sessions SET disconnected_at=?,duration_seconds=?,close_reason='disconnect' WHERE id=?",
                        (now, duration, session[0]),
                    )
                    connection.execute("UPDATE player_profiles SET total_play_seconds=total_play_seconds+? WHERE identity=?", (duration, identity))
            if changed:
                topic = "player.connected" if connected else "player.disconnected"
                self._record_player_history(connection, identity, topic, source, {"name": name}, now)
        return {"identity": identity, "changed": changed}

    def reconcile_online_players(self, players: list[str], xuids: dict[str, str], source: str) -> None:
        now = time.time()
        online_identities: set[str] = set()
        for name in players:
            result = self.observe_player(name, True, xuids.get(name, ""), source, now)
            online_identities.add(result["identity"])
        with self._connect() as connection:
            missing = connection.execute("SELECT identity,current_name FROM player_profiles WHERE online=1").fetchall()
        for identity, name in missing:
            if identity not in online_identities:
                self.observe_player(str(name), False, source=source, occurred_at=now)

    def close_online_sessions(self, reason: str, source: str = "docker-events") -> list[str]:
        now = time.time()
        with self._connect() as connection:
            rows = connection.execute("SELECT identity,current_name,connected_at FROM player_profiles WHERE online=1").fetchall()
            for identity, name, connected_at in rows:
                duration = max(0, now - float(connected_at or now))
                connection.execute(
                    "UPDATE player_sessions SET disconnected_at=?,duration_seconds=?,close_reason=?,inferred=1 "
                    "WHERE id=(SELECT id FROM player_sessions WHERE identity=? AND disconnected_at IS NULL ORDER BY id DESC LIMIT 1)",
                    (now, duration, reason, identity),
                )
                connection.execute(
                    "UPDATE player_profiles SET online=0,connected_at=NULL,last_seen_at=?,total_play_seconds=total_play_seconds+? WHERE identity=?",
                    (now, duration, identity),
                )
                self._record_player_history(connection, identity, "player.disconnected", source, {"name": name, "reason": reason, "inferred": True}, now)
        return [str(row[1]) for row in rows]

    def record_player_death(self, name: str, cause: str, raw: str, source: str, event_key: str) -> bool:
        now = time.time()
        with self._connect() as connection:
            identity = self._player_identity(connection, name)
            if not connection.execute("SELECT 1 FROM player_profiles WHERE identity=?", (identity,)).fetchone():
                connection.execute(
                    "INSERT INTO player_profiles(identity,current_name,first_seen_at,last_seen_at,online) VALUES(?,?,?,?,0)",
                    (identity, name, now, now),
                )
            inserted = self._record_player_history(
                connection, identity, "player.death", source,
                {"name": name, "cause": cause, "raw": raw, "derived": True}, now, event_key,
            )
            if inserted:
                connection.execute("UPDATE player_profiles SET deaths_count=deaths_count+1,last_death_at=?,last_seen_at=? WHERE identity=?", (now, now, identity))
            return inserted

    def _record_player_history(self, connection: sqlite3.Connection, identity: str, topic: str, source: str, payload: dict[str, Any], occurred_at: float, event_key: str | None = None) -> bool:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO player_history(identity,topic,occurred_at,source,payload,event_key) VALUES(?,?,?,?,?,?)",
            (identity, topic, occurred_at, source, json.dumps(payload, ensure_ascii=False), event_key),
        )
        return cursor.rowcount > 0

    def set_player_permission(self, name: str, permission: str, source: str = "manager") -> None:
        now = time.time()
        with self._connect() as connection:
            identity = self._player_identity(connection, name)
            existing = connection.execute("SELECT permission FROM player_profiles WHERE identity=?", (identity,)).fetchone()
            if not existing:
                connection.execute(
                    "INSERT INTO player_profiles(identity,current_name,first_seen_at,last_seen_at,permission) VALUES(?,?,?,?,?)",
                    (identity, name, now, now, permission),
                )
            else:
                connection.execute("UPDATE player_profiles SET permission=? WHERE identity=?", (permission, identity))
            if not existing or existing[0] != permission:
                self._record_player_history(connection, identity, "player.permission.changed", source, {"name": name, "permission": permission}, now)

    def player_profiles(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT identity,current_name,first_seen_at,last_seen_at,online,connected_at,sessions_count,"
                "total_play_seconds,deaths_count,last_death_at,permission FROM player_profiles "
                "ORDER BY online DESC,last_seen_at DESC"
            ).fetchall()
            telemetry_rows = connection.execute("SELECT identity,stats,updated_at FROM player_telemetry").fetchall()
        telemetry = {row[0]: (json.loads(row[1]), row[2]) for row in telemetry_rows}
        now = time.time()
        result = []
        for row in rows:
            stats, telemetry_at = telemetry.get(row[0], ({}, None))
            authoritative_deaths = stats.get("deaths") if isinstance(stats.get("deaths"), int) else None
            result.append({
            "id": self._public_player_id(row[0]), "name": row[1], "first_seen_at": row[2], "last_seen_at": row[3],
            "online": bool(row[4]), "connected_at": row[5], "sessions_count": row[6],
            "total_play_seconds": int(float(row[7]) + (max(0, now - row[5]) if row[4] and row[5] else 0)),
            "deaths_count": authoritative_deaths if authoritative_deaths is not None else row[8],
            "deaths_source": "behavior-pack" if authoritative_deaths is not None else "derived-log",
            "last_death_at": row[9], "permission": row[10], "operator": row[10] == "operator",
            "telemetry": stats, "telemetry_updated_at": telemetry_at,
            })
        return result

    def ingest_telemetry(self, envelope: dict[str, Any]) -> tuple[bool, list[str]]:
        sequence, topic = envelope["sequence"], envelope["type"]
        player = (envelope.get("player") or {}).get("name")
        replay_identity = f":{envelope.get('timestamp', '-')}" if topic.startswith("snapshot.") or topic == "telemetry.started" else ""
        key = f"{sequence}:{topic}:{player or '-'}{replay_identity}"
        now = time.time()
        changed: list[str] = []
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO telemetry_events(event_key,sequence,topic,received_at,payload) VALUES(?,?,?,?,?)",
                (key, sequence, topic, now, json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))),
            )
            if cursor.rowcount == 0:
                return False, []
            connection.execute("DELETE FROM telemetry_events WHERE rowid NOT IN (SELECT rowid FROM telemetry_events ORDER BY received_at DESC LIMIT 10000)")
            if topic == "snapshot.player" and player:
                identity = self._player_identity(connection, player)
                if not connection.execute("SELECT 1 FROM player_profiles WHERE identity=?", (identity,)).fetchone():
                    connection.execute(
                        "INSERT INTO player_profiles(identity,current_name,first_seen_at,last_seen_at) VALUES(?,?,?,?)",
                        (identity, player, now, now),
                    )
                connection.execute(
                    "INSERT INTO player_telemetry(identity,stats,sequence,updated_at) VALUES(?,?,?,?) "
                    "ON CONFLICT(identity) DO UPDATE SET stats=excluded.stats,sequence=excluded.sequence,updated_at=excluded.updated_at",
                    (identity, json.dumps(envelope["data"], ensure_ascii=False), sequence, now),
                )
                changed.append(player)
            elif topic in {"block.broken", "block.placed", "player.respawned", "player.dimension.changed", "entity.died"}:
                changed.extend(self._apply_telemetry_delta(connection, envelope, now))
        return True, changed

    def _apply_telemetry_delta(self, connection: sqlite3.Connection, envelope: dict[str, Any], now: float) -> list[str]:
        topic, data = envelope["type"], envelope["data"]
        names: list[str] = []
        if topic == "entity.died":
            names = [name for name in (data.get("victim"), data.get("killer")) if isinstance(name, str)]
        else:
            name = (envelope.get("player") or {}).get("name")
            names = [name] if name else []
        for name in dict.fromkeys(names):
            identity = self._player_identity(connection, name)
            row = connection.execute("SELECT stats FROM player_telemetry WHERE identity=?", (identity,)).fetchone()
            if row:
                stats = json.loads(row[0])
                if topic == "block.broken" and name == names[0]:
                    stats["blocksBroken"] = int(stats.get("blocksBroken", 0)) + 1
                    self._increment_block_map(stats, "brokenByType", data.get("blockType"))
                if topic == "block.placed" and name == names[0]:
                    stats["blocksPlaced"] = int(stats.get("blocksPlaced", 0)) + 1
                    self._increment_block_map(stats, "placedByType", data.get("blockType"))
                if topic == "entity.died" and name == data.get("victim"): stats["deaths"] = int(stats.get("deaths", 0)) + 1
                if topic == "entity.died" and name == data.get("killer"):
                    key = "playerKills" if data.get("victim") else "mobKills"
                    stats[key] = int(stats.get(key, 0)) + 1
                connection.execute("UPDATE player_telemetry SET stats=?,sequence=?,updated_at=? WHERE identity=?", (json.dumps(stats), envelope["sequence"], now, identity))
            if topic == "entity.died" and name == data.get("victim"):
                if not connection.execute("SELECT 1 FROM player_profiles WHERE identity=?", (identity,)).fetchone():
                    connection.execute(
                        "INSERT INTO player_profiles(identity,current_name,first_seen_at,last_seen_at) VALUES(?,?,?,?)",
                        (identity, name, now, now),
                    )
                connection.execute("UPDATE player_profiles SET last_death_at=?,last_seen_at=? WHERE identity=?", (now, now, identity))
                self._record_player_history(
                    connection, identity, "player.death", "behavior-pack", data, now,
                    f"telemetry:{envelope['sequence']}:death:{identity}",
                )
            elif topic in {"player.respawned", "player.dimension.changed"}:
                if not connection.execute("SELECT 1 FROM player_profiles WHERE identity=?", (identity,)).fetchone():
                    connection.execute(
                        "INSERT INTO player_profiles(identity,current_name,first_seen_at,last_seen_at) VALUES(?,?,?,?)",
                        (identity, name, now, now),
                    )
                connection.execute("UPDATE player_profiles SET last_seen_at=? WHERE identity=?", (now, identity))
                self._record_player_history(
                    connection, identity, topic, "behavior-pack", data, now,
                    f"telemetry:{envelope['sequence']}:{topic}:{identity}",
                )
        return list(dict.fromkeys(names))

    @staticmethod
    def _increment_block_map(stats: dict[str, Any], field: str, block_type: Any, limit: int = 128) -> None:
        if not isinstance(block_type, str) or not block_type.startswith("minecraft:") or len(block_type) > 112:
            return
        values = stats.get(field) if isinstance(stats.get(field), dict) else {}
        values[block_type] = int(values.get(block_type, 0)) + 1
        if len(values) > limit:
            values = dict(sorted(values.items(), key=lambda item: (-int(item[1]), item[0]))[:limit])
        stats[field] = values

    def player_profile(self, public_id: str, history_limit: int = 100, session_limit: int = 50) -> dict[str, Any] | None:
        with self._connect() as connection:
            identities = [row[0] for row in connection.execute("SELECT identity FROM player_profiles")]
            identity = next((value for value in identities if self._public_player_id(value) == public_id), None)
            if identity is None:
                return None
            aliases = [row[0] for row in connection.execute("SELECT name FROM player_aliases WHERE identity=? ORDER BY first_seen_at", (identity,))]
            history = connection.execute(
                "SELECT id,topic,occurred_at,source,payload FROM player_history WHERE identity=? ORDER BY occurred_at DESC LIMIT ?",
                (identity, history_limit),
            ).fetchall()
            sessions = connection.execute(
                "SELECT id,connected_at,disconnected_at,duration_seconds,close_reason,inferred "
                "FROM player_sessions WHERE identity=? ORDER BY connected_at DESC LIMIT ?",
                (identity, session_limit),
            ).fetchall()
        profile = next((item for item in self.player_profiles() if item["id"] == public_id), None)
        if profile is None:
            return None
        profile["aliases"] = aliases
        profile["history"] = [{"id": row[0], "topic": row[1], "timestamp": row[2], "source": row[3], "payload": json.loads(row[4])} for row in history]
        profile["sessions"] = [{
            "id": row[0], "connected_at": row[1], "disconnected_at": row[2],
            "duration_seconds": int(row[3] or max(0, time.time() - row[1])),
            "close_reason": row[4], "inferred": bool(row[5]), "active": row[2] is None,
        } for row in sessions]
        return profile

    def player_activity(
        self, kind: str = "all", player: str = "", source: str = "all", search: str = "",
        days: int = 0, page: int = 1, page_size: int = 25,
    ) -> dict[str, Any]:
        topics = {
            "all": ("player.connected", "player.disconnected", "player.respawned", "player.dimension.changed", "player.death", "player.permission.changed"),
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
                "(SELECT 1 FROM player_aliases a WHERE a.identity=h.identity AND lower(a.name)=lower(?)))"
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
            total = int(connection.execute(
                f"SELECT count(*) FROM player_history h JOIN player_profiles p ON p.identity=h.identity WHERE {where}",
                parameters,
            ).fetchone()[0])
            rows = connection.execute(
                "SELECT h.id,h.topic,h.occurred_at,h.source,h.payload,h.identity,p.current_name "
                f"FROM player_history h JOIN player_profiles p ON p.identity=h.identity WHERE {where} "
                "ORDER BY h.occurred_at DESC,h.id DESC LIMIT ? OFFSET ?",
                (*parameters, page_size, offset),
            ).fetchall()
            summary_rows = connection.execute(
                "SELECT h.topic,count(*) FROM player_history h JOIN player_profiles p ON p.identity=h.identity "
                f"WHERE {where} GROUP BY h.topic", parameters,
            ).fetchall()
        events = []
        for row in rows:
            payload = json.loads(row[4])
            location = payload.get("location") if isinstance(payload.get("location"), dict) else {}
            events.append({
                "id": row[0], "topic": row[1], "timestamp": row[2], "source": row[3],
                "player": {"id": self._public_player_id(row[5]), "name": row[6]},
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
                    "coordinates": {key: location.get(key) for key in ("x", "y", "z") if location.get(key) is not None},
                },
            })
        counts = {row[0]: int(row[1]) for row in summary_rows}
        return {
            "events": events, "page": page, "page_size": page_size, "total": total,
            "pages": max(1, (total + page_size - 1) // page_size),
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
                "FROM player_sessions GROUP BY identity", (time.time(),),
            ).fetchall()
        longest = {self._public_player_id(row[0]): int(max(0, row[1] or 0)) for row in longest_rows}

        definitions = {
            "play_time": ("manager", lambda profile: int(profile.get("total_play_seconds", 0))),
            "sessions": ("manager", lambda profile: int(profile.get("sessions_count", 0))),
            "longest_session": ("manager", lambda profile: longest.get(profile["id"], 0)),
            "deaths": ("mixed", lambda profile: int(profile.get("deaths_count", 0))),
            "player_kills": ("telemetry-pack", lambda profile: int(profile.get("telemetry", {}).get("playerKills", 0))),
            "mob_kills": ("telemetry-pack", lambda profile: int(profile.get("telemetry", {}).get("mobKills", 0))),
            "blocks_broken": ("telemetry-pack", lambda profile: int(profile.get("telemetry", {}).get("blocksBroken", 0))),
            "blocks_placed": ("telemetry-pack", lambda profile: int(profile.get("telemetry", {}).get("blocksPlaced", 0))),
            "damage_dealt": ("telemetry-pack", lambda profile: float(profile.get("telemetry", {}).get("damageDealt", 0))),
            "damage_taken": ("telemetry-pack", lambda profile: float(profile.get("telemetry", {}).get("damageTaken", 0))),
            "distance": ("telemetry-pack", lambda profile: float(profile.get("telemetry", {}).get("distance", 0))),
            "dimensions": ("telemetry-pack", lambda profile: len(profile.get("telemetry", {}).get("dimensions", {}))),
        }
        metrics: dict[str, list[dict[str, Any]]] = {}
        for key, (source, value_for) in definitions.items():
            eligible = profiles if source in {"manager", "mixed"} else [profile for profile in profiles if profile.get("telemetry_updated_at")]
            entries = [{
                "player": {"id": profile["id"], "name": profile["name"]},
                "value": value_for(profile),
                "source": profile.get("deaths_source", source) if key == "deaths" else source,
                "updated_at": profile.get("telemetry_updated_at") if source == "telemetry-pack" else profile.get("last_seen_at"),
            } for profile in eligible]
            entries = [entry for entry in entries if entry["value"] > 0]
            entries.sort(key=lambda entry: (-entry["value"], entry["player"]["name"].casefold()))
            metrics[key] = entries[:limit]
        return {"generated_at": time.time(), "period": "lifetime", "metrics": metrics}

    def block_analytics(self, limit: int = 10) -> dict[str, Any]:
        profiles = [profile for profile in self.player_profiles() if profile.get("telemetry_updated_at")]
        global_broken: dict[str, int] = {}
        global_placed: dict[str, int] = {}
        ore_totals = {ore: 0 for ore in ORE_BLOCKS}
        players = []

        def clean_map(value: Any) -> dict[str, int]:
            if not isinstance(value, dict):
                return {}
            return {str(key): int(count) for key, count in value.items() if str(key).startswith("minecraft:") and isinstance(count, (int, float)) and count > 0}

        def favorite(values: dict[str, int]) -> dict[str, Any] | None:
            if not values:
                return None
            block, count = min(values.items(), key=lambda item: (-item[1], item[0]))
            return {"block": block, "count": count}

        for profile in profiles:
            telemetry = profile.get("telemetry", {})
            broken = clean_map(telemetry.get("brokenByType"))
            placed = clean_map(telemetry.get("placedByType"))
            ores = {ore: sum(broken.get(block, 0) for block in blocks) for ore, blocks in ORE_BLOCKS.items()}
            for block, count in broken.items(): global_broken[block] = global_broken.get(block, 0) + count
            for block, count in placed.items(): global_placed[block] = global_placed.get(block, 0) + count
            for ore, count in ores.items(): ore_totals[ore] += count
            players.append({
                "player": {"id": profile["id"], "name": profile["name"]},
                "blocks_broken": int(telemetry.get("blocksBroken", 0)),
                "blocks_placed": int(telemetry.get("blocksPlaced", 0)),
                "favorite_broken": favorite(broken), "favorite_placed": favorite(placed),
                "ores": ores, "updated_at": profile.get("telemetry_updated_at"),
            })

        def ranking(value_for):
            entries = [{"player": item["player"], "value": value_for(item), "updated_at": item["updated_at"]} for item in players]
            entries = [entry for entry in entries if entry["value"] > 0]
            return sorted(entries, key=lambda entry: (-entry["value"], entry["player"]["name"].casefold()))[:limit]

        def top(values: dict[str, int]) -> list[dict[str, Any]]:
            return [{"block": block, "count": count} for block, count in sorted(values.items(), key=lambda item: (-item[1], item[0]))[:limit]]

        return {
            "generated_at": time.time(), "period": "lifetime",
            "totals": {"broken": sum(item["blocks_broken"] for item in players), "placed": sum(item["blocks_placed"] for item in players)},
            "top_broken": top(global_broken), "top_placed": top(global_placed), "ores": ore_totals,
            "rankings": {
                "miners": ranking(lambda item: item["blocks_broken"]),
                "builders": ranking(lambda item: item["blocks_placed"]),
                "ores": {ore: ranking(lambda item, key=ore: item["ores"][key]) for ore in ORE_BLOCKS},
            },
            "players": players,
        }

    def combat_analytics(self, limit: int = 10) -> dict[str, Any]:
        profiles = self.player_profiles()
        known = {profile["name"].casefold(): {"id": profile["id"], "name": profile["name"]} for profile in profiles}
        players = []
        for profile in profiles:
            stats = profile.get("telemetry", {}) if profile.get("telemetry_updated_at") else {}
            players.append({
                "player": {"id": profile["id"], "name": profile["name"]},
                "deaths": int(profile.get("deaths_count", 0)),
                "player_kills": int(stats.get("playerKills", 0)),
                "mob_kills": int(stats.get("mobKills", 0)),
                "damage_dealt": float(stats.get("damageDealt", 0)),
                "damage_taken": float(stats.get("damageTaken", 0)),
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
            if isinstance(cause, str) and cause: causes[cause] = causes.get(cause, 0) + 1
            opponent = killer_name or killer_type
            if isinstance(opponent, str) and opponent: opponents[opponent] = opponents.get(opponent, 0) + 1
            if isinstance(projectile, str) and projectile: projectiles[projectile] = projectiles.get(projectile, 0) + 1
            if isinstance(killer_name, str) and killer_name:
                pair = (killer_name, victim)
                pvp[pair] = pvp.get(pair, 0) + 1

        def ranking(field: str) -> list[dict[str, Any]]:
            entries = [{"player": item["player"], "value": item[field], "updated_at": item["updated_at"]} for item in players if item[field] > 0]
            return sorted(entries, key=lambda entry: (-entry["value"], entry["player"]["name"].casefold()))[:limit]

        def top(values: dict[str, int]) -> list[dict[str, Any]]:
            return [{"key": key, "count": count} for key, count in sorted(values.items(), key=lambda item: (-item[1], item[0].casefold()))[:limit]]

        duels = []
        for (attacker, victim), count in sorted(pvp.items(), key=lambda item: (-item[1], item[0][0].casefold(), item[0][1].casefold()))[:limit]:
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
            "pvp": duels,
            "rankings": {field: ranking(field) for field in ("deaths", "player_kills", "mob_kills", "damage_dealt", "damage_taken")},
            "players": players,
        }

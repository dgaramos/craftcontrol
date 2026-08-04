from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
import sqlite3
import time
from typing import Any
import json
import hashlib


class StateRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS state (kind TEXT, key TEXT, value TEXT, updated_at REAL, "
                "source TEXT, PRIMARY KEY(kind,key))"
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(state)")}
            if "changed_at" not in columns:
                connection.execute("ALTER TABLE state ADD COLUMN changed_at REAL")
                connection.execute("UPDATE state SET changed_at = updated_at WHERE changed_at IS NULL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT NOT NULL, "
                "created_at REAL NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS player_profiles (identity TEXT PRIMARY KEY, xuid TEXT UNIQUE, "
                "current_name TEXT NOT NULL, first_seen_at REAL NOT NULL, last_seen_at REAL NOT NULL, "
                "online INTEGER NOT NULL DEFAULT 0, connected_at REAL, sessions_count INTEGER NOT NULL DEFAULT 0, "
                "total_play_seconds REAL NOT NULL DEFAULT 0, deaths_count INTEGER NOT NULL DEFAULT 0, "
                "last_death_at REAL, permission TEXT NOT NULL DEFAULT 'member')"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS player_aliases (identity TEXT NOT NULL, name TEXT NOT NULL, "
                "first_seen_at REAL NOT NULL, last_seen_at REAL NOT NULL, PRIMARY KEY(identity,name))"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS player_sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "identity TEXT NOT NULL, connected_at REAL NOT NULL, disconnected_at REAL, duration_seconds REAL, "
                "close_reason TEXT, inferred INTEGER NOT NULL DEFAULT 0)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS player_history (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "identity TEXT NOT NULL, topic TEXT NOT NULL, occurred_at REAL NOT NULL, source TEXT NOT NULL, "
                "payload TEXT NOT NULL, event_key TEXT UNIQUE)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_player_history_identity ON player_history(identity,occurred_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_player_sessions_identity ON player_sessions(identity,connected_at DESC)")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS player_telemetry (identity TEXT PRIMARY KEY, stats TEXT NOT NULL, "
                "sequence INTEGER NOT NULL, updated_at REAL NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS telemetry_events (event_key TEXT PRIMARY KEY, sequence INTEGER NOT NULL, "
                "topic TEXT NOT NULL, received_at REAL NOT NULL)"
            )
            connection.execute("PRAGMA journal_mode=WAL")

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
                "INSERT OR IGNORE INTO telemetry_events(event_key,sequence,topic,received_at) VALUES(?,?,?,?)",
                (key, sequence, topic, now),
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
            elif topic in {"block.broken", "block.placed", "player.dimension.changed", "entity.died"}:
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
                if topic == "block.broken" and name == names[0]: stats["blocksBroken"] = int(stats.get("blocksBroken", 0)) + 1
                if topic == "block.placed" and name == names[0]: stats["blocksPlaced"] = int(stats.get("blocksPlaced", 0)) + 1
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
        return list(dict.fromkeys(names))

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

from __future__ import annotations

import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import threading
import time
from typing import Any

import docker as docker_sdk
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

CONTAINER = os.getenv("MINECRAFT_CONTAINER", "minecraft-bedrock")
PROJECT = Path(os.getenv("MINECRAFT_PROJECT", "/minecraft-project"))
ENV_FILE = PROJECT / ".env"
DATABASE = Path("/data/manager.db")
REFRESH_LOCK = threading.Lock()
REFRESHING = False

SETTINGS: dict[str, dict[str, Any]] = {
    "SERVER_NAME": {"label": "Nome do servidor", "type": "text", "group": "Geral", "restart": True},
    "GAMEMODE": {"label": "Modo de jogo", "type": "select", "options": ["survival", "creative", "adventure"], "group": "Geral", "restart": True},
    "DIFFICULTY": {"label": "Dificuldade", "type": "select", "options": ["peaceful", "easy", "normal", "hard"], "group": "Geral", "restart": True},
    "ALLOW_CHEATS": {"label": "Permitir cheats", "type": "boolean", "group": "Geral", "restart": True},
    "MAX_PLAYERS": {"label": "Máximo de jogadores", "type": "number", "min": 1, "max": 100, "group": "Geral", "restart": True},
    "VIEW_DISTANCE": {"label": "Distância de visão", "type": "number", "min": 5, "max": 96, "group": "Mundo", "restart": True},
    "TICK_DISTANCE": {"label": "Distância de simulação", "type": "number", "min": 4, "max": 12, "group": "Mundo", "restart": True},
    "LEVEL_NAME": {"label": "Nome interno do mundo", "type": "text", "group": "Mundo", "restart": True, "warning": "Trocar seleciona ou cria outro mundo"},
    "LEVEL_SEED": {"label": "Seed", "type": "text", "group": "Mundo", "restart": True, "warning": "Só afeta um mundo novo"},
    "LEVEL_TYPE": {"label": "Tipo do mundo", "type": "select", "options": ["DEFAULT", "FLAT", "LEGACY"], "group": "Mundo", "restart": True},
    "FORCE_GAMEMODE": {"label": "Forçar modo de jogo", "type": "boolean", "group": "Mundo", "restart": True},
    "PLAYER_IDLE_TIMEOUT": {"label": "Expulsar inativo (minutos)", "type": "number", "min": 0, "max": 1440, "group": "Jogadores", "restart": True},
    "DEFAULT_PLAYER_PERMISSION_LEVEL": {"label": "Permissão padrão", "type": "select", "options": ["visitor", "member", "operator"], "group": "Jogadores", "restart": True},
    "ALLOW_LIST": {"label": "Usar allowlist", "type": "boolean", "group": "Jogadores", "restart": True},
    "ONLINE_MODE": {"label": "Autenticação Xbox Live", "type": "boolean", "group": "Jogadores", "restart": True},
    "TEXTUREPACK_REQUIRED": {"label": "Exigir resource packs", "type": "boolean", "group": "Packs", "restart": True},
    "ENABLE_LAN_VISIBILITY": {"label": "Descoberta na rede local", "type": "boolean", "group": "Rede", "restart": True},
    "SERVER_PORT": {"label": "Porta IPv4", "type": "number", "min": 1, "max": 65535, "group": "Rede", "restart": True},
    "SERVER_PORT_V6": {"label": "Porta IPv6", "type": "number", "min": 1, "max": 65535, "group": "Rede", "restart": True},
    "MAX_THREADS": {"label": "Máximo de threads", "type": "number", "min": 0, "max": 64, "group": "Avançado", "restart": True},
    "COMPRESSION_THRESHOLD": {"label": "Limite de compressão", "type": "number", "min": 0, "max": 65535, "group": "Avançado", "restart": True},
}

GAMERULES: dict[str, dict[str, Any]] = {
    "showcoordinates": {"label": "Mostrar coordenadas", "group": "Interface", "type": "boolean"},
    "showdaysplayed": {"label": "Mostrar dias jogados", "group": "Interface", "type": "boolean"},
    "showdeathmessages": {"label": "Mostrar mensagens de morte", "group": "Interface", "type": "boolean"},
    "showrecipemessages": {"label": "Avisos de receitas", "group": "Interface", "type": "boolean"},
    "pvp": {"label": "PvP", "group": "Jogabilidade", "type": "boolean"},
    "keepinventory": {"label": "Manter inventário ao morrer", "group": "Jogabilidade", "type": "boolean"},
    "naturalregeneration": {"label": "Regeneração natural", "group": "Jogabilidade", "type": "boolean"},
    "doimmediaterespawn": {"label": "Respawn imediato", "group": "Jogabilidade", "type": "boolean"},
    "spawnradius": {"label": "Raio de spawn", "group": "Jogabilidade", "type": "number", "min": 0, "max": 128},
    "dodaylightcycle": {"label": "Ciclo do dia", "group": "Tempo e clima", "type": "boolean"},
    "doweathercycle": {"label": "Ciclo climático", "group": "Tempo e clima", "type": "boolean"},
    "dofiretick": {"label": "Fogo se espalha", "group": "Tempo e clima", "type": "boolean"},
    "tntexplodes": {"label": "TNT explode", "group": "Tempo e clima", "type": "boolean"},
    "randomtickspeed": {"label": "Velocidade de ticks aleatórios", "group": "Tempo e clima", "type": "number", "min": 0, "max": 4096},
    "domobspawning": {"label": "Surgimento de criaturas", "group": "Criaturas", "type": "boolean"},
    "mobgriefing": {"label": "Criaturas alteram blocos", "group": "Criaturas", "type": "boolean"},
    "doinsomnia": {"label": "Phantoms por insônia", "group": "Criaturas", "type": "boolean"},
    "domobloot": {"label": "Criaturas deixam itens", "group": "Drops", "type": "boolean"},
    "dotiledrops": {"label": "Blocos deixam itens", "group": "Drops", "type": "boolean"},
    "doentitydrops": {"label": "Entidades deixam itens", "group": "Drops", "type": "boolean"},
    "tntexplosiondropdecay": {"label": "Explosão reduz drops", "group": "Drops", "type": "boolean"},
    "commandblockoutput": {"label": "Saída de command blocks", "group": "Comandos", "type": "boolean"},
    "sendcommandfeedback": {"label": "Feedback de comandos", "group": "Comandos", "type": "boolean"},
    "commandblocksenabled": {"label": "Command blocks ativos", "group": "Comandos", "type": "boolean"},
    "maxcommandchainlength": {"label": "Tamanho máximo da cadeia", "group": "Comandos", "type": "number", "min": 0, "max": 65536},
    "functioncommandlimit": {"label": "Limite de comandos por função", "group": "Comandos", "type": "number", "min": 0, "max": 10000},
}

PROPERTY_NAMES = {
    "SERVER_NAME": "server-name", "GAMEMODE": "gamemode", "FORCE_GAMEMODE": "force-gamemode",
    "DIFFICULTY": "difficulty", "ALLOW_CHEATS": "allow-cheats", "MAX_PLAYERS": "max-players",
    "VIEW_DISTANCE": "view-distance", "TICK_DISTANCE": "tick-distance", "LEVEL_NAME": "level-name",
    "LEVEL_SEED": "level-seed", "LEVEL_TYPE": "level-type", "PLAYER_IDLE_TIMEOUT": "player-idle-timeout",
    "DEFAULT_PLAYER_PERMISSION_LEVEL": "default-player-permission-level", "ALLOW_LIST": "allow-list",
    "ONLINE_MODE": "online-mode", "TEXTUREPACK_REQUIRED": "texturepack-required",
    "ENABLE_LAN_VISIBILITY": "enable-lan-visibility", "SERVER_PORT": "server-port",
    "SERVER_PORT_V6": "server-portv6", "MAX_THREADS": "max-threads",
    "COMPRESSION_THRESHOLD": "compression-threshold",
}


def database() -> sqlite3.Connection:
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS state (kind TEXT, key TEXT, value TEXT, updated_at REAL, source TEXT, PRIMARY KEY(kind,key))"
    )
    return connection


def cache_values(kind: str, values: dict[str, str], source: str) -> None:
    now = time.time()
    with database() as connection:
        connection.executemany(
            "INSERT INTO state(kind,key,value,updated_at,source) VALUES(?,?,?,?,?) "
            "ON CONFLICT(kind,key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at,source=excluded.source",
            [(kind, key, value, now, source) for key, value in values.items()],
        )


def replace_cache(kind: str, values: dict[str, str], source: str) -> None:
    with database() as connection:
        connection.execute("DELETE FROM state WHERE kind = ?", (kind,))
    cache_values(kind, values, source)


def cached_state() -> dict[str, Any]:
    result: dict[str, Any] = {
        "settings": {}, "gamerules": {}, "players": [], "online": 0,
        "max_players": 0, "updated_at": 0, "refreshing": REFRESHING,
    }
    with database() as connection:
        rows = connection.execute("SELECT kind,key,value,updated_at FROM state").fetchall()
    for kind, key, value, updated_at in rows:
        if kind == "players":
            result["players"].append(key)
        elif kind == "server" and key in {"online", "max_players"}:
            result[key] = int(value)
        else:
            result.setdefault(kind, {})[key] = value
        result["updated_at"] = max(result["updated_at"], updated_at)
    return result


def read_properties() -> dict[str, str]:
    path = PROJECT / "data" / "server.properties"
    properties: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                properties[key.strip()] = value.strip()
    return properties


def query_console_state() -> tuple[dict[str, str], list[str], int, int]:
    client = docker_sdk.from_env()
    container = client.containers.get(CONTAINER)
    since = int(time.time()) - 1
    channel = container.attach_socket(params={"stdin": 1, "stream": 1, "stdout": 0, "stderr": 0})
    try:
        raw_socket = getattr(channel, "_sock", channel)
        commands = "".join(f"gamerule {rule}\n" for rule in GAMERULES) + "list\n"
        raw_socket.sendall(commands.encode("utf-8"))
    finally:
        channel.close()
    time.sleep(1.0)
    logs = container.logs(since=since, tail=250).decode("utf-8", errors="replace")
    client.close()
    values: dict[str, str] = {}
    for rule in GAMERULES:
        matches = re.findall(rf"{re.escape(rule)}[^\r\n]*?\b(true|false|-?\d+)\b", logs, re.IGNORECASE)
        if matches:
            values[rule] = matches[-1].lower()
    players: list[str] = []
    online = 0
    maximum = 0
    markers = list(re.finditer(r"There are\s+(\d+)/(\d+)\s+players online:?", logs, re.IGNORECASE))
    if markers:
        current = markers[-1]
        online, maximum = int(current.group(1)), int(current.group(2))
        for line in logs[current.end():].splitlines():
            clean = re.sub(r"^\[[^]]+\]\s*", "", line).strip()
            if not clean or re.search(r"gamerule|Game rule|INFO|WARN|ERROR", clean, re.IGNORECASE):
                continue
            players.extend(name.strip() for name in clean.split(",") if name.strip())
            if len(players) >= online:
                break
    return values, players[:online], online, maximum


def refresh_state() -> None:
    global REFRESHING
    if not REFRESH_LOCK.acquire(blocking=False):
        return
    REFRESHING = True
    try:
        _, env_values = read_env()
        properties = read_properties()
        settings = {key: env_values.get(key) or properties.get(PROPERTY_NAMES.get(key, ""), "") for key in SETTINGS}
        cache_values("settings", settings, "env+server.properties")
        gamerules, players, online, maximum = query_console_state()
        if gamerules:
            cache_values("gamerules", gamerules, "bedrock-console")
        replace_cache("players", {name: "online" for name in players}, "bedrock-console")
        cache_values("server", {"online": str(online), "max_players": str(maximum)}, "bedrock-console")
    finally:
        REFRESHING = False
        REFRESH_LOCK.release()


def refresh_async() -> None:
    threading.Thread(target=refresh_state, name="state-refresh", daemon=True).start()


def run_docker(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)


def send_console(parts: list[str]) -> None:
    if not parts or any(not re.fullmatch(r"[a-z0-9_-]+", part, re.IGNORECASE) for part in parts):
        raise ValueError("Comando inválido")
    client = docker_sdk.from_env()
    container = client.containers.get(CONTAINER)
    channel = container.attach_socket(params={"stdin": 1, "stream": 1, "stdout": 0, "stderr": 0})
    try:
        raw_socket = getattr(channel, "_sock", channel)
        raw_socket.sendall((" ".join(parts) + "\n").encode("utf-8"))
    finally:
        channel.close()
        client.close()


def read_env() -> tuple[list[str], dict[str, str]]:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    values: dict[str, str] = {}
    for line in lines:
        if line and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return lines, values


def write_env(changes: dict[str, str]) -> None:
    lines, _ = read_env()
    found: set[str] = set()
    output: list[str] = []
    for line in lines:
        if line and not line.lstrip().startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in changes:
                output.append(f"{key}={changes[key]}")
                found.add(key)
                continue
        output.append(line)
    for key, value in changes.items():
        if key not in found:
            output.append(f"{key}={value}")
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".env.", dir=ENV_FILE.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output).rstrip() + "\n")
        os.replace(temporary, ENV_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_value(definition: dict[str, Any], value: Any) -> str:
    kind = definition["type"]
    if kind == "boolean":
        if value not in (True, False, "true", "false"):
            raise ValueError("valor booleano inválido")
        return "true" if value in (True, "true") else "false"
    if kind == "number":
        number = int(value)
        if number < definition.get("min", number) or number > definition.get("max", number):
            raise ValueError("valor fora do intervalo")
        return str(number)
    value = str(value).strip()
    if kind == "select" and value not in definition["options"]:
        raise ValueError("opção inválida")
    if not value or len(value) > 120 or any(character in value for character in "\n\r\0"):
        raise ValueError("texto inválido")
    return value


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/api/schema")
def schema():
    return jsonify(settings=SETTINGS, gamerules=GAMERULES)


@app.get("/api/config")
def config():
    current = cached_state()["settings"]
    if not current:
        refresh_state()
        current = cached_state()["settings"]
    return jsonify(current)


@app.get("/api/state")
def state():
    return jsonify(cached_state())


@app.post("/api/refresh")
def refresh():
    refresh_async()
    return jsonify(ok=True, refreshing=True), 202


@app.put("/api/config")
def update_config():
    payload = request.get_json(force=True)
    if not isinstance(payload, dict):
        return jsonify(error="Formato inválido"), 400
    try:
        changes = {key: validate_value(SETTINGS[key], value) for key, value in payload.items() if key in SETTINGS}
    except (TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    if not changes:
        return jsonify(error="Nenhuma configuração válida"), 400
    write_env(changes)
    cache_values("settings", changes, "manager")
    return jsonify(ok=True, restart_required=True, changed=list(changes))


@app.get("/api/status")
def status():
    result = run_docker("inspect", "-f", "{{.State.Status}}", CONTAINER)
    state = result.stdout.strip() if result.returncode == 0 else "stopped"
    return jsonify(container=CONTAINER, state=state, online=state == "running")


@app.post("/api/server/<action>")
def server_action(action: str):
    if action == "start":
        result = run_docker("compose", "--project-directory", str(PROJECT), "up", "-d", "minecraft-bedrock", timeout=120)
    elif action == "apply":
        result = run_docker("compose", "--project-directory", str(PROJECT), "up", "-d", "--force-recreate", "minecraft-bedrock", timeout=120)
    elif action in {"stop", "restart"}:
        result = run_docker(action, CONTAINER, timeout=120)
    else:
        return jsonify(error="Ação não permitida"), 404
    if result.returncode != 0:
        return jsonify(error=(result.stderr or result.stdout).strip()), 500
    return jsonify(ok=True, action=action)


@app.put("/api/gamerules/<rule>")
def set_gamerule(rule: str):
    if rule not in GAMERULES:
        return jsonify(error="Gamerule não permitida"), 404
    try:
        value = validate_value(GAMERULES[rule], request.get_json(force=True).get("value"))
    except (AttributeError, TypeError, ValueError) as error:
        return jsonify(error=str(error)), 400
    try:
        send_console(["gamerule", rule, value])
        cache_values("gamerules", {rule: value}, "manager")
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, rule=rule, value=value)


@app.post("/api/world/<action>")
def world_action(action: str):
    commands = {"day": ["time", "set", "day"], "night": ["time", "set", "night"], "clear-weather": ["weather", "clear"]}
    if action not in commands:
        return jsonify(error="Ação não permitida"), 404
    try:
        send_console(commands[action])
    except Exception as error:
        return jsonify(error=str(error)), 500
    return jsonify(ok=True, action=action)


with database():
    pass
refresh_async()

from __future__ import annotations

from typing import Any

Field = dict[str, Any]

SETTINGS: dict[str, Field] = {
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

GAMERULES: dict[str, Field] = {
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
    "SERVER_PORT_V6": "server-portv6", "MAX_THREADS": "max-threads", "COMPRESSION_THRESHOLD": "compression-threshold",
}


def validate_value(definition: Field, value: Any) -> str:
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
    text = str(value).strip()
    if kind == "select" and text not in definition["options"]:
        raise ValueError("opção inválida")
    if not text or len(text) > 120 or any(character in text for character in "\n\r\0"):
        raise ValueError("texto inválido")
    return text

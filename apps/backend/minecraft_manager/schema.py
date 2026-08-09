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

DESCRIPTIONS = {
    "SERVER_NAME": "Nome exibido na lista de servidores dos jogadores.",
    "GAMEMODE": "Define o modo padrão: sobrevivência, criativo ou aventura.",
    "DIFFICULTY": "Controla dano, fome e força e frequência das criaturas hostis.",
    "ALLOW_CHEATS": "Permite comandos administrativos que podem desativar conquistas neste mundo.",
    "MAX_PLAYERS": "Quantidade máxima de jogadores conectados ao mesmo tempo.",
    "VIEW_DISTANCE": "Distância, em chunks, enviada ao jogador. Valores altos usam mais rede e memória.",
    "TICK_DISTANCE": "Área ao redor dos jogadores onde plantações, criaturas e mecanismos continuam funcionando.",
    "LEVEL_NAME": "Pasta do mundo carregada pelo servidor. Um nome diferente pode criar ou abrir outro mundo.",
    "LEVEL_SEED": "Código usado para gerar um mundo novo. Não modifica partes já geradas do mundo atual.",
    "LEVEL_TYPE": "Formato da geração de um mundo novo, como normal ou plano.",
    "FORCE_GAMEMODE": "Força jogadores a usarem o modo padrão sempre que entrarem no servidor.",
    "PLAYER_IDLE_TIMEOUT": "Expulsa jogadores inativos após este tempo. Use zero para desativar.",
    "DEFAULT_PLAYER_PERMISSION_LEVEL": "Permissão concedida por padrão: visitante, membro ou operador.",
    "ALLOW_LIST": "Quando ativada, somente jogadores adicionados à lista de permissão podem entrar.",
    "ONLINE_MODE": "Valida a conta do jogador pelos serviços Xbox Live. Recomenda-se manter ativado.",
    "TEXTUREPACK_REQUIRED": "Impede a entrada de quem recusar os pacotes de recursos do servidor.",
    "ENABLE_LAN_VISIBILITY": "Permite que dispositivos na rede local descubram o servidor automaticamente.",
    "SERVER_PORT": "Porta UDP usada por conexões Bedrock via IPv4. O padrão costuma ser 19132.",
    "SERVER_PORT_V6": "Porta UDP usada por conexões Bedrock via IPv6. O padrão costuma ser 19133.",
    "MAX_THREADS": "Limita threads do servidor. Zero deixa o Bedrock escolher automaticamente.",
    "COMPRESSION_THRESHOLD": "Tamanho mínimo, em bytes, para comprimir pacotes de rede. Alterar sem necessidade pode piorar o desempenho.",
    "showcoordinates": "Mostra as coordenadas X, Y e Z no canto da tela dos jogadores.",
    "showdaysplayed": "Mostra quantos dias do Minecraft já transcorreram neste mundo.",
    "showdeathmessages": "Exibe mensagens de morte no chat para os jogadores.",
    "showrecipemessages": "Mostra notificações quando novas receitas são desbloqueadas.",
    "pvp": "Permite que jogadores causem dano uns aos outros.",
    "keepinventory": "Mantém inventário e experiência do jogador depois da morte.",
    "naturalregeneration": "Recupera vida naturalmente quando o jogador está bem alimentado.",
    "doimmediaterespawn": "Faz o jogador renascer sem mostrar a tela de morte.",
    "spawnradius": "Raio aleatório, em blocos, ao redor do ponto inicial onde novos jogadores aparecem.",
    "dodaylightcycle": "Faz o tempo avançar normalmente entre dia e noite.",
    "doweathercycle": "Permite mudanças naturais entre tempo limpo, chuva e tempestade.",
    "dofiretick": "Permite que fogo se espalhe e apague naturalmente.",
    "tntexplodes": "Permite que blocos de TNT ativados explodam.",
    "randomtickspeed": "Velocidade de eventos aleatórios como crescimento de plantas. O padrão do Bedrock é 1.",
    "domobspawning": "Permite o surgimento natural de criaturas no mundo.",
    "mobgriefing": "Permite que criaturas alterem blocos, como Creepers destruindo e Endermen movendo blocos.",
    "doinsomnia": "Permite o aparecimento de Phantoms quando jogadores passam vários dias sem dormir.",
    "domobloot": "Faz criaturas deixarem itens e experiência quando morrem.",
    "dotiledrops": "Faz blocos destruídos deixarem seus itens correspondentes.",
    "doentitydrops": "Permite que entidades que não são criaturas deixem itens quando destruídas.",
    "tntexplosiondropdecay": "Reduz a quantidade de blocos recuperados após explosões de TNT.",
    "commandblockoutput": "Exibe no chat a saída produzida por blocos de comando.",
    "sendcommandfeedback": "Mostra ao executor a resposta dos comandos utilizados.",
    "commandblocksenabled": "Permite o funcionamento de blocos de comando no mundo.",
    "maxcommandchainlength": "Número máximo de blocos de comando em cadeia executados no mesmo tick.",
    "functioncommandlimit": "Quantidade máxima de comandos executados por uma função de uma só vez.",
}

for key, description in DESCRIPTIONS.items():
    (SETTINGS.get(key) or GAMERULES[key])["description"] = description

ENGLISH_FIELDS = {
    "SERVER_NAME": ("Server name", "Name shown to players in the server list."),
    "GAMEMODE": ("Game mode", "Sets the default mode: survival, creative, or adventure."),
    "DIFFICULTY": ("Difficulty", "Controls damage, hunger, and the strength and frequency of hostile mobs."),
    "ALLOW_CHEATS": ("Allow cheats", "Allows administrative commands that may disable achievements in this world."),
    "MAX_PLAYERS": ("Maximum players", "Maximum number of players connected at the same time."),
    "VIEW_DISTANCE": ("View distance", "Chunks sent to each player. Higher values use more network bandwidth and memory."),
    "TICK_DISTANCE": ("Simulation distance", "Area around players where crops, mobs, and mechanisms continue to work."),
    "LEVEL_NAME": ("Internal world name", "World folder loaded by the server. A different name may create or open another world."),
    "LEVEL_SEED": ("Seed", "Code used to generate a new world. It does not change existing generated areas."),
    "LEVEL_TYPE": ("World type", "Generation format for a new world, such as normal or flat."),
    "FORCE_GAMEMODE": ("Force game mode", "Forces players into the default game mode whenever they join."),
    "PLAYER_IDLE_TIMEOUT": ("Idle timeout (minutes)", "Kicks inactive players after this time. Use zero to disable."),
    "DEFAULT_PLAYER_PERMISSION_LEVEL": ("Default permission", "Default permission assigned to players: visitor, member, or operator."),
    "ALLOW_LIST": ("Use allowlist", "Only players added to the allowlist can join when enabled."),
    "ONLINE_MODE": ("Xbox Live authentication", "Validates player accounts through Xbox Live services. Keep this enabled when possible."),
    "TEXTUREPACK_REQUIRED": ("Require resource packs", "Prevents players from joining if they refuse the server resource packs."),
    "ENABLE_LAN_VISIBILITY": ("LAN discovery", "Allows devices on the local network to discover the server automatically."),
    "SERVER_PORT": ("IPv4 port", "UDP port for Bedrock IPv4 connections. The common default is 19132."),
    "SERVER_PORT_V6": ("IPv6 port", "UDP port for Bedrock IPv6 connections. The common default is 19133."),
    "MAX_THREADS": ("Maximum threads", "Limits server threads. Zero lets Bedrock choose automatically."),
    "COMPRESSION_THRESHOLD": ("Compression threshold", "Minimum packet size in bytes before compression. Unnecessary changes may reduce performance."),
    "showcoordinates": ("Show coordinates", "Shows X, Y, and Z coordinates on the players' screens."),
    "showdaysplayed": ("Show days played", "Shows how many Minecraft days have elapsed in this world."),
    "showdeathmessages": ("Show death messages", "Displays player death messages in chat."),
    "showrecipemessages": ("Show recipe messages", "Shows notifications when new recipes are unlocked."),
    "pvp": ("PvP", "Allows players to damage one another."),
    "keepinventory": ("Keep inventory", "Keeps a player's inventory and experience after death."),
    "naturalregeneration": ("Natural regeneration", "Restores health naturally when a player is well fed."),
    "doimmediaterespawn": ("Immediate respawn", "Respawns players without showing the death screen."),
    "spawnradius": ("Spawn radius", "Random radius in blocks around the world spawn where new players appear."),
    "dodaylightcycle": ("Daylight cycle", "Advances time normally between day and night."),
    "doweathercycle": ("Weather cycle", "Allows natural changes between clear weather, rain, and storms."),
    "dofiretick": ("Fire spread", "Allows fire to spread and extinguish naturally."),
    "tntexplodes": ("TNT explodes", "Allows primed TNT blocks to explode."),
    "randomtickspeed": ("Random tick speed", "Controls random events such as crop growth. The Bedrock default is 1."),
    "domobspawning": ("Mob spawning", "Allows mobs to spawn naturally in the world."),
    "mobgriefing": ("Mob griefing", "Allows mobs to change blocks, such as Creeper explosions and Endermen moving blocks."),
    "doinsomnia": ("Insomnia", "Allows Phantoms to spawn after players go several days without sleeping."),
    "domobloot": ("Mob loot", "Makes mobs drop items and experience when they die."),
    "dotiledrops": ("Block drops", "Makes destroyed blocks drop their corresponding items."),
    "doentitydrops": ("Entity drops", "Allows non-mob entities to drop items when destroyed."),
    "tntexplosiondropdecay": ("TNT drop decay", "Reduces the number of blocks recovered after TNT explosions."),
    "commandblockoutput": ("Command block output", "Displays command block output in chat."),
    "sendcommandfeedback": ("Command feedback", "Shows command responses to the player who executed them."),
    "commandblocksenabled": ("Command blocks", "Allows command blocks to operate in the world."),
    "maxcommandchainlength": ("Maximum command chain", "Maximum command blocks in a chain executed during one tick."),
    "functioncommandlimit": ("Function command limit", "Maximum number of commands executed by a function at once."),
}

SETTINGS["LEVEL_NAME"]["warning_en"] = "Changing this selects or creates another world"
SETTINGS["LEVEL_SEED"]["warning_en"] = "Only affects a newly generated world"

for key, (label, description) in ENGLISH_FIELDS.items():
    field = SETTINGS.get(key) or GAMERULES[key]
    field["label_en"] = label
    field["description_en"] = description


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

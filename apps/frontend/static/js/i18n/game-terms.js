export function createGameTerms({ getLocale, escapeHtml }) {
  const blockLabels = {
    stone: ["Pedra", "Stone"], cobblestone: ["Pedregulho", "Cobblestone"], deepslate: ["Ardósia profunda", "Deepslate"], cobbled_deepslate: ["Ardósia profunda quebrada", "Cobbled deepslate"],
    dirt: ["Terra", "Dirt"], grass_block: ["Bloco de grama", "Grass block"], sand: ["Areia", "Sand"], red_sand: ["Areia vermelha", "Red sand"], gravel: ["Cascalho", "Gravel"], clay: ["Argila", "Clay"],
    oak_log: ["Tronco de carvalho", "Oak log"], birch_log: ["Tronco de bétula", "Birch log"], spruce_log: ["Tronco de pinheiro", "Spruce log"], jungle_log: ["Tronco de árvore da selva", "Jungle log"], acacia_log: ["Tronco de acácia", "Acacia log"], dark_oak_log: ["Tronco de carvalho escuro", "Dark oak log"], mangrove_log: ["Tronco de mangue", "Mangrove log"], cherry_log: ["Tronco de cerejeira", "Cherry log"],
    oak_planks: ["Tábuas de carvalho", "Oak planks"], birch_planks: ["Tábuas de bétula", "Birch planks"], spruce_planks: ["Tábuas de pinheiro", "Spruce planks"], jungle_planks: ["Tábuas da selva", "Jungle planks"], acacia_planks: ["Tábuas de acácia", "Acacia planks"], dark_oak_planks: ["Tábuas de carvalho escuro", "Dark oak planks"], mangrove_planks: ["Tábuas de mangue", "Mangrove planks"], cherry_planks: ["Tábuas de cerejeira", "Cherry planks"],
    glass: ["Vidro", "Glass"], glass_pane: ["Painel de vidro", "Glass pane"], netherrack: ["Netherrack", "Netherrack"], soul_sand: ["Areia das almas", "Soul sand"], obsidian: ["Obsidiana", "Obsidian"], bedrock: ["Rocha-mãe", "Bedrock"],
    coal_ore: ["Minério de carvão", "Coal ore"], iron_ore: ["Minério de ferro", "Iron ore"], copper_ore: ["Minério de cobre", "Copper ore"], gold_ore: ["Minério de ouro", "Gold ore"], redstone_ore: ["Minério de redstone", "Redstone ore"], lapis_ore: ["Minério de lápis-lazúli", "Lapis lazuli ore"], diamond_ore: ["Minério de diamante", "Diamond ore"], emerald_ore: ["Minério de esmeralda", "Emerald ore"], nether_quartz_ore: ["Minério de quartzo do Nether", "Nether quartz ore"], ancient_debris: ["Detritos ancestrais", "Ancient debris"],
    deepslate_coal_ore: ["Minério de carvão em ardósia", "Deepslate coal ore"], deepslate_iron_ore: ["Minério de ferro em ardósia", "Deepslate iron ore"], deepslate_copper_ore: ["Minério de cobre em ardósia", "Deepslate copper ore"], deepslate_gold_ore: ["Minério de ouro em ardósia", "Deepslate gold ore"], deepslate_redstone_ore: ["Minério de redstone em ardósia", "Deepslate redstone ore"], deepslate_lapis_ore: ["Minério de lápis-lazúli em ardósia", "Deepslate lapis ore"], deepslate_diamond_ore: ["Minério de diamante em ardósia", "Deepslate diamond ore"], deepslate_emerald_ore: ["Minério de esmeralda em ardósia", "Deepslate emerald ore"],
    water: ["Água", "Water"], flowing_water: ["Água corrente", "Flowing water"], lava: ["Lava", "Lava"], flowing_lava: ["Lava corrente", "Flowing lava"], torch: ["Tocha", "Torch"], crafting_table: ["Bancada de trabalho", "Crafting table"], furnace: ["Fornalha", "Furnace"], chest: ["Baú", "Chest"],
    overworld: ["Mundo superior", "Overworld"], nether: ["Nether", "Nether"], the_end: ["End", "The End"],
    acacia_leaves: ["Folhas de acácia", "Acacia leaves"], acacia_sapling: ["Muda de acácia", "Acacia sapling"], acacia_trapdoor: ["Alçapão de acácia", "Acacia trapdoor"],
    andesite: ["Andesito", "Andesite"], bed: ["Cama", "Bed"], birch_door: ["Porta de bétula", "Birch door"], birch_fence: ["Cerca de bétula", "Birch fence"], birch_fence_gate: ["Portão de cerca de bétula", "Birch fence gate"], birch_leaves: ["Folhas de bétula", "Birch leaves"], birch_pressure_plate: ["Placa de pressão de bétula", "Birch pressure plate"], birch_sapling: ["Muda de bétula", "Birch sapling"],
    brown_wool: ["Lã marrom", "Brown wool"], bush: ["Arbusto", "Bush"], carrots: ["Cenouras", "Carrots"], cobblestone_wall: ["Muro de pedregulho", "Cobblestone wall"], composter: ["Composteira", "Composter"],
    diorite: ["Diorito", "Diorite"], fence_gate: ["Portão de cerca", "Fence gate"], firefly_bush: ["Arbusto de vaga-lumes", "Firefly bush"], granite: ["Granito", "Granite"], jungle_fence_gate: ["Portão de cerca da selva", "Jungle fence gate"], ladder: ["Escada de mão", "Ladder"], leaf_litter: ["Folhiço", "Leaf litter"], melon_stem: ["Caule de melancia", "Melon stem"],
    oak_leaves: ["Folhas de carvalho", "Oak leaves"], oak_sapling: ["Muda de carvalho", "Oak sapling"], oak_stairs: ["Escadas de carvalho", "Oak stairs"], peony: ["Peônia", "Peony"], potatoes: ["Batatas", "Potatoes"], reeds: ["Cana-de-açúcar", "Sugar cane"], short_grass: ["Grama baixa", "Short grass"], stone_stairs: ["Escadas de pedra", "Stone stairs"], stripped_birch_log: ["Tronco de bétula descascado", "Stripped birch log"], tall_grass: ["Grama alta", "Tall grass"], trapdoor: ["Alçapão", "Trapdoor"], trip_wire: ["Fio de armadilha", "Tripwire"], vine: ["Trepadeiras", "Vines"], wheat: ["Trigo", "Wheat"], wildflowers: ["Flores silvestres", "Wildflowers"], wooden_door: ["Porta de madeira", "Wooden door"],
  };

  const blockWordLabels = { polished: "polido", bricks: "tijolos", brick: "tijolo", stairs: "escadas", slab: "laje", wall: "muro", leaves: "folhas", leaf: "folha", litter: "folhiço", log: "tronco", wood: "madeira", planks: "tábuas", stripped: "descascado", mossy: "musgoso", sapling: "muda", door: "porta", trapdoor: "alçapão", fence: "cerca", gate: "portão", pressure: "pressão", plate: "placa", stem: "caule", bush: "arbusto", flowers: "flores", grass: "grama", white: "branco", black: "preto", red: "vermelho", blue: "azul", green: "verde", yellow: "amarelo", brown: "marrom", gray: "cinza", light: "claro", concrete: "concreto", wool: "lã", terracotta: "terracota", stone: "pedra", cobblestone: "pedregulho", deepslate: "ardósia profunda", oak: "carvalho", birch: "bétula", spruce: "pinheiro", jungle: "selva", acacia: "acácia", cherry: "cerejeira", mangrove: "mangue", dark: "escuro" };
  const blockLabelsEs = {
    stone: "Piedra", cobblestone: "Adoquín", deepslate: "Pizarra profunda", cobbled_deepslate: "Pizarra profunda rocosa", dirt: "Tierra", grass_block: "Bloque de césped", sand: "Arena", red_sand: "Arena roja", gravel: "Grava", clay: "Arcilla",
    oak_log: "Tronco de roble", birch_log: "Tronco de abedul", spruce_log: "Tronco de abeto", jungle_log: "Tronco de jungla", acacia_log: "Tronco de acacia", dark_oak_log: "Tronco de roble oscuro", mangrove_log: "Tronco de mangle", cherry_log: "Tronco de cerezo",
    oak_planks: "Tablones de roble", birch_planks: "Tablones de abedul", spruce_planks: "Tablones de abeto", jungle_planks: "Tablones de jungla", acacia_planks: "Tablones de acacia", dark_oak_planks: "Tablones de roble oscuro", mangrove_planks: "Tablones de mangle", cherry_planks: "Tablones de cerezo",
    glass: "Cristal", glass_pane: "Panel de cristal", netherrack: "Netherrack", soul_sand: "Arena de almas", obsidian: "Obsidiana", bedrock: "Roca madre", coal_ore: "Mena de carbón", iron_ore: "Mena de hierro", copper_ore: "Mena de cobre", gold_ore: "Mena de oro", redstone_ore: "Mena de redstone", lapis_ore: "Mena de lapislázuli", diamond_ore: "Mena de diamante", emerald_ore: "Mena de esmeralda", nether_quartz_ore: "Mena de cuarzo del Nether", ancient_debris: "Escombros ancestrales",
    water: "Agua", flowing_water: "Agua fluyendo", lava: "Lava", flowing_lava: "Lava fluyendo", torch: "Antorcha", crafting_table: "Mesa de trabajo", furnace: "Horno", chest: "Cofre", overworld: "Supramundo", nether: "Nether", the_end: "El End",
    acacia_leaves: "Hojas de acacia", acacia_sapling: "Brote de acacia", acacia_trapdoor: "Trampilla de acacia", andesite: "Andesita", bed: "Cama", birch_door: "Puerta de abedul", birch_fence: "Valla de abedul", birch_fence_gate: "Puerta de valla de abedul", birch_leaves: "Hojas de abedul", birch_pressure_plate: "Placa de presión de abedul", birch_sapling: "Brote de abedul", brown_wool: "Lana marrón", bush: "Arbusto", carrots: "Zanahorias", cobblestone_wall: "Muro de adoquín", composter: "Compostador", diorite: "Diorita", fence_gate: "Puerta de valla", firefly_bush: "Arbusto de luciérnagas", granite: "Granito", jungle_fence_gate: "Puerta de valla de jungla", ladder: "Escalera de mano", leaf_litter: "Hojarasca", melon_stem: "Tallo de sandía", oak_leaves: "Hojas de roble", oak_sapling: "Brote de roble", oak_stairs: "Escaleras de roble", peony: "Peonía", potatoes: "Patatas", reeds: "Caña de azúcar", short_grass: "Hierba corta", stone_stairs: "Escaleras de piedra", stripped_birch_log: "Tronco de abedul sin corteza", tall_grass: "Hierba alta", trapdoor: "Trampilla", trip_wire: "Hilo de trampa", vine: "Enredaderas", wheat: "Trigo", wildflowers: "Flores silvestres", wooden_door: "Puerta de madera",
  };

  function blockName(identifier) {
    const raw = String(identifier || "—").replace(/^minecraft:/, "");
    if (getLocale() === "es" && blockLabelsEs[raw]) return blockLabelsEs[raw];
    const known = blockLabels[raw];
    if (known) return known[getLocale() === "pt" ? 0 : 1];
    const words = raw.split("_");
    const localized = getLocale() === "pt" ? words.map((word) => blockWordLabels[word] || word).join(" ") : words.join(" ");
    return localized.charAt(0).toLocaleUpperCase() + localized.slice(1);
  }

  function blockIconName(identifier) {
    const raw = String(identifier || "").replace(/^minecraft:/, "");
    if (/water/.test(raw)) return "water";
    if (/lava/.test(raw)) return "lava";
    if (/ancient_debris/.test(raw)) return "ancient-debris";
    for (const ore of ["diamond", "emerald", "redstone", "lapis", "copper", "gold", "iron", "coal", "quartz"]) if (raw.includes(ore)) return ore;
    if (/deepslate/.test(raw)) return "deepslate";
    if (/grass|moss/.test(raw)) return "grass";
    if (/dirt|mud|clay/.test(raw)) return "dirt";
    if (/sand|gravel/.test(raw)) return "sand";
    if (/log|stem|wood/.test(raw)) return "log";
    if (/planks|slab|stairs|fence|door|trapdoor/.test(raw)) return "planks";
    if (/leaves|leaf|vine|sapling|bush|flower|grass|wheat|carrot|potato|reeds|stem/.test(raw)) return "leaves";
    if (/glass|ice/.test(raw)) return "glass";
    if (/stone|andesite|granite|diorite|obsidian|netherrack|brick|concrete|terracotta|bedrock/.test(raw)) return "stone";
    if (/ore/.test(raw)) return "ore";
    return "unknown";
  }

  function blockIcon(identifier, label = "") {
    const icon = blockIconName(identifier);
    const accessible = label ? ` role="img" aria-label="${escapeHtml(label)}"` : " aria-hidden=\"true\"";
    return `<svg class="block-icon block-icon-${icon}" viewBox="0 0 24 24"${accessible}><use href="/static/craftcontrol-blocks.svg#block-${icon}"></use></svg>`;
  }

  function blockTermMarkup(identifier) {
    const label = blockName(identifier);
    return `<span class="block-term">${blockIcon(identifier)}<span>${escapeHtml(label)}</span></span>`;
  }

  function dimensionName(identifier) {
    const name = blockName(identifier);
    if (String(identifier || "").replace(/^minecraft:/, "") !== "the_end") return name;
    return getLocale() === "pt" ? "O End" : getLocale() === "es" ? "El End" : "The End";
  }

  function uiIcon(name, label = "", className = "") {
    const safeName = /^[a-z0-9-]+$/.test(name) ? name : "blocks";
    const accessible = label ? ` role="img" aria-label="${escapeHtml(label)}"` : " aria-hidden=\"true\"";
    return `<svg class="cc-icon cc-icon-${safeName} ${className}" viewBox="0 0 24 24"${accessible}><use href="/static/craftcontrol-ui.svg#ui-${safeName}"></use></svg>`;
  }

  const gameTerms = {
    entity: {
      zombie: ["zombie", "Zumbi", "Zombie"], skeleton: ["skeleton", "Esqueleto", "Skeleton"], creeper: ["creeper", "Creeper", "Creeper"],
      spider: ["spider", "Aranha", "Spider"], drowned: ["drowned", "Afogado", "Drowned"], cow: ["cow", "Vaca", "Cow"],
      pig: ["pig", "Porco", "Pig"], sheep: ["sheep", "Ovelha", "Sheep"], chicken: ["chicken", "Galinha", "Chicken"],
      player: ["player", "Jogador", "Player"], arrow: ["arrow", "Flecha", "Arrow"], trident: ["trident", "Tridente", "Trident"],
      zombie_villager_v2: ["zombie", "Aldeão zumbi", "Zombie villager"], enderman: ["enderman", "Enderman", "Enderman"],
      blaze: ["blaze", "Blaze", "Blaze"], ghast: ["ghast", "Ghast", "Ghast"], witch: ["witch", "Bruxa", "Witch"],
    },
    cause: {
      entityAttack: ["unknown", "Ataque de criatura", "Entity attack"], entityExplosion: ["creeper", "Explosão de criatura", "Entity explosion"],
      blockExplosion: ["creeper", "Explosão de bloco", "Block explosion"], projectile: ["arrow", "Projétil", "Projectile"],
      fall: ["unknown", "Queda", "Fall"], fire: ["blaze", "Fogo", "Fire"], fireTick: ["blaze", "Queimadura", "Burning"],
      lava: ["blaze", "Lava", "Lava"], drowning: ["drowned", "Afogamento", "Drowning"], suffocation: ["unknown", "Sufocamento", "Suffocation"],
      starvation: ["unknown", "Fome", "Starvation"], void: ["enderman", "Vazio", "Void"], magic: ["witch", "Magia", "Magic"],
      wither: ["unknown", "Wither", "Wither"], freezing: ["unknown", "Congelamento", "Freezing"], lightning: ["unknown", "Raio", "Lightning"],
    },
  };

  function gameTerm(value, kind = "entity") {
    const raw = String(value || "—").replace(/^minecraft:/, "");
    const known = gameTerms[kind]?.[raw];
    if (known) return known;
    const words = raw.replace(/([a-z])([A-Z])/g, "$1 $2").replaceAll("_", " ").toLocaleLowerCase();
    return ["unknown", words.charAt(0).toLocaleUpperCase() + words.slice(1), words.charAt(0).toLocaleUpperCase() + words.slice(1)];
  }

  function gameIcon(value, kind = "entity", label = "") {
    const icon = gameTerm(value, kind)[0];
    const safeIcon = /^[a-z0-9-]+$/.test(icon) ? icon : "unknown";
    const accessible = label ? ` role="img" aria-label="${escapeHtml(label)}"` : " aria-hidden=\"true\"";
    return `<svg class="mob-icon mob-icon-${safeIcon}" viewBox="0 0 24 24"${accessible}><use href="/static/craftcontrol-mobs.svg#mob-${safeIcon}"></use></svg>`;
  }
  const gameLabelsEs = { zombie: "Zombi", skeleton: "Esqueleto", creeper: "Creeper", spider: "Araña", drowned: "Ahogado", cow: "Vaca", pig: "Cerdo", sheep: "Oveja", chicken: "Gallina", player: "Jugador", arrow: "Flecha", trident: "Tridente", zombie_villager_v2: "Aldeano zombi", enderman: "Enderman", blaze: "Blaze", ghast: "Ghast", witch: "Bruja", entityAttack: "Ataque de criatura", entityExplosion: "Explosión de criatura", blockExplosion: "Explosión de bloque", projectile: "Proyectil", fall: "Caída", fire: "Fuego", fireTick: "Quemadura", lava: "Lava", drowning: "Ahogamiento", suffocation: "Asfixia", starvation: "Hambre", void: "Vacío", magic: "Magia", wither: "Wither", freezing: "Congelación", lightning: "Rayo" };
  function gameLabel(value, kind = "entity") { const raw = String(value || "—").replace(/^minecraft:/, ""); if (getLocale() === "es" && gameLabelsEs[raw]) return gameLabelsEs[raw]; const term = gameTerm(value, kind); return term[getLocale() === "pt" ? 1 : 2]; }
  function gameTermMarkup(value, kind = "entity") {
    const label = gameLabel(value, kind);
    return `<span class="game-term">${gameIcon(value, kind)}<span>${escapeHtml(label)}</span></span>`;
  }

  return { blockTermMarkup, blockIcon, dimensionName, gameTermMarkup, gameIcon, gameLabel, uiIcon };
}

import { api } from "./js/api.js?v=1";
import { connectEventStream } from "./js/events.js";
import { requireSession } from "./js/auth.js?v=1";

const state = {
  schema: null, config: {}, gamerules: {}, players: [], online: 0, maxPlayers: 0,
  changes: {}, tab: "home", tabs: ["home", "world", "players", "analytics", "rules", "server"], status: null, updatedAt: 0, domains: {},
  analytics: { kind: "all", player: "", source: "all", search: "", days: 0, page: 1, rankingCategory: "activity", rankingMetric: "play_time", blocksMode: "mining", selectedOre: "diamond", combatMetric: "mob_kills" },
  locale: (localStorage.getItem("craftcontrol-locale") || localStorage.getItem("manager-locale")) === "en" ? "en" : "pt",
  user: null,
};
const $ = (selector) => document.querySelector(selector);
const content = $("#content");

if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
window.addEventListener("pageshow", () => requestAnimationFrame(() => window.scrollTo(0, 0)));

const messages = {
  pt: {
    brandKicker: "CENTRAL BEDROCK",
    refresh: "Atualizar", worldState: "ESTADO DO MUNDO", quickActions: "Ações rápidas",
    day: "Dia", night: "Noite", clearWeather: "Clima limpo", server: "Servidor",
    saveChanges: "Salvar alterações", control: "CONTROLE", serverOperation: "Operação do servidor",
    restartNotice: "Alterações persistentes entram em vigor ao aplicar e reiniciar.",
    start: "Iniciar", restart: "Reiniciar", stop: "Parar", close: "Fechar",
    checking: "Verificando…", online: "Online", stopped: "Parado", serverOnline: "Servidor online",
    serverStopped: "Servidor parado", playersOnline: "jogadores online", nobody: "Ninguém conectado",
    awaiting: "Aguardando atualização", updated: "Atualizado", enabled: "Ativado", disabled: "Desativado",
    unknown: "Não consultado", immediate: "Aplicação imediata", restartRequired: "Aplicado ao salvar e reiniciar",
    saved: "Salvo. Aplicando no servidor…", serverUpdated: "Servidor atualizado",
    noChanges: "Nenhuma alteração pendente", querying: "Consultando o servidor…",
    stateUpdated: "Estado atualizado", worldUpdated: "Mundo atualizado", operationDone: "Operação concluída",
    confirmAction: (action) => `${action} o servidor?`, saveCount: (count) => `Salvar (${count})`,
    fieldUpdated: (label) => `${label} atualizado`,
    timeControls: "Tempo e clima", timeControlsHint: "Horário, ciclos e clima", timeOfDay: "Horário do mundo",
    sunrise: "Nascer do sol", noon: "Meio-dia", sunset: "Pôr do sol", midnight: "Meia-noite",
    exactTime: "Horário exato", exactTimeHelp: "Defina um valor entre 0 e 24000 ticks.", setTime: "Definir horário",
    advanceTime: "Avançar tempo", advanceTimeHelp: "Adicione de 1 a 240000 ticks ao relógio atual.", addTime: "Avançar",
    cycles: "Ciclos automáticos", daylightCycle: "Ciclo de dia e noite", weatherCycle: "Ciclo climático",
    timeQueries: "Consultar relógio", daytime: "Ticks do dia", gametime: "Tempo total", days: "Dias jogados",
    queryResult: "Resultado", weatherTitle: "Clima", clear: "Limpo", rain: "Chuva", thunder: "Tempestade",
    duration: "Duração opcional em ticks", setWeather: "Aplicar clima", queryWeather: "Consultar clima",
    resetDays: "Zerar contagem de dias", resetDaysHelp: "Define o tempo como tick 0 e reinicia a contagem exibida de dias.",
    resetDaysConfirm: "Zerar a contagem de dias e definir o relógio como tick 0?", timeUpdated: "Tempo atualizado",
    queryUnavailable: "O servidor não retornou um valor legível.",
    onlinePlayers: "Jogadores online", operatorAccess: "Operador", operatorHelp: "Pode usar comandos administrativos dentro do jogo.",
    noOnlinePlayers: "Nenhum jogador online no momento.", permissionUpdated: "Permissão atualizada",
    allPlayers: "Todos os jogadores", playerHistoryHelp: "Ficha permanente de todos que já passaram pelo servidor.",
    offline: "Offline", sessions: "Sessões", playTime: "Tempo jogado", deaths: "Mortes", firstSeen: "Primeiro acesso",
    lastSeen: "Último acesso", viewHistory: "Ver histórico", hideHistory: "Ocultar histórico", noHistory: "Nenhum evento registrado.",
    historyUnavailable: "O servidor não retornou uma ficha válida para este jogador.",
    totalPlayers: "Jogadores", offlinePlayers: "Offline", totalDeaths: "Mortes registradas", totalPlayTime: "Tempo acumulado",
    searchPlayers: "Buscar jogador", filterAll: "Todos", filterOnline: "Online", filterOffline: "Offline", filterOperators: "Operadores",
    connectedSince: "Conectado desde", lastDeath: "Última morte", permission: "Permissão", aliases: "Nomes conhecidos",
    recentSessions: "Sessões recentes", activeSession: "Em andamento", normalExit: "Saída normal", inferredExit: "Encerramento inferido",
    derivedDeaths: "Contagem derivada das mensagens do servidor", noPlayersFound: "Nenhum jogador corresponde aos filtros.",
    telemetryStats: "Estatísticas do mundo", authoritative: "Dados estruturados pelo behavior pack", playerKills: "Jogadores eliminados", mobKills: "Criaturas eliminadas", blocksBroken: "Blocos quebrados", blocksPlaced: "Blocos colocados", damageDealt: "Dano causado", damageTaken: "Dano recebido", distanceTraveled: "Distância percorrida", dimensionsVisited: "Dimensões visitadas",
    deathHistory: "Histórico de mortes", noDeaths: "Nenhuma morte detalhada registrada.", deathCause: "Causa", killedBy: "Responsável", projectile: "Projétil", telemetrySource: "Behavior pack",
    home: "Início", world: "Mundo", players: "Jogadores", analytics: "Dados", rules: "Regras", settings: "Servidor",
    analyticsTitle: "Atividade do servidor", analyticsHelp: "A história compartilhada de quem entrou, saiu, morreu ou teve permissões alteradas.",
    activityView: "Atividade", deathsView: "Mortes", rankingsView: "Rankings", blocksView: "Blocos", combatView: "Combate", eventFilter: "Evento", playerFilter: "Jogador", periodFilter: "Período", sourceFilter: "Origem", detailFilter: "Causa ou responsável", detailFilterHint: "Ex.: zombie, lava…",
    everyEvent: "Todos os eventos", joinsOnly: "Entradas", leavesOnly: "Saídas", permissionsOnly: "Permissões", respawnsOnly: "Respawns", dimensionsOnly: "Dimensões",
    everyPlayer: "Todos os jogadores", lifetime: "Desde o início", last7Days: "Últimos 7 dias", last30Days: "Últimos 30 dias",
    everySource: "Todas as fontes", structuredSource: "Telemetry Pack", serverSource: "Servidor e manager",
    activityEmpty: "Nenhum evento corresponde a estes filtros.", eventCount: (count) => `${count} eventos`, pageCount: (page, pages) => `Página ${page} de ${pages}`,
    previous: "Anterior", next: "Próxima", refreshData: "Atualizar dados", sourceStructured: "Estruturado", sourceServer: "Evidência do servidor", deathDetails: "Detalhes da morte", viewDetails: "Ver detalhes", fromDimension: "Origem", toDimension: "Destino",
    rankingsTitle: "Rankings e recordes", rankingsHelp: "Compare os recordes vitalícios que o servidor consegue provar hoje.", lifetimeRecord: "Recorde vitalício", leaderboard: "Classificação", records: "Recordes do servidor", noRankingData: "Ainda não há dados para esta categoria.",
    categoryActivity: "Atividade", categoryCombat: "Combate", categoryBuilding: "Blocos", categoryExploration: "Exploração", rankPlayTime: "Tempo jogado", rankSessions: "Sessões", rankLongestSession: "Maior sessão", rankDeaths: "Mortes", rankPlayerKills: "Jogadores eliminados", rankMobKills: "Criaturas eliminadas", rankBlocksBroken: "Blocos quebrados", rankBlocksPlaced: "Blocos colocados", rankDamageDealt: "Dano causado", rankDamageTaken: "Dano recebido", rankDistance: "Distância", rankDimensions: "Dimensões",
    blocksTitle: "Mineração e construção", blocksHelp: "Descubra o que o mundo consumiu, quem mais minerou e quem mais construiu.", miningView: "Mineração", buildingView: "Construção", oresTitle: "Minérios encontrados", topBlocks: "Blocos mais frequentes", favoriteBlocks: "Favoritos dos jogadores", miners: "Mineradores", builders: "Construtores", noBlockData: "Ainda não há blocos registrados pelo Telemetry Pack.", blocksTelemetryHint: "Os números começam a contar após a instalação do Telemetry Pack.", broken: "Quebrados", placed: "Colocados", oreRanking: "Ranking do minério",
    oreDiamond: "Diamante", oreIron: "Ferro", oreGold: "Ouro", oreCopper: "Cobre", oreCoal: "Carvão", oreRedstone: "Redstone", oreLapis: "Lápis-lazúli", oreEmerald: "Esmeralda", oreQuartz: "Quartzo", oreAncient_debris: "Detritos ancestrais",
    combatTitle: "Combate do servidor", combatHelp: "Mortes, eliminações e dano acumulado com a evidência disponível no mundo.", combatEmptyHelp: "Os painéis permanecem visíveis e começam a preencher quando o Telemetry Pack observar combate.", combatDeaths: "Mortes", combatPlayerKills: "Eliminações PvP", combatMobKills: "Criaturas eliminadas", combatDamageDealt: "Dano causado", combatDamageTaken: "Dano recebido", combatRankings: "Ranking de combate", deathCauses: "Causas de morte", lethalOpponents: "Responsáveis pelas mortes", projectiles: "Projéteis", pvpDuels: "Confrontos PvP", combatProfiles: "Resumo por jogador", noCombatEvidence: "Nenhuma evidência registrada ainda.", telemetryWaiting: "Aguardando telemetria", observedDeaths: "Mortes estruturadas observadas",
    worldIntro: "Configuração do mundo", rulesIntro: "Comportamento do jogo", serverIntro: "Infraestrutura do servidor",
    pendingChanges: "ALTERAÇÕES PENDENTES", reviewChanges: "Revisar alterações",
    pendingHelp: "Estas configurações serão salvas e o servidor será reiniciado somente quando você aplicar.",
    discardAll: "Descartar todas", applyChanges: "Aplicar alterações", removeChange: "Remover",
    currentValue: "Atual", newValue: "Novo", reviewCount: (count) => `Revisar (${count})`,
    confirmedAt: "Confirmado",
    telemetryPack: "Telemetry Pack", telemetryPackHelp: "Estatísticas nativas e histórico estruturado do mundo.",
    installedVersion: "Versão instalada", bundledVersion: "Versão disponível", packHealth: "Saúde", lastResponse: "Última resposta",
    packActive: "Instalado e ativo", packInactive: "Desativado", packMissing: "Não instalado", upgradeAvailable: "Atualização disponível",
    installPack: "Instalar", upgradePack: "Atualizar", disablePack: "Desativar", rollbackPack: "Restaurar backup",
    restartPackNotice: "A alteração foi preparada. Reinicie o servidor Bedrock explicitamente para aplicá-la.",
    packActionConfirm: "Executar esta ação no Telemetry Pack? Um backup será criado antes da alteração.",
    telemetrySequence: "Sequência", lastSnapshot: "Último snapshot", detectedGaps: "Lacunas", missingEvents: "Eventos ausentes",
    healthy: "Saudável", syncing: "Sincronizando", degraded: "Degradado", waiting: "Aguardando",
    storageVersion: "Versão do armazenamento", storageStatus: "Migração do estado", migrated: "Migrado", notRequired: "Atual",
    capabilities: "Capacidades", capabilityFull: "Suporte completo", capabilityLimited: "Suporte parcial",
    playerJoins: "Entradas", playerLeaves: "Saídas", playerRespawns: "Respawns", deathsAndKills: "Mortes e eliminações",
    damageAggregates: "Dano", blocksBroken: "Blocos quebrados", blocksPlaced: "Blocos colocados", dimensionChanges: "Dimensões",
    movementSampling: "Distância", snapshotRequests: "Snapshots",
  },
  en: {
    brandKicker: "BEDROCK CONTROL CENTER",
    refresh: "Refresh", worldState: "WORLD STATE", quickActions: "Quick actions",
    day: "Day", night: "Night", clearWeather: "Clear weather", server: "Server",
    saveChanges: "Save changes", control: "CONTROL", serverOperation: "Server operation",
    restartNotice: "Persistent changes take effect after applying and restarting.",
    start: "Start", restart: "Restart", stop: "Stop", close: "Close",
    checking: "Checking…", online: "Online", stopped: "Stopped", serverOnline: "Server online",
    serverStopped: "Server stopped", playersOnline: "players online", nobody: "Nobody connected",
    awaiting: "Waiting for an update", updated: "Updated", enabled: "Enabled", disabled: "Disabled",
    unknown: "Not queried", immediate: "Applied immediately", restartRequired: "Applied when saved and restarted",
    saved: "Saved. Applying to the server…", serverUpdated: "Server updated",
    noChanges: "No pending changes", querying: "Querying the server…",
    stateUpdated: "State updated", worldUpdated: "World updated", operationDone: "Operation completed",
    confirmAction: (action) => `${action} the server?`, saveCount: (count) => `Save (${count})`,
    fieldUpdated: (label) => `${label} updated`,
    timeControls: "Time & weather", timeControlsHint: "Clock, cycles, and weather", timeOfDay: "World time",
    sunrise: "Sunrise", noon: "Noon", sunset: "Sunset", midnight: "Midnight",
    exactTime: "Exact time", exactTimeHelp: "Set a value between 0 and 24000 ticks.", setTime: "Set time",
    advanceTime: "Advance time", advanceTimeHelp: "Add 1 to 240000 ticks to the current clock.", addTime: "Advance",
    cycles: "Automatic cycles", daylightCycle: "Daylight cycle", weatherCycle: "Weather cycle",
    timeQueries: "Query clock", daytime: "Day ticks", gametime: "Total game time", days: "Days played",
    queryResult: "Result", weatherTitle: "Weather", clear: "Clear", rain: "Rain", thunder: "Thunder",
    duration: "Optional duration in ticks", setWeather: "Apply weather", queryWeather: "Query weather",
    resetDays: "Reset day count", resetDaysHelp: "Sets time to tick 0 and resets the displayed day count.",
    resetDaysConfirm: "Reset the day count and set the clock to tick 0?", timeUpdated: "Time updated",
    queryUnavailable: "The server did not return a readable value.",
    onlinePlayers: "Online players", operatorAccess: "Operator", operatorHelp: "Can use administrative commands in the game.",
    noOnlinePlayers: "No players are online right now.", permissionUpdated: "Permission updated",
    allPlayers: "All players", playerHistoryHelp: "Permanent profile for everyone who has joined the server.",
    offline: "Offline", sessions: "Sessions", playTime: "Play time", deaths: "Deaths", firstSeen: "First seen",
    lastSeen: "Last seen", viewHistory: "View history", hideHistory: "Hide history", noHistory: "No events recorded.",
    historyUnavailable: "The server did not return a valid profile for this player.",
    totalPlayers: "Players", offlinePlayers: "Offline", totalDeaths: "Recorded deaths", totalPlayTime: "Combined play time",
    searchPlayers: "Search players", filterAll: "All", filterOnline: "Online", filterOffline: "Offline", filterOperators: "Operators",
    connectedSince: "Connected since", lastDeath: "Last death", permission: "Permission", aliases: "Known names",
    recentSessions: "Recent sessions", activeSession: "In progress", normalExit: "Normal exit", inferredExit: "Inferred closure",
    derivedDeaths: "Count derived from server messages", noPlayersFound: "No players match the filters.",
    telemetryStats: "World statistics", authoritative: "Structured by the behavior pack", playerKills: "Player kills", mobKills: "Mob kills", blocksBroken: "Blocks broken", blocksPlaced: "Blocks placed", damageDealt: "Damage dealt", damageTaken: "Damage taken", distanceTraveled: "Distance traveled", dimensionsVisited: "Dimensions visited",
    deathHistory: "Death history", noDeaths: "No detailed deaths recorded.", deathCause: "Cause", killedBy: "Killed by", projectile: "Projectile", telemetrySource: "Behavior pack",
    home: "Home", world: "World", players: "Players", analytics: "Data", rules: "Rules", settings: "Server",
    analyticsTitle: "Server activity", analyticsHelp: "The shared history of players joining, leaving, dying, or receiving permission changes.",
    activityView: "Activity", deathsView: "Deaths", rankingsView: "Rankings", blocksView: "Blocks", combatView: "Combat", eventFilter: "Event", playerFilter: "Player", periodFilter: "Period", sourceFilter: "Source", detailFilter: "Cause or responsible", detailFilterHint: "E.g. zombie, lava…",
    everyEvent: "All events", joinsOnly: "Joins", leavesOnly: "Leaves", permissionsOnly: "Permissions", respawnsOnly: "Respawns", dimensionsOnly: "Dimensions",
    everyPlayer: "All players", lifetime: "All time", last7Days: "Last 7 days", last30Days: "Last 30 days",
    everySource: "All sources", structuredSource: "Telemetry Pack", serverSource: "Server and manager",
    activityEmpty: "No events match these filters.", eventCount: (count) => `${count} events`, pageCount: (page, pages) => `Page ${page} of ${pages}`,
    previous: "Previous", next: "Next", refreshData: "Refresh data", sourceStructured: "Structured", sourceServer: "Server evidence", deathDetails: "Death details", viewDetails: "View details", fromDimension: "From", toDimension: "To",
    rankingsTitle: "Rankings and records", rankingsHelp: "Compare the lifetime records the server can prove today.", lifetimeRecord: "Lifetime record", leaderboard: "Leaderboard", records: "Server records", noRankingData: "There is no data for this category yet.",
    categoryActivity: "Activity", categoryCombat: "Combat", categoryBuilding: "Blocks", categoryExploration: "Exploration", rankPlayTime: "Play time", rankSessions: "Sessions", rankLongestSession: "Longest session", rankDeaths: "Deaths", rankPlayerKills: "Player kills", rankMobKills: "Mob kills", rankBlocksBroken: "Blocks broken", rankBlocksPlaced: "Blocks placed", rankDamageDealt: "Damage dealt", rankDamageTaken: "Damage taken", rankDistance: "Distance", rankDimensions: "Dimensions",
    blocksTitle: "Mining and building", blocksHelp: "See what the world consumed, who mined the most, and who built the most.", miningView: "Mining", buildingView: "Building", oresTitle: "Ores discovered", topBlocks: "Most frequent blocks", favoriteBlocks: "Player favorites", miners: "Miners", builders: "Builders", noBlockData: "The Telemetry Pack has not recorded any blocks yet.", blocksTelemetryHint: "Counters start after the Telemetry Pack is installed.", broken: "Broken", placed: "Placed", oreRanking: "Ore ranking",
    oreDiamond: "Diamond", oreIron: "Iron", oreGold: "Gold", oreCopper: "Copper", oreCoal: "Coal", oreRedstone: "Redstone", oreLapis: "Lapis lazuli", oreEmerald: "Emerald", oreQuartz: "Quartz", oreAncient_debris: "Ancient debris",
    combatTitle: "Server combat", combatHelp: "Deaths, kills, and accumulated damage backed by the evidence available in the world.", combatEmptyHelp: "Panels remain visible and begin filling when the Telemetry Pack observes combat.", combatDeaths: "Deaths", combatPlayerKills: "PvP kills", combatMobKills: "Mobs defeated", combatDamageDealt: "Damage dealt", combatDamageTaken: "Damage taken", combatRankings: "Combat ranking", deathCauses: "Death causes", lethalOpponents: "Responsible for deaths", projectiles: "Projectiles", pvpDuels: "PvP encounters", combatProfiles: "Player summaries", noCombatEvidence: "No evidence has been recorded yet.", telemetryWaiting: "Waiting for telemetry", observedDeaths: "Observed structured deaths",
    worldIntro: "World configuration", rulesIntro: "Game behavior", serverIntro: "Server infrastructure",
    pendingChanges: "PENDING CHANGES", reviewChanges: "Review changes",
    pendingHelp: "These settings are saved and the server restarts only after you apply them.",
    discardAll: "Discard all", applyChanges: "Apply changes", removeChange: "Remove",
    currentValue: "Current", newValue: "New", reviewCount: (count) => `Review (${count})`,
    confirmedAt: "Confirmed",
    telemetryPack: "Telemetry Pack", telemetryPackHelp: "Native statistics and structured world history.",
    installedVersion: "Installed version", bundledVersion: "Available version", packHealth: "Health", lastResponse: "Last response",
    packActive: "Installed and active", packInactive: "Disabled", packMissing: "Not installed", upgradeAvailable: "Upgrade available",
    installPack: "Install", upgradePack: "Upgrade", disablePack: "Disable", rollbackPack: "Restore backup",
    restartPackNotice: "The change is ready. Explicitly restart the Bedrock server to apply it.",
    packActionConfirm: "Run this Telemetry Pack action? A backup will be created before the change.",
    telemetrySequence: "Sequence", lastSnapshot: "Last snapshot", detectedGaps: "Gaps", missingEvents: "Missing events",
    healthy: "Healthy", syncing: "Synchronizing", degraded: "Degraded", waiting: "Waiting",
    storageVersion: "Storage version", storageStatus: "State migration", migrated: "Migrated", notRequired: "Current",
    capabilities: "Capabilities", capabilityFull: "Full support", capabilityLimited: "Partial support",
    playerJoins: "Joins", playerLeaves: "Leaves", playerRespawns: "Respawns", deathsAndKills: "Deaths and kills",
    damageAggregates: "Damage", blocksBroken: "Blocks broken", blocksPlaced: "Blocks placed", dimensionChanges: "Dimensions",
    movementSampling: "Distance", snapshotRequests: "Snapshots",
  },
};

const groups = {
  Geral: "General", Mundo: "World", Jogadores: "Players", Packs: "Packs", Rede: "Network",
  Avançado: "Advanced", Interface: "Interface", Jogabilidade: "Gameplay",
  "Tempo e clima": "Time and weather", Criaturas: "Mobs", Drops: "Drops", Comandos: "Commands",
};
const optionNames = {
  survival: { pt: "Sobrevivência", en: "Survival" }, creative: { pt: "Criativo", en: "Creative" },
  adventure: { pt: "Aventura", en: "Adventure" }, peaceful: { pt: "Pacífico", en: "Peaceful" },
  easy: { pt: "Fácil", en: "Easy" }, normal: { pt: "Normal", en: "Normal" }, hard: { pt: "Difícil", en: "Hard" },
  DEFAULT: { pt: "Normal", en: "Default" }, FLAT: { pt: "Plano", en: "Flat" }, LEGACY: { pt: "Legado", en: "Legacy" },
  visitor: { pt: "Visitante", en: "Visitor" }, member: { pt: "Membro", en: "Member" }, operator: { pt: "Operador", en: "Operator" },
};

function t(key, ...args) {
  const value = messages[state.locale][key];
  return typeof value === "function" ? value(...args) : value;
}

function can(capability) {
  const capabilities = state.user?.capabilities || [];
  return capabilities.includes("*") || capabilities.includes(capability);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function fieldLabel(definition) {
  return state.locale === "en" ? definition.label_en : definition.label;
}

function fieldDescription(definition) {
  return state.locale === "en" ? definition.description_en : definition.description;
}

function groupLabel(group) {
  if (group === "__time__") return t("timeControls");
  if (group === "__players__") return t("onlinePlayers");
  return state.locale === "en" ? (groups[group] || group) : group;
}

const destinationGroups = {
  world: ["Geral", "Mundo"],
  players: ["Jogadores"],
  rules: ["Interface", "Jogabilidade", "Tempo e clima", "Criaturas", "Drops", "Comandos"],
  server: ["Packs", "Rede", "Avançado"],
};

function optionLabel(option) {
  return optionNames[option]?.[state.locale] || option;
}

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.style.background = error ? "#ffd2cf" : "#eef8ee";
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 2600);
}

function booleanControl(id, value) {
  const normalized = String(value).toLowerCase();
  const known = normalized === "true" || normalized === "false";
  const checked = normalized === "true";
  const text = known ? (checked ? t("enabled") : t("disabled")) : t("unknown");
  if (id === "detail-operator" && !can("players.manage_permissions")) {
    return `<span class="read-only-badge">${state.locale === "pt" ? "Somente leitura" : "Read only"}</span>`;
  }
  return `<div class="toggle-control"><span class="toggle-value ${known ? "" : "unknown"}">${text}</span><label class="switch"><input id="${id}" type="checkbox" ${checked ? "checked" : ""}><span></span></label></div>`;
}

function segmentedControl(id, definition, value) {
  const options = definition.options.map((option) =>
    `<button type="button" class="segment ${option === value ? "active" : ""}" data-choice="${escapeHtml(option)}">${escapeHtml(optionLabel(option))}</button>`
  ).join("");
  return `<div class="segmented" role="radiogroup" aria-labelledby="label-${id}">${options}<input id="${id}" type="hidden" value="${escapeHtml(value)}"></div>`;
}

function inputFor(key, definition, value, live = false) {
  const id = `field-${key}`;
  let input;
  if (definition.type === "boolean") {
    input = booleanControl(id, value);
  } else if (definition.type === "select") {
    input = segmentedControl(id, definition, value);
  } else {
    input = `<input id="${id}" type="${definition.type}" value="${escapeHtml(value)}" placeholder="${live && value == null ? t("unknown") : ""}" ${definition.min !== undefined ? `min="${definition.min}"` : ""} ${definition.max !== undefined ? `max="${definition.max}"` : ""}>`;
  }
  const warningText = state.locale === "en" ? definition.warning_en : definition.warning;
  const warning = warningText ? `<small class="field-warning">⚠ ${escapeHtml(warningText)}</small>` : "";
  return `<div class="field ${live ? "live-field" : ""}"><div class="field-copy"><label id="label-${id}" for="${id}">${escapeHtml(fieldLabel(definition))}</label><p>${escapeHtml(fieldDescription(definition))}</p>${warning}<small class="field-meta">${live ? "⚡ " + t("immediate") : "↻ " + t("restartRequired")}</small></div>${input}</div>`;
}

function updateSaveLabel() {
  const count = Object.keys(state.changes).length;
  $("#save").hidden = count === 0;
  $("#save-label").textContent = t("reviewCount", count);
  document.querySelector("footer").classList.toggle("has-pending", count > 0);
  if ($("#changes-drawer").open) renderChangesDrawer();
}

function comparableValue(value) {
  if (typeof value === "boolean") return String(value);
  return String(value ?? "").trim().toLowerCase();
}

function displayValue(value, definition) {
  if (definition.type === "boolean") return comparableValue(value) === "true" ? t("enabled") : t("disabled");
  if (definition.type === "select") return optionLabel(String(value));
  return String(value ?? "—");
}

function definitionFor(key) {
  return state.schema.settings[key];
}

function renderChangesDrawer() {
  const entries = Object.entries(state.changes);
  if (!entries.length) {
    $("#changes-drawer").close();
    return;
  }
  $("#changes-list").innerHTML = entries.map(([key, value]) => {
    const definition = definitionFor(key);
    return `<article class="change-item"><div class="change-copy"><strong>${escapeHtml(fieldLabel(definition))}</strong><div class="change-values"><span><small>${t("currentValue")}</small>${escapeHtml(displayValue(state.config[key], definition))}</span><b>→</b><span><small>${t("newValue")}</small>${escapeHtml(displayValue(value, definition))}</span></div></div><button type="button" class="remove-change" data-remove-change="${escapeHtml(key)}" aria-label="${t("removeChange")}">×</button></article>`;
  }).join("");
  $("#changes-list").querySelectorAll("[data-remove-change]").forEach((button) => button.onclick = () => {
    delete state.changes[button.dataset.removeChange];
    render();
    updateSaveLabel();
  });
}

function bindSegmentedControls() {
  content.querySelectorAll(".segmented").forEach((control) => {
    const input = control.querySelector("input");
    control.querySelectorAll(".segment").forEach((button) => {
      button.onclick = () => {
        control.querySelectorAll(".segment").forEach((item) => item.classList.toggle("active", item === button));
        input.value = button.dataset.choice;
        input.dispatchEvent(new Event("change"));
      };
    });
  });
}

function updateToggleLabel(element) {
  const label = element.closest(".toggle-control").querySelector(".toggle-value");
  label.textContent = element.checked ? t("enabled") : t("disabled");
  label.classList.remove("unknown");
}

function render() {
  if (!state.schema) return;
  $("#hero").hidden = state.tab !== "home";
  if (state.tab === "__time__") {
    renderTimePanel();
    return;
  }
  if (state.tab === "__players__") {
    renderPlayersPanel();
    return;
  }
  if (state.tab === "analytics") {
    renderAnalyticsPanel();
    return;
  }
  if (state.tab === "home") {
    content.innerHTML = "";
    return;
  }
  const prefix = state.tab === "world" ? `<button class="section-feature" id="open-time"><span>☀</span><div><strong>${t("timeControls")}</strong><small>${t("timeControlsHint")}</small></div><b>›</b></button>` : state.tab === "server" ? telemetryPackMarkup() : "";
  renderSettingsGroups(destinationGroups[state.tab] || [], prefix);
  if (state.tab === "world") $("#open-time").onclick = openTimeControls;
  if (state.tab === "server") loadTelemetryPack();
}

function telemetryPackMarkup() {
  return `<section class="telemetry-pack-card block-panel"><div><span class="eyebrow">CRAFTCONTROL</span><h3>${t("telemetryPack")}</h3><p>${t("telemetryPackHelp")}</p></div><div id="telemetry-pack-state" class="telemetry-pack-state">${t("checking")}</div></section>`;
}

async function loadTelemetryPack() {
  const target = $("#telemetry-pack-state");
  if (!target) return;
  try {
    const pack = await api("/api/telemetry-pack");
    const status = pack.installed ? (pack.enabled ? t("packActive") : t("packInactive")) : t("packMissing");
    const primaryAction = pack.installed ? (pack.upgrade_available ? "upgrade" : null) : "install";
    const health = t(pack.health) || pack.health || t("waiting");
    const storageState = pack.storage_status === "migrated" ? t("migrated") : pack.storage_status === "not-required" ? t("notRequired") : pack.storage_status || "—";
    const capabilityEntries = Object.entries(pack.capabilities || {});
    const capabilityState = pack.capability_status === "limited" ? t("capabilityLimited") : capabilityEntries.length ? t("capabilityFull") : t("unknown");
    const capabilityMarkup = capabilityEntries.length ? `<section class="capability-panel"><div><strong>${t("capabilities")}</strong><small>${escapeHtml(capabilityState)} · ${pack.capabilities_supported}/${pack.capabilities_total}</small></div><ul>${capabilityEntries.map(([name, value]) => `<li class="${value.supported ? "supported" : "unavailable"}"><span>${value.supported ? "✓" : "×"}</span>${escapeHtml(t(name) || name)}</li>`).join("")}</ul></section>` : "";
    target.innerHTML = `<div class="telemetry-pack-summary"><strong>${escapeHtml(status)}</strong><span class="health-${escapeHtml(pack.health || "waiting")}">${escapeHtml(health)}</span>${pack.upgrade_available && pack.installed ? `<span>${t("upgradeAvailable")}</span>` : ""}</div><dl><div><dt>${t("installedVersion")}</dt><dd>${escapeHtml(pack.installed_version || "—")}</dd></div><div><dt>${t("bundledVersion")}</dt><dd>${escapeHtml(pack.source_version)}</dd></div><div><dt>${t("storageVersion")}</dt><dd>${escapeHtml(pack.storage_version || "—")}</dd></div><div><dt>${t("storageStatus")}</dt><dd>${escapeHtml(storageState)}</dd></div><div><dt>${t("telemetrySequence")}</dt><dd>${escapeHtml(pack.sequence || "—")}</dd></div><div><dt>${t("lastResponse")}</dt><dd>${formatDate(pack.last_response_at)}</dd></div><div><dt>${t("lastSnapshot")}</dt><dd>${formatDate(pack.last_snapshot_at)}</dd></div><div><dt>${t("detectedGaps")}</dt><dd>${escapeHtml(pack.gap_count || 0)}</dd></div><div><dt>${t("missingEvents")}</dt><dd>${escapeHtml(pack.missing_events || 0)}</dd></div><div><dt>${t("packHealth")}</dt><dd>${escapeHtml(health)}</dd></div></dl>${capabilityMarkup}${pack.last_error ? `<p class="telemetry-pack-error">${escapeHtml(pack.last_error)}</p>` : ""}<div class="telemetry-pack-actions">${primaryAction ? `<button data-pack-action="${primaryAction}">${t(primaryAction === "install" ? "installPack" : "upgradePack")}</button>` : ""}${pack.enabled ? `<button class="secondary" data-pack-action="disable">${t("disablePack")}</button>` : ""}<button class="secondary" data-pack-action="rollback">${t("rollbackPack")}</button></div>`;
    target.querySelectorAll("[data-pack-action]").forEach((button) => button.onclick = async () => {
      if (!confirm(t("packActionConfirm"))) return;
      button.disabled = true;
      try {
        const result = await api(`/api/telemetry-pack/${button.dataset.packAction}`, { method: "POST" });
        toast(result.restart_required ? t("restartPackNotice") : t("operationDone"));
        await loadTelemetryPack();
      } catch (error) { toast(error.message, true); button.disabled = false; }
    });
  } catch (error) { target.textContent = error.message; }
}

function settingsMarkup(groupNames) {
  return groupNames.map((group, index) => {
    const persistent = Object.entries(state.schema.settings).filter(([, definition]) => definition.group === group);
    const live = Object.entries(state.schema.gamerules).filter(([, definition]) => definition.group === group);
    if (!persistent.length && !live.length) return "";
    const domain = persistent.length ? state.domains.settings : state.domains.gamerules;
    const observed = domain?.observed_at ? `${t("confirmedAt")} ${new Date(domain.observed_at * 1000).toLocaleTimeString(state.locale === "en" ? "en-US" : "pt-BR")}` : t("unknown");
    return `<details class="settings-accordion" ${index === 0 ? "open" : ""}><summary><span>${escapeHtml(groupLabel(group))}<small>${escapeHtml(observed)}</small></span><b>${persistent.length + live.length}</b></summary><div class="card">${persistent.map(([key, definition]) => inputFor(key, definition, Object.hasOwn(state.changes, key) ? state.changes[key] : state.config[key])).join("")}${live.map(([key, definition]) => inputFor(key, definition, state.gamerules[key], true)).join("")}</div></details>`;
  }).join("");
}

function playerSettingsMarkup() {
  const persistent = Object.entries(state.schema.settings).filter(([, definition]) => definition.group === "Jogadores");
  const live = Object.entries(state.schema.gamerules).filter(([, definition]) => definition.group === "Jogadores");
  return `<section class="player-server-settings block-panel"><div class="section-heading"><div><span class="eyebrow">${state.locale === "pt" ? "REGRAS GERAIS" : "GENERAL RULES"}</span><h3>${state.locale === "pt" ? "Configurações para todos os jogadores" : "Settings for every player"}</h3><p>${state.locale === "pt" ? "Limites e regras do servidor. Alterações instantâneas são identificadas pelo raio." : "Server-wide limits and rules. Instant changes are marked with a lightning bolt."}</p></div></div><div class="card">${persistent.map(([key, definition]) => inputFor(key, definition, Object.hasOwn(state.changes, key) ? state.changes[key] : state.config[key])).join("")}${live.map(([key, definition]) => inputFor(key, definition, state.gamerules[key], true)).join("")}</div></section>`;
}

function renderSettingsGroups(groupNames, prefix = "") {
  const titleKey = state.tab === "world" ? "worldIntro" : state.tab === "rules" ? "rulesIntro" : state.tab === "server" ? "serverIntro" : "onlinePlayers";
  content.innerHTML = `<div class="section-heading"><h2>${t(titleKey)}</h2></div>${prefix}<div class="accordion-list">${settingsMarkup(groupNames)}</div>`;
  bindSegmentedControls();
  bindSettingFields(groupNames);
}

function bindSettingFields(groupNames) {
  const persistent = Object.entries(state.schema.settings).filter(([, definition]) => groupNames.includes(definition.group));
  const live = Object.entries(state.schema.gamerules).filter(([, definition]) => groupNames.includes(definition.group));
  persistent.forEach(([key, definition]) => {
    const element = $(`#field-${key}`);
    element.addEventListener("change", () => {
      if (definition.type === "boolean") updateToggleLabel(element);
      const value = definition.type === "boolean" ? element.checked : element.value;
      if (comparableValue(value) === comparableValue(state.config[key])) delete state.changes[key];
      else state.changes[key] = value;
      updateSaveLabel();
    });
  });
  live.forEach(([key, definition]) => {
    const element = $(`#field-${key}`);
    element.addEventListener("change", async () => {
      const previous = state.gamerules[key];
      if (definition.type === "boolean") updateToggleLabel(element);
      const value = definition.type === "boolean" ? element.checked : element.value;
      try {
        await api(`/api/gamerules/${key}`, { method: "PUT", body: JSON.stringify({ value }) });
        state.gamerules[key] = String(value);
        toast(t("fieldUpdated", fieldLabel(definition)));
      } catch (error) {
        state.gamerules[key] = previous;
        toast(error.message, true);
        render();
      }
    });
  });
}

async function renderPlayersPanel() {
  content.innerHTML = `<div class="players-screen block-panel"><div class="section-heading"><div><span class="eyebrow">${state.locale === "pt" ? "JOGADORES" : "PLAYERS"}</span><h3>${t("allPlayers")}</h3><p>${state.locale === "pt" ? "Selecione uma pessoa para abrir sua ficha, histórico e permissões." : "Select a person to open their profile, history, and permissions."}</p></div></div><div id="player-overview" class="player-overview" hidden></div><div class="player-toolbar" hidden><input id="player-search" type="search" placeholder="${t("searchPlayers")}" autocomplete="off"><div class="player-filters"><button class="active" data-player-filter="all">${t("filterAll")}</button><button data-player-filter="online">${t("filterOnline")}</button><button data-player-filter="offline">${t("filterOffline")}</button><button data-player-filter="operator">${t("filterOperators")}</button></div></div><div class="loading-players">${t("checking")}</div></div>${playerSettingsMarkup()}`;
  bindSegmentedControls();
  bindSettingFields(["Jogadores"]);
  try {
    const result = await api("/api/players");
    const list = result.players || [];
    let access = {};
    if (state.user?.role === "owner") {
      const accessResult = await api("/api/auth/access");
      access = Object.fromEntries((accessResult.players || []).map((item) => [item.name.toLocaleLowerCase(), item]));
    }
    const container = content.querySelector(".loading-players");
    if (!list.length) {
      container.textContent = t("noHistory");
      return;
    }
    renderPlayerOverview(list);
    const toolbar = content.querySelector(".player-toolbar");
    toolbar.hidden = false;
    container.className = "player-management-list";
    let activeFilter = "all";
    const updateList = () => {
      const query = $("#player-search").value.trim().toLocaleLowerCase();
      const filtered = list.filter((player) => (!query || player.name.toLocaleLowerCase().includes(query)) && (activeFilter === "all" || (activeFilter === "online" && player.online) || (activeFilter === "offline" && !player.online) || (activeFilter === "operator" && player.operator)));
      renderPlayerCards(container, filtered, access);
    };
    $("#player-search").oninput = updateList;
    content.querySelectorAll("[data-player-filter]").forEach((button) => button.onclick = () => {
      activeFilter = button.dataset.playerFilter;
      content.querySelectorAll("[data-player-filter]").forEach((item) => item.classList.toggle("active", item === button));
      updateList();
    });
    updateList();
  } catch (error) { const loading = content.querySelector(".loading-players"); if (loading) loading.textContent = error.message; else toast(error.message, true); }
}

function renderPlayerOverview(list) {
  const overview = $("#player-overview");
  const online = list.filter((player) => player.online).length;
  const deaths = list.reduce((total, player) => total + Number(player.deaths_count || 0), 0);
  const seconds = list.reduce((total, player) => total + Number(player.total_play_seconds || 0), 0);
  overview.innerHTML = `<span><b>${list.length}</b>${t("totalPlayers")}</span><span><b>${online}</b>${t("online")}</span><span><b>${deaths}</b>${t("totalDeaths")}</span><span><b>${formatDuration(seconds)}</b>${t("totalPlayTime")}</span>`;
  overview.hidden = false;
}

function renderPlayerCards(container, list, access = {}) {
  if (!list.length) { container.innerHTML = `<p class="no-player-results">${t("noPlayersFound")}</p>`; return; }
  container.innerHTML = list.map((player, index) => {
    const account = access[player.name.toLocaleLowerCase()];
    const gameRole = player.operator ? (state.locale === "pt" ? "Operador Minecraft" : "Minecraft operator") : (state.locale === "pt" ? "Membro Minecraft" : "Minecraft member");
    const panelRole = account?.status === "active" ? `CraftControl · ${account.role}` : (state.locale === "pt" ? "Sem acesso ao painel" : "No panel access");
    return `<article class="player-roster-row ${player.online ? "is-online" : "is-offline"}"><button class="player-roster-open" data-player-index="${index}" type="button"><span class="player-avatar" aria-hidden="true">${escapeHtml(player.name.slice(0, 1).toUpperCase())}</span><span class="player-roster-identity"><strong>${escapeHtml(player.name)}</strong><small>${player.online ? "● " + t("online") : "○ " + t("offline")} · ${player.online ? formatDuration(Date.now() / 1000 - player.connected_at) : formatDate(player.last_seen_at)}</small></span><span class="player-roster-badges"><b class="game-role-badge">${escapeHtml(gameRole)}</b><b class="panel-role-badge ${account?.status === "active" ? "has-access" : ""}">${escapeHtml(panelRole)}</b></span><span class="player-roster-summary"><small>${t("playTime")}</small><b>${formatDuration(player.total_play_seconds)}</b></span><span class="player-roster-arrow" aria-hidden="true">›</span></button></article>`;
  }).join("");
  container.querySelectorAll("[data-player-index]").forEach((button) => {
    button.onclick = () => {
      const player = list[Number(button.dataset.playerIndex)];
      renderPlayerDetail(player, access[player.name.toLocaleLowerCase()]);
    };
  });
}

async function renderPlayerDetail(player, account, back = renderPlayersPanel) {
  content.innerHTML = `<div class="player-detail-loading">${t("checking")}</div>`;
  try {
    const result = await api(`/api/players/profile/${encodeURIComponent(player.id)}`);
    const profile = result?.profile || result;
    if (!profile || !Array.isArray(profile.history)) throw new Error(t("historyUnavailable"));
    const gameTitle = state.locale === "pt" ? "Permissão no Minecraft" : "Minecraft permission";
    const panelTitle = state.locale === "pt" ? "Acesso ao CraftControl" : "CraftControl access";
    content.innerHTML = `<div class="player-detail-screen"><button id="back-to-players" class="secondary player-back" type="button">← ${state.locale === "pt" ? "Todos os jogadores" : "All players"}</button><header class="player-detail-hero block-panel"><div class="player-avatar large" aria-hidden="true">${escapeHtml(profile.name.slice(0, 1).toUpperCase())}</div><div><span class="eyebrow">${profile.online ? t("online") : t("offline")}</span><h2>${escapeHtml(profile.name)}</h2><p>${profile.online ? `${t("connectedSince")} ${formatDate(profile.connected_at)}` : `${t("lastSeen")} ${formatDate(profile.last_seen_at)}`}</p></div></header><div class="player-detail-stats">${[[t("playTime"), formatDuration(profile.total_play_seconds)], [t("sessions"), profile.sessions_count], [t("deaths"), profile.deaths_count], [t("firstSeen"), formatDate(profile.first_seen_at)]].map(([label, value]) => `<span><small>${label}</small><b>${value}</b></span>`).join("")}</div><div class="player-admin-grid"><section class="player-admin-card block-panel"><span class="admin-scope game-scope">MINECRAFT</span><h3>${gameTitle}</h3><p>${state.locale === "pt" ? "Controla comandos administrativos dentro do jogo. Não concede acesso ao painel." : "Controls administrative commands in-game. It does not grant panel access."}</p><div class="permission-choice"><div><strong>${profile.operator ? (state.locale === "pt" ? "Operador" : "Operator") : (state.locale === "pt" ? "Membro" : "Member")}</strong><small>${profile.operator ? t("operatorHelp") : (state.locale === "pt" ? "Joga normalmente, sem comandos administrativos." : "Regular play without administrative commands.")}</small></div>${booleanControl("detail-operator", profile.operator)}</div></section>${panelAccessDetailMarkup(profile, account, panelTitle)}</div>${telemetryMarkup(profile)}<div class="player-history-grid">${profileMarkup(profile)}</div></div>`;
    if (back === renderAnalyticsPanel) $("#back-to-players").textContent = `← ${state.locale === "pt" ? "Voltar aos dados" : "Back to data"}`;
    $("#back-to-players").onclick = back;
    const operator = $("#detail-operator");
    if (operator) operator.onchange = async (event) => {
      updateToggleLabel(event.target);
      try { await api(`/api/players/${encodeURIComponent(profile.name)}/operator`, { method: "PUT", body: JSON.stringify({ enabled: event.target.checked }) }); toast(t("permissionUpdated")); }
      catch (error) { toast(error.message, true); renderPlayerDetail(player, account, back); }
    };
    bindPlayerAccess(profile, account);
  } catch (error) { content.innerHTML = `<p class="no-player-results">${escapeHtml(error.message)}</p>`; }
}

function panelAccessDetailMarkup(profile, account, title) {
  if (state.user?.role !== "owner") return `<section class="player-admin-card block-panel"><span class="admin-scope panel-scope">CRAFTCONTROL</span><h3>${title}</h3><p>${state.locale === "pt" ? "Somente owners podem gerenciar acesso ao painel." : "Only owners can manage panel access."}</p><b>${escapeHtml(account?.status === "active" ? account.role : (state.locale === "pt" ? "Sem acesso" : "No access"))}</b></section>`;
  const action = account?.status === "active" ? (state.locale === "pt" ? "Gerar recuperação" : "Generate recovery") : (state.locale === "pt" ? "Gerar acesso" : "Generate access");
  return `<section class="player-admin-card block-panel"><span class="admin-scope panel-scope">CRAFTCONTROL</span><h3>${title}</h3><p>${state.locale === "pt" ? "Define o que esta pessoa pode fazer no painel. Não altera permissões dentro do Minecraft." : "Defines what this person can do in the panel. It does not change Minecraft permissions."}</p><div class="panel-account-status"><strong>${account?.status === "active" ? account.role : (state.locale === "pt" ? "Sem acesso ativo" : "No active access")}</strong><small>${account?.active_sessions || 0} ${state.locale === "pt" ? "sessões ativas" : "active sessions"}</small></div><label class="panel-role-field"><span>${state.locale === "pt" ? "Papel no painel" : "Panel role"}</span><select id="detail-access-role"><option value="viewer" ${account?.role === "viewer" ? "selected" : ""}>Viewer · ${state.locale === "pt" ? "somente leitura" : "read only"}</option><option value="operator" ${account?.role === "operator" ? "selected" : ""}>Operator · ${state.locale === "pt" ? "gerencia o servidor" : "manages server"}</option><option value="owner" ${account?.role === "owner" ? "selected" : ""}>Owner · ${state.locale === "pt" ? "controle completo" : "full control"}</option></select></label><div class="panel-access-actions"><button id="detail-access-invite" class="primary" type="button">${action}</button>${account?.status === "active" ? `<button id="detail-access-suspend" class="danger" type="button">${state.locale === "pt" ? "Suspender acesso" : "Suspend access"}</button>` : ""}</div><div id="detail-access-code" class="access-code" hidden><code></code><button type="button">${state.locale === "pt" ? "Copiar código" : "Copy code"}</button><small>${state.locale === "pt" ? "Mostrado uma única vez. Expira em 15 minutos." : "Shown once. Expires in 15 minutes."}</small></div></section>`;
}

function bindPlayerAccess(profile, account) {
  const invite = $("#detail-access-invite");
  if (!invite) return;
  invite.onclick = async () => {
    try {
      const role = $("#detail-access-role").value;
      const result = await api("/api/auth/access/invite", { method: "POST", body: JSON.stringify({ player: profile.name, role }) });
      const output = $("#detail-access-code");
      output.hidden = false;
      output.querySelector("code").textContent = result.token;
      output.querySelector("button").onclick = async () => { await navigator.clipboard.writeText(result.token); toast(state.locale === "pt" ? "Código copiado" : "Code copied"); };
    } catch (error) { toast(error.message, true); }
  };
  const suspend = $("#detail-access-suspend");
  if (suspend) suspend.onclick = async () => {
    if (!confirm(state.locale === "pt" ? `Suspender o acesso de ${profile.name}?` : `Suspend ${profile.name}'s access?`)) return;
    try { await api(`/api/auth/access/${encodeURIComponent(profile.name)}/suspend`, { method: "PUT" }); toast(state.locale === "pt" ? "Acesso suspenso" : "Access suspended"); renderPlayersPanel(); }
    catch (error) { toast(error.message, true); }
  };
}

function formatDate(timestamp) {
  if (!timestamp) return "—";
  return new Date(timestamp * 1000).toLocaleString(state.locale === "en" ? "en-US" : "pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function timelineTimestamp(timestamp) {
  if (!timestamp) return `<time class="timeline-timestamp"><span>—</span></time>`;
  const value = new Date(timestamp * 1000);
  const locale = state.locale === "en" ? "en-US" : "pt-BR";
  const date = value.toLocaleDateString(locale, { day: "2-digit", month: "short", year: "numeric" });
  const time = value.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  return `<time class="timeline-timestamp" datetime="${value.toISOString()}"><span>${escapeHtml(date)}</span><b>${escapeHtml(time)}</b></time>`;
}

function formatDuration(seconds) {
  const minutes = Math.floor((seconds || 0) / 60);
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
}

function historyMarkup(events) {
  if (!events.length) return `<p>${t("noHistory")}</p>`;
  const labels = {
    "player.connected": { pt: "Entrou no servidor", en: "Joined the server" },
    "player.disconnected": { pt: "Saiu do servidor", en: "Left the server" },
    "player.death": { pt: "Morreu", en: "Died" },
    "player.permission.changed": { pt: "Permissão alterada", en: "Permission changed" },
  };
  return `<ol class="timeline-list">${events.map((event) => {
    const payload = event?.payload || {};
    const action = (labels[event?.topic] || {})[state.locale] || event?.topic || "event";
    const details = [
      payload.cause ? escapeHtml(payload.cause) : "",
      payload.inferred ? (state.locale === "pt" ? "Encerramento inferido pelo estado do servidor" : "Inferred from server state") : "",
    ].filter(Boolean);
    return `<li class="timeline-item"><span class="timeline-node" aria-hidden="true"></span><div class="timeline-action"><strong>${escapeHtml(action)}</strong>${details.length ? `<small>${details.join(" · ")}</small>` : ""}</div>${timelineTimestamp(event?.timestamp)}</li>`;
  }).join("")}</ol>`;
}

function sessionMoment(timestamp) {
  if (!timestamp) return "—";
  const value = new Date(timestamp * 1000);
  const locale = state.locale === "en" ? "en-US" : "pt-BR";
  const date = value.toLocaleDateString(locale, { day: "2-digit", month: "short", year: "numeric" });
  const time = value.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  return `<time datetime="${value.toISOString()}"><span>${escapeHtml(date)}</span><b>${escapeHtml(time)}</b></time>`;
}

function sessionsMarkup(sessions) {
  if (!sessions.length) return `<p>${t("noHistory")}</p>`;
  return `<ol class="session-list">${sessions.map((session) => {
    const active = Boolean(session.active);
    const inferred = Boolean(session.inferred);
    const title = active
      ? (state.locale === "pt" ? "Sessão em andamento" : "Session in progress")
      : (state.locale === "pt" ? "Sessão encerrada" : "Session ended");
    const status = active ? (state.locale === "pt" ? "Jogador conectado agora" : "Player currently connected") : inferred ? t("inferredExit") : t("normalExit");
    const reason = session.close_reason && session.close_reason !== "disconnect" ? ` · ${escapeHtml(session.close_reason)}` : "";
    return `<li class="session-item ${active ? "is-active" : ""} ${inferred ? "is-inferred" : ""}"><div class="session-state"><span class="session-status-dot" aria-hidden="true"></span><div><strong>${title}</strong><small>${status}${reason}</small></div></div><div class="session-duration"><small>${active ? (state.locale === "pt" ? "Tempo atual" : "Elapsed") : (state.locale === "pt" ? "Duração" : "Duration")}</small><b>${formatDuration(session.duration_seconds)}</b></div><div class="session-period"><span><small>${state.locale === "pt" ? "Início" : "Started"}</small>${sessionMoment(session.connected_at)}</span>${session.disconnected_at ? `<span><small>${state.locale === "pt" ? "Fim" : "Ended"}</small>${sessionMoment(session.disconnected_at)}</span>` : ""}</div></li>`;
  }).join("")}</ol>`;
}

function profileMarkup(profile) {
  const aliases = (profile.aliases || []).filter((name) => name !== profile.name);
  const sessions = Array.isArray(profile.sessions) ? profile.sessions : [];
  return `<div class="profile-facts"><span><small>${t("permission")}</small><b>${escapeHtml(optionLabel(profile.permission || "member"))}</b></span><span><small>${t("lastDeath")}</small><b>${formatDate(profile.last_death_at)}</b></span><span><small>${t("aliases")}</small><b>${aliases.length ? aliases.map(escapeHtml).join(" · ") : "—"}</b></span></div>${deathHistoryMarkup(profile.history || [])}<section class="session-history"><h4>${t("recentSessions")}</h4>${sessionsMarkup(sessions)}</section><section class="event-history"><h4>${state.locale === "pt" ? "Linha do tempo" : "Timeline"}</h4>${historyMarkup(profile.history || [])}</section>`;
}

function deathHistoryMarkup(events) {
  const deaths = events.filter((event) => event?.topic === "player.death");
  if (!deaths.length) return `<section class="death-history"><h4>${t("deathHistory")}</h4><p>${t("noDeaths")}</p></section>`;
  return `<section class="death-history"><h4>${t("deathHistory")}</h4><ol>${deaths.map((event) => {
    const data = event.payload || {};
    const killer = data.killer || data.killerType || "—";
    const details = [[t("deathCause"), data.cause], [t("killedBy"), killer], [t("projectile"), data.projectileType]].filter(([, value]) => value);
    return `<li><div><b>☠ ${formatDate(event.timestamp)}</b><small>${event.source === "behavior-pack" ? t("telemetrySource") : escapeHtml(event.source || "")}</small></div><dl>${details.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(String(value).replace(/^minecraft:/, ""))}</dd></div>`).join("")}</dl></li>`;
  }).join("")}</ol></section>`;
}

function telemetryMarkup(profile) {
  if (!profile.telemetry_updated_at) return "";
  const stats = profile.telemetry || {};
  const dimensions = Object.keys(stats.dimensions || {}).length;
  const items = [["playerKills", stats.playerKills], ["mobKills", stats.mobKills], ["blocksBroken", stats.blocksBroken], ["blocksPlaced", stats.blocksPlaced], ["damageDealt", Number(stats.damageDealt || 0).toFixed(1)], ["damageTaken", Number(stats.damageTaken || 0).toFixed(1)], ["distanceTraveled", `${Math.round(stats.distance || 0)} m`], ["dimensionsVisited", dimensions]];
  return `<section class="telemetry-profile"><h4>${t("telemetryStats")}</h4><small>◆ ${t("authoritative")} · ${t("updated")} ${formatDate(profile.telemetry_updated_at)}</small><div class="telemetry-grid">${items.map(([label, value]) => `<span><b>${value || 0}</b>${t(label)}</span>`).join("")}</div></section>`;
}

function analyticsEventPresentation(event) {
  const definitions = {
    "player.connected": { icon: "↘", pt: "Entrou no servidor", en: "Joined the server", tone: "join" },
    "player.disconnected": { icon: "↗", pt: "Saiu do servidor", en: "Left the server", tone: "leave" },
    "player.respawned": { icon: "✦", pt: "Renasceu", en: "Respawned", tone: "respawn" },
    "player.dimension.changed": { icon: "◈", pt: "Mudou de dimensão", en: "Changed dimension", tone: "dimension" },
    "player.death": { icon: "☠", pt: "Morreu", en: "Died", tone: "death" },
    "player.permission.changed": { icon: "◆", pt: "Permissão alterada", en: "Permission changed", tone: "permission" },
  };
  return definitions[event.topic] || { icon: "•", pt: event.topic, en: event.topic, tone: "default" };
}

function analyticsEventDetails(event) {
  const details = event.details || {};
  const items = [];
  if (details.cause) items.push([t("deathCause"), details.cause]);
  if (details.killer) items.push([t("killedBy"), String(details.killer).replace(/^minecraft:/, "")]);
  if (details.projectile) items.push([t("projectile"), String(details.projectile).replace(/^minecraft:/, "")]);
  if (details.permission) items.push([t("permission"), optionLabel(details.permission)]);
  if (details.dimension) items.push([state.locale === "pt" ? "Dimensão" : "Dimension", String(details.dimension).replace(/^minecraft:/, "")]);
  if (details.from_dimension) items.push([t("fromDimension"), String(details.from_dimension).replace(/^minecraft:/, "")]);
  if (details.to_dimension) items.push([t("toDimension"), String(details.to_dimension).replace(/^minecraft:/, "")]);
  const coordinates = details.coordinates || {};
  if (Object.keys(coordinates).length) items.push([state.locale === "pt" ? "Coordenadas" : "Coordinates", [coordinates.x, coordinates.y, coordinates.z].filter((value) => value !== undefined).join(", ")]);
  if (details.inferred) items.push([state.locale === "pt" ? "Observação" : "Note", t("inferredExit")]);
  return items.length ? `<dl class="analytics-event-details">${items.map(([label, value]) => `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>` : "";
}

function analyticsEventsMarkup(events) {
  if (!events.length) return `<div class="analytics-empty"><span>◇</span><p>${t("activityEmpty")}</p></div>`;
  return `<ol class="analytics-event-list">${events.map((event, index) => {
    const presentation = analyticsEventPresentation(event);
    const source = event.source === "behavior-pack" ? t("sourceStructured") : t("sourceServer");
    return `<li class="analytics-event tone-${presentation.tone}"><span class="analytics-event-icon" aria-hidden="true">${presentation.icon}</span><div class="analytics-event-main"><div class="analytics-event-title"><div><button class="analytics-player-link" data-analytics-player="${escapeHtml(event.player?.id || "")}" type="button">${escapeHtml(event.player?.name || "—")}</button><span>${escapeHtml(presentation[state.locale])}</span></div><b class="analytics-source ${event.source === "behavior-pack" ? "structured" : "server"}">${escapeHtml(source)}</b></div>${analyticsEventDetails(event)}${event.topic === "player.death" ? `<button class="analytics-detail-button" data-death-detail="${index}" type="button">${t("viewDetails")} ›</button>` : ""}</div>${timelineTimestamp(event.timestamp)}</li>`;
  }).join("")}</ol>`;
}

function showDeathDetails(event) {
  const dialog = $("#analytics-death-dialog");
  const presentation = analyticsEventPresentation(event);
  dialog.querySelector("h2").textContent = `${presentation.icon} ${event.player?.name || "—"}`;
  dialog.querySelector(".analytics-death-content").innerHTML = `<p>${escapeHtml(presentation[state.locale])}</p>${analyticsEventDetails(event)}<div class="analytics-death-meta"><span>${event.source === "behavior-pack" ? t("sourceStructured") : t("sourceServer")}</span>${timelineTimestamp(event.timestamp)}</div>`;
  dialog.showModal();
}

async function openAnalyticsPlayer(publicId) {
  try {
    const roster = await api("/api/players");
    const player = (roster.players || []).find((item) => item.id === publicId);
    if (!player) throw new Error(t("historyUnavailable"));
    let account;
    if (state.user?.role === "owner") {
      const access = await api("/api/auth/access");
      account = (access.players || []).find((item) => item.name.toLocaleLowerCase() === player.name.toLocaleLowerCase());
    }
    await renderPlayerDetail(player, account, renderAnalyticsPanel);
  } catch (error) { toast(error.message, true); }
}

function analyticsViewSwitch(active) {
  return `<div class="analytics-view-switch"><button data-analytics-view="all" class="${!['deaths', 'rankings', 'blocks', 'combat'].includes(active) ? "active" : ""}" type="button">☷ ${t("activityView")}</button><button data-analytics-view="deaths" class="death ${active === "deaths" ? "active" : ""}" type="button">☠ ${t("deathsView")}</button><button data-analytics-view="rankings" class="ranking ${active === "rankings" ? "active" : ""}" type="button">♛ ${t("rankingsView")}</button><button data-analytics-view="blocks" class="blocks ${active === "blocks" ? "active" : ""}" type="button">▦ ${t("blocksView")}</button><button data-analytics-view="combat" class="combat ${active === "combat" ? "active" : ""}" type="button">⚔ ${t("combatView")}</button></div>`;
}

const rankingDefinitions = {
  play_time: { label: "rankPlayTime", category: "activity", format: "duration" },
  sessions: { label: "rankSessions", category: "activity", format: "number" },
  longest_session: { label: "rankLongestSession", category: "activity", format: "duration" },
  deaths: { label: "rankDeaths", category: "combat", format: "number" },
  player_kills: { label: "rankPlayerKills", category: "combat", format: "number" },
  mob_kills: { label: "rankMobKills", category: "combat", format: "number" },
  damage_dealt: { label: "rankDamageDealt", category: "combat", format: "decimal" },
  damage_taken: { label: "rankDamageTaken", category: "combat", format: "decimal" },
  blocks_broken: { label: "rankBlocksBroken", category: "building", format: "number" },
  blocks_placed: { label: "rankBlocksPlaced", category: "building", format: "number" },
  distance: { label: "rankDistance", category: "exploration", format: "distance" },
  dimensions: { label: "rankDimensions", category: "exploration", format: "number" },
};

function formatRankingValue(value, format) {
  if (format === "duration") return formatDuration(Number(value));
  if (format === "distance") return `${Math.round(Number(value || 0)).toLocaleString(state.locale === "en" ? "en-US" : "pt-BR")} m`;
  if (format === "decimal") return Number(value || 0).toLocaleString(state.locale === "en" ? "en-US" : "pt-BR", { maximumFractionDigits: 1 });
  return Number(value || 0).toLocaleString(state.locale === "en" ? "en-US" : "pt-BR");
}

function bindAnalyticsViewSwitch() {
  content.querySelectorAll("[data-analytics-view]").forEach((button) => button.onclick = () => {
    state.analytics.kind = button.dataset.analyticsView;
    state.analytics.page = 1;
    renderAnalyticsPanel();
  });
}

async function renderRankingsPanel() {
  const analytics = state.analytics;
  content.innerHTML = `<div class="rankings-screen">${analyticsViewSwitch("rankings")}<header class="rankings-hero block-panel"><div><span class="eyebrow">LIFETIME</span><h2>${t("rankingsTitle")}</h2><p>${t("rankingsHelp")}</p></div><button id="rankings-refresh" class="secondary" type="button">↻ ${t("refreshData")}</button></header><div class="ranking-categories">${[["activity", "categoryActivity", "⌛"], ["combat", "categoryCombat", "⚔"], ["building", "categoryBuilding", "▦"], ["exploration", "categoryExploration", "◇"]].map(([category, label, icon]) => `<button data-ranking-category="${category}" class="${analytics.rankingCategory === category ? "active" : ""}" type="button"><span>${icon}</span>${t(label)}</button>`).join("")}</div><div id="rankings-content" class="rankings-content"><div class="analytics-loading">${t("checking")}</div></div></div>`;
  bindAnalyticsViewSwitch();
  const load = async () => {
    const target = $("#rankings-content");
    target.innerHTML = `<div class="analytics-loading">${t("checking")}</div>`;
    try {
      const result = await api("/api/analytics/rankings?limit=10");
      const categoryMetrics = Object.entries(rankingDefinitions).filter(([, definition]) => definition.category === analytics.rankingCategory);
      if (!categoryMetrics.some(([key]) => key === analytics.rankingMetric)) analytics.rankingMetric = categoryMetrics[0][0];
      const selectedDefinition = rankingDefinitions[analytics.rankingMetric];
      const selectedEntries = result.metrics?.[analytics.rankingMetric] || [];
      const podium = selectedEntries.slice(0, 3);
      target.innerHTML = `<div class="ranking-metric-picker">${categoryMetrics.map(([key, definition]) => `<button data-ranking-metric="${key}" class="${key === analytics.rankingMetric ? "active" : ""}" type="button">${t(definition.label)}</button>`).join("")}</div>${podium.length ? `<section class="ranking-podium block-panel"><div class="ranking-section-title"><span class="eyebrow">${t("lifetimeRecord")}</span><h3>${t(selectedDefinition.label)}</h3></div><div class="podium-places">${podium.map((entry, index) => `<article class="podium-place rank-${index + 1}"><span class="podium-medal">${["🥇", "🥈", "🥉"][index]}</span><button data-ranking-player="${escapeHtml(entry.player.id)}" type="button">${escapeHtml(entry.player.name)}</button><b>${formatRankingValue(entry.value, selectedDefinition.format)}</b><small>${entry.source === "telemetry-pack" ? t("sourceStructured") : t("sourceServer")}</small></article>`).join("")}</div></section>` : `<div class="analytics-empty"><p>${t("noRankingData")}</p></div>`}<div class="rankings-grid"><section class="leaderboard-panel block-panel"><div class="ranking-section-title"><span class="eyebrow">TOP 10</span><h3>${t("leaderboard")}</h3></div><ol>${selectedEntries.map((entry, index) => `<li><b>${index + 1}</b><button data-ranking-player="${escapeHtml(entry.player.id)}" type="button">${escapeHtml(entry.player.name)}</button><strong>${formatRankingValue(entry.value, selectedDefinition.format)}</strong></li>`).join("")}</ol></section><section class="records-panel block-panel"><div class="ranking-section-title"><span class="eyebrow">LIFETIME</span><h3>${t("records")}</h3></div><div class="record-cards">${categoryMetrics.map(([key, definition]) => { const leader = result.metrics?.[key]?.[0]; return `<article><small>${t(definition.label)}</small>${leader ? `<button data-ranking-player="${escapeHtml(leader.player.id)}" type="button">${escapeHtml(leader.player.name)}</button><b>${formatRankingValue(leader.value, definition.format)}</b>` : `<span>—</span>`}</article>`; }).join("")}</div></section></div><small class="ranking-freshness">${t("updated")} ${formatDate(result.generated_at)} · ${t("lifetime")}</small>`;
      target.querySelectorAll("[data-ranking-metric]").forEach((button) => button.onclick = () => { analytics.rankingMetric = button.dataset.rankingMetric; load(); });
      target.querySelectorAll("[data-ranking-player]").forEach((button) => button.onclick = () => openAnalyticsPlayer(button.dataset.rankingPlayer));
    } catch (error) { target.innerHTML = `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`; }
  };
  content.querySelectorAll("[data-ranking-category]").forEach((button) => button.onclick = () => { analytics.rankingCategory = button.dataset.rankingCategory; load(); content.querySelectorAll("[data-ranking-category]").forEach((item) => item.classList.toggle("active", item === button)); });
  $("#rankings-refresh").onclick = load;
  await load();
}

function blockName(identifier) {
  return String(identifier || "—").replace(/^minecraft:/, "").replaceAll("_", " ");
}

function oreLabel(ore) {
  return t(`ore${ore.charAt(0).toUpperCase()}${ore.slice(1)}`);
}

function blockLeaderboard(entries, title) {
  return `<section class="block-leaderboard block-panel"><div class="ranking-section-title"><span class="eyebrow">TOP 10</span><h3>${title}</h3></div>${entries.length ? `<ol>${entries.map((entry, index) => `<li><b>${index + 1}</b><span>${escapeHtml(blockName(entry.block))}</span><strong>${formatRankingValue(entry.count, "number")}</strong></li>`).join("")}</ol>` : `<div class="analytics-empty"><p>${t("noBlockData")}</p></div>`}</section>`;
}

function playerBlockRanking(entries, title) {
  return `<section class="block-player-ranking block-panel"><div class="ranking-section-title"><span class="eyebrow">LIFETIME</span><h3>${title}</h3></div>${entries.length ? `<ol>${entries.map((entry, index) => `<li><b>${index + 1}</b><button data-block-player="${escapeHtml(entry.player.id)}" type="button">${escapeHtml(entry.player.name)}</button><strong>${formatRankingValue(entry.value, "number")}</strong></li>`).join("")}</ol>` : `<div class="analytics-empty"><p>${t("noBlockData")}</p></div>`}</section>`;
}

async function renderBlocksPanel() {
  const analytics = state.analytics;
  content.innerHTML = `<div class="blocks-screen">${analyticsViewSwitch("blocks")}<header class="blocks-hero block-panel"><div><span class="eyebrow">WORLD STATISTICS</span><h2>${t("blocksTitle")}</h2><p>${t("blocksHelp")}</p></div><button id="blocks-refresh" class="secondary" type="button">↻ ${t("refreshData")}</button></header><div class="blocks-mode"><button data-block-mode="mining" class="${analytics.blocksMode === "mining" ? "active" : ""}" type="button">⛏ ${t("miningView")}</button><button data-block-mode="building" class="${analytics.blocksMode === "building" ? "active" : ""}" type="button">▦ ${t("buildingView")}</button></div><div id="blocks-content"><div class="analytics-loading">${t("checking")}</div></div></div>`;
  bindAnalyticsViewSwitch();
  const load = async () => {
    const target = $("#blocks-content");
    target.innerHTML = `<div class="analytics-loading">${t("checking")}</div>`;
    try {
      const result = await api("/api/analytics/blocks?limit=10");
      const mining = analytics.blocksMode === "mining";
      const oreEntries = Object.entries(result.ores || {});
      if (!oreEntries.some(([ore]) => ore === analytics.selectedOre)) analytics.selectedOre = oreEntries[0]?.[0] || "diamond";
      const ranking = mining ? result.rankings?.miners || [] : result.rankings?.builders || [];
      const types = mining ? result.top_broken || [] : result.top_placed || [];
      const oreRanking = result.rankings?.ores?.[analytics.selectedOre] || [];
      target.innerHTML = `<section class="blocks-summary"><article><small>${t("broken")}</small><b>${formatRankingValue(result.totals?.broken, "number")}</b><span>⛏</span></article><article><small>${t("placed")}</small><b>${formatRankingValue(result.totals?.placed, "number")}</b><span>▦</span></article><p>${t("blocksTelemetryHint")}<br><small>${t("updated")} ${formatDate(result.generated_at)}</small></p></section>${mining ? `<section class="ore-section block-panel"><div class="ranking-section-title"><span class="eyebrow">ORE TRACKER</span><h3>${t("oresTitle")}</h3></div><div class="ore-grid">${oreEntries.map(([ore, count]) => `<button data-ore="${ore}" class="${ore === analytics.selectedOre ? "active" : ""}" type="button"><span class="ore-gem ore-${ore}">◆</span><small>${oreLabel(ore)}</small><b>${formatRankingValue(count, "number")}</b></button>`).join("")}</div></section>` : ""}<div class="blocks-rank-grid">${blockLeaderboard(types, t("topBlocks"))}${playerBlockRanking(ranking, mining ? t("miners") : t("builders"))}${mining ? playerBlockRanking(oreRanking, `${t("oreRanking")}: ${oreLabel(analytics.selectedOre)}`) : ""}</div><section class="player-favorites block-panel"><div class="ranking-section-title"><span class="eyebrow">PLAYERS</span><h3>${t("favoriteBlocks")}</h3></div><div>${(result.players || []).map((item) => { const favorite = mining ? item.favorite_broken : item.favorite_placed; return `<button data-block-player="${escapeHtml(item.player.id)}" type="button"><strong>${escapeHtml(item.player.name)}</strong><span>${favorite ? escapeHtml(blockName(favorite.block)) : "—"}</span><b>${favorite ? formatRankingValue(favorite.count, "number") : "0"}</b></button>`; }).join("") || `<p>${t("noBlockData")}</p>`}</div></section>`;
      target.querySelectorAll("[data-block-player]").forEach((button) => button.onclick = () => openAnalyticsPlayer(button.dataset.blockPlayer));
      target.querySelectorAll("[data-ore]").forEach((button) => button.onclick = () => { analytics.selectedOre = button.dataset.ore; load(); });
    } catch (error) { target.innerHTML = `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`; }
  };
  content.querySelectorAll("[data-block-mode]").forEach((button) => button.onclick = () => {
    analytics.blocksMode = button.dataset.blockMode;
    content.querySelectorAll("[data-block-mode]").forEach((item) => item.classList.toggle("active", item === button));
    load();
  });
  $("#blocks-refresh").onclick = load;
  await load();
}

const combatDefinitions = {
  mob_kills: { label: "combatMobKills", format: "number" },
  player_kills: { label: "combatPlayerKills", format: "number" },
  deaths: { label: "combatDeaths", format: "number" },
  damage_dealt: { label: "combatDamageDealt", format: "decimal" },
  damage_taken: { label: "combatDamageTaken", format: "decimal" },
};

function combatBreakdown(title, entries, icon) {
  return `<section class="combat-breakdown block-panel"><div class="ranking-section-title"><span class="eyebrow">${icon} LIFETIME</span><h3>${title}</h3></div>${entries.length ? `<ol>${entries.map((entry, index) => `<li><b>${index + 1}</b><span>${escapeHtml(blockName(entry.key))}</span><strong>${formatRankingValue(entry.count, "number")}</strong></li>`).join("")}</ol>` : `<div class="combat-zero"><span>${icon}</span><p>${t("noCombatEvidence")}</p></div>`}</section>`;
}

async function renderCombatPanel() {
  const analytics = state.analytics;
  content.innerHTML = `<div class="combat-screen">${analyticsViewSwitch("combat")}<header class="combat-hero block-panel"><div><span class="eyebrow">COMBAT LOG</span><h2>${t("combatTitle")}</h2><p>${t("combatHelp")}</p></div><button id="combat-refresh" class="secondary" type="button">↻ ${t("refreshData")}</button></header><div id="combat-content"><div class="analytics-loading">${t("checking")}</div></div></div>`;
  bindAnalyticsViewSwitch();
  const load = async () => {
    const target = $("#combat-content");
    target.innerHTML = `<div class="analytics-loading">${t("checking")}</div>`;
    try {
      const result = await api("/api/analytics/combat?limit=10");
      const definition = combatDefinitions[analytics.combatMetric] || combatDefinitions.mob_kills;
      const ranking = result.rankings?.[analytics.combatMetric] || [];
      const totals = result.totals || {};
      const breakdowns = result.breakdowns || {};
      target.innerHTML = `<section class="combat-summary">${Object.entries(combatDefinitions).map(([key, item]) => `<article><small>${t(item.label)}</small><b>${formatRankingValue(totals[key], item.format)}</b><span>${key === "deaths" ? "☠" : key.includes("damage") ? "♥" : "⚔"}</span></article>`).join("")}</section><p class="combat-empty-note">${t("combatEmptyHelp")} <small>${t("updated")} ${formatDate(result.generated_at)}</small></p><div class="combat-metric-picker">${Object.entries(combatDefinitions).map(([key, item]) => `<button data-combat-metric="${key}" class="${analytics.combatMetric === key ? "active" : ""}" type="button">${t(item.label)}</button>`).join("")}</div><div class="combat-main-grid">${playerBlockRanking(ranking, `${t("combatRankings")}: ${t(definition.label)}`)}<section class="pvp-panel block-panel"><div class="ranking-section-title"><span class="eyebrow">⚔ ${t("observedDeaths")}</span><h3>${t("pvpDuels")}</h3></div>${(result.pvp || []).length ? `<ol>${result.pvp.map((duel) => `<li><button data-combat-player="${escapeHtml(duel.attacker.id)}" type="button">${escapeHtml(duel.attacker.name)}</button><span>→</span><button data-combat-player="${escapeHtml(duel.victim.id)}" type="button">${escapeHtml(duel.victim.name)}</button><b>${duel.count}</b></li>`).join("")}</ol>` : `<div class="combat-zero"><span>⚔</span><p>${t("noCombatEvidence")}</p></div>`}</section></div><div class="combat-breakdown-grid">${combatBreakdown(t("deathCauses"), breakdowns.causes || [], "☠")}${combatBreakdown(t("lethalOpponents"), breakdowns.opponents || [], "♞")}${combatBreakdown(t("projectiles"), breakdowns.projectiles || [], "➶")}</div><section class="combat-profiles block-panel"><div class="ranking-section-title"><span class="eyebrow">PLAYERS</span><h3>${t("combatProfiles")}</h3></div><div>${(result.players || []).map((item) => `<button data-combat-player="${escapeHtml(item.player.id)}" type="button"><strong>${escapeHtml(item.player.name)}</strong><span>${t("combatMobKills")} <b>${formatRankingValue(item.mob_kills, "number")}</b></span><span>${t("combatPlayerKills")} <b>${formatRankingValue(item.player_kills, "number")}</b></span><span>${t("combatDeaths")} <b>${formatRankingValue(item.deaths, "number")}</b></span><small>${item.telemetry_available ? `${t("sourceStructured")} · ${t("updated")} ${formatDate(item.updated_at)}` : t("telemetryWaiting")}</small></button>`).join("") || `<div class="combat-zero"><span>◇</span><p>${t("noCombatEvidence")}</p></div>`}</div></section>`;
      target.querySelectorAll("[data-block-player], [data-combat-player]").forEach((button) => button.onclick = () => { const id = button.dataset.blockPlayer || button.dataset.combatPlayer; if (id) openAnalyticsPlayer(id); });
      target.querySelectorAll("[data-combat-metric]").forEach((button) => button.onclick = () => { analytics.combatMetric = button.dataset.combatMetric; load(); });
    } catch (error) { target.innerHTML = `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`; }
  };
  $("#combat-refresh").onclick = load;
  await load();
}

async function renderAnalyticsPanel() {
  const filters = state.analytics;
  if (filters.kind === "rankings") {
    await renderRankingsPanel();
    return;
  }
  if (filters.kind === "blocks") {
    await renderBlocksPanel();
    return;
  }
  if (filters.kind === "combat") {
    await renderCombatPanel();
    return;
  }
  content.innerHTML = `<div class="analytics-screen">${analyticsViewSwitch(filters.kind)}<header class="analytics-hero block-panel"><div><span class="eyebrow">CRAFTCONTROL ANALYTICS</span><h2>${t("analyticsTitle")}</h2><p>${t("analyticsHelp")}</p></div><button id="analytics-refresh" class="secondary" type="button">↻ ${t("refreshData")}</button></header><section class="analytics-filters block-panel"><label><span>${t("eventFilter")}</span><select id="analytics-kind" ${filters.kind === "deaths" ? "disabled" : ""}><option value="all">${t("everyEvent")}</option><option value="joins">${t("joinsOnly")}</option><option value="leaves">${t("leavesOnly")}</option><option value="respawns">${t("respawnsOnly")}</option><option value="dimensions">${t("dimensionsOnly")}</option><option value="permissions">${t("permissionsOnly")}</option></select></label><label><span>${t("playerFilter")}</span><select id="analytics-player"><option value="">${t("everyPlayer")}</option></select></label><label><span>${t("periodFilter")}</span><select id="analytics-days"><option value="0">${t("lifetime")}</option><option value="7">${t("last7Days")}</option><option value="30">${t("last30Days")}</option></select></label><label><span>${t("sourceFilter")}</span><select id="analytics-source"><option value="all">${t("everySource")}</option><option value="structured">${t("structuredSource")}</option><option value="server">${t("serverSource")}</option></select></label><label><span>${t("detailFilter")}</span><input id="analytics-search" type="search" maxlength="64" value="${escapeHtml(filters.search)}" placeholder="${t("detailFilterHint")}"></label></section><div id="analytics-results" class="analytics-results"><div class="analytics-loading">${t("checking")}</div></div><dialog id="analytics-death-dialog" class="analytics-death-dialog"><div class="drawer-header"><div><span class="eyebrow">${t("deathDetails")}</span><h2></h2></div><button class="drawer-close" type="button" aria-label="${t("close")}">×</button></div><div class="analytics-death-content"></div></dialog></div>`;
  const applyFilterValues = () => {
    $("#analytics-kind").value = filters.kind === "deaths" ? "all" : filters.kind;
    $("#analytics-days").value = String(filters.days);
    $("#analytics-source").value = filters.source;
  };
  applyFilterValues();
  const reload = async () => {
    const target = $("#analytics-results");
    target.innerHTML = `<div class="analytics-loading">${t("checking")}</div>`;
    try {
      const query = new URLSearchParams({ kind: filters.kind, player: filters.player, source: filters.source, search: filters.search, days: String(filters.days), page: String(filters.page), page_size: "25" });
      const [result, roster] = await Promise.all([api(`/api/analytics/activity?${query}`), api("/api/players")]);
      const playerSelect = $("#analytics-player");
      const options = (roster.players || []).map((player) => `<option value="${escapeHtml(player.name)}">${escapeHtml(player.name)}</option>`).join("");
      playerSelect.innerHTML = `<option value="">${t("everyPlayer")}</option>${options}`;
      playerSelect.value = filters.player;
      const summary = result.summary || {};
      target.innerHTML = `<div class="analytics-summary"><span><small>${t("joinsOnly")}</small><b>${summary.joins || 0}</b></span><span><small>${t("leavesOnly")}</small><b>${summary.leaves || 0}</b></span><span><small>${t("respawnsOnly")}</small><b>${summary.respawns || 0}</b></span><span><small>${t("dimensionsOnly")}</small><b>${summary.dimensions || 0}</b></span><span class="death"><small>${t("deathsView")}</small><b>${summary.deaths || 0}</b></span><span><small>${t("permissionsOnly")}</small><b>${summary.permissions || 0}</b></span></div><div class="analytics-result-meta"><b>${t("eventCount", result.total)}</b><span>${t("pageCount", result.page, result.pages)}</span></div>${analyticsEventsMarkup(result.events || [])}<div class="analytics-pagination"><button id="analytics-previous" class="secondary" type="button" ${result.page <= 1 ? "disabled" : ""}>← ${t("previous")}</button><button id="analytics-next" class="secondary" type="button" ${result.page >= result.pages ? "disabled" : ""}>${t("next")} →</button></div>`;
      target.querySelectorAll("[data-analytics-player]").forEach((button) => button.onclick = () => openAnalyticsPlayer(button.dataset.analyticsPlayer));
      target.querySelectorAll("[data-death-detail]").forEach((button) => button.onclick = () => showDeathDetails((result.events || [])[Number(button.dataset.deathDetail)]));
      $("#analytics-previous").onclick = () => { filters.page -= 1; reload(); window.scrollTo({ top: 0, behavior: "smooth" }); };
      $("#analytics-next").onclick = () => { filters.page += 1; reload(); window.scrollTo({ top: 0, behavior: "smooth" }); };
    } catch (error) { target.innerHTML = `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`; }
  };
  bindAnalyticsViewSwitch();
  [["analytics-kind", "kind"], ["analytics-player", "player"], ["analytics-source", "source"]].forEach(([id, key]) => {
    $(`#${id}`).onchange = (event) => { filters[key] = event.target.value; filters.page = 1; reload(); };
  });
  $("#analytics-days").onchange = (event) => { filters.days = Number(event.target.value); filters.page = 1; reload(); };
  $("#analytics-search").onchange = (event) => { filters.search = event.target.value.trim(); filters.page = 1; reload(); };
  $("#analytics-refresh").onclick = reload;
  $("#analytics-death-dialog .drawer-close").onclick = () => $("#analytics-death-dialog").close();
  await reload();
}

function renderTimePanel() {
  const presets = ["sunrise", "day", "noon", "sunset", "night", "midnight"];
  const presetIcons = { sunrise: "🌅", day: "☀", noon: "◉", sunset: "🌇", night: "☾", midnight: "✦" };
  content.innerHTML = `
    <div class="time-screen">
      <section class="time-card block-panel"><h3>${t("timeOfDay")}</h3><p>${state.locale === "pt" ? "Escolha um momento predefinido do ciclo completo." : "Choose a preset from the complete daylight cycle."}</p><div class="time-presets">${presets.map((preset) => `<button type="button" data-time-preset="${preset}"><span>${presetIcons[preset]}</span>${t(preset)}</button>`).join("")}</div></section>
      <section class="time-card block-panel"><h3>${t("exactTime")}</h3><p>${t("exactTimeHelp")}</p><div class="command-row"><input id="exact-time" type="number" min="0" max="24000" value="0"><button type="button" id="set-exact-time">${t("setTime")}</button></div><h3 class="subheading">${t("advanceTime")}</h3><p>${t("advanceTimeHelp")}</p><div class="command-row"><input id="add-time" type="number" min="1" max="240000" value="1000"><button type="button" id="add-time-button">${t("addTime")}</button></div></section>
      <section class="time-card block-panel"><h3>${t("cycles")}</h3><div class="cycle-row"><div><strong>${t("daylightCycle")}</strong><small>${state.locale === "pt" ? "Desative para congelar o horário atual." : "Disable to freeze the current time."}</small></div>${booleanControl("time-daylight-cycle", state.gamerules.dodaylightcycle)}</div><div class="cycle-row"><div><strong>${t("weatherCycle")}</strong><small>${state.locale === "pt" ? "Desative para manter o clima escolhido." : "Disable to keep the selected weather."}</small></div>${booleanControl("time-weather-cycle", state.gamerules.doweathercycle)}</div></section>
      <section class="time-card block-panel"><h3>${t("weatherTitle")}</h3><p>${state.locale === "pt" ? "Escolha o clima e, se quiser, uma duração em ticks." : "Choose the weather and optionally set a duration in ticks."}</p><div class="weather-options"><button data-weather="clear">☀ ${t("clear")}</button><button data-weather="rain">☂ ${t("rain")}</button><button data-weather="thunder">ϟ ${t("thunder")}</button></div><input id="weather-duration" type="number" min="1" max="1000000" placeholder="${t("duration")}"><button id="weather-query" class="secondary wide">${t("queryWeather")}</button></section>
      <section class="time-card block-panel"><h3>${t("timeQueries")}</h3><div class="query-buttons"><button data-time-query="daytime">${t("daytime")}</button><button data-time-query="gametime">${t("gametime")}</button><button data-time-query="day">${t("days")}</button></div><output id="time-query-result">${t("queryResult")}: —</output></section>
      <section class="time-card danger-zone block-panel"><h3>${t("resetDays")}</h3><p>${t("resetDaysHelp")}</p><button id="reset-days" class="danger wide">${t("resetDays")}</button></section>
    </div>`;
  bindTimePanel();
}

async function runTimeAction(action, payload = {}) {
  const result = await api(`/api/time/${action}`, { method: "POST", body: JSON.stringify(payload) });
  toast(t("timeUpdated"));
  return result;
}

function bindTimePanel() {
  content.querySelectorAll("[data-time-preset]").forEach((button) => button.onclick = async () => {
    try { await runTimeAction("preset", { value: button.dataset.timePreset }); } catch (error) { toast(error.message, true); }
  });
  $("#set-exact-time").onclick = async () => {
    try { await runTimeAction("set", { value: $("#exact-time").value }); } catch (error) { toast(error.message, true); }
  };
  $("#add-time-button").onclick = async () => {
    try { await runTimeAction("add", { value: $("#add-time").value }); } catch (error) { toast(error.message, true); }
  };
  [["time-daylight-cycle", "dodaylightcycle"], ["time-weather-cycle", "doweathercycle"]].forEach(([id, rule]) => {
    $(`#${id}`).onchange = async (event) => {
      updateToggleLabel(event.target);
      try {
        await api(`/api/gamerules/${rule}`, { method: "PUT", body: JSON.stringify({ value: event.target.checked }) });
        state.gamerules[rule] = String(event.target.checked);
      } catch (error) { toast(error.message, true); renderTimePanel(); }
    };
  });
  content.querySelectorAll("[data-weather]").forEach((button) => button.onclick = async () => {
    try { await runTimeAction("weather", { value: button.dataset.weather, duration: $("#weather-duration").value }); } catch (error) { toast(error.message, true); }
  });
  $("#weather-query").onclick = async () => {
    try { const result = await runTimeAction("weather-query"); $("#time-query-result").textContent = `${t("queryResult")}: ${t(result.value) || result.value}`; } catch (error) { toast(error.message, true); }
  };
  content.querySelectorAll("[data-time-query]").forEach((button) => button.onclick = async () => {
    try {
      const result = await runTimeAction("query", { value: button.dataset.timeQuery });
      $("#time-query-result").textContent = `${t("queryResult")}: ${result.value ?? t("queryUnavailable")}`;
    } catch (error) { toast(error.message, true); }
  });
  $("#reset-days").onclick = async () => {
    if (!confirm(t("resetDaysConfirm"))) return;
    try { await runTimeAction("reset-days"); } catch (error) { toast(error.message, true); }
  };
}

function renderTabs() {
  const icons = { home: "⌂", world: "◆", players: "♟", analytics: "▥", rules: "☷", server: "⚙" };
  const activeDestination = state.tab === "__time__" ? "world" : state.tab === "__players__" ? "players" : state.tab;
  $("#tabs").innerHTML = state.tabs.map((tab) => `<button class="${tab === activeDestination ? "active" : ""}" data-tab="${tab}"><i>${icons[tab]}</i><span>${t(tab === "server" ? "settings" : tab)}</span></button>`).join("");
  $("#tabs").querySelectorAll("button").forEach((button) => button.onclick = () => {
    state.tab = button.dataset.tab === "players" ? "__players__" : button.dataset.tab;
    renderTabs();
    render();
  });
}

function setStatus(status) {
  state.status = status;
  const element = $("#status");
  element.textContent = status.online ? `● ${t("online")}` : `○ ${t("stopped")}`;
  element.classList.toggle("online", status.online);
  $("#server-state-title").textContent = status.online ? t("serverOnline") : t("serverStopped");
  $("#hero").classList.toggle("offline", !status.online);
}

function showPlayers(snapshot) {
  state.players = snapshot.players || [];
  state.online = snapshot.online || 0;
  state.maxPlayers = snapshot.max_players || 0;
  if (snapshot.updated_at !== undefined) state.updatedAt = snapshot.updated_at || 0;
  $("#players-summary").textContent = `${state.online} / ${state.maxPlayers || "?"} ${t("playersOnline")}`;
  $("#players-list").textContent = state.players.length ? state.players.join(" · ") : t("nobody");
  $("#updated-at").textContent = state.updatedAt ? `${t("updated")} ${new Date(state.updatedAt * 1000).toLocaleTimeString(state.locale === "en" ? "en-US" : "pt-BR")}` : t("awaiting");
}

function updateBrand() {
  const name = state.config.SERVER_NAME || "Minecraft Bedrock";
  $("#instance-name").textContent = name;
  document.title = `CraftControl · ${name}`;
}

function applyLocale() {
  document.documentElement.lang = state.locale === "en" ? "en" : "pt-BR";
  document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n); });
  $("#language").textContent = state.locale === "pt" ? "EN" : "PT";
  $("#language").setAttribute("aria-label", state.locale === "pt" ? "Switch to English" : "Mudar para português");
  renderTabs();
  render();
  updateSaveLabel();
  if (state.status) setStatus(state.status);
  showPlayers({ players: state.players, online: state.online, max_players: state.maxPlayers, updated_at: state.updatedAt });
  updateBrand();
}

async function loadState() {
  const snapshot = await api("/api/state");
  state.config = snapshot.settings || {};
  state.gamerules = snapshot.gamerules || {};
  state.domains = snapshot.domains || {};
  updateBrand();
  showPlayers(snapshot);
  render();
}

async function boot() {
  const [schema, snapshot, status] = await Promise.all([api("/api/schema"), api("/api/state"), api("/api/status")]);
  state.schema = schema;
  state.config = snapshot.settings || {};
  state.gamerules = snapshot.gamerules || {};
  state.domains = snapshot.domains || {};
  updateBrand();
  showPlayers(snapshot);
  setStatus(status);
  applyLocale();
  connectEvents();
}

let eventRefreshTimer = null;
function connectEvents() {
  connectEventStream((event) => {
    if (event.topic === "state.changed" || event.topic.startsWith("server.")) {
      clearTimeout(eventRefreshTimer);
      eventRefreshTimer = setTimeout(async () => {
        await loadState();
        if (event.topic.startsWith("server.")) setStatus(await api("/api/status"));
      }, 300);
    }
  });
}

$("#language").onclick = () => {
  state.locale = state.locale === "pt" ? "en" : "pt";
  localStorage.setItem("craftcontrol-locale", state.locale);
  applyLocale();
};

function openTimeControls() {
  state.tab = "__time__";
  renderTabs();
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

$("#time-controls").onclick = openTimeControls;

function openPlayers() {
  state.tab = "__players__";
  renderTabs();
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

$("#open-players").onclick = openPlayers;

$("#refresh").onclick = async () => {
  try {
    $("#refresh").classList.add("spinning");
    await api("/api/refresh", { method: "POST" });
    toast(t("querying"));
    setTimeout(async () => { await loadState(); $("#refresh").classList.remove("spinning"); toast(t("stateUpdated")); }, 1800);
  } catch (error) { $("#refresh").classList.remove("spinning"); toast(error.message, true); }
};

$("#save").onclick = () => {
  renderChangesDrawer();
  $("#changes-drawer").showModal();
};

$("#close-changes").onclick = () => $("#changes-drawer").close();
$("#discard-all").onclick = () => {
  state.changes = {};
  $("#changes-drawer").close();
  render();
  updateSaveLabel();
};

$("#apply-changes").onclick = async () => {
  if (!Object.keys(state.changes).length) return;
  try {
    $("#apply-changes").disabled = true;
    await api("/api/config", { method: "PUT", body: JSON.stringify(state.changes) });
    toast(t("saved"));
    await api("/api/server/apply", { method: "POST" });
    Object.assign(state.config, state.changes);
    state.changes = {};
    $("#changes-drawer").close();
    updateSaveLabel();
    toast(t("serverUpdated"));
  } catch (error) { toast(error.message, true); }
  finally { $("#apply-changes").disabled = false; }
};

document.querySelectorAll("[data-world]").forEach((button) => button.onclick = async () => {
  try { await api(`/api/world/${button.dataset.world}`, { method: "POST" }); toast(t("worldUpdated")); }
  catch (error) { toast(error.message, true); }
});
$("#server-menu").onclick = () => $("#server-dialog").showModal();
$("#close-dialog").onclick = () => $("#server-dialog").close();
document.querySelectorAll("[data-server]").forEach((button) => button.onclick = async () => {
  if (!confirm(t("confirmAction", t(button.dataset.server)))) return;
  try {
    await api(`/api/server/${button.dataset.server}`, { method: "POST" });
    toast(t("operationDone"));
    $("#server-dialog").close();
    setTimeout(async () => setStatus(await api("/api/status")), 1500);
  } catch (error) { toast(error.message, true); }
});

requireSession().then((user) => {
  if (user) { state.user = user; boot().catch((error) => toast(error.message, true)); }
}).catch((error) => toast(error.message, true));

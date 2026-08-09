import { api } from "./js/api.js?v=1";
import { connectEventStream } from "./js/events.js";
import { requireSession } from "./js/auth.js?v=4";
import { state } from "./js/core/state.js?v=1";
import { $, escapeHtml } from "./js/core/dom.js?v=1";
import { toast } from "./js/components/feedback.js?v=1";
import { formatDate as formatLocalizedDate, formatDuration, timelineTimestamp as localizedTimelineTimestamp } from "./js/components/time.js?v=1";
import { createAnalyticsFeature } from "./js/features/analytics/index.js?v=1";
import { createPlayersFeature } from "./js/features/players/index.js?v=1";
import { createWorldFeature } from "./js/features/world/index.js?v=1";
import { createRulesFeature } from "./js/features/rules/index.js?v=1";
import { createServerFeature } from "./js/features/server/index.js?v=1";
import { startAuthenticatedApplication } from "./js/features/auth/bootstrap.js?v=1";

const content = $("#content");

if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
window.addEventListener("pageshow", () => requestAnimationFrame(() => window.scrollTo(0, 0)));

const messages = {
  pt: {
    language: "Idioma",
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
    activityView: "Atividade", deathsView: "Mortes", rankingsView: "Rankings", blocksView: "Blocos", combatView: "Combate", explorationView: "Exploração", trendsView: "Períodos", eventFilter: "Evento", playerFilter: "Jogador", periodFilter: "Período", sourceFilter: "Origem", detailFilter: "Causa ou responsável", detailFilterHint: "Ex.: zombie, lava…",
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
    favoriteTargets: "Criaturas favoritas", targetKills: "eliminações",
    explorationTitle: "Exploração do mundo", explorationHelp: "Distância amostrada, dimensões, sessões e jornadas dos jogadores.", explorationEmptyHelp: "Toda a expedição permanece visível mesmo antes do primeiro dado de movimento.", distanceTraveled: "Distância percorrida", dimensionsDiscovered: "Dimensões descobertas", dimensionVisits: "Visitas a dimensões", explorationSessions: "Sessões", explorerRanking: "Ranking de exploradores", dimensionMap: "Mapa dimensional", recentJourneys: "Jornadas recentes", explorerProfiles: "Exploradores", noExplorationEvidence: "Nenhuma jornada registrada ainda.", favoriteDimension: "Dimensão favorita", explorationFirstSeen: "Primeira visita", explorationLastSeen: "Última visita", horizontalSampled: "Distância horizontal amostrada; teletransportes longos são ignorados.", visitCount: "visitas",
    activeMovementTime: "Tempo ativo em movimento", dimensionDistance: "Distância na dimensão",
    trendsTitle: "Histórico por período", trendsHelp: "Rankings reais, calendário diário e horários de atividade construídos sem reescrever o passado.", sevenDays: "7 dias", thirtyDays: "30 dias", periodRanking: "Ranking do período", activityCalendar: "Calendário de atividade", sessionHeatmap: "Horários de jogo", mostActiveDay: "Dia mais ativo", collectionStarted: "A coleta diária começa nesta versão; dados vitalícios anteriores não são atribuídos artificialmente a hoje.", noPeriodData: "Ainda não há atividade registrada neste período.", dailyPlayers: "Jogadores ativos", dailyBlocks: "Blocos", dailyKills: "Eliminações", lessActive: "Menos", moreActive: "Mais", weekdayShort: ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
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
    craftControlImage: "Imagem CraftControl", activeSince: "Ativa desde", packObserved: "Pack observado", packInstalledAt: "Arquivos atualizados em",
  },
  en: {
    language: "Language",
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
    activityView: "Activity", deathsView: "Deaths", rankingsView: "Rankings", blocksView: "Blocks", combatView: "Combat", explorationView: "Exploration", trendsView: "Periods", eventFilter: "Event", playerFilter: "Player", periodFilter: "Period", sourceFilter: "Source", detailFilter: "Cause or responsible", detailFilterHint: "E.g. zombie, lava…",
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
    favoriteTargets: "Favorite creatures", targetKills: "kills",
    explorationTitle: "World exploration", explorationHelp: "Sampled distance, dimensions, sessions, and player journeys.", explorationEmptyHelp: "The complete expedition remains visible even before the first movement sample.", distanceTraveled: "Distance traveled", dimensionsDiscovered: "Dimensions discovered", dimensionVisits: "Dimension visits", explorationSessions: "Sessions", explorerRanking: "Explorer ranking", dimensionMap: "Dimension map", recentJourneys: "Recent journeys", explorerProfiles: "Explorers", noExplorationEvidence: "No journey has been recorded yet.", favoriteDimension: "Favorite dimension", explorationFirstSeen: "First seen", explorationLastSeen: "Last seen", horizontalSampled: "Sampled horizontal distance; long teleports are ignored.", visitCount: "visits",
    activeMovementTime: "Active movement time", dimensionDistance: "Distance in dimension",
    trendsTitle: "Period history", trendsHelp: "Real rankings, a daily calendar, and play-hour patterns built without rewriting the past.", sevenDays: "7 days", thirtyDays: "30 days", periodRanking: "Period ranking", activityCalendar: "Activity calendar", sessionHeatmap: "Play hours", mostActiveDay: "Most active day", collectionStarted: "Daily collection starts with this release; previous lifetime totals are not artificially assigned to today.", noPeriodData: "There is no recorded activity in this period yet.", dailyPlayers: "Active players", dailyBlocks: "Blocks", dailyKills: "Kills", lessActive: "Less", moreActive: "More", weekdayShort: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
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
    craftControlImage: "CraftControl image", activeSince: "Active since", packObserved: "Observed pack", packInstalledAt: "Files updated at",
  },
};

messages.es = {
  ...messages.en,
  language: "Idioma", brandKicker: "CENTRAL DE CONTROL BEDROCK", refresh: "Actualizar", worldState: "ESTADO DEL MUNDO", quickActions: "Acciones rápidas",
  day: "Día", night: "Noche", clearWeather: "Clima despejado", server: "Servidor", saveChanges: "Guardar cambios", control: "CONTROL", serverOperation: "Operación del servidor",
  restartNotice: "Los cambios persistentes se aplican al guardar y reiniciar.", start: "Iniciar", restart: "Reiniciar", stop: "Detener", close: "Cerrar",
  checking: "Comprobando…", online: "En línea", stopped: "Detenido", serverOnline: "Servidor en línea", serverStopped: "Servidor detenido", playersOnline: "jugadores en línea", nobody: "Nadie conectado",
  awaiting: "Esperando actualización", updated: "Actualizado", enabled: "Activado", disabled: "Desactivado", unknown: "Sin consultar", immediate: "Aplicación inmediata", restartRequired: "Se aplica al guardar y reiniciar",
  saved: "Guardado. Aplicando en el servidor…", serverUpdated: "Servidor actualizado", noChanges: "No hay cambios pendientes", querying: "Consultando el servidor…", stateUpdated: "Estado actualizado", worldUpdated: "Mundo actualizado", operationDone: "Operación completada",
  confirmAction: (action) => `¿${action} el servidor?`, saveCount: (count) => `Guardar (${count})`, fieldUpdated: (label) => `${label} actualizado`,
  timeControls: "Hora y clima", timeControlsHint: "Hora, ciclos y clima", timeOfDay: "Hora del mundo", sunrise: "Amanecer", noon: "Mediodía", sunset: "Atardecer", midnight: "Medianoche", exactTime: "Hora exacta", exactTimeHelp: "Define un valor entre 0 y 24000 ticks.", setTime: "Definir hora", advanceTime: "Avanzar el tiempo", addTime: "Avanzar", cycles: "Ciclos automáticos", daylightCycle: "Ciclo de día y noche", weatherCycle: "Ciclo climático", timeQueries: "Consultar reloj", days: "Días jugados", queryResult: "Resultado", weatherTitle: "Clima", clear: "Despejado", rain: "Lluvia", thunder: "Tormenta", setWeather: "Aplicar clima", queryWeather: "Consultar clima",
  onlinePlayers: "Jugadores en línea", operatorAccess: "Operador", noOnlinePlayers: "No hay jugadores en línea.", permissionUpdated: "Permiso actualizado", allPlayers: "Todos los jugadores", offline: "Desconectado", sessions: "Sesiones", playTime: "Tiempo jugado", deaths: "Muertes", firstSeen: "Primera conexión", lastSeen: "Última conexión", viewHistory: "Ver historial", hideHistory: "Ocultar historial", noHistory: "No hay eventos registrados.", totalPlayers: "Jugadores", totalDeaths: "Muertes registradas", totalPlayTime: "Tiempo acumulado", searchPlayers: "Buscar jugador", filterAll: "Todos", filterOnline: "En línea", filterOffline: "Desconectados", filterOperators: "Operadores", connectedSince: "Conectado desde", lastDeath: "Última muerte", permission: "Permiso", aliases: "Nombres conocidos", recentSessions: "Sesiones recientes", normalExit: "Salida normal", inferredExit: "Cierre inferido", noPlayersFound: "Ningún jugador coincide con los filtros.",
  telemetryStats: "Estadísticas del mundo", authoritative: "Datos estructurados por el behavior pack", playerKills: "Jugadores eliminados", mobKills: "Criaturas eliminadas", blocksBroken: "Bloques rotos", blocksPlaced: "Bloques colocados", damageDealt: "Daño causado", damageTaken: "Daño recibido", distanceTraveled: "Distancia recorrida", dimensionsVisited: "Dimensiones visitadas", deathHistory: "Historial de muertes", noDeaths: "No hay muertes detalladas registradas.", deathCause: "Causa", killedBy: "Responsable", projectile: "Proyectil",
  home: "Inicio", world: "Mundo", players: "Jugadores", analytics: "Datos", rules: "Reglas", settings: "Servidor", analyticsTitle: "Actividad del servidor", analyticsHelp: "El historial compartido de entradas, salidas, muertes y cambios de permisos.", activityView: "Actividad", deathsView: "Muertes", rankingsView: "Clasificaciones", blocksView: "Bloques", combatView: "Combate", explorationView: "Exploración", trendsView: "Períodos", eventFilter: "Evento", playerFilter: "Jugador", periodFilter: "Período", sourceFilter: "Origen", everyEvent: "Todos los eventos", joinsOnly: "Entradas", leavesOnly: "Salidas", permissionsOnly: "Permisos", dimensionsOnly: "Dimensiones", everyPlayer: "Todos los jugadores", lifetime: "Desde el inicio", last7Days: "Últimos 7 días", last30Days: "Últimos 30 días", everySource: "Todos los orígenes", activityEmpty: "Ningún evento coincide con estos filtros.", eventCount: (count) => `${count} eventos`, pageCount: (page, pages) => `Página ${page} de ${pages}`, previous: "Anterior", next: "Siguiente", refreshData: "Actualizar datos", deathDetails: "Detalles de la muerte", viewDetails: "Ver detalles",
  rankingsTitle: "Clasificaciones y récords", leaderboard: "Clasificación", records: "Récords del servidor", noRankingData: "Todavía no hay datos para esta categoría.", categoryActivity: "Actividad", categoryCombat: "Combate", categoryBuilding: "Bloques", categoryExploration: "Exploración", rankPlayTime: "Tiempo jugado", rankSessions: "Sesiones", rankDeaths: "Muertes", rankBlocksBroken: "Bloques rotos", rankBlocksPlaced: "Bloques colocados", rankDistance: "Distancia", rankDimensions: "Dimensiones",
  blocksTitle: "Minería y construcción", blocksHelp: "Descubre qué consumió el mundo, quién minó más y quién construyó más.", miningView: "Minería", buildingView: "Construcción", oresTitle: "Minerales encontrados", topBlocks: "Bloques más frecuentes", favoriteBlocks: "Favoritos de los jugadores", miners: "Mineros", builders: "Constructores", noBlockData: "Todavía no hay bloques registrados por el Telemetry Pack.", broken: "Rotos", placed: "Colocados", oreRanking: "Clasificación del mineral",
  combatTitle: "Combate del servidor", combatDeaths: "Muertes", combatPlayerKills: "Eliminaciones JcJ", combatMobKills: "Criaturas eliminadas", combatDamageDealt: "Daño causado", combatDamageTaken: "Daño recibido", combatRankings: "Clasificación de combate", deathCauses: "Causas de muerte", lethalOpponents: "Responsables de las muertes", projectiles: "Proyectiles", noCombatEvidence: "Todavía no hay evidencias registradas.", telemetryWaiting: "Esperando telemetría", favoriteTargets: "Criaturas favoritas", targetKills: "eliminaciones",
  explorationTitle: "Exploración del mundo", distanceTraveled: "Distancia recorrida", dimensionsDiscovered: "Dimensiones descubiertas", dimensionVisits: "Visitas a dimensiones", explorationSessions: "Sesiones", explorerRanking: "Clasificación de exploradores", recentJourneys: "Viajes recientes", noExplorationEvidence: "Todavía no hay viajes registrados.", favoriteDimension: "Dimensión favorita", visitCount: "visitas",
  trendsTitle: "Historial por período", sevenDays: "7 días", thirtyDays: "30 días", periodRanking: "Clasificación del período", activityCalendar: "Calendario de actividad", sessionHeatmap: "Horarios de juego", mostActiveDay: "Día más activo", noPeriodData: "Todavía no hay actividad registrada en este período.", dailyPlayers: "Jugadores activos", dailyBlocks: "Bloques", dailyKills: "Eliminaciones", lessActive: "Menos", moreActive: "Más", weekdayShort: ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
  worldIntro: "Configuración del mundo", rulesIntro: "Comportamiento del juego", serverIntro: "Infraestructura del servidor", pendingChanges: "CAMBIOS PENDIENTES", reviewChanges: "Revisar cambios", pendingHelp: "Estas configuraciones se guardarán y el servidor solo se reiniciará cuando las apliques.", discardAll: "Descartar todos", applyChanges: "Aplicar cambios", removeChange: "Quitar", currentValue: "Actual", newValue: "Nuevo", reviewCount: (count) => `Revisar (${count})`, confirmedAt: "Confirmado",
  telemetryPackHelp: "Estadísticas nativas e historial estructurado del mundo.", installedVersion: "Versión instalada", bundledVersion: "Versión disponible", packHealth: "Estado", lastResponse: "Última respuesta", packActive: "Instalado y activo", packInactive: "Desactivado", packMissing: "No instalado", upgradeAvailable: "Actualización disponible", installPack: "Instalar", upgradePack: "Actualizar", disablePack: "Desactivar", rollbackPack: "Restaurar copia", healthy: "Saludable", syncing: "Sincronizando", degraded: "Degradado", waiting: "Esperando", craftControlImage: "Imagen de CraftControl", activeSince: "Activa desde", packObserved: "Pack observado", packInstalledAt: "Archivos actualizados el",
};

const groups = {
  Geral: "General", Mundo: "World", Jogadores: "Players", Packs: "Packs", Rede: "Network",
  Avançado: "Advanced", Interface: "Interface", Jogabilidade: "Gameplay",
  "Tempo e clima": "Time and weather", Criaturas: "Mobs", Drops: "Drops", Comandos: "Commands",
};
const optionNames = {
  survival: { pt: "Sobrevivência", en: "Survival", es: "Supervivencia" }, creative: { pt: "Criativo", en: "Creative", es: "Creativo" },
  adventure: { pt: "Aventura", en: "Adventure", es: "Aventura" }, peaceful: { pt: "Pacífico", en: "Peaceful", es: "Pacífico" },
  easy: { pt: "Fácil", en: "Easy", es: "Fácil" }, normal: { pt: "Normal", en: "Normal", es: "Normal" }, hard: { pt: "Difícil", en: "Hard", es: "Difícil" },
  DEFAULT: { pt: "Normal", en: "Default", es: "Predeterminado" }, FLAT: { pt: "Plano", en: "Flat", es: "Plano" }, LEGACY: { pt: "Legado", en: "Legacy", es: "Heredado" },
  visitor: { pt: "Visitante", en: "Visitor", es: "Visitante" }, member: { pt: "Membro", en: "Member", es: "Miembro" }, operator: { pt: "Operador", en: "Operator", es: "Operador" },
};

function t(key, ...args) {
  const value = messages[state.locale]?.[key] ?? messages.en[key] ?? key;
  return typeof value === "function" ? value(...args) : value;
}

function localeTag() { return { pt: "pt-BR", en: "en-US", es: "es-ES" }[state.locale]; }
function localized(pt, en, es = en) { return state.locale === "pt" ? pt : state.locale === "es" ? es : en; }

function can(capability) {
  const capabilities = state.user?.capabilities || [];
  return capabilities.includes("*") || capabilities.includes(capability);
}

function fieldLabel(definition) {
  return state.locale === "pt" ? definition.label : definition[`label_${state.locale}`] || definition.label_en;
}

function fieldDescription(definition) {
  return state.locale === "pt" ? definition.description : definition[`description_${state.locale}`] || definition.description_en;
}

function groupLabel(group) {
  if (group === "__time__") return t("timeControls");
  if (group === "__players__") return t("onlinePlayers");
  const spanishGroups = { Geral: "General", Mundo: "Mundo", Jogadores: "Jugadores", Packs: "Packs", Rede: "Red", Avançado: "Avanzado", Interface: "Interfaz", Jogabilidade: "Jugabilidad", "Tempo e clima": "Hora y clima", Criaturas: "Criaturas", Drops: "Botín", Comandos: "Comandos" };
  return state.locale === "pt" ? group : state.locale === "es" ? (spanishGroups[group] || group) : (groups[group] || group);
}

function optionLabel(option) {
  return optionNames[option]?.[state.locale] || option;
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
  const warning = warningText ? `<small class="field-warning">${uiIcon("warning")} ${escapeHtml(warningText)}</small>` : "";
  return `<div class="field ${live ? "live-field" : ""}"><div class="field-copy"><label id="label-${id}" for="${id}">${escapeHtml(fieldLabel(definition))}</label><p>${escapeHtml(fieldDescription(definition))}</p>${warning}<small class="field-meta">${uiIcon(live ? "live" : "restart")} ${live ? t("immediate") : t("restartRequired")}</small></div>${input}</div>`;
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
    return `<article class="change-item"><div class="change-copy"><strong>${escapeHtml(fieldLabel(definition))}</strong><div class="change-values"><span><small>${t("currentValue")}</small>${escapeHtml(displayValue(state.config[key], definition))}</span><b>→</b><span><small>${t("newValue")}</small>${escapeHtml(displayValue(value, definition))}</span></div></div><button type="button" class="remove-change" data-remove-change="${escapeHtml(key)}" aria-label="${t("removeChange")}">${uiIcon("close")}</button></article>`;
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
    getWorldFeature().renderTimePanel();
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
  if (state.tab === "world") getWorldFeature().renderWorld();
  else if (state.tab === "rules") getRulesFeature().renderRules();
  else if (state.tab === "server") getServerFeature().renderServer();
}

function settingsMarkup(groupNames) {
  return groupNames.map((group, index) => {
    const persistent = Object.entries(state.schema.settings).filter(([, definition]) => definition.group === group);
    const live = Object.entries(state.schema.gamerules).filter(([, definition]) => definition.group === group);
    if (!persistent.length && !live.length) return "";
    const domain = persistent.length ? state.domains.settings : state.domains.gamerules;
    const observed = domain?.observed_at ? `${t("confirmedAt")} ${new Date(domain.observed_at * 1000).toLocaleTimeString(localeTag())}` : t("unknown");
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

let worldFeature = null;
let rulesFeature = null;
let serverFeature = null;

function getWorldFeature() {
  if (!worldFeature) worldFeature = createWorldFeature({ state, content, t, api, $, uiIcon, booleanControl, updateToggleLabel, toast, renderSettingsGroups, renderTabs });
  return worldFeature;
}

function getRulesFeature() {
  if (!rulesFeature) rulesFeature = createRulesFeature({ renderSettingsGroups });
  return rulesFeature;
}

function getServerFeature() {
  if (!serverFeature) serverFeature = createServerFeature({ state, content, t, api, $, escapeHtml, uiIcon, formatDate, toast, renderSettingsGroups });
  return serverFeature;
}

function formatDate(timestamp) {
  return formatLocalizedDate(timestamp, localeTag());
}

function timelineTimestamp(timestamp) {
  return localizedTimelineTimestamp(timestamp, localeTag());
}

let playersFeature = null;
function getPlayersFeature() {
  if (!playersFeature) {
    playersFeature = createPlayersFeature({
      state, content, t, api, $, escapeHtml, toast, playerSettingsMarkup,
      bindSegmentedControls, bindSettingFields, formatDuration, formatDate,
      timelineTimestamp, gameLabel, gameIcon, gameTermMarkup, optionLabel,
      blockTermMarkup, dimensionName, formatRankingValue, uiIcon, booleanControl,
      renderAnalyticsPanel, renderTabs, updateToggleLabel,
    });
  }
  return playersFeature;
}

async function renderPlayersPanel() {
  await getPlayersFeature().renderPlayersPanel();
}

async function renderPlayerDetail(player, account, back = renderPlayersPanel) {
  await getPlayersFeature().renderPlayerDetail(player, account, back);
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
  if (format === "distance") return `${Math.round(Number(value || 0)).toLocaleString(localeTag())} m`;
  if (format === "decimal") return Number(value || 0).toLocaleString(localeTag(), { maximumFractionDigits: 1 });
  return Number(value || 0).toLocaleString(localeTag());
}

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
  if (state.locale === "es" && blockLabelsEs[raw]) return blockLabelsEs[raw];
  const known = blockLabels[raw];
  if (known) return known[state.locale === "pt" ? 0 : 1];
  const words = raw.split("_");
  const localized = state.locale === "pt" ? words.map((word) => blockWordLabels[word] || word).join(" ") : words.join(" ");
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
function gameLabel(value, kind = "entity") { const raw = String(value || "—").replace(/^minecraft:/, ""); if (state.locale === "es" && gameLabelsEs[raw]) return gameLabelsEs[raw]; const term = gameTerm(value, kind); return term[state.locale === "pt" ? 1 : 2]; }
function gameTermMarkup(value, kind = "entity") {
  const label = gameLabel(value, kind);
  return `<span class="game-term">${gameIcon(value, kind)}<span>${escapeHtml(label)}</span></span>`;
}

function oreLabel(ore) {
  return t(`ore${ore.charAt(0).toUpperCase()}${ore.slice(1)}`);
}

let analyticsFeature = null;
async function renderAnalyticsPanel() {
  if (!analyticsFeature) {
    analyticsFeature = createAnalyticsFeature({
      state, content, t, uiIcon, api, $, escapeHtml, optionLabel,
      gameTermMarkup, timelineTimestamp, rankingDefinitions, formatRankingValue,
      formatDate, openAnalyticsPlayer, blockTermMarkup, blockIcon, oreLabel,
      formatDuration, dimensionName, localeTag, requestRender: renderAnalyticsPanel,
    });
  }
  await analyticsFeature.render();
}

function renderTabs() {
  const icons = { home: "home", world: "world", players: "players", analytics: "data", rules: "rules", server: "server" };
  const activeDestination = state.tab === "__time__" ? "world" : state.tab === "__players__" ? "players" : state.tab;
  $("#tabs").innerHTML = state.tabs.map((tab) => `<button class="${tab === activeDestination ? "active" : ""}" data-tab="${tab}"><i>${uiIcon(icons[tab])}</i><span>${t(tab === "server" ? "settings" : tab)}</span></button>`).join("");
  $("#tabs").querySelectorAll("button").forEach((button) => button.onclick = () => {
    state.tab = button.dataset.tab === "players" ? "__players__" : button.dataset.tab;
    renderTabs();
    render();
  });
}

function setStatus(status) {
  state.status = status;
  const element = $("#status");
  element.textContent = status.online ? t("online") : t("stopped");
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
  $("#updated-at").textContent = state.updatedAt ? `${t("updated")} ${new Date(state.updatedAt * 1000).toLocaleTimeString(localeTag())}` : t("awaiting");
}

function updateBrand() {
  const name = state.config.SERVER_NAME || "Minecraft Bedrock";
  $("#instance-name").textContent = name;
  document.title = `CraftControl · ${name}`;
}

function applyLocale() {
  document.documentElement.lang = localeTag();
  document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n); });
  const languageNames = { pt: "Português", en: "English", es: "Español" };
  const languageFlags = { pt: "br", en: "us", es: "es" };
  $("#language span").textContent = languageNames[state.locale];
  $("#language use").setAttribute("href", `/static/craftcontrol-ui.svg?v=2#ui-flag-${languageFlags[state.locale]}`);
  $("#language").setAttribute("aria-label", t("language"));
  document.querySelectorAll("[data-locale]").forEach((option) => option.setAttribute("aria-selected", String(option.dataset.locale === state.locale)));
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
  const [schema, snapshot, status, releases] = await Promise.all([api("/api/schema"), api("/api/state"), api("/api/status"), api("/api/telemetry-pack").catch(() => ({})), getServerFeature().loadFrontendVersion()]);
  state.schema = schema;
  state.config = snapshot.settings || {};
  state.gamerules = snapshot.gamerules || {};
  state.domains = snapshot.domains || {};
  updateBrand();
  showPlayers(snapshot);
  setStatus(status);
  getServerFeature().renderReleaseTags(releases);
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
  const menu = $("#language-menu");
  menu.hidden = !menu.hidden;
  $("#language").setAttribute("aria-expanded", String(!menu.hidden));
};
document.querySelectorAll("[data-locale]").forEach((option) => option.onclick = () => {
  state.locale = ["pt", "en", "es"].includes(option.dataset.locale) ? option.dataset.locale : "pt";
  localStorage.setItem("craftcontrol-locale", state.locale);
  $("#language-menu").hidden = true;
  $("#language").setAttribute("aria-expanded", "false");
  applyLocale();
});
document.addEventListener("click", (event) => {
  if (!event.target.closest("#language-picker")) { $("#language-menu").hidden = true; $("#language").setAttribute("aria-expanded", "false"); }
});

$("#time-controls").onclick = () => getWorldFeature().openTimeControls();

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

startAuthenticatedApplication({ requireSession, state, boot, toast });

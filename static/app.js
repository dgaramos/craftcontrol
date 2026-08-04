import { api } from "./js/api.js";
import { connectEventStream } from "./js/events.js";
import { requireSession } from "./js/auth.js";

const state = {
  schema: null, config: {}, gamerules: {}, players: [], online: 0, maxPlayers: 0,
  changes: {}, tab: "home", tabs: ["home", "world", "players", "rules", "server"], status: null, updatedAt: 0, domains: {},
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
    home: "Início", world: "Mundo", players: "Jogadores", rules: "Regras", settings: "Servidor",
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
    home: "Home", world: "World", players: "Players", rules: "Rules", settings: "Server",
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
  content.innerHTML = `<div class="players-screen block-panel"><h3>${t("allPlayers")}</h3><p>${t("playerHistoryHelp")}</p><div id="player-overview" class="player-overview" hidden></div><div class="player-toolbar" hidden><input id="player-search" type="search" placeholder="${t("searchPlayers")}" autocomplete="off"><div class="player-filters"><button class="active" data-player-filter="all">${t("filterAll")}</button><button data-player-filter="online">${t("filterOnline")}</button><button data-player-filter="offline">${t("filterOffline")}</button><button data-player-filter="operator">${t("filterOperators")}</button></div></div><div class="loading-players">${t("checking")}</div></div><div class="accordion-list">${settingsMarkup(["Jogadores"])}</div>`;
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
  container.innerHTML = list.map((player, index) => `<article class="player-management-card ${player.online ? "is-online" : "is-offline"}"><div class="player-avatar" aria-hidden="true">${escapeHtml(player.name.slice(0, 1).toUpperCase())}</div><div class="player-identity"><strong>${escapeHtml(player.name)}</strong><small>${player.online ? "● " + t("online") : "○ " + t("offline")}</small></div><div class="player-role"><span>${escapeHtml(optionLabel(player.permission || "member"))}</span>${booleanControl(`operator-${index}`, player.operator)}</div><div class="player-stats"><span><b>${player.sessions_count}</b>${t("sessions")}</span><span><b>${formatDuration(player.total_play_seconds)}</b>${t("playTime")}</span><span title="${t("derivedDeaths")}"><b>${player.deaths_count}*</b>${t("deaths")}</span></div><div class="player-dates"><span>${t("firstSeen")}: <b>${formatDate(player.first_seen_at)}</b></span><span>${player.online ? t("connectedSince") : t("lastSeen")}: <b>${formatDate(player.online ? player.connected_at : player.last_seen_at)}</b></span>${player.last_death_at ? `<span>${t("lastDeath")}: <b>${formatDate(player.last_death_at)}</b></span>` : ""}</div>${accessMarkup(player, index, access[player.name.toLocaleLowerCase()])}<button class="secondary player-history-button" data-player-index="${index}">${t("viewHistory")}</button><div class="player-history" id="player-history-${index}" hidden></div></article>`).join("");
  container.querySelectorAll(".player-management-card").forEach((card, index) => {
    const player = list[index];
    if (!player.telemetry_updated_at) return;
    card.classList.add("has-telemetry");
    card.querySelector(".player-identity small").insertAdjacentHTML("afterend", `<small class="telemetry-badge">◆ ${t("authoritative")}</small>`);
  });
  list.forEach((player, index) => {
      const id = `operator-${index}`;
      $(`#${id}`).onchange = async (event) => {
        updateToggleLabel(event.target);
        try {
          await api(`/api/players/${encodeURIComponent(player.name)}/operator`, { method: "PUT", body: JSON.stringify({ enabled: event.target.checked }) });
          toast(t("permissionUpdated"));
        } catch (error) { toast(error.message, true); renderPlayersPanel(); }
      };
      const invite = container.querySelector(`[data-access-invite="${index}"]`);
      if (invite) invite.onclick = async () => {
        const role = container.querySelector(`[data-access-role="${index}"]`).value;
        try {
          const result = await api("/api/auth/access/invite", { method: "POST", body: JSON.stringify({ player: player.name, role }) });
          const output = container.querySelector(`[data-access-code="${index}"]`);
          output.hidden = false;
          output.querySelector("code").textContent = result.token;
          output.querySelector("button").onclick = async () => { await navigator.clipboard.writeText(result.token); toast(state.locale === "pt" ? "Código copiado" : "Code copied"); };
        } catch (error) { toast(error.message, true); }
      };
      const suspend = container.querySelector(`[data-access-suspend="${index}"]`);
      if (suspend) suspend.onclick = async () => {
        if (!confirm(state.locale === "pt" ? `Suspender o acesso de ${player.name}?` : `Suspend ${player.name}'s access?`)) return;
        try { await api(`/api/auth/access/${encodeURIComponent(player.name)}/suspend`, { method: "PUT" }); toast(state.locale === "pt" ? "Acesso suspenso" : "Access suspended"); renderPlayersPanel(); }
        catch (error) { toast(error.message, true); }
      };
      container.querySelector(`[data-player-index="${index}"]`).onclick = async (event) => {
        const button = event.currentTarget;
        const history = $(`#player-history-${index}`);
        if (!history.hidden) { history.hidden = true; button.textContent = t("viewHistory"); return; }
        try {
          const result = await api(`/api/players/profile/${encodeURIComponent(player.id)}`);
          const profile = result?.profile || result;
          if (!profile || !Array.isArray(profile.history)) throw new Error(t("historyUnavailable"));
          history.innerHTML = profileMarkup(profile);
          history.insertAdjacentHTML("afterbegin", telemetryMarkup(profile));
          history.hidden = false;
          button.textContent = t("hideHistory");
        } catch (error) { toast(error.message, true); }
      };
  });
}

function accessMarkup(player, index, account) {
  if (state.user?.role !== "owner") return "";
  const label = state.locale === "pt" ? "Acesso ao painel" : "Panel access";
  const invite = account?.status === "active" ? (state.locale === "pt" ? "Gerar código de recuperação" : "Generate recovery code") : (state.locale === "pt" ? "Gerar código de acesso" : "Generate access code");
  const status = account?.status && account.status !== "none" ? `${account.role} · ${account.status}` : (state.locale === "pt" ? "Sem acesso" : "No access");
  return `<section class="panel-access"><div><strong>${label}</strong><small>${escapeHtml(status)}</small></div><div class="panel-access-actions"><select data-access-role="${index}" aria-label="Role"><option value="viewer" ${account?.role === "viewer" ? "selected" : ""}>Viewer</option><option value="operator" ${account?.role === "operator" ? "selected" : ""}>Operator</option><option value="owner" ${account?.role === "owner" ? "selected" : ""}>Owner</option></select><button class="secondary" data-access-invite="${index}" type="button">${invite}</button>${account?.status === "active" ? `<button class="danger" data-access-suspend="${index}" type="button">${state.locale === "pt" ? "Suspender" : "Suspend"}</button>` : ""}</div><div class="access-code" data-access-code="${index}" hidden><code></code><button type="button">${state.locale === "pt" ? "Copiar" : "Copy"}</button><small>${state.locale === "pt" ? "Este código aparece apenas uma vez e expira em 15 minutos." : "This code is shown once and expires in 15 minutes."}</small></div></section>`;
}

function formatDate(timestamp) {
  if (!timestamp) return "—";
  return new Date(timestamp * 1000).toLocaleString(state.locale === "en" ? "en-US" : "pt-BR", { dateStyle: "short", timeStyle: "short" });
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
  return `<ol>${events.map((event) => { const payload = event?.payload || {}; return `<li><div><b>${escapeHtml((labels[event?.topic] || {})[state.locale] || event?.topic || "event")}</b><time>${formatDate(event?.timestamp)}</time></div>${payload.cause ? `<small>${escapeHtml(payload.cause)}</small>` : ""}${payload.inferred ? `<small>${state.locale === "pt" ? "Encerramento inferido pelo estado do servidor" : "Inferred from server state"}</small>` : ""}</li>`; }).join("")}</ol>`;
}

function profileMarkup(profile) {
  const aliases = (profile.aliases || []).filter((name) => name !== profile.name);
  const sessions = Array.isArray(profile.sessions) ? profile.sessions : [];
  return `<div class="profile-facts"><span><small>${t("permission")}</small><b>${escapeHtml(optionLabel(profile.permission || "member"))}</b></span><span><small>${t("lastDeath")}</small><b>${formatDate(profile.last_death_at)}</b></span><span><small>${t("aliases")}</small><b>${aliases.length ? aliases.map(escapeHtml).join(" · ") : "—"}</b></span></div>${deathHistoryMarkup(profile.history || [])}<section class="session-history"><h4>${t("recentSessions")}</h4>${sessions.length ? `<ol>${sessions.map((session) => `<li><div><b>${formatDate(session.connected_at)}</b><time>${session.active ? t("activeSession") : formatDuration(session.duration_seconds)}</time></div><small>${session.active ? t("connectedSince") : session.inferred ? t("inferredExit") : t("normalExit")}${session.close_reason ? ` · ${escapeHtml(session.close_reason)}` : ""}</small></li>`).join("")}</ol>` : `<p>${t("noHistory")}</p>`}</section><section class="event-history"><h4>${state.locale === "pt" ? "Linha do tempo" : "Timeline"}</h4>${historyMarkup(profile.history || [])}</section>`;
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
  const icons = { home: "⌂", world: "◆", players: "♟", rules: "☷", server: "⚙" };
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

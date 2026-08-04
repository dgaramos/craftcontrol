const state = {
  schema: null, config: {}, gamerules: {}, players: [], online: 0, maxPlayers: 0,
  changes: {}, tab: "Geral", tabs: [], status: null, updatedAt: 0,
  locale: localStorage.getItem("manager-locale") === "en" ? "en" : "pt",
};
const $ = (selector) => document.querySelector(selector);
const content = $("#content");

const messages = {
  pt: {
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
  },
  en: {
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
  return state.locale === "en" ? (groups[group] || group) : group;
}

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

async function api(url, options = {}) {
  const response = await fetch(url, { headers: { "Content-Type": "application/json" }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request failed");
  return data;
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
  $("#save-label").textContent = count ? t("saveCount", count) : t("saveChanges");
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
  if (state.tab === "__time__") {
    renderTimePanel();
    return;
  }
  const persistent = Object.entries(state.schema.settings).filter(([, definition]) => definition.group === state.tab);
  const live = Object.entries(state.schema.gamerules).filter(([, definition]) => definition.group === state.tab);
  content.innerHTML = `<div class="group"><div class="group-title">${escapeHtml(groupLabel(state.tab))}</div><div class="card">${persistent.map(([key, definition]) => inputFor(key, definition, Object.hasOwn(state.changes, key) ? state.changes[key] : state.config[key])).join("")}${live.map(([key, definition]) => inputFor(key, definition, state.gamerules[key], true)).join("")}</div></div>`;
  bindSegmentedControls();
  persistent.forEach(([key, definition]) => {
    const element = $(`#field-${key}`);
    element.addEventListener("change", () => {
      if (definition.type === "boolean") updateToggleLabel(element);
      state.changes[key] = definition.type === "boolean" ? element.checked : element.value;
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
  $("#tabs").innerHTML = state.tabs.map((tab) => `<button class="${tab === state.tab ? "active" : ""}" data-tab="${escapeHtml(tab)}">${escapeHtml(groupLabel(tab))}</button>`).join("");
  $("#tabs").querySelectorAll("button").forEach((button) => button.onclick = () => {
    state.tab = button.dataset.tab;
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
}

async function loadState() {
  const snapshot = await api("/api/state");
  state.config = snapshot.settings || {};
  state.gamerules = snapshot.gamerules || {};
  showPlayers(snapshot);
  render();
}

async function boot() {
  const [schema, snapshot, status] = await Promise.all([api("/api/schema"), api("/api/state"), api("/api/status")]);
  state.schema = schema;
  state.config = snapshot.settings || {};
  state.gamerules = snapshot.gamerules || {};
  const regularTabs = [...new Set([...Object.values(schema.settings), ...Object.values(schema.gamerules)].map((item) => item.group))];
  const worldIndex = regularTabs.indexOf("Mundo") + 1;
  regularTabs.splice(worldIndex, 0, "__time__");
  state.tabs = regularTabs;
  showPlayers(snapshot);
  setStatus(status);
  applyLocale();
}

$("#language").onclick = () => {
  state.locale = state.locale === "pt" ? "en" : "pt";
  localStorage.setItem("manager-locale", state.locale);
  applyLocale();
};

$("#time-controls").onclick = () => {
  state.tab = "__time__";
  renderTabs();
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
};

$("#refresh").onclick = async () => {
  try {
    $("#refresh").classList.add("spinning");
    await api("/api/refresh", { method: "POST" });
    toast(t("querying"));
    setTimeout(async () => { await loadState(); $("#refresh").classList.remove("spinning"); toast(t("stateUpdated")); }, 1800);
  } catch (error) { $("#refresh").classList.remove("spinning"); toast(error.message, true); }
};

$("#save").onclick = async () => {
  if (!Object.keys(state.changes).length) return toast(t("noChanges"));
  try {
    await api("/api/config", { method: "PUT", body: JSON.stringify(state.changes) });
    toast(t("saved"));
    await api("/api/server/apply", { method: "POST" });
    Object.assign(state.config, state.changes);
    state.changes = {};
    updateSaveLabel();
    toast(t("serverUpdated"));
  } catch (error) { toast(error.message, true); }
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

boot().catch((error) => toast(error.message, true));

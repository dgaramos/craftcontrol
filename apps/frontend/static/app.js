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
import { createI18n } from "./js/i18n/index.js?v=1";
import { createGameTerms } from "./js/i18n/game-terms.js?v=1";

const content = $("#content");

if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
window.addEventListener("pageshow", () => requestAnimationFrame(() => window.scrollTo(0, 0)));

const { t, localeTag, localized, groupLabel, optionLabel } = createI18n(() => state.locale);
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

const { blockTermMarkup, blockIcon, gameTermMarkup, gameIcon, gameLabel, uiIcon } = createGameTerms({ getLocale: () => state.locale, escapeHtml });
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

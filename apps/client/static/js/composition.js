import { api } from "./api.js?v=7";
import { connectEventStream } from "./events.js";
import { requireSession } from "./auth.js?v=8";
import { state } from "./core/state.js?v=7";
import { $, escapeHtml } from "./core/dom.js?v=7";
import { connectInvalidation } from "./core/invalidation.js?v=7";
import { createNavigation } from "./core/navigation.js?v=8";
import { toast } from "./components/feedback.js?v=7";
import { formatDate as formatLocalizedDate, formatDuration, sessionMoment as localizedSessionMoment, timelineTimestamp as localizedTimelineTimestamp } from "./components/time.js?v=9";
import { createAnalyticsFeature } from "./features/analytics/index.js?v=8";
import { createPlayersFeature } from "./features/players/index.js?v=7";
import { createWorldFeature } from "./features/world/index.js?v=7";
import { createRulesFeature } from "./features/rules/index.js?v=7";
import { createServerFeature } from "./features/server/index.js?v=13";
import { startAuthenticatedApplication } from "./features/auth/bootstrap.js?v=7";
import { createSettingsFeature } from "./features/settings/index.js?v=7";
import { createI18n } from "./i18n/index.js?v=8";
import { createGameTerms } from "./i18n/game-terms.js?v=7";

export function startApplication() {
  const content = $("#content");

  if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
  window.addEventListener("pageshow", () => requestAnimationFrame(() => window.scrollTo(0, 0)));

  const { t, localeTag, localized, groupLabel, optionLabel } = createI18n(() => state.locale);
  let settingsFeature = null;
  function getSettingsFeature() {
    if (!settingsFeature) settingsFeature = createSettingsFeature({ state, content, t, api, $, escapeHtml, toast, uiIcon, optionLabel, localeTag, groupLabel, refreshActivePanel });
    return settingsFeature;
  }

  let navigation = null;
  function getNavigation() {
    if (!navigation) navigation = createNavigation({ state, $, t, uiIcon });
    return navigation;
  }

  function playerSettingsMarkup(...args) { return getSettingsFeature().playerSettingsMarkup(...args); }

  function refreshActivePanel() {
    if (!state.schema) return;
    $("#hero").hidden = state.tab !== "home";
    if (state.tab === "__time__") return getWorldFeature().renderTimePanel();
    if (state.tab === "__players__") return renderPlayersPanel();
    if (state.tab === "analytics") return renderAnalyticsPanel();
    if (state.tab === "home") { content.innerHTML = ""; return; }
    if (state.tab === "world") getWorldFeature().renderWorld();
    else if (state.tab === "rules") getRulesFeature().renderRules();
    else if (state.tab === "server") { getServerFeature().renderServer(); getServerFeature().loadDiagnostics(); }
  }

  let worldFeature = null;
  let rulesFeature = null;
  let serverFeature = null;

  function getWorldFeature() {
    if (!worldFeature) worldFeature = createWorldFeature({ state, content, t, api, $, uiIcon, toast, getSettingsFeature, getNavigation });
    return worldFeature;
  }

  function getRulesFeature() {
    if (!rulesFeature) rulesFeature = createRulesFeature({ getSettingsFeature });
    return rulesFeature;
  }

  function getServerFeature() {
    if (!serverFeature) serverFeature = createServerFeature({ state, content, t, api, $, escapeHtml, uiIcon, formatDate, toast, getSettingsFeature });
    return serverFeature;
  }

  function formatDate(timestamp) {
    return formatLocalizedDate(timestamp, localeTag());
  }

  function timelineTimestamp(timestamp) {
    return localizedTimelineTimestamp(timestamp, localeTag());
  }

  function sessionMoment(timestamp) {
    return localizedSessionMoment(timestamp, localeTag());
  }

  let playersFeature = null;
  function getPlayersFeature() {
    if (!playersFeature) {
      playersFeature = createPlayersFeature({
        state, content, t, localized, api, $, escapeHtml, toast, playerSettingsMarkup,
        formatDuration, formatDate, sessionMoment,
        timelineTimestamp, gameLabel, gameIcon, gameTermMarkup, optionLabel,
        blockTermMarkup, dimensionName, formatRankingValue, uiIcon,
        getSettingsFeature, getNavigation, renderAnalyticsPanel,
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

  const { blockTermMarkup, blockIcon, dimensionName, gameTermMarkup, gameIcon, gameLabel, uiIcon } = createGameTerms({ getLocale: () => state.locale, escapeHtml });
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

  function setStatus(status) {
    state.status = status;
    const element = $("#status");
    element.textContent = status.online ? t("online") : t("stopped");
    element.classList.toggle("online", status.online);
    const titleKey = state.operationActive && !status.online ? "serverRestarting" : (status.online ? "serverOnline" : "serverStopped");
    $("#server-state-title").textContent = t(titleKey);
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
    $("#language use").setAttribute("href", `/static/craftcontrol-ui.svg?v=7#ui-flag-${languageFlags[state.locale]}`);
    $("#language").setAttribute("aria-label", t("language"));
    $("#close-operation-drawer").setAttribute("aria-label", t("close"));
    document.querySelectorAll("[data-locale]").forEach((option) => option.setAttribute("aria-selected", String(option.dataset.locale === state.locale)));
    getNavigation().renderTabs();
    refreshActivePanel();
    getSettingsFeature().updateSaveLabel();
    if (state.status) setStatus(state.status);
    showPlayers({ players: state.players, online: state.online, max_players: state.maxPlayers, updated_at: state.updatedAt });
    updateBrand();
  }

  async function loadState() {
    const snapshot = await api("/api/state");
    state.batch(() => {
      state.config = snapshot.settings || {};
      state.gamerules = snapshot.gamerules || {};
      state.domains = snapshot.domains || {};
      showPlayers(snapshot);
    });
  }

  async function boot() {
    const [schema, snapshot, status, releases] = await Promise.all([api("/api/schema"), api("/api/state"), api("/api/status"), api("/api/telemetry-pack").catch(() => ({})), getServerFeature().loadFrontendVersion(), getServerFeature().initializeOperationProgress()]);
    state.batch(() => {
      state.schema = schema;
      state.config = snapshot.settings || {};
      state.gamerules = snapshot.gamerules || {};
      state.domains = snapshot.domains || {};
      showPlayers(snapshot);
    });
    setStatus(status);
    getServerFeature().renderReleaseTags(releases);
    applyLocale();
    connectEvents();
  }

  function connectEvents() {
    connectInvalidation({ connectEventStream, loadState, refreshStatus: () => api("/api/status"), setStatus });
  }

  state.subscribe("tab", () => {
    getNavigation().renderTabs();
    refreshActivePanel();
  });
  state.subscribe("operationActive", () => {
    if (state.status) setStatus(state.status);
    getSettingsFeature().updateSaveLabel();
    if (state.operationActive) $("#changes-drawer").close();
    if (["world", "rules", "server", "__players__"].includes(state.tab)) refreshActivePanel();
  });
  state.subscribe("locale", applyLocale);
  state.subscribe("config", () => {
    updateBrand();
    if (["world", "rules", "server", "__time__"].includes(state.tab)) refreshActivePanel();
  });
  state.subscribe("gamerules", () => {
    if (["world", "rules", "server", "__time__"].includes(state.tab)) refreshActivePanel();
  });
  state.subscribe("schema", refreshActivePanel);

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
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#language-picker")) { $("#language-menu").hidden = true; $("#language").setAttribute("aria-expanded", "false"); }
  });

  $("#time-controls").onclick = () => getWorldFeature().openTimeControls();

  $("#open-players").onclick = () => getNavigation().openPlayers();

  $("#refresh").onclick = async () => {
    try {
      $("#refresh").classList.add("spinning");
      await api("/api/refresh", { method: "POST" });
      toast(t("querying"));
      setTimeout(async () => { await loadState(); $("#refresh").classList.remove("spinning"); toast(t("stateUpdated")); }, 1800);
    } catch (error) { $("#refresh").classList.remove("spinning"); toast(error.message, true); }
  };

  $("#save").onclick = () => {
    getSettingsFeature().renderChangesDrawer();
    $("#changes-drawer").showModal();
  };

  $("#close-changes").onclick = () => $("#changes-drawer").close();
  $("#operation-indicator").onclick = () => getServerFeature().openOperationDrawer();
  $("#close-operation-drawer").onclick = () => $("#operation-drawer").close();
  $("#discard-all").onclick = () => {
    state.changes = {};
    $("#changes-drawer").close();
    refreshActivePanel();
    getSettingsFeature().updateSaveLabel();
  };

  $("#apply-changes").onclick = async () => {
    if (state.operationActive) {
      toast(t("operationLocked"), true);
      $("#changes-drawer").close();
      return;
    }
    if (!Object.keys(state.changes).length) return;
    try {
      $("#apply-changes").disabled = true;
      await api("/api/config", { method: "PUT", body: JSON.stringify(state.changes) });
      toast(t("saved"));
      state.changes = {};
      $("#changes-drawer").close();
      getSettingsFeature().updateSaveLabel();
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
}

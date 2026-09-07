import { api } from "./api.js?v=7";
import { connectEventStream } from "./events.js";
import { requireSession, showSessions, showPasswordChange } from "./auth.js?v=8";
import { state } from "./core/state.js?v=7";
import { createNavTrail } from "./core/route.js?v=8";
import { indicatorState, worldPresentation } from "./core/panel-state.js?v=1";
import { $, escapeHtml } from "./core/dom.js?v=7";
import { connectInvalidation } from "./core/invalidation.js?v=7";
import { createNavigation } from "./core/navigation.js?v=9";
import { toast } from "./components/feedback.js?v=7";
import { formatDate as formatLocalizedDate, formatDuration, sessionMoment as localizedSessionMoment, timelineTimestamp as localizedTimelineTimestamp } from "./components/time.js?v=9";
import { createAnalyticsFeature } from "./features/analytics/index.js?v=9";
import { createPlayersFeature } from "./features/players/index.js?v=9";
import { createWorldFeature } from "./features/world/index.js?v=12";
import { createRulesFeature } from "./features/rules/index.js?v=7";
import { createServerFeature } from "./features/server/index.js?v=20";
import { UNRESPONSIVE_AFTER_MS } from "./features/server/operation.js?v=15";
import { startAuthenticatedApplication } from "./features/auth/bootstrap.js?v=7";
import { createSettingsFeature } from "./features/settings/index.js?v=9";
import { createAuditFeature } from "./features/audit/index.js?v=2";
import { createExportsFeature } from "./features/exports/index.js?v=1";
import { downloadFile } from "./core/download.js?v=1";
import { createHomeFeature } from "./features/home/index.js?v=7";
import { createI18n } from "./i18n/index.js?v=15";
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

  /* Inner screens are reachable from more than one place — Rules from Home and
     from the Server hub, Time from Home and from World — so a hard-coded
     destination sends you somewhere you were not. Keep the trail instead.
     Landing on a root tab clears it: the bottom nav is a fresh start. */
  const BACK_LABELS = { home: "navHome", __players__: "navPlayers", server: "navServer", world: "world", rules: "rules", analytics: "analytics", audit: "audit", exports: "exportTitle", __server_settings__: "settings", __time__: "timeControls" };
  const navTrail = createNavTrail();

  state.subscribe("tab", (value, previous) => navTrail.record(value, previous));

  function goBack() {
    state.tab = navTrail.back();
  }

  /* The affordance lives in the shell, not inside #content: analytics and audit
     render asynchronously and would overwrite anything prepended to the panel. */
  function showBackButton(visible) {
    const button = $("#panel-back");
    if (!button) return;
    button.hidden = !visible;
    if (!visible) return;
    const label = $("#panel-back-label");
    if (label) label.textContent = t(BACK_LABELS[navTrail.peek()] || "navHome");
  }

  const ROOT_TABS = new Set(["home", "__players__", "server"]);

  function refreshActivePanel() {
    $("#hero").hidden = state.tab !== "home";
    showBackButton(!ROOT_TABS.has(state.tab));
    // Home remains useful while the backend is reconnecting: its time shortcut,
    // game-mode review and navigation do not depend on the schema response.
    if (state.tab === "home") return getHomeFeature().render();
    if (!state.schema) {
      content.innerHTML = `<section class="panel-pending block-panel" role="status">${t("querying")}</section>`;
      return;
    }
    if (state.tab === "__time__") return getWorldFeature().renderTimePanel();
    if (state.tab === "__server_settings__") return getServerFeature().renderServerSettings();
    if (state.tab === "__players__") return renderPlayersPanel();
    if (state.tab === "analytics") return renderAnalyticsPanel();
    if (state.tab === "audit") return getAuditFeature().renderAuditPanel();
    if (state.tab === "exports") return getExportsFeature().renderExportsPanel();
    if (state.tab === "world") getWorldFeature().renderWorld();
    else if (state.tab === "rules") getRulesFeature().renderRules();
    else if (state.tab === "server") getServerFeature().renderServer();
  }

  let worldFeature = null;
  let rulesFeature = null;
  let serverFeature = null;
  let auditFeature = null;
  let exportsFeature = null;
  let homeFeature = null;

  function getHomeFeature() {
    if (!homeFeature) homeFeature = createHomeFeature({ state, content, t, uiIcon, getSettingsFeature, openTimeControls: () => getWorldFeature().openTimeControls() });
    return homeFeature;
  }

  function getWorldFeature() {
    if (!worldFeature) worldFeature = createWorldFeature({ state, content, t, api, $, uiIcon, toast, getSettingsFeature, getNavigation, refreshWorldCells });
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

  function getAuditFeature() {
    if (!auditFeature) auditFeature = createAuditFeature({ state, content, t, api, $, escapeHtml, toast, formatDate, uiIcon });
    return auditFeature;
  }

  function getExportsFeature() {
    if (!exportsFeature) exportsFeature = createExportsFeature({
      state, content, t, $, escapeHtml, toast, download: (url) => downloadFile(url),
    });
    return exportsFeature;
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

  // Navigation must stay available while boot waits for the backend (or when it
  // is unavailable). Its previous lazy initialization only happened after the
  // initial API requests completed, leaving the bottom nav without handlers.
  getNavigation();

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
    const summary = $("#players-summary");
    summary.textContent = `${state.online} `;
    const max = document.createElement("span");
    max.className = "players-max";
    max.textContent = `/ ${state.maxPlayers || "?"}`;
    summary.append(max);
    $("#players-list").textContent = state.players.length ? state.players.join(" · ") : t("nobody");
    $("#updated-at").textContent = state.updatedAt ? `${t("updated")} ${new Date(state.updatedAt * 1000).toLocaleTimeString(localeTag())}` : t("awaiting");
  }

  let _tickTimer = null;
  let _localDaytime = NaN;

  function setWorldCells(field, text) {
    if (typeof document === "undefined") return;
    document.querySelectorAll(`[data-world="${field}"]`).forEach((node) => { node.textContent = text; });
  }

  function setWorldIcons(field, symbol) {
    if (typeof document === "undefined") return;
    document.querySelectorAll(`[data-world-icon="${field}"]`).forEach((node) => setIcon(node, symbol));
  }

  function _updateTickDisplay() {
    _localDaytime = (_localDaytime + 2) % 24000;
    setWorldCells("ticks", Math.round(_localDaytime).toLocaleString(localeTag()));
    {
      const minutes = Math.round(((_localDaytime + 6000) % 24000) / 1000 * 60);
      const hour = Math.floor(minutes / 60) % 24;
      const minute = minutes % 60;
      setWorldCells("time", new Intl.DateTimeFormat(localeTag(), { hour: "numeric", minute: "2-digit" }).format(new Date(2000, 0, 1, hour, minute)));
    }
    setWorldIcons("time", worldPresentation({ daytime: _localDaytime }).timeIcon);
    _applyWeatherAccent();
  }

  function setIcon(useEl, symbol) {
    if (!useEl) return;
    const href = `/static/craftcontrol-ui.svg#${symbol}`;
    if (useEl.getAttribute("href") !== href) useEl.setAttribute("href", href);
  }

  function _applyWeatherAccent() {
    const cells = document.querySelectorAll('[data-world-cell="weather"]');
    if (!cells.length) return;
    const { weatherKey } = worldPresentation({ weather: state.world?.weather, daytime: _localDaytime });
    cells.forEach((cell) => { if (cell.dataset.weather !== weatherKey) cell.dataset.weather = weatherKey; });
  }

  /* Re-applies the current world values to every marked cell. A screen that
     renders its own copy calls this once after mounting; the live clock keeps
     it updated from then on. */
  function refreshWorldCells() {
    setWorldCells("day", state.world?.day ?? "—");
    const weather = state.world?.weather;
    setWorldCells("weather", weather ? t(weather) : "—");
    if (Number.isFinite(_localDaytime)) {
      _updateTickDisplay();
    } else {
      setWorldCells("time", "—");
      setWorldCells("ticks", "");
    }
    setWorldIcons("weather", worldPresentation({ weather, daytime: _localDaytime }).weatherIcon);
    _applyWeatherAccent();
  }

  function showWorld(snapshot) {
    state.world = snapshot.world || {};
    setWorldCells("day", state.world.day ?? "—");
    const daytime = Number(state.world.daytime);
    if (_tickTimer) { clearInterval(_tickTimer); _tickTimer = null; }
    if (Number.isFinite(daytime)) {
      _localDaytime = daytime;
      _updateTickDisplay();
      _tickTimer = setInterval(_updateTickDisplay, 100);
    } else {
      _localDaytime = NaN;
      setWorldCells("time", "—");
      setWorldCells("ticks", "");
    }
    const weather = state.world.weather;
    setWorldCells("weather", weather ? t(weather) : "—");
    setWorldIcons("weather", worldPresentation({ weather, daytime: _localDaytime }).weatherIcon);
    _applyWeatherAccent();
  }

  function updateBrand() {
    const name = state.config.SERVER_NAME || "Minecraft Bedrock";
    $("#instance-name").textContent = name;
    $("#hero-instance-name").textContent = name;
    document.title = `CraftControl · ${name}`;
  }

  function applyLocale() {
    document.documentElement.lang = localeTag();
    document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.dataset.i18n); });
    document.querySelectorAll("[data-i18n-aria]").forEach((element) => { element.setAttribute("aria-label", t(element.dataset.i18nAria)); });
    const languageNames = { pt: "Português", en: "English", es: "Español" };
    const languageFlags = { pt: "br", en: "us", es: "es" };
    const langSpan = $("#language span"); if (langSpan) langSpan.textContent = languageNames[state.locale];
    const langUse = $("#language use"); if (langUse) langUse.setAttribute("href", `/static/craftcontrol-ui.svg?v=8#ui-flag-${languageFlags[state.locale]}`);
    const langBtn = $("#language"); if (langBtn) langBtn.setAttribute("aria-label", t("language"));
    $("#close-operation-drawer").setAttribute("aria-label", t("close"));
    document.querySelectorAll("[data-locale]").forEach((option) => option.setAttribute("aria-selected", String(option.dataset.locale === state.locale)));
    getNavigation().renderTabs();
    refreshActivePanel();
    getSettingsFeature().updateSaveLabel();
    if (state.status) setStatus(state.status);
    showPlayers({ players: state.players, online: state.online, max_players: state.maxPlayers, updated_at: state.updatedAt });
    showWorld({ world: state.world });
    updateBrand();
    refreshIndicatorBars();
  }

  /* SSE covers changes the server announces, but the world clock and weather
     drift on their own with no event to carry them. A slow poll keeps the Home
     cells honest, and only while Home is on screen — every other tab cancels
     it, so a backgrounded screen costs nothing. */
  const HOME_POLL_MS = 45000;
  let _homePollTimer = null;

  function startHomePolling() {
    stopHomePolling();
    if (state.tab !== "home") return;
    _homePollTimer = setInterval(() => { loadState().catch(() => {}); }, HOME_POLL_MS);
  }

  function stopHomePolling() {
    if (_homePollTimer) { clearInterval(_homePollTimer); _homePollTimer = null; }
  }

  state.subscribe("tab", startHomePolling);

  async function loadState() {
    const snapshot = await api("/api/state");
    state.batch(() => {
      state.config = snapshot.settings || {};
      state.gamerules = snapshot.gamerules || {};
      showWorld(snapshot);
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
      showWorld(snapshot);
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
    startHomePolling();
  }

  state.subscribe("tab", () => {
    getNavigation().renderBottomNav();
    refreshActivePanel();
  });
  state.subscribe("operationStalled", refreshIndicatorBars);
  state.subscribe("operationState", refreshIndicatorBars);
  state.subscribe("operationActive", () => {
    if (state.status) setStatus(state.status);
    getSettingsFeature().updateSaveLabel();
    if (state.operationActive) $("#changes-drawer").close();
    if (["world", "rules", "server", "__players__"].includes(state.tab)) refreshActivePanel();
    refreshIndicatorBars();
  });
  state.subscribe("locale", applyLocale);
  state.subscribe("config", () => {
    updateBrand();
    if (["home", "world", "rules", "server", "__time__"].includes(state.tab)) refreshActivePanel();
  });
  state.subscribe("gamerules", () => {
    if (["home", "world", "rules", "server", "__time__"].includes(state.tab)) refreshActivePanel();
  });
  state.subscribe("schema", refreshActivePanel);
  /* Exactly one bar is ever shown. An operation — running, or gone silent and
     needing a decision — outranks pending changes, because it is the thing
     standing between the operator and applying them. */
  function refreshIndicatorBars() {
    const changesCount = Object.keys(state.changes).length;
    const { showOperation, showChanges, stalled: opStalled } = indicatorState({
      changesCount,
      operationActive: state.operationActive,
      operationStalled: state.operationStalled,
    });

    const opBar = $("#operation-bar");
    if (opBar) {
      opBar.hidden = !showOperation;
      opBar.classList.toggle("indicator-bar--stalled", opStalled);
    }
    const opIcon = $("#operation-bar-icon");
    if (opIcon) opIcon.classList.toggle("indicator-bar-live", !opStalled);
    const opIconUse = $("#operation-bar-icon-use");
    if (opIconUse) opIconUse.setAttribute("href", `/static/craftcontrol-ui.svg#${opStalled ? "ui-warning" : "ui-live"}`);
    const opTitle = $("#operation-bar-title");
    if (opTitle && showOperation) opTitle.textContent = opStalled ? t("indicatorOperationStalled") : t("indicatorOperationTitle");
    const opLabel = $("#operation-bar-label");
    if (opLabel && showOperation) {
      opLabel.textContent = opStalled
        ? t("indicatorOperationStalledHint", UNRESPONSIVE_AFTER_MS / 60000)
        : (t(`opState_${state.operationState}`) || state.operationState || "");
    }

    const changesBar = $("#changes-bar");
    if (changesBar) changesBar.hidden = !showChanges;
    const changesLabel = $("#changes-bar-label");
    if (changesLabel && changesCount > 0) changesLabel.textContent = t("indicatorChangesTitle", changesCount);
  }
  state.subscribe("changes", () => { getSettingsFeature().updateSaveLabel(); refreshIndicatorBars(); });

  const languageBtn = $("#language");
  if (languageBtn) {
    languageBtn.onclick = () => {
      const menu = $("#language-menu");
      if (!menu) return;
      menu.hidden = !menu.hidden;
      languageBtn.setAttribute("aria-expanded", String(!menu.hidden));
    };
    document.addEventListener("click", (event) => {
      if (!event.target.closest("#language-picker")) { const menu = $("#language-menu"); if (menu) { menu.hidden = true; languageBtn.setAttribute("aria-expanded", "false"); } }
    });
  }
  document.querySelectorAll("[data-locale]").forEach((option) => option.onclick = () => {
    state.locale = ["pt", "en", "es"].includes(option.dataset.locale) ? option.dataset.locale : "pt";
    localStorage.setItem("craftcontrol-locale", state.locale);
  });

  function openProfileSheet() {
    const sheet = $("#profile-sheet");
    if (!sheet) return;
    const user = state.user;
    if (user) {
      const initial = (user.name || "").charAt(0).toUpperCase();
      const profileInitial = $("#profile-initial");
      if (profileInitial) profileInitial.textContent = initial;
      const sheetInitial = $("#profile-sheet-initial");
      if (sheetInitial) sheetInitial.textContent = initial;
      const sheetName = $("#profile-sheet-name");
      if (sheetName) sheetName.textContent = user.name || "";
      const sheetRole = $("#profile-sheet-role");
      if (sheetRole) {
        const role = user.role || "";
        const roleCap = role ? role.charAt(0).toUpperCase() + role.slice(1) : "";
        const serverName = state.config?.SERVER_NAME;
        sheetRole.textContent = serverName ? `${roleCap} · ${serverName}` : roleCap;
      }
    }
    sheet.hidden = false;
  }

  function closeProfileSheet() {
    const sheet = $("#profile-sheet");
    if (sheet) sheet.hidden = true;
  }

  $("#profile-btn").onclick = openProfileSheet;
  $("#profile-sheet").querySelector(".bottom-sheet-backdrop").onclick = closeProfileSheet;

  $("#sign-out-btn").onclick = async () => {
    try { await api("/api/auth/logout", { method: "POST" }); window.location.reload(); }
    catch { toast(t("requestFailed") || "Sign out failed", true); }
  };
  $("#manage-sessions-btn").onclick = () => { closeProfileSheet(); showSessions(); };
  $("#change-password-btn").onclick = () => { closeProfileSheet(); showPasswordChange(); };


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
  $("#changes-bar")?.addEventListener("click", () => {
    getSettingsFeature().renderChangesDrawer();
    $("#changes-drawer").showModal();
  });
  $("#operation-bar")?.addEventListener("click", () => getServerFeature().openOperationDrawer());
  $("#panel-back").onclick = goBack;
  $("#close-operation-drawer").onclick = () => $("#operation-drawer").close();
  const dismissOperation = $("#dismiss-operation");
  if (dismissOperation) dismissOperation.onclick = () => $("#operation-drawer").close();
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

  // Inject the audit tab for owners only, once user identity is known.
  state.subscribe("user", (user) => {
    if (user?.role === "owner" && !state.tabs.includes("audit")) {
      state.tabs = [...state.tabs, "audit", "exports"];
    }
  });

  // Draw the mobile shell and its local actions before authentication and
  // backend boot complete. This keeps Home usable during an API reconnect.
  applyLocale();
  startAuthenticatedApplication({ requireSession, state, boot, toast });
}

import { createActivityView } from "./activity.js?v=5";
import { createRankingsPanel } from "./rankings.js?v=5";
import { createBlocksPanel } from "./blocks.js?v=5";
import { createCombatPanel } from "./combat.js?v=5";
import { createExplorationPanel } from "./exploration.js?v=5";
import { createTrendsPanel } from "./trends.js?v=5";

export function createAnalyticsFeature(deps) {
  const { state, content, t, uiIcon, api, $, escapeHtml, optionLabel, gameTermMarkup, timelineTimestamp, rankingDefinitions, formatRankingValue, formatDate, openAnalyticsPlayer, blockTermMarkup, blockIcon, oreLabel, formatDuration, dimensionName, localeTag, requestRender } = deps;
  const analyticsViewSwitch = (active) => {
    const views = [["all", "activity", "activityView"], ["deaths", "deaths", "deathsView"], ["rankings", "rankings", "rankingsView"], ["blocks", "blocks", "blocksView"], ["combat", "combat", "combatView"], ["exploration", "exploration", "explorationView"], ["trends", "periods", "trendsView"]];
    return `<div class="analytics-view-switch">${views.map(([view, icon, label]) => `<button data-analytics-view="${view}" class="${view} ${(view === "all" ? !["deaths", "rankings", "blocks", "combat", "exploration", "trends"].includes(active) : active === view) ? "active" : ""}" type="button">${uiIcon(icon)} ${t(label)}</button>`).join("")}</div>`;
  };
  const bindAnalyticsViewSwitch = () => {
    content.querySelectorAll("[data-analytics-view]").forEach((button) => button.onclick = () => {
      state.analytics.kind = button.dataset.analyticsView;
      state.analytics.page = 1;
      requestRender();
    });
  };
  const shared = { ...deps, analyticsViewSwitch, bindAnalyticsViewSwitch };
  const activityView = createActivityView({ state, t, optionLabel, uiIcon, gameTermMarkup, timelineTimestamp });
  const renderRankingsPanel = createRankingsPanel({ ...shared, rankingDefinitions });
  const renderBlocksPanel = createBlocksPanel(shared);
  const renderCombatPanel = createCombatPanel(shared);
  const renderExplorationPanel = createExplorationPanel(shared);
  const renderTrendsPanel = createTrendsPanel(shared);

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
  if (filters.kind === "exploration") {
    await renderExplorationPanel();
    return;
  }
  if (filters.kind === "trends") {
    await renderTrendsPanel();
    return;
  }
  content.innerHTML = `<div class="analytics-screen">${analyticsViewSwitch(filters.kind)}<header class="analytics-hero block-panel"><div><span class="eyebrow">CRAFTCONTROL ANALYTICS</span><h2>${t("analyticsTitle")}</h2><p>${t("analyticsHelp")}</p></div><button id="analytics-refresh" class="secondary" type="button">${uiIcon("refresh")} ${t("refreshData")}</button></header><section class="analytics-filters block-panel"><label><span>${t("eventFilter")}</span><select id="analytics-kind" ${filters.kind === "deaths" ? "disabled" : ""}><option value="all">${t("everyEvent")}</option><option value="joins">${t("joinsOnly")}</option><option value="leaves">${t("leavesOnly")}</option><option value="respawns">${t("respawnsOnly")}</option><option value="dimensions">${t("dimensionsOnly")}</option><option value="permissions">${t("permissionsOnly")}</option></select></label><label><span>${t("playerFilter")}</span><select id="analytics-player"><option value="">${t("everyPlayer")}</option></select></label><label><span>${t("periodFilter")}</span><select id="analytics-days"><option value="0">${t("lifetime")}</option><option value="7">${t("last7Days")}</option><option value="30">${t("last30Days")}</option></select></label><label><span>${t("sourceFilter")}</span><select id="analytics-source"><option value="all">${t("everySource")}</option><option value="structured">${t("structuredSource")}</option><option value="server">${t("serverSource")}</option></select></label><label><span>${t("detailFilter")}</span><input id="analytics-search" type="search" maxlength="64" value="${escapeHtml(filters.search)}" placeholder="${t("detailFilterHint")}"></label></section><div id="analytics-results" class="analytics-results"><div class="analytics-loading">${t("checking")}</div></div><dialog id="analytics-death-dialog" class="analytics-death-dialog"><div class="drawer-header"><div><span class="eyebrow">${t("deathDetails")}</span><h2></h2></div><button class="drawer-close" type="button" aria-label="${t("close")}">${uiIcon("close")}</button></div><div class="analytics-death-content"></div></dialog></div>`;
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
      target.innerHTML = `<div class="analytics-summary"><span><small>${t("joinsOnly")}</small><b>${summary.joins || 0}</b></span><span><small>${t("leavesOnly")}</small><b>${summary.leaves || 0}</b></span><span><small>${t("respawnsOnly")}</small><b>${summary.respawns || 0}</b></span><span><small>${t("dimensionsOnly")}</small><b>${summary.dimensions || 0}</b></span><span class="death"><small>${t("deathsView")}</small><b>${summary.deaths || 0}</b></span><span><small>${t("permissionsOnly")}</small><b>${summary.permissions || 0}</b></span></div><div class="analytics-result-meta"><b>${t("eventCount", result.total)}</b><span>${t("pageCount", result.page, result.pages)}</span></div>${activityView.eventsMarkup(result.events || [])}<div class="analytics-pagination"><button id="analytics-previous" class="secondary" type="button" ${result.page <= 1 ? "disabled" : ""}>← ${t("previous")}</button><button id="analytics-next" class="secondary" type="button" ${result.page >= result.pages ? "disabled" : ""}>${t("next")} →</button></div>`;
      target.querySelectorAll("[data-analytics-player]").forEach((button) => button.onclick = () => openAnalyticsPlayer(button.dataset.analyticsPlayer));
      target.querySelectorAll("[data-death-detail]").forEach((button) => button.onclick = () => activityView.showDeathDetails((result.events || [])[Number(button.dataset.deathDetail)]));
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


  return { render: renderAnalyticsPanel };
}


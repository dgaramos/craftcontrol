import { renderMarkup } from "../../core/render.js";

export function createTrendsPanel({ state, content, t, uiIcon, api, $, escapeHtml, analyticsViewSwitch, bindAnalyticsViewSwitch, formatRankingValue, openAnalyticsPlayer, formatDate, formatDuration, localeTag }) {
const periodDefinitions = {
  play_seconds: { label: "playTime", format: "duration" },
  sessions: { label: "explorationSessions", format: "number" },
  blocks_broken: { label: "rankBlocksBroken", format: "number" },
  blocks_placed: { label: "rankBlocksPlaced", format: "number" },
  mob_kills: { label: "combatMobKills", format: "number" },
  player_kills: { label: "combatPlayerKills", format: "number" },
  deaths: { label: "combatDeaths", format: "number" },
  distance: { label: "distanceTraveled", format: "distance" },
};

function calendarDate(day) {
  return new Date(`${day}T12:00:00`).toLocaleDateString(localeTag(), { day: "2-digit", month: "short" });
}

function validHour(value) {
  const hour = Number(value);
  return Number.isInteger(hour) && hour >= 0 && hour <= 23 ? hour : null;
}

function sessionCount(value) {
  const sessions = Number(value);
  return Number.isFinite(sessions) && sessions >= 0 ? sessions : 0;
}

return async function renderTrendsPanel() {
  const analytics = state.analytics;
  // all API data paths use escapeHtml, formatRankingValue, or formatDuration.
  renderMarkup(content, `<div class="trends-screen">${analyticsViewSwitch("trends")}<header class="trends-hero block-panel"><div><span class="eyebrow">${t("dailyHistory")}</span><h2>${t("trendsTitle")}</h2><p>${t("trendsHelp")}</p></div><button id="trends-refresh" class="secondary" type="button">${uiIcon("refresh")} ${t("refreshData")}</button></header><div class="period-switch"><button data-period-days="7" class="${analytics.periodDays === 7 ? "active" : ""}" type="button">${t("sevenDays")}</button><button data-period-days="30" class="${analytics.periodDays === 30 ? "active" : ""}" type="button">${t("thirtyDays")}</button></div><div id="trends-content"><div class="analytics-loading">${t("checking")}</div></div></div>`);  bindAnalyticsViewSwitch();
  const load = async () => {
    const target = $("#trends-content");
    renderMarkup(target, `<div class="analytics-loading">${t("checking")}</div>`);    try {
      const result = await api(`/api/analytics/periods?days=${analytics.periodDays}&limit=10`);
      const definition = periodDefinitions[analytics.periodMetric] || periodDefinitions.play_seconds;
      const ranking = result.rankings?.[analytics.periodMetric] || [];
      const days = result.calendar || [];
      const maxDay = Math.max(1, ...days.map((day) => Number(day.play_seconds || 0)));
      const heatmap = (result.heatmap || []).filter((cell) => validHour(cell.hour) !== null);
      const maxHeat = Math.max(1, ...heatmap.map((cell) => Number(cell.seconds || 0)));
      const weekdays = t("weekdayShort");
      const totals = result.totals || {};
      renderMarkup(target, `<p class="trends-note">${t("collectionStarted")}<small>${escapeHtml(result.timezone || "")} · ${t("updated")} ${formatDate(result.generated_at)}</small></p><section class="trends-summary"><article><small>${t("playTime")}</small><b>${formatDuration(totals.play_seconds || 0)}</b></article><article><small>${t("explorationSessions")}</small><b>${formatRankingValue(totals.sessions, "number")}</b></article><article><small>${t("dailyBlocks")}</small><b>${formatRankingValue((totals.blocks_broken || 0) + (totals.blocks_placed || 0), "number")}</b></article><article><small>${t("dailyKills")}</small><b>${formatRankingValue((totals.mob_kills || 0) + (totals.player_kills || 0), "number")}</b></article><article><small>${t("mostActiveDay")}</small><b>${result.most_active_day ? calendarDate(result.most_active_day.day) : "—"}</b></article></section><div class="period-metric-picker">${Object.entries(periodDefinitions).map(([key, item]) => `<button data-period-metric="${key}" class="${analytics.periodMetric === key ? "active" : ""}" type="button">${t(item.label)}</button>`).join("")}</div><div class="trends-main-grid"><section class="period-ranking block-panel"><div class="ranking-section-title"><span class="eyebrow">${t("periodDaysLabel", analytics.periodDays)}</span><h3>${t("periodRanking")}: ${t(definition.label)}</h3></div>${ranking.length ? `<ol>${ranking.map((entry, index) => `<li><b>${index + 1}</b><button data-period-player="${escapeHtml(entry.player.id)}" type="button">${escapeHtml(entry.player.name)}</button><strong>${formatRankingValue(entry.value, definition.format)}</strong></li>`).join("")}</ol>` : `<div class="trends-zero"><span>${uiIcon("periods")}</span><p>${t("noPeriodData")}</p></div>`}</section><section class="activity-calendar block-panel"><div class="ranking-section-title"><span class="eyebrow">${t("periodDaysLabel", analytics.periodDays)}</span><h3>${t("activityCalendar")}</h3></div><div class="calendar-grid">${days.map((day) => { const level = Math.ceil((Number(day.play_seconds || 0) / maxDay) * 4); return `<article class="level-${level}" title="${escapeHtml(calendarDate(day.day))}"><span>${calendarDate(day.day)}</span><b>${day.play_seconds ? formatDuration(day.play_seconds) : "—"}</b><small>${sessionCount(day.sessions)} ${t("explorationSessions").toLocaleLowerCase()}</small></article>`; }).join("")}</div></section></div><section class="heatmap-panel block-panel"><div class="ranking-section-title"><span class="eyebrow">${escapeHtml(result.timezone || "")}</span><h3>${t("sessionHeatmap")}</h3></div><div class="heatmap-scroll"><div class="heatmap-grid"><span></span>${Array.from({ length: 24 }, (_, hour) => `<b>${String(hour).padStart(2, "0")}</b>`).join("")}${weekdays.map((weekday, weekdayIndex) => `<strong>${weekday}</strong>${heatmap.filter((cell) => cell.weekday === weekdayIndex).map((cell) => { const hour = validHour(cell.hour); const level = Math.ceil((Number(cell.seconds || 0) / maxHeat) * 4); return `<i class="level-${level}" title="${weekday} ${String(hour).padStart(2, "0")}:00 · ${formatDuration(cell.seconds)}"></i>`; }).join("")}`).join("")}</div></div><div class="heatmap-legend"><span>${t("lessActive")}</span><i class="level-0"></i><i class="level-1"></i><i class="level-2"></i><i class="level-3"></i><i class="level-4"></i><span>${t("moreActive")}</span></div></section>`);      target.querySelectorAll("[data-period-player]").forEach((button) => button.onclick = () => openAnalyticsPlayer(button.dataset.periodPlayer));
      target.querySelectorAll("[data-period-metric]").forEach((button) => button.onclick = () => { analytics.periodMetric = button.dataset.periodMetric; load(); });
    } catch (error) { renderMarkup(target, `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`); }
  };
  content.querySelectorAll("[data-period-days]").forEach((button) => button.onclick = () => {
    analytics.periodDays = Number(button.dataset.periodDays);
    content.querySelectorAll("[data-period-days]").forEach((item) => item.classList.toggle("active", item === button));
    load();
  });
  $("#trends-refresh").onclick = load;
  await load();
}

}

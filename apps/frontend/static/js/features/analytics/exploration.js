export function createExplorationPanel({ state, content, t, uiIcon, api, $, escapeHtml, analyticsViewSwitch, bindAnalyticsViewSwitch, formatRankingValue, openAnalyticsPlayer, formatDate, formatDuration, dimensionName, timelineTimestamp }) {
const explorationDefinitions = {
  distance: { label: "distanceTraveled", format: "distance" },
  dimension_count: { label: "dimensionsDiscovered", format: "number" },
  play_seconds: { label: "playTime", format: "duration" },
  sessions: { label: "explorationSessions", format: "number" },
  active_seconds: { label: "activeMovementTime", format: "duration" },
};

function explorationRanking(entries, definition) {
  return `<section class="exploration-ranking block-panel"><div class="ranking-section-title"><span class="eyebrow">LIFETIME</span><h3>${t("explorerRanking")}: ${t(definition.label)}</h3></div>${entries.length ? `<ol>${entries.map((entry, index) => `<li><b>${index + 1}</b><button data-exploration-player="${escapeHtml(entry.player.id)}" type="button">${escapeHtml(entry.player.name)}</button><strong>${formatRankingValue(entry.value, definition.format)}</strong></li>`).join("")}</ol>` : `<div class="exploration-zero"><span>${uiIcon("exploration")}</span><p>${t("noExplorationEvidence")}</p></div>`}</section>`;
}

return async function renderExplorationPanel() {
  const analytics = state.analytics;
  content.innerHTML = `<div class="exploration-screen">${analyticsViewSwitch("exploration")}<header class="exploration-hero block-panel"><div><span class="eyebrow">WORLD ATLAS</span><h2>${t("explorationTitle")}</h2><p>${t("explorationHelp")}</p></div><button id="exploration-refresh" class="secondary" type="button">${uiIcon("refresh")} ${t("refreshData")}</button></header><div id="exploration-content"><div class="analytics-loading">${t("checking")}</div></div></div>`;
  bindAnalyticsViewSwitch();
  const load = async () => {
    const target = $("#exploration-content");
    target.innerHTML = `<div class="analytics-loading">${t("checking")}</div>`;
    try {
      const result = await api("/api/analytics/exploration?limit=10");
      const totals = result.totals || {};
      const definition = explorationDefinitions[analytics.explorationMetric] || explorationDefinitions.distance;
      const ranking = result.rankings?.[analytics.explorationMetric] || [];
      const summary = [["distanceTraveled", totals.distance, "distance", "distance"], ["dimensionsDiscovered", totals.dimensions, "number", "exploration"], ["dimensionVisits", totals.dimension_visits, "number", "world"], ["activeMovementTime", totals.active_seconds, "duration", "activity"], ["playTime", totals.play_seconds, "duration", "periods"], ["explorationSessions", totals.sessions, "number", "sessions"]];
      target.innerHTML = `<section class="exploration-summary">${summary.map(([label, value, format, icon]) => `<article><small>${t(label)}</small><b>${formatRankingValue(value, format)}</b><span>${uiIcon(icon)}</span></article>`).join("")}</section><p class="exploration-note">${t("explorationEmptyHelp")} <span>${t("horizontalSampled")}</span><small>${t("updated")} ${formatDate(result.generated_at)}</small></p><div class="exploration-metric-picker">${Object.entries(explorationDefinitions).map(([key, item]) => `<button data-exploration-metric="${key}" class="${analytics.explorationMetric === key ? "active" : ""}" type="button">${t(item.label)}</button>`).join("")}</div><div class="exploration-main-grid">${explorationRanking(ranking, definition)}<section class="dimension-map block-panel"><div class="ranking-section-title"><span class="eyebrow">ATLAS</span><h3>${t("dimensionMap")}</h3></div><div class="dimension-cards">${(result.dimensions || []).map((item) => `<article><span>${uiIcon("exploration")}</span><strong>${escapeHtml(dimensionName(item.dimension))}</strong><b>${formatRankingValue(item.distance, "distance")}</b><small>${t("dimensionDistance")}</small><b>${formatDuration(item.active_seconds || 0)}</b><small>${t("activeMovementTime")}</small><em>${t("explorationFirstSeen")} ${formatDate(item.first_seen_at)}<br>${t("explorationLastSeen")} ${formatDate(item.last_seen_at)}</em></article>`).join("") || `<div class="exploration-zero"><span>${uiIcon("exploration")}</span><p>${t("noExplorationEvidence")}</p></div>`}</div></section></div><section class="journey-panel block-panel"><div class="ranking-section-title"><span class="eyebrow">TRAVEL LOG</span><h3>${t("recentJourneys")}</h3></div>${(result.transitions || []).length ? `<ol>${result.transitions.map((journey) => `<li><button data-exploration-player="${escapeHtml(journey.player.id)}" type="button">${escapeHtml(journey.player.name)}</button><span>${escapeHtml(dimensionName(journey.from))} → ${escapeHtml(dimensionName(journey.to))}</span>${timelineTimestamp(journey.timestamp)}</li>`).join("")}</ol>` : `<div class="exploration-zero"><span>${uiIcon("distance")}</span><p>${t("noExplorationEvidence")}</p></div>`}</section><section class="explorer-profiles block-panel"><div class="ranking-section-title"><span class="eyebrow">PLAYERS</span><h3>${t("explorerProfiles")}</h3></div><div>${(result.players || []).map((item) => `<button data-exploration-player="${escapeHtml(item.player.id)}" type="button"><strong>${escapeHtml(item.player.name)}</strong><span>${t("distanceTraveled")} <b>${formatRankingValue(item.distance, "distance")}</b></span><span>${t("activeMovementTime")} <b>${formatDuration(item.active_seconds || 0)}</b></span><span>${t("dimensionsDiscovered")} <b>${item.dimension_count}</b></span><span>${t("favoriteDimension")} <b>${item.favorite_dimension ? escapeHtml(dimensionName(item.favorite_dimension.dimension)) : "—"}</b></span><small>${t("explorationFirstSeen")} ${formatDate(item.first_seen_at)} · ${t("explorationLastSeen")} ${formatDate(item.last_seen_at)}</small></button>`).join("") || `<div class="exploration-zero"><span>${uiIcon("exploration")}</span><p>${t("noExplorationEvidence")}</p></div>`}</div></section>`;
      target.querySelectorAll("[data-exploration-player]").forEach((button) => button.onclick = () => openAnalyticsPlayer(button.dataset.explorationPlayer));
      target.querySelectorAll("[data-exploration-metric]").forEach((button) => button.onclick = () => { analytics.explorationMetric = button.dataset.explorationMetric; load(); });
    } catch (error) { target.innerHTML = `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`; }
  };
  $("#exploration-refresh").onclick = load;
  await load();
}

}

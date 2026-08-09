export function createRankingsPanel({ state, content, t, uiIcon, api, $, escapeHtml, analyticsViewSwitch, bindAnalyticsViewSwitch, rankingDefinitions, formatRankingValue, formatDate, openAnalyticsPlayer }) {
return async function renderRankingsPanel() {
  const analytics = state.analytics;
  content.innerHTML = `<div class="rankings-screen">${analyticsViewSwitch("rankings")}<header class="rankings-hero block-panel"><div><span class="eyebrow">LIFETIME</span><h2>${t("rankingsTitle")}</h2><p>${t("rankingsHelp")}</p></div><button id="rankings-refresh" class="secondary" type="button">${uiIcon("refresh")} ${t("refreshData")}</button></header><div class="ranking-categories">${[["activity", "categoryActivity", "activity"], ["combat", "categoryCombat", "combat"], ["building", "categoryBuilding", "blocks"], ["exploration", "categoryExploration", "exploration"]].map(([category, label, icon]) => `<button data-ranking-category="${category}" class="${analytics.rankingCategory === category ? "active" : ""}" type="button"><span>${uiIcon(icon)}</span>${t(label)}</button>`).join("")}</div><div id="rankings-content" class="rankings-content"><div class="analytics-loading">${t("checking")}</div></div></div>`;
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

}


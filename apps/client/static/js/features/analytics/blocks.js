import { renderMarkup } from "../../core/render.js";

export function createBlocksPanel({ state, content, t, uiIcon, api, $, escapeHtml, analyticsViewSwitch, bindAnalyticsViewSwitch, blockTermMarkup, blockIcon, oreLabel, formatRankingValue, openAnalyticsPlayer, formatDate }) {
const allowedOres = new Set(["coal", "iron", "copper", "gold", "redstone", "lapis_lazuli", "diamond", "emerald", "quartz", "ancient_debris"]);
function blockLeaderboard(entries, title) {
  return `<section class="block-leaderboard block-panel"><div class="ranking-section-title"><span class="eyebrow">TOP 10</span><h3>${title}</h3></div>${entries.length ? `<ol>${entries.map((entry, index) => `<li><b>${index + 1}</b>${blockTermMarkup(entry.block)}<strong>${formatRankingValue(entry.count, "number")}</strong></li>`).join("")}</ol>` : `<div class="analytics-empty"><p>${t("noBlockData")}</p></div>`}</section>`;
}

function playerBlockRanking(entries, title) {
  return `<section class="block-player-ranking block-panel"><div class="ranking-section-title"><span class="eyebrow">LIFETIME</span><h3>${title}</h3></div>${entries.length ? `<ol>${entries.map((entry, index) => `<li><b>${index + 1}</b><button data-block-player="${escapeHtml(entry.player.id)}" type="button">${escapeHtml(entry.player.name)}</button><strong>${formatRankingValue(entry.value, "number")}</strong></li>`).join("")}</ol>` : `<div class="analytics-empty"><p>${t("noBlockData")}</p></div>`}</section>`;
}

return async function renderBlocksPanel() {
  const analytics = state.analytics;
  // all API data paths use escapeHtml or formatRankingValue.
  renderMarkup(content, `<div class="blocks-screen">${analyticsViewSwitch("blocks")}<header class="blocks-hero block-panel"><div><span class="eyebrow">WORLD STATISTICS</span><h2>${t("blocksTitle")}</h2><p>${t("blocksHelp")}</p></div><button id="blocks-refresh" class="secondary" type="button">${uiIcon("refresh")} ${t("refreshData")}</button></header><div class="blocks-mode"><button data-block-mode="mining" class="${analytics.blocksMode === "mining" ? "active" : ""}" type="button">${uiIcon("mining")} ${t("miningView")}</button><button data-block-mode="building" class="${analytics.blocksMode === "building" ? "active" : ""}" type="button">${uiIcon("building")} ${t("buildingView")}</button></div><div id="blocks-content"><div class="analytics-loading">${t("checking")}</div></div></div>`);  bindAnalyticsViewSwitch();
  const load = async () => {
    const target = $("#blocks-content");
    renderMarkup(target, `<div class="analytics-loading">${t("checking")}</div>`);    try {
      const result = await api("/api/analytics/blocks?limit=10");
      const mining = analytics.blocksMode === "mining";
      const oreEntries = Object.entries(result.ores || {}).filter(([ore]) => allowedOres.has(ore));
      if (!oreEntries.some(([ore]) => ore === analytics.selectedOre)) analytics.selectedOre = oreEntries[0]?.[0] || "diamond";
      const ranking = mining ? result.rankings?.miners || [] : result.rankings?.builders || [];
      const types = mining ? result.top_broken || [] : result.top_placed || [];
      const oreRanking = result.rankings?.ores?.[analytics.selectedOre] || [];
      renderMarkup(target, `<section class="blocks-summary"><article><small>${t("broken")}</small><b>${formatRankingValue(result.totals?.broken, "number")}</b><span>${uiIcon("mining")}</span></article><article><small>${t("placed")}</small><b>${formatRankingValue(result.totals?.placed, "number")}</b><span>${uiIcon("building")}</span></article><p>${t("blocksTelemetryHint")}<br><small>${t("updated")} ${formatDate(result.generated_at)}</small></p></section>${mining ? `<section class="ore-section block-panel"><div class="ranking-section-title"><span class="eyebrow">ORE TRACKER</span><h3>${t("oresTitle")}</h3></div><div class="ore-grid">${oreEntries.map(([ore, count]) => `<button data-ore="${ore}" class="${ore === analytics.selectedOre ? "active" : ""}" type="button"><span class="ore-gem ore-${ore}">${blockIcon(`minecraft:${ore === "ancient_debris" ? ore : `${ore}_ore`}`)}</span><small>${oreLabel(ore)}</small><b>${formatRankingValue(count, "number")}</b></button>`).join("")}</div></section>` : ""}<div class="blocks-rank-grid">${blockLeaderboard(types, t("topBlocks"))}${playerBlockRanking(ranking, mining ? t("miners") : t("builders"))}${mining ? playerBlockRanking(oreRanking, `${t("oreRanking")}: ${oreLabel(analytics.selectedOre)}`) : ""}</div><section class="player-favorites block-panel"><div class="ranking-section-title"><span class="eyebrow">PLAYERS</span><h3>${t("favoriteBlocks")}</h3></div><div>${(result.players || []).map((item) => { const favorite = mining ? item.favorite_broken : item.favorite_placed; return `<button data-block-player="${escapeHtml(item.player.id)}" type="button"><strong>${escapeHtml(item.player.name)}</strong><span>${favorite ? blockTermMarkup(favorite.block) : "—"}</span><b>${favorite ? formatRankingValue(favorite.count, "number") : "0"}</b></button>`; }).join("") || `<p>${t("noBlockData")}</p>`}</div></section>`);      target.querySelectorAll("[data-block-player]").forEach((button) => button.onclick = () => openAnalyticsPlayer(button.dataset.blockPlayer));
      target.querySelectorAll("[data-ore]").forEach((button) => button.onclick = () => { analytics.selectedOre = button.dataset.ore; load(); });
    } catch (error) { renderMarkup(target, `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`); }
  };
  content.querySelectorAll("[data-block-mode]").forEach((button) => button.onclick = () => {
    analytics.blocksMode = button.dataset.blockMode;
    content.querySelectorAll("[data-block-mode]").forEach((item) => item.classList.toggle("active", item === button));
    load();
  });
  $("#blocks-refresh").onclick = load;
  await load();
}

}

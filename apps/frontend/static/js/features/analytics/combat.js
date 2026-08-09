export function createCombatPanel({ state, content, t, uiIcon, gameTermMarkup, api, $, escapeHtml, analyticsViewSwitch, bindAnalyticsViewSwitch, formatRankingValue, openAnalyticsPlayer, formatDate }) {
const combatDefinitions = {
  mob_kills: { label: "combatMobKills", format: "number" },
  player_kills: { label: "combatPlayerKills", format: "number" },
  deaths: { label: "combatDeaths", format: "number" },
  damage_dealt: { label: "combatDamageDealt", format: "decimal" },
  damage_taken: { label: "combatDamageTaken", format: "decimal" },
};

function combatBreakdown(title, entries, icon) {
  const kind = title === t("deathCauses") ? "cause" : "entity";
  return `<section class="combat-breakdown block-panel"><div class="ranking-section-title"><span class="eyebrow">${uiIcon(icon)} LIFETIME</span><h3>${title}</h3></div>${entries.length ? `<ol>${entries.map((entry, index) => `<li><b>${index + 1}</b>${gameTermMarkup(entry.key, kind)}<strong>${formatRankingValue(entry.count, "number")}</strong></li>`).join("")}</ol>` : `<div class="combat-zero"><span>${uiIcon(icon)}</span><p>${t("noCombatEvidence")}</p></div>`}</section>`;
}

function combatPlayerRanking(entries, title) {
  return `<section class="block-player-ranking block-panel"><div class="ranking-section-title"><span class="eyebrow">LIFETIME</span><h3>${title}</h3></div>${entries.length ? `<ol>${entries.map((entry, index) => `<li><b>${index + 1}</b><button data-combat-player="${escapeHtml(entry.player.id)}" type="button">${escapeHtml(entry.player.name)}</button><strong>${formatRankingValue(entry.value, "number")}</strong></li>`).join("")}</ol>` : `<div class="combat-zero"><span>${uiIcon("combat")}</span><p>${t("noCombatEvidence")}</p></div>`}</section>`;
}

return async function renderCombatPanel() {
  const analytics = state.analytics;
  content.innerHTML = `<div class="combat-screen">${analyticsViewSwitch("combat")}<header class="combat-hero block-panel"><div><span class="eyebrow">COMBAT LOG</span><h2>${t("combatTitle")}</h2><p>${t("combatHelp")}</p></div><button id="combat-refresh" class="secondary" type="button">${uiIcon("refresh")} ${t("refreshData")}</button></header><div id="combat-content"><div class="analytics-loading">${t("checking")}</div></div></div>`;
  bindAnalyticsViewSwitch();
  const load = async () => {
    const target = $("#combat-content");
    target.innerHTML = `<div class="analytics-loading">${t("checking")}</div>`;
    try {
      const result = await api("/api/analytics/combat?limit=10");
      const definition = combatDefinitions[analytics.combatMetric] || combatDefinitions.mob_kills;
      const ranking = result.rankings?.[analytics.combatMetric] || [];
      const totals = result.totals || {};
      const breakdowns = result.breakdowns || {};
      target.innerHTML = `<section class="combat-summary">${Object.entries(combatDefinitions).map(([key, item]) => `<article><small>${t(item.label)}</small><b>${formatRankingValue(totals[key], item.format)}</b><span>${uiIcon(key === "deaths" ? "deaths" : key.includes("damage") ? "damage" : "combat")}</span></article>`).join("")}</section><p class="combat-empty-note">${t("combatEmptyHelp")} <small>${t("updated")} ${formatDate(result.generated_at)}</small></p><div class="combat-metric-picker">${Object.entries(combatDefinitions).map(([key, item]) => `<button data-combat-metric="${key}" class="${analytics.combatMetric === key ? "active" : ""}" type="button">${t(item.label)}</button>`).join("")}</div><div class="combat-main-grid">${combatPlayerRanking(ranking, `${t("combatRankings")}: ${t(definition.label)}`)}<section class="pvp-panel block-panel"><div class="ranking-section-title"><span class="eyebrow">${uiIcon("combat")} ${t("observedDeaths")}</span><h3>${t("pvpDuels")}</h3></div>${(result.pvp || []).length ? `<ol>${result.pvp.map((duel) => `<li><button data-combat-player="${escapeHtml(duel.attacker.id)}" type="button">${escapeHtml(duel.attacker.name)}</button><span>→</span><button data-combat-player="${escapeHtml(duel.victim.id)}" type="button">${escapeHtml(duel.victim.name)}</button><b>${duel.count}</b></li>`).join("")}</ol>` : `<div class="combat-zero"><span>${uiIcon("combat")}</span><p>${t("noCombatEvidence")}</p></div>`}</section></div><div class="combat-breakdown-grid">${combatBreakdown(t("favoriteTargets"), (result.top_targets || []).map((item) => ({ key: item.target, count: item.kills })), "combat")}${combatBreakdown(t("deathCauses"), breakdowns.causes || [], "deaths")}${combatBreakdown(t("lethalOpponents"), breakdowns.opponents || [], "combat")}${combatBreakdown(t("projectiles"), breakdowns.projectiles || [], "activity")}</div><section class="combat-profiles block-panel"><div class="ranking-section-title"><span class="eyebrow">PLAYERS</span><h3>${t("combatProfiles")}</h3></div><div>${(result.players || []).map((item) => `<button data-combat-player="${escapeHtml(item.player.id)}" type="button"><strong>${escapeHtml(item.player.name)}</strong><span>${t("combatMobKills")} <b>${formatRankingValue(item.mob_kills, "number")}</b></span><span>${t("combatPlayerKills")} <b>${formatRankingValue(item.player_kills, "number")}</b></span><span>${t("combatDeaths")} <b>${formatRankingValue(item.deaths, "number")}</b></span><span>${t("favoriteTargets")} <b>${item.favorite_target ? gameTermMarkup(item.favorite_target.target) : "—"}</b></span><small>${item.telemetry_available ? `${t("sourceStructured")} · ${t("updated")} ${formatDate(item.updated_at)}` : t("telemetryWaiting")}</small></button>`).join("") || `<div class="combat-zero"><span>${uiIcon("combat")}</span><p>${t("noCombatEvidence")}</p></div>`}</div></section>`;
      target.querySelectorAll("[data-block-player], [data-combat-player]").forEach((button) => button.onclick = () => { const id = button.dataset.blockPlayer || button.dataset.combatPlayer; if (id) openAnalyticsPlayer(id); });
      target.querySelectorAll("[data-combat-metric]").forEach((button) => button.onclick = () => { analytics.combatMetric = button.dataset.combatMetric; load(); });
    } catch (error) { target.innerHTML = `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`; }
  };
  $("#combat-refresh").onclick = load;
  await load();
}

}

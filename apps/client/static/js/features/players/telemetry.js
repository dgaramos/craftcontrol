export function createPlayerTelemetry({ state, t, escapeHtml, gameTermMarkup, blockTermMarkup, dimensionName, formatRankingValue, uiIcon, gameIcon, formatDate }) {
function sortedTelemetryEntries(value, limit = 12) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value).filter(([, count]) => Number(count) > 0).sort((left, right) => Number(right[1]) - Number(left[1]) || left[0].localeCompare(right[0])).slice(0, limit);
}

function playerBreakdownMarkup(entries, type, emptyLabel) {
  if (!entries.length) return `<p class="player-data-empty">${escapeHtml(emptyLabel)}</p>`;
  return `<ol class="player-data-ranking">${entries.map(([key, count]) => `<li>${type === "entity" ? gameTermMarkup(key) : type === "block" ? blockTermMarkup(key) : `<span>${escapeHtml(dimensionName(key))}</span>`}<strong>${formatRankingValue(count, "number")}</strong></li>`).join("")}</ol>`;
}

function playerDataMarkup(profile) {
  if (!profile.telemetry_updated_at) return `<section class="player-data-workspace block-panel"><div class="player-data-heading"><span class="eyebrow">${t("playerDataKicker")}</span><h3>${t("playerDataTitle")}</h3><p>${t("telemetryWaiting")}</p></div></section>`;
  const stats = profile.telemetry || {};
  const dimensions = sortedTelemetryEntries(stats.dimensions);
  const dimensionCount = Object.keys(stats.dimensions && typeof stats.dimensions === "object" ? stats.dimensions : {}).length;
  const items = [["playerKills", stats.playerKills], ["mobKills", stats.mobKills], ["blocksBroken", stats.blocksBroken], ["blocksPlaced", stats.blocksPlaced], ["damageDealt", Number(stats.damageDealt || 0).toFixed(1)], ["damageTaken", Number(stats.damageTaken || 0).toFixed(1)], ["distanceTraveled", `${Math.round(stats.distance || 0)} m`], ["dimensionsVisited", dimensionCount]];
  const noKills = t("noCreatureData");
  const noBlocks = t("noBlockRecords");
  const noDimensions = t("noDimensionRecords");
  return `<section class="player-data-workspace"><header class="player-data-heading block-panel"><div><span class="eyebrow">${t("playerDataKicker")}</span><h3>${t("playerDataTitle")}</h3><p>${t("playerDataHelp", escapeHtml(profile.name))}</p></div><small>${uiIcon("check")} ${t("authoritative")} · ${t("updated")} ${formatDate(profile.telemetry_updated_at)}</small></header><div class="telemetry-grid">${items.map(([label, value]) => `<span><b>${value || 0}</b>${t(label)}</span>`).join("")}</div><div class="player-data-drawers">${[
    [gameIcon("skeleton"), t("categoryCombat"), t("mobKills"), playerBreakdownMarkup(sortedTelemetryEntries(stats.killsByType), "entity", noKills)],
    [uiIcon("mining"), t("miningView"), t("blocksBroken"), playerBreakdownMarkup(sortedTelemetryEntries(stats.brokenByType), "block", noBlocks)],
    [uiIcon("building"), t("buildingView"), t("blocksPlaced"), playerBreakdownMarkup(sortedTelemetryEntries(stats.placedByType), "block", noBlocks)],
    [uiIcon("exploration"), t("categoryExploration"), t("dimensionsVisited"), playerBreakdownMarkup(dimensions, "dimension", noDimensions)],
  ].map(([icon, kicker, title, body]) => `<details class="player-data-drawer"><summary><span class="player-data-drawer-icon">${icon}</span><span class="player-data-drawer-copy"><small>${kicker}</small><strong>${title}</strong></span></summary><div class="player-data-drawer-body">${body}</div></details>`).join("")}</div></section>`;
}


  return { sortedTelemetryEntries, playerBreakdownMarkup, playerDataMarkup };
}


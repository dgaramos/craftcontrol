import { renderMarkup } from "../../core/render.js";

/**
 * Opt-in item and interaction analytics (issue #275).
 *
 * Every number here is optional data, so the panel says where each one stands
 * before it draws it: a metric nobody enabled has no zero to show, and neither
 * does one the server cannot report. Only a metric that is both enabled and
 * supported may present a total — and a total of zero then means what it says.
 *
 * The notice explains the number in front of the reader. The pack's own state —
 * which metrics are on, which capabilities it has — belongs to the server
 * infrastructure screen, not here.
 */
export function createInteractionsPanel({ state, content, t, uiIcon, api, $, escapeHtml, analyticsViewSwitch, bindAnalyticsViewSwitch, blockTermMarkup, gameTermMarkup, formatRankingValue, openAnalyticsPlayer, formatDate }) {
  const METRICS = [
    { metric: "itemUse", label: "itemUseMetric", empty: "noItemUseYet" },
    { metric: "blockInteractions", label: "blockInteractionsMetric", empty: "noBlockInteractionsYet" },
    { metric: "entityInteractions", label: "entityInteractionsMetric", empty: "noEntityInteractionsYet" },
    { metric: "containerInteractions", label: "containerInteractionsMetric", empty: "noContainerOpensYet" },
  ];

  const typeMarkup = (metric, type) =>
    metric === "entityInteractions" ? gameTermMarkup(type) : blockTermMarkup(type);

  /**
   * Say what a metric's numbers are worth before showing any.
   *
   * Returns `null` when the metric is collecting and the totals may be drawn.
   */
  function availabilityNotice(availability) {
    if (!availability) return { title: t("metricUnknown"), help: t("metricUnknownHelp") };
    if (!availability.enabled) return { title: t("metricDisabled"), help: t("metricDisabledHelp") };
    if (availability.supported === false) return { title: t("metricUnsupported"), help: t("metricUnsupportedHelp") };
    if (availability.supported === null) return { title: t("metricUnconfirmed"), help: t("metricUnconfirmedHelp") };
    return null;
  }

  return async function renderInteractionsPanel() {
    const analytics = state.analytics;
    if (!METRICS.some((item) => item.metric === analytics.interactionMetric)) {
      analytics.interactionMetric = METRICS[0].metric;
    }
    renderMarkup(content, `<div class="interactions-screen">${analyticsViewSwitch("interactions")}<header class="interactions-hero block-panel"><div><span class="eyebrow">${t("optInKicker")}</span><h2>${t("interactionsTitle")}</h2><p>${t("interactionsHelp")}</p></div><button id="interactions-refresh" class="secondary" type="button">${uiIcon("refresh")} ${t("refreshData")}</button></header><div class="choice-group interactions-metric-picker">${METRICS.map((item) => `<button data-interaction-metric="${item.metric}" class="${item.metric === analytics.interactionMetric ? "active" : ""}" type="button">${t(item.label)}</button>`).join("")}</div><div id="interactions-content"><div class="analytics-loading">${t("checking")}</div></div></div>`);
    bindAnalyticsViewSwitch();

    const load = async () => {
      const target = $("#interactions-content");
      renderMarkup(target, `<div class="analytics-loading">${t("checking")}</div>`);
      try {
        const result = await api("/api/analytics/interactions?limit=10");
        const selected = METRICS.find((item) => item.metric === analytics.interactionMetric) || METRICS[0];
        const notice = availabilityNotice((result.availability || {})[selected.metric]);
        const total = (result.totals || {})[selected.metric] || 0;
        const top = (result.top || {})[selected.metric] || [];
        const ranking = (result.rankings || {})[selected.metric] || [];

        const body = notice
          ? `<section class="analytics-empty interactions-unavailable block-panel"><h3>${notice.title}</h3><p>${notice.help}</p></section>`
          : `<section class="interactions-summary"><article><small>${t(selected.label)}</small><b>${formatRankingValue(total, "number")}</b><span>${uiIcon("data")}</span></article><p>${t("interactionsTelemetryHint")}<br><small>${t("updated")} ${formatDate(result.generated_at)}</small></p></section><div class="interactions-rank-grid"><section class="block-panel"><div class="ranking-section-title"><span class="eyebrow">${t("topTenKicker")}</span><h3>${t("topInteractionTypes")}</h3></div>${top.length ? `<ol>${top.map((entry, index) => `<li><b>${index + 1}</b>${typeMarkup(selected.metric, entry.type)}<strong>${formatRankingValue(entry.count, "number")}</strong></li>`).join("")}</ol>` : `<div class="analytics-empty"><p>${t(selected.empty)}</p></div>`}</section><section class="block-panel"><div class="ranking-section-title"><span class="eyebrow">${t("lifetime")}</span><h3>${t("players")}</h3></div>${ranking.length ? `<ol>${ranking.map((entry, index) => `<li><b>${index + 1}</b><button data-interaction-player="${escapeHtml(entry.player.id)}" type="button">${escapeHtml(entry.player.name)}</button><strong>${formatRankingValue(entry.value, "number")}</strong></li>`).join("")}</ol>` : `<div class="analytics-empty"><p>${t(selected.empty)}</p></div>`}</section></div>`;

        renderMarkup(target, body);
        target.querySelectorAll("[data-interaction-player]").forEach((button) => button.onclick = () => openAnalyticsPlayer(button.dataset.interactionPlayer));
      } catch (error) {
        renderMarkup(target, `<div class="analytics-empty"><p>${escapeHtml(error.message)}</p></div>`);
      }
    };

    content.querySelectorAll("[data-interaction-metric]").forEach((button) => button.onclick = () => {
      analytics.interactionMetric = button.dataset.interactionMetric;
      content.querySelectorAll("[data-interaction-metric]").forEach((item) => item.classList.toggle("active", item === button));
      load();
    });
    $("#interactions-refresh").onclick = load;
    await load();
  };
}

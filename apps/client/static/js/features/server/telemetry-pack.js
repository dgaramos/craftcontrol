import { createPackHealthPanel } from "./health.js?v=3";

/**
 * The Telemetry Pack screen (issue #275 follow-up).
 *
 * Everything about the pack in one place, in the order an owner asks it: does
 * it work, what may it collect, what is installed — and, folded away, the
 * numbers that only matter while something is wrong.
 *
 * Before this screen the same `/api/telemetry-pack` payload was drawn twice on
 * the settings page, in two visual languages, above the server settings that
 * page exists for.
 */
export function createTelemetryPackScreen({ content, t, api, $, escapeHtml, uiIcon, formatDate, toast, loadDiagnostics }) {
  const OPT_IN_METRICS = [
    ["itemUse", "itemUseMetric"],
    ["blockInteractions", "blockInteractionsMetric"],
    ["entityInteractions", "entityInteractionsMetric"],
    ["containerInteractions", "containerInteractionsMetric"],
  ];

  const renderPackHealth = createPackHealthPanel({ $, t, api, formatDate, uiIcon });

  function markup() {
    return `<section class="settings-screen telemetry-screen">
      <header class="inner-heading"><span class="eyebrow">${t("behaviorPackEyebrow")}</span><h2>${t("telemetryPack")}</h2><p>${t("telemetryPackHelp")}</p></header>
      <section id="pack-status" class="pack-status block-panel">${t("checking")}</section>
      <section class="pack-collection block-panel"><div class="ranking-section-title"><span class="eyebrow">${t("optInKicker")}</span><h3>${t("optInMetrics")}</h3></div><p>${t("optInMetricsHelp")}</p><div id="telemetry-metrics" class="telemetry-metrics">${t("checking")}</div></section>
      <section id="pack-install" class="pack-install block-panel">${t("checking")}</section>
      <details class="pack-details diag-details"><summary><div class="diag-summary-header"><div><span class="eyebrow">${t("behaviorPackEyebrow")}</span><h3 class="diag-summary-title">${t("technicalDetails")}</h3><p class="diag-summary-sub">${t("technicalDetailsHelp")}</p></div><span class="diag-summary-toggle"></span></div></summary><div id="pack-health" class="diag-details-body"><div class="analytics-loading">${t("checking")}</div></div></details>
      <details id="diagnostics-details" class="pack-details diag-details"><summary><div class="diag-summary-header"><div><span class="eyebrow">${t("diagDashboardEyebrow")}</span><h3 class="diag-summary-title">${t("diagDashboard")}</h3><p class="diag-summary-sub">${t("diagDashboardHelp")}</p></div><span class="diag-summary-toggle"></span></div></summary><div id="diagnostics-state" class="diag-details-body"></div></details>
    </section>`;
  }

  /** One line that answers "is it working?" before any detail is offered. */
  function statusMarkup(pack) {
    const health = t(pack.health) || pack.health || t("waiting");
    const state = pack.installed ? (pack.enabled ? t("packActive") : t("packInactive")) : t("packMissing");
    return `<div class="pack-status-line"><span class="pack-status-version">v${escapeHtml(pack.runtime_version || pack.installed_version || "—")}</span><span class="health-badge health-${escapeHtml(pack.health || "waiting")}">${escapeHtml(health)}</span><span class="pack-status-state">${escapeHtml(state)}</span></div><p class="pack-status-note">${t("lastResponse")}: ${formatDate(pack.last_response_at)}</p>${pack.last_error ? `<p class="telemetry-pack-error">${escapeHtml(pack.last_error)}</p>` : ""}`;
  }

  function installMarkup(pack) {
    const primaryAction = pack.installed ? (pack.upgrade_available ? "upgrade" : null) : "install";
    return `<div class="ranking-section-title"><span class="eyebrow">${t("administration")}</span><h3>${t("packInstallation")}</h3></div><div class="release-version-grid"><article><small>${t("installedVersion")}</small><strong>v${escapeHtml(pack.installed_version || "—")}</strong><span>${t("packInstalledAt")} ${formatDate(pack.installed_updated_at)}</span></article><article><small>${t("bundledVersion")}</small><strong>v${escapeHtml(pack.source_version)}</strong><span>${pack.upgrade_available && pack.installed ? t("upgradeAvailable") : t("packUpToDate")}</span></article></div><div class="telemetry-pack-actions">${primaryAction ? `<button data-pack-action="${primaryAction}">${t(primaryAction === "install" ? "installPack" : "upgradePack")}</button>` : ""}${pack.enabled ? `<button class="secondary" data-pack-action="disable">${t("disablePack")}</button>` : ""}<button class="secondary" data-pack-action="rollback">${t("rollbackPack")}</button></div>`;
  }

  /**
   * The opt-in switches.
   *
   * A change travels the Bedrock console, so the row says the request is in
   * flight rather than flipping to a state the pack has not confirmed.
   */
  async function loadCollection(capabilities = {}) {
    const target = $("#telemetry-metrics");
    if (!target) return;
    try {
      const result = await api("/api/telemetry/collection");
      const metrics = result.metrics || {};
      target.innerHTML = `<ul>${OPT_IN_METRICS.map(([metric, label]) => {
        const enabled = metrics[metric] === true;
        // Only an explicit `false` means the runtime cannot deliver it. An
        // absent capability is unprobed — `containerInteractions` is only
        // probed on the first block interaction — and must not block anything.
        const unsupported = capabilities[metric]?.supported === false;
        const status = unsupported ? t("metricUnsupported") : enabled ? t("metricCollecting") : t("metricDisabled");
        // Turning on a metric this server cannot report would collect nothing
        // and read as unavailable in Analytics, so the control is withheld.
        // Turning one off stays available: what is on must be stoppable.
        const blocked = unsupported && !enabled;
        return `<li class="${enabled ? "supported" : "unavailable"}"><span>${uiIcon(enabled ? "check" : "close")}</span><div><strong>${escapeHtml(t(label))}</strong><small>${escapeHtml(status)}</small></div><button class="secondary" data-metric="${metric}" data-metric-enabled="${enabled ? "false" : "true"}" type="button"${blocked ? " disabled" : ""}>${enabled ? t("metricDisable") : t("metricEnable")}</button></li>`;
      }).join("")}</ul>`;
      target.querySelectorAll("[data-metric]").forEach((button) => button.onclick = async () => {
        button.disabled = true;
        const note = button.closest("li")?.querySelector("small");
        if (note) note.textContent = t("metricPending");
        try {
          await api("/api/telemetry/collection", {
            method: "POST",
            body: JSON.stringify({ metric: button.dataset.metric, enabled: button.dataset.metricEnabled === "true" }),
          });
          toast(t("metricChanged"));
          await loadCollection(capabilities);
        } catch (error) { toast(error.message, true); button.disabled = false; }
      });
    } catch (error) { target.textContent = error.message; }
  }

  async function load() {
    const status = $("#pack-status");
    const install = $("#pack-install");
    try {
      const pack = await api("/api/telemetry-pack");
      if (status) status.innerHTML = statusMarkup(pack);
      if (install) {
        install.innerHTML = installMarkup(pack);
        install.querySelectorAll("[data-pack-action]").forEach((button) => button.onclick = async () => {
          if (!confirm(t("packActionConfirm"))) return;
          button.disabled = true;
          try {
            const result = await api(`/api/telemetry-pack/${button.dataset.packAction}`, { method: "POST" });
            toast(result.restart_required ? t("restartPackNotice") : t("operationDone"));
            // An install or a rollback changes what the folded panels report,
            // so they are re-read too: stale sequence and capability numbers
            // under a fresh status line would be worse than none.
            await load();
            await renderPackHealth();
            loadDiagnostics();
          } catch (error) { toast(error.message, true); button.disabled = false; }
        });
      }
      await loadCollection(pack.capabilities || {});
    } catch (error) {
      if (status) status.textContent = error.message;
    }
  }

  return async function renderTelemetryPackScreen() {
    content.innerHTML = markup();
    await load();
    // Detail and diagnostics are folded away: they answer questions nobody has
    // until something is wrong, and they used to occupy the top of the screen.
    await renderPackHealth();
    loadDiagnostics();
  };
}

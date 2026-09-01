import { createOperationFeature } from "./operation.js?v=13";

export function createServerFeature({ state, content, t, api, $, escapeHtml, uiIcon, formatDate, toast, getSettingsFeature }) {
function telemetryPackMarkup() {
  return `<section class="telemetry-pack-card block-panel"><div><span class="eyebrow">CRAFTCONTROL</span><h3>${t("telemetryPack")}</h3><p>${t("telemetryPackHelp")}</p></div><div id="telemetry-pack-state" class="telemetry-pack-state">${t("checking")}</div><div id="diagnostics-state" class="telemetry-pack-state"></div></section>`;
}

async function loadDiagnostics() {
  const target = $("#diagnostics-state");
  if (!target) return;
  try {
    const result = await api("/api/diagnostics");
    const telemetry = result.telemetry || {};
    const broker = result.broker || {};
    const section = document.createElement("section");
    section.className = "capability-panel";
    const heading = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = t("diagnostics");
    const help = document.createElement("small");
    help.textContent = t("diagnosticsHelp");
    heading.append(title, help);
    const metrics = document.createElement("dl");
    const groups = [];
    const add = (label, value) => {
      const item = document.createElement("div");
      const term = document.createElement("dt");
      term.textContent = label;
      const detail = document.createElement("dd");
      detail.textContent = String(value);
      item.append(term, detail);
      metrics.append(item);
    };
    add(t("telemetryAccepted"), telemetry.accepted || 0);
    add(t("telemetryRejected"), telemetry.rejected || 0);
    add(t("telemetryDuplicates"), telemetry.duplicates || 0);
    add(t("telemetryOld"), telemetry.old || 0);
    const sequence = telemetry.sequence || {};
    add(t("telemetryLost"), sequence.lost || 0);
    add(t("detectedGaps"), sequence.gaps || 0);
    add(t("resetCount"), sequence.resets || 0);
    const topicMetrics = Object.entries(telemetry.by_topic || {});
    if (topicMetrics.length) {
      const topicGroup = document.createElement("div");
      const label = document.createElement("strong");
      label.textContent = t("telemetryTopicDiagnostics");
      topicGroup.append(label);
      topicMetrics.forEach(([topic, values]) => {
        const item = document.createElement("small");
        item.textContent = `${topic}: ${t("telemetryAccepted")} ${values.accepted}, ${t("telemetryRejected")} ${values.rejected}, ${t("telemetryDuplicates")} ${values.duplicates}, ${t("telemetryOld")} ${values.old}, ${t("detectedGaps")} ${values.gaps}, ${t("resetCount")} ${values.resets}`;
        topicGroup.append(item);
      });
      groups.push(topicGroup);
    }
    add(t("ingestionDuration"), `${telemetry.ingestion_duration_ms_average || 0} ms`);
    add(t("ingestionDurationMax"), `${telemetry.ingestion_duration_ms_max || 0} ms`);
    add(t("sseConnections"), broker.sse_connections || 0);
    add(t("sseConnectionsTotal"), broker.sse_connections_total || 0);
    add(t("runtimeRefreshing"), result.runtime_refreshing ? t("yes") : t("no"));
    const addGroup = (title, values, definitions) => {
      if (!values || !definitions.some(({ key }) => values[key] !== null && values[key] !== undefined)) return;
      const group = document.createElement("div");
      const label = document.createElement("strong");
      label.textContent = title;
      group.append(label);
      definitions.forEach(({ key, label, format }) => {
        const value = values[key];
        if (value === null || value === undefined) return;
        const item = document.createElement("small");
        item.textContent = `${t(label)}: ${format ? format(value) : value}`;
        group.append(item);
      });
      groups.push(group);
    };
    addGroup(t("telemetryDetails"), result.telemetry_state, [
      { key: "status", label: "diagnosticStatus" },
      { key: "sequence", label: "telemetrySequence" },
      { key: "expected_sequence", label: "expectedSequence" },
      { key: "gap_count", label: "detectedGaps" },
      { key: "missing_events", label: "missingEvents" },
      { key: "reset_count", label: "resetCount" },
      { key: "last_snapshot_at", label: "lastSnapshot", format: formatDate },
      { key: "last_event_at", label: "lastResponse", format: formatDate },
    ]);
    addGroup(t("persistenceDiagnostics"), result.persistence, [
      { key: "connections", label: "sqliteConnections" },
      { key: "wait_ms_average", label: "sqliteWaitAverage", format: (value) => `${value} ms` },
      { key: "wait_ms_max", label: "sqliteWaitMax", format: (value) => `${value} ms` },
      { key: "contention_failures", label: "sqliteContentionFailures" },
      { key: "retries", label: "sqliteRetries" },
      { key: "database_size_bytes", label: "sqliteDatabaseSize", format: (value) => `${value} B` },
    ]);
    addGroup(t("runtimeDiagnostics"), result.runtime, [
      { key: "refreshing", label: "runtimeRefreshing", format: (value) => value ? t("yes") : t("no") },
      { key: "pending_gamerule_refreshes", label: "pendingGameruleRefreshes" },
      { key: "gamerule_worker_running", label: "gameruleWorkerRunning", format: (value) => value ? t("yes") : t("no") },
      { key: "snapshot_running", label: "snapshotRunning", format: (value) => value ? t("yes") : t("no") },
    ]);
    section.append(heading, metrics, ...groups);
    const topics = Object.entries(broker.events_by_topic || {});
    if (topics.length) {
      const list = document.createElement("ul");
      topics.forEach(([topic, count]) => {
        const item = document.createElement("li");
        item.textContent = `${topic}: ${count}`;
        list.append(item);
      });
      section.append(list);
    }
    target.replaceChildren(section);
  } catch (_) { target.textContent = ""; }
}

async function loadTelemetryPack() {
  const target = $("#telemetry-pack-state");
  if (!target) return;
  try {
    const pack = await api("/api/telemetry-pack");
    renderReleaseTags(pack);
    const status = pack.installed ? (pack.enabled ? t("packActive") : t("packInactive")) : t("packMissing");
    const primaryAction = pack.installed ? (pack.upgrade_available ? "upgrade" : null) : "install";
    const health = t(pack.health) || pack.health || t("waiting");
    const storageState = pack.storage_status === "migrated" ? t("migrated") : pack.storage_status === "not-required" ? t("notRequired") : pack.storage_status || "—";
    const capabilityEntries = Object.entries(pack.capabilities || {});
    const capabilityState = pack.capability_status === "limited" ? t("capabilityLimited") : capabilityEntries.length ? t("capabilityFull") : t("unknown");
    const capabilityMarkup = capabilityEntries.length ? `<section class="capability-panel"><div><strong>${t("capabilities")}</strong><small>${escapeHtml(capabilityState)} · ${pack.capabilities_supported}/${pack.capabilities_total}</small></div><ul>${capabilityEntries.map(([name, value]) => `<li class="${value.supported ? "supported" : "unavailable"}"><span>${uiIcon(value.supported ? "check" : "close")}</span>${escapeHtml(t(name) || name)}</li>`).join("")}</ul></section>` : "";
    target.innerHTML = `<div class="release-version-grid"><article><small>${t("craftControlImage")}</small><strong>v${escapeHtml(pack.application?.version || "—")}</strong><span>${t("activeSince")} ${formatDate(pack.application?.started_at)}</span></article><article><small>BEHAVIOR PACK</small><strong>v${escapeHtml(pack.runtime_version || pack.installed_version || "—")}</strong><span>${t("packInstalledAt")} ${formatDate(pack.installed_updated_at)}</span></article></div><div class="telemetry-pack-summary"><strong>${escapeHtml(status)}</strong><span class="health-${escapeHtml(pack.health || "waiting")}">${escapeHtml(health)}</span>${pack.upgrade_available && pack.installed ? `<span>${t("upgradeAvailable")}</span>` : ""}</div><dl><div><dt>${t("installedVersion")}</dt><dd>${escapeHtml(pack.installed_version || "—")}</dd></div><div><dt>${t("packObserved")}</dt><dd>${escapeHtml(pack.runtime_version || "—")}</dd></div><div><dt>${t("bundledVersion")}</dt><dd>${escapeHtml(pack.source_version)}</dd></div><div><dt>${t("storageVersion")}</dt><dd>${escapeHtml(pack.storage_version || "—")}</dd></div><div><dt>${t("storageStatus")}</dt><dd>${escapeHtml(storageState)}</dd></div><div><dt>${t("telemetrySequence")}</dt><dd>${escapeHtml(pack.sequence || "—")}</dd></div><div><dt>${t("lastResponse")}</dt><dd>${formatDate(pack.last_response_at)}</dd></div><div><dt>${t("lastSnapshot")}</dt><dd>${formatDate(pack.last_snapshot_at)}</dd></div><div><dt>${t("detectedGaps")}</dt><dd>${escapeHtml(pack.gap_count || 0)}</dd></div><div><dt>${t("missingEvents")}</dt><dd>${escapeHtml(pack.missing_events || 0)}</dd></div><div><dt>${t("packHealth")}</dt><dd>${escapeHtml(health)}</dd></div></dl>${capabilityMarkup}${pack.last_error ? `<p class="telemetry-pack-error">${escapeHtml(pack.last_error)}</p>` : ""}<div class="telemetry-pack-actions">${primaryAction ? `<button data-pack-action="${primaryAction}">${t(primaryAction === "install" ? "installPack" : "upgradePack")}</button>` : ""}${pack.enabled ? `<button class="secondary" data-pack-action="disable">${t("disablePack")}</button>` : ""}<button class="secondary" data-pack-action="rollback">${t("rollbackPack")}</button></div>`;
    target.querySelectorAll("[data-pack-action]").forEach((button) => button.onclick = async () => {
      if (!confirm(t("packActionConfirm"))) return;
      button.disabled = true;
      try {
        const result = await api(`/api/telemetry-pack/${button.dataset.packAction}`, { method: "POST" });
        toast(result.restart_required ? t("restartPackNotice") : t("operationDone"));
        await loadTelemetryPack();
      } catch (error) { toast(error.message, true); button.disabled = false; }
    });
  } catch (error) { target.textContent = error.message; }
}

function renderReleaseTags(pack) {
  const target = $("#release-tags");
  if (!target) return;
  const frontendTag = state.frontendVersion ? `<span>UI v${escapeHtml(state.frontendVersion)}</span>` : "";
  target.innerHTML = `${frontendTag}<span title="${escapeHtml(`${t("craftControlImage")} · ${t("activeSince")} ${formatDate(pack.application?.started_at)}`)}">API v${escapeHtml(pack.application?.version || "—")}</span><span title="${escapeHtml(`${t("packObserved")} · ${t("updated")} ${formatDate(pack.last_response_at)}`)}">PACK v${escapeHtml(pack.runtime_version || pack.installed_version || "—")}</span>`;
}

async function loadFrontendVersion() {
  try {
    const response = await fetch("/version.json", { cache: "no-store" });
    if (!response.ok) return;
    const release = await response.json();
    if (release.service === "frontend" && typeof release.version === "string") state.frontendVersion = release.version;
  } catch (_) { /* The compatibility image has no independent frontend version. */ }
}

// ------------------------------------------------------------------
// Operation lifecycle progress
// ------------------------------------------------------------------

const operationFeature = createOperationFeature({ api, t, formatDate, uiIcon, toast });

function refreshOperationPanel() {
  const container = $("#operation-progress-container");
  const indicator = $("#operation-indicator");
  const indicatorLabel = $("#operation-indicator-label");
  const op = operationFeature.getOperation();
  if (indicator) {
    indicator.hidden = !op;
    indicator.classList?.toggle("op-indicator-terminal", !!op && !["pending", "running"].includes(op.state));
  }
  if (indicatorLabel) indicatorLabel.textContent = op ? (t(`opState_${op.state}`) || op.state) : "";
  if (!container) return;
  const frag = op ? operationFeature.renderOperation(op) : null;
  container.replaceChildren(...(frag ? [frag] : []));
  operationFeature.bindRecoveryActions(container);
}

operationFeature.setUpdateCallback((op) => {
  const wasActive = state.operationActive;
  state.operationActive = !!(op && (op.state === "pending" || op.state === "running"));
  refreshOperationPanel();
  if (state.operationActive && !wasActive) openOperationDrawer();
});

function openOperationDrawer() {
  const drawer = $("#operation-drawer");
  if (drawer && !drawer.open) drawer.showModal();
}

async function initializeOperationProgress() {
  await operationFeature.initialize();
  const op = operationFeature.getOperation();
  state.operationActive = !!(op && (op.state === "pending" || op.state === "running"));
  refreshOperationPanel();
  if (state.operationActive) openOperationDrawer();
}

  const renderServer = () => {
    getSettingsFeature().renderSettingsGroups(["Packs", "Rede", "Avançado"], telemetryPackMarkup());
    loadTelemetryPack();
  };
  return { renderServer, renderReleaseTags, loadFrontendVersion, initializeOperationProgress, loadDiagnostics, openOperationDrawer, refreshOperationPanel };
}

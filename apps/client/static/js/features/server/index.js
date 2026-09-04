import { createOperationFeature } from "./operation.js?v=13";

export function createServerFeature({ state, content, t, api, $, escapeHtml, uiIcon, formatDate, toast, getSettingsFeature }) {
function telemetryPackMarkup() {
  return `<section class="telemetry-pack-card block-panel"><div><span class="eyebrow">CRAFTCONTROL</span><h3>${t("telemetryPack")}</h3><p>${t("telemetryPackHelp")}</p></div><div id="telemetry-pack-state" class="telemetry-pack-state">${t("checking")}</div><div id="diagnostics-state" class="telemetry-pack-state"></div></section>`;
}

function formatBytes(n) {
  if (n == null) return "—";
  if (n < 1024) return n + " B";
  if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
  if (n < 1073741824) return (n / 1048576).toFixed(1) + " MB";
  return (n / 1073741824).toFixed(2) + " GB";
}

function formatMs(n) {
  if (n == null) return "—";
  if (n < 1000) return Math.round(n) + " ms";
  return (n / 1000).toFixed(1) + " s";
}

function formatCount(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString();
}

function formatAge(seconds) {
  if (seconds == null) return "—";
  const s = Math.round(seconds);
  if (s < 60) return s + "s";
  if (s < 3600) return Math.floor(s / 60) + "m " + (s % 60) + "s";
  return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
}

function formatRelativeTime(isoString) {
  if (!isoString) return "—";
  const diff = Math.max(0, Math.floor((Date.now() - new Date(isoString).getTime()) / 1000));
  if (diff < 60) return diff + t("timeAgoSeconds");
  if (diff < 3600) return Math.floor(diff / 60) + t("timeAgoMinutes");
  return Math.floor(diff / 3600) + t("timeAgoHours");
}

async function loadDiagnostics() {
  const target = $("#diagnostics-state");
  if (!target) return;

  const existingBtn = target.querySelector("#diag-refresh");
  if (existingBtn) existingBtn.disabled = true;

  try {
    const result = await api("/api/diagnostics");
    const telemetry = result.telemetry || {};
    const persistence = result.persistence || {};
    const runtime = result.runtime || {};
    const reconciliation = runtime.reconciliation || {};
    const telemetryState = result.telemetry_state || {};

    // -- Toolbar --
    const toolbar = document.createElement("div");
    toolbar.className = "diag-toolbar";
    const stamp = document.createElement("small");
    stamp.className = "muted";
    stamp.id = "diag-updated-at";
    stamp.textContent = `${t("diagUpdatedAt")} ${new Date().toLocaleTimeString()}`;
    const btn = document.createElement("button");
    btn.className = "secondary diag-refresh-btn";
    btn.id = "diag-refresh";
    btn.textContent = `↻ ${t("refresh")}`;
    btn.addEventListener("click", () => loadDiagnostics());
    toolbar.append(stamp, btn);

    // -- KPI tiles --
    function makeTile(labelKey, value, anomaly) {
      const tile = document.createElement("div");
      tile.className = "diag-tile" + (anomaly === "alert" ? " diag-tile--alert" : anomaly === "warn" ? " diag-tile--warn" : "");
      const label = document.createElement("dt");
      label.className = "diag-tile-label";
      label.textContent = t(labelKey);
      const val = document.createElement("dd");
      val.className = "diag-tile-value";
      val.textContent = String(value ?? "—");
      tile.append(label, val);
      if (anomaly) {
        const flag = document.createElement("span");
        flag.className = "diag-tile-flag";
        flag.setAttribute("aria-label", "anomaly");
        flag.textContent = "!";
        tile.append(flag);
      }
      return tile;
    }

    const connections = persistence.connections ?? 0;
    const contentionFailures = persistence.contention_failures ?? 0;
    const rejected = telemetry.rejected ?? 0;
    const reconciliationCount = reconciliation.count ?? 0;
    const waitAvg = persistence.wait_ms_average ?? 0;

    // Last snapshot age in seconds
    let snapshotAnomalyClass = null;
    let snapshotDisplay = "—";
    let snapshotIso = null;
    const snapshotTs = Number(telemetryState.last_snapshot_at);
    if (Number.isFinite(snapshotTs) && snapshotTs > 0) {
      const ageSeconds = (Date.now() / 1000) - snapshotTs;
      snapshotIso = new Date(snapshotTs * 1000).toISOString();
      snapshotDisplay = formatRelativeTime(snapshotIso);
      if (ageSeconds > 900) snapshotAnomalyClass = "alert";
      else if (ageSeconds > 300) snapshotAnomalyClass = "warn";
    }

    function makeTileWithTitle(labelKey, value, anomaly, titleAttr) {
      const tile = makeTile(labelKey, value, anomaly);
      if (titleAttr) tile.querySelector(".diag-tile-value").title = titleAttr;
      return tile;
    }

    const kpiGrid = document.createElement("dl");
    kpiGrid.className = "diag-kpi-grid";
    kpiGrid.append(
      makeTile("sqliteConnections", formatCount(connections), connections > 5 ? "warn" : null),
      makeTile("sqliteContentionFailures", formatCount(contentionFailures), contentionFailures > 0 ? "alert" : null),
      makeTile("telemetryRejected", formatCount(rejected), rejected > 0 ? "warn" : null),
      makeTile("reconciliationCount", formatCount(reconciliationCount), null),
      makeTileWithTitle("lastSnapshot", snapshotDisplay, snapshotAnomalyClass, snapshotIso),
      makeTile("sqliteWaitAverage", formatMs(waitAvg), waitAvg > 200 ? "alert" : waitAvg > 50 ? "warn" : null),
    );

    // -- Section builder (detail grid) --
    function makeSection(headingKey, definitions, values) {
      if (!values) return null;
      const hasData = definitions.some(({ key }) => values[key] != null);
      if (!hasData) return null;
      const section = document.createElement("div");
      section.className = "diag-section";
      const heading = document.createElement("h4");
      heading.className = "diag-section-heading";
      heading.textContent = t(headingKey);
      const grid = document.createElement("dl");
      grid.className = "diag-detail-grid";
      definitions.forEach(({ key, labelKey, format }) => {
        const raw = values[key];
        if (raw == null) return;
        const cell = document.createElement("div");
        const term = document.createElement("dt");
        term.textContent = t(labelKey);
        const detail = document.createElement("dd");
        detail.textContent = format ? format(raw) : String(raw);
        cell.append(term, detail);
        grid.append(cell);
      });
      section.append(heading, grid);
      return section;
    }

    // -- Ingestion Topics --
    function makeTopicsTable(byTopic) {
      const topics = Object.entries(byTopic).sort(([a], [b]) => a.localeCompare(b));
      if (!topics.length) return "";
      const rows = topics.map(([topic, v]) => {
        const rej = Number(v.rejected || 0);
        const rejClass = rej > 0 ? ' class="diag-topic-anomaly"' : "";
        return `<tr>
          <td>${escapeHtml(topic)}</td>
          <td>${formatCount(v.accepted)}</td>
          <td${rejClass}>${formatCount(v.rejected)}</td>
          <td>${formatCount(v.duplicates)}</td>
          <td>${formatCount(v.out_of_order)}</td>
        </tr>`;
      }).join("");
      return `<div class="diag-topics-scroll" tabindex="0" role="region" aria-label="${escapeHtml(t("telemetryTopic"))}">
        <table class="diag-topics-table">
          <thead><tr>
            <th>${escapeHtml(t("telemetryTopic"))}</th>
            <th>${escapeHtml(t("telemetryAccepted"))}</th>
            <th>${escapeHtml(t("telemetryRejected"))}</th>
            <th>${escapeHtml(t("telemetryDuplicates"))}</th>
            <th>${escapeHtml(t("telemetryOld"))}</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
    }

    const byTopic = telemetry.by_topic || {};
    let topicsSection = null;
    if (Object.keys(byTopic).length) {
      topicsSection = document.createElement("div");
      topicsSection.className = "diag-section";
      const topicsHeading = document.createElement("h4");
      topicsHeading.className = "diag-section-heading";
      topicsHeading.textContent = t("telemetryTopicDiagnostics");
      topicsSection.append(topicsHeading);
      topicsSection.insertAdjacentHTML("beforeend", makeTopicsTable(byTopic));
    }

    // -- Domain Freshness --
    const domains = result.domains || {};
    const domainEntries = Object.entries(domains);
    let domainsSection = null;
    if (domainEntries.length) {
      domainsSection = document.createElement("div");
      domainsSection.className = "diag-section";
      const domainsHeading = document.createElement("h4");
      domainsHeading.className = "diag-section-heading";
      domainsHeading.textContent = t("domainFreshness");
      const domainList = document.createElement("div");
      domainList.className = "diag-domain-list";
      domainEntries.forEach(([name, info]) => {
        const row = document.createElement("div");
        row.className = "diag-domain-row";
        const nameEl = document.createElement("span");
        nameEl.className = "diag-domain-name";
        nameEl.textContent = name;
        const badge = document.createElement("span");
        badge.className = `badge ${info.stale ? "freshness-stale" : "freshness-fresh"}`;
        badge.textContent = info.stale ? t("domainStale") : t("domainFresh");
        const age = document.createElement("span");
        age.className = "diag-domain-age muted";
        age.textContent = formatAge(info.age_seconds);
        row.append(nameEl, badge, age);
        domainList.append(row);
      });
      domainsSection.append(domainsHeading, domainList);
    }

    // -- Runtime & Reconciliation --
    const runtimeSection = makeSection("diagRuntimeSection", [
      { key: "refreshing", labelKey: "runtimeRefreshing", format: (v) => v ? t("yes") : t("no") },
      { key: "pending_gamerule_refreshes", labelKey: "pendingGameruleRefreshes" },
      { key: "gamerule_worker_running", labelKey: "gameruleWorkerRunning", format: (v) => v ? t("yes") : t("no") },
      { key: "snapshot_running", labelKey: "snapshotRunning", format: (v) => v ? t("yes") : t("no") },
      { key: "count", labelKey: "reconciliationCount" },
      { key: "duration_ms_total", labelKey: "reconciliationDurationTotal", format: formatMs },
      { key: "duration_ms_max", labelKey: "reconciliationDurationMax", format: formatMs },
      { key: "duration_ms_last", labelKey: "reconciliationDurationLast", format: formatMs },
    ], { ...runtime, ...reconciliation });

    // -- SQLite Persistence --
    const sqliteSection = makeSection("persistenceDiagnostics", [
      { key: "connections", labelKey: "sqliteConnections" },
      { key: "wait_ms_average", labelKey: "sqliteWaitAverage", format: formatMs },
      { key: "wait_ms_max", labelKey: "sqliteWaitMax", format: formatMs },
      { key: "contention_failures", labelKey: "sqliteContentionFailures" },
      { key: "retries", labelKey: "sqliteRetries" },
      { key: "database_size_bytes", labelKey: "sqliteDatabaseSize", format: formatBytes },
    ], persistence);

    // -- Telemetry State --
    const telemetrySection = makeSection("telemetryDetails", [
      { key: "status", labelKey: "diagnosticStatus" },
      { key: "sequence", labelKey: "telemetrySequence" },
      { key: "expected_sequence", labelKey: "expectedSequence" },
      { key: "gap_count", labelKey: "detectedGaps" },
      { key: "missing_events", labelKey: "missingEvents" },
      { key: "reset_count", labelKey: "resetCount" },
      { key: "last_snapshot_at", labelKey: "lastSnapshot", format: formatDate },
      { key: "last_event_at", labelKey: "lastResponse", format: formatDate },
    ], telemetryState);

    // -- Key Metrics heading --
    const kpiSection = document.createElement("div");
    kpiSection.className = "diag-section";
    const kpiHeading = document.createElement("h4");
    kpiHeading.className = "diag-section-heading";
    kpiHeading.textContent = t("diagKeyMetrics");
    kpiSection.append(kpiHeading, kpiGrid);

    // -- Assemble --
    const children = [toolbar, kpiSection];
    if (topicsSection) children.push(topicsSection);
    if (domainsSection) children.push(domainsSection);
    if (runtimeSection) children.push(runtimeSection);
    if (sqliteSection) children.push(sqliteSection);
    if (telemetrySection) children.push(telemetrySection);
    target.replaceChildren(...children);
  } catch (_) {
    if (existingBtn) existingBtn.disabled = false;
    else target.textContent = "";
  }
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

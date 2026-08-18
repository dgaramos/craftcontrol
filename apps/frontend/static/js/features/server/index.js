export function createServerFeature({ state, content, t, api, $, escapeHtml, uiIcon, formatDate, toast, getSettingsFeature }) {
function telemetryPackMarkup() {
  return `<section class="telemetry-pack-card block-panel"><div><span class="eyebrow">CRAFTCONTROL</span><h3>${t("telemetryPack")}</h3><p>${t("telemetryPackHelp")}</p></div><div id="telemetry-pack-state" class="telemetry-pack-state">${t("checking")}</div></section>`;
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


  const renderServer = () => {
    getSettingsFeature().renderSettingsGroups(["Packs", "Rede", "Avançado"], telemetryPackMarkup());
    loadTelemetryPack();
  };
  return { renderServer, renderReleaseTags, loadFrontendVersion };
}


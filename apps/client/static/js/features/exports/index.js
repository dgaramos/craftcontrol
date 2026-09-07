/**
 * Export controls (issue #272).
 *
 * Owner-only panel over the export endpoints from #270 and #271. The panel only
 * offers scopes the API accepts: a resource that needs a player keeps the button
 * disabled until one is given, and a resource without a period never shows one.
 * A refusal is read from the response and explained; it never becomes a file.
 */

const PLAYER_RESOURCES = ["profiles", "sessions", "activity", "deaths"];
const ANALYTICS_RESOURCES = ["rankings", "periods", "blocks", "combat", "exploration"];
// Filters each resource accepts, mirroring the API's own allowlists.
const NEEDS_PLAYER = new Set(["sessions"]);
const PLAYER_PERIODS = new Set(["activity", "deaths"]);
const ANALYTICS_PERIODS = new Set(["periods"]);

export function createExportsFeature({ state, content, t, $, escapeHtml, toast, download }) {
  let family = "players";
  let resource = "profiles";
  let format = "json";
  let player = "";
  let days = 0;
  let limit = 10;
  let busy = false;

  const resources = () => (family === "players" ? PLAYER_RESOURCES : ANALYTICS_RESOURCES);
  const supportsPlayer = () => family === "players" && resource !== "profiles";
  const supportsPeriod = () =>
    family === "players" ? PLAYER_PERIODS.has(resource) : ANALYTICS_PERIODS.has(resource);
  const supportsLimit = () => family === "analytics";
  const missingPlayer = () => NEEDS_PLAYER.has(resource) && !player.trim();

  function periodOptions() {
    return family === "players" ? [0, 7, 30] : [7, 30];
  }

  function exportUrl() {
    const params = new URLSearchParams({ format });
    if (supportsPlayer() && player.trim()) params.set("player", player.trim());
    if (supportsPeriod()) params.set("days", String(days));
    if (supportsLimit()) params.set("limit", String(limit));
    return `/api/exports/${family}/${resource}?${params}`;
  }

  function render() {
    const options = (values, selected, labeller) => values
      .map((value) => `<option value="${escapeHtml(String(value))}" ${value === selected ? "selected" : ""}>${escapeHtml(labeller(value))}</option>`)
      .join("");

    content.innerHTML = `
      <section class="settings-screen exports-screen">
        <header class="inner-heading">
          <span class="eyebrow">${t("administration")}</span>
          <h2>${t("exportTitle")}</h2>
          <p>${t("exportHelp")}</p>
        </header>
        <div class="block-panel card">
          <div class="field">
            <div class="field-copy"><label for="export-family">${t("exportFamily")}</label></div>
            <div class="segmented" id="export-family-control">
              <button type="button" class="segment ${family === "players" ? "active" : ""}" data-export-family="players">${t("navPlayers")}</button>
              <button type="button" class="segment ${family === "analytics" ? "active" : ""}" data-export-family="analytics">${t("analytics")}</button>
            </div>
          </div>
          <div class="field">
            <div class="field-copy">
              <label for="export-resource">${t("exportResource")}</label>
              <p>${t(`exportResource_${resource}`)}</p>
            </div>
            <select id="export-resource">${options(resources(), resource, (value) => t(`exportResourceName_${value}`))}</select>
          </div>
          <div class="field">
            <div class="field-copy"><label for="export-format">${t("exportFormat")}</label></div>
            <div class="segmented" id="export-format-control">
              <button type="button" class="segment ${format === "json" ? "active" : ""}" data-export-format="json">JSON</button>
              <button type="button" class="segment ${format === "csv" ? "active" : ""}" data-export-format="csv">CSV</button>
            </div>
          </div>
          ${supportsPlayer() ? `
          <div class="field">
            <div class="field-copy">
              <label for="export-player">${t("exportPlayer")}</label>
              <p>${NEEDS_PLAYER.has(resource) ? t("exportPlayerRequired") : t("exportPlayerOptional")}</p>
            </div>
            <input id="export-player" type="text" maxlength="64" value="${escapeHtml(player)}" placeholder="${t("exportPlayerPlaceholder")}">
          </div>` : ""}
          ${supportsPeriod() ? `
          <div class="field">
            <div class="field-copy"><label for="export-days">${t("periodFilter")}</label></div>
            <select id="export-days">${options(periodOptions(), days, (value) => value === 0 ? t("lifetime") : t(value === 7 ? "last7Days" : "last30Days"))}</select>
          </div>` : ""}
          ${supportsLimit() ? `
          <div class="field">
            <div class="field-copy">
              <label for="export-limit">${t("exportLimit")}</label>
              <p>${t("exportLimitHelp")}</p>
            </div>
            <input id="export-limit" type="number" min="1" max="25" value="${limit}">
          </div>` : ""}
        </div>
        <p class="export-notice">${t("exportPrivacyNotice")}</p>
        <p class="export-notice">${t("exportLimitNotice")}</p>
        <div class="export-actions">
          <button id="export-download" class="primary" type="button" ${missingPlayer() || busy ? "disabled" : ""}>
            ${busy ? t("exportRunning") : t("exportDownload")}
          </button>
          ${missingPlayer() ? `<small class="export-blocked" role="status">${t("exportPlayerRequired")}</small>` : ""}
        </div>
      </section>`;
    bind();
  }

  function bind() {
    content.querySelectorAll("[data-export-family]").forEach((button) => {
      button.onclick = () => {
        family = button.dataset.exportFamily;
        resource = resources()[0];
        days = family === "players" ? 0 : 7;
        render();
      };
    });
    content.querySelectorAll("[data-export-format]").forEach((button) => {
      button.onclick = () => { format = button.dataset.exportFormat; render(); };
    });
    const resourceSelect = $("#export-resource");
    if (resourceSelect) resourceSelect.onchange = () => {
      resource = resourceSelect.value;
      if (!supportsPeriod()) days = family === "players" ? 0 : 7;
      render();
    };
    const playerInput = $("#export-player");
    if (playerInput) playerInput.oninput = () => {
      const blocked = missingPlayer();
      player = playerInput.value;
      // Re-render only when the button's availability actually changes, so the
      // field does not lose focus on every keystroke.
      if (blocked !== missingPlayer()) render();
    };
    const daysSelect = $("#export-days");
    if (daysSelect) daysSelect.onchange = () => { days = Number(daysSelect.value); };
    const limitInput = $("#export-limit");
    if (limitInput) limitInput.onchange = () => { limit = Number(limitInput.value); };
    const button = $("#export-download");
    if (button) button.onclick = runExport;
  }

  async function runExport() {
    if (busy || missingPlayer()) return;
    busy = true;
    render();
    try {
      await download(exportUrl());
      toast(t("exportReady"));
    } catch (error) {
      toast(exportError(error), true);
    } finally {
      busy = false;
      render();
    }
  }

  function exportError(error) {
    // A refusal names the ceiling it hit; everything else keeps the server text.
    if (error?.payload?.limit) {
      return t("exportTooLarge", error.payload.measured, error.payload.allowed);
    }
    if (error?.status === 403) return t("exportForbidden");
    return error?.message || t("exportFailed");
  }

  function renderExportsPanel() {
    render();
  }

  return { renderExportsPanel, exportUrl, exportError };
}

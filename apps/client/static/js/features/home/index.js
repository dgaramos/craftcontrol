export function createHomeFeature({ state, content, t, uiIcon, getSettingsFeature, openTimeControls }) {
  function render() {
    const modes = ["survival", "creative", "adventure"];
    const selected = state.changes.GAMEMODE || state.config.GAMEMODE || "survival";
    content.innerHTML = `
      <section class="home-dashboard" aria-label="${t("quickActions")}">
        <button class="home-time-action" type="button" data-home-time>
          <span class="home-action-icon">${uiIcon("sun")}</span>
          <span><strong>${t("homeTimeAction")}</strong></span>
        </button>
        <section class="home-mode-card block-panel">
          <div class="home-mode-heading"><span>${uiIcon("world")}</span><strong>${t("gameModeLabel")}</strong><small>${Object.keys(state.changes).length ? t("restartRequired") : ""}</small></div>
          <div class="home-game-modes" role="group" aria-label="${t("gameModeLabel")}">
            ${modes.map((mode) => `<button type="button" aria-label="${t(mode)}" title="${t(mode)}" data-home-gamemode="${mode}" class="${mode === selected ? "active" : ""}">${mode.slice(0, 1).toUpperCase()}</button>`).join("")}
            <button type="button" class="unavailable" disabled aria-label="${t("spectatorUnavailable")}" title="${t("spectatorUnavailable")}">Sp</button>
          </div>
        </section>
        <div class="home-shortcuts" aria-label="${t("quickActions")}">
          <button type="button" class="home-shortcut rules" data-home-tab="rules"><span>${uiIcon("rules")}</span><span><small>${t("rules")} <b>${t("instant")}</b></small><strong>${t("serverRules")}</strong></span><b>›</b></button>
          <button type="button" class="home-shortcut server" data-home-tab="server"><span>${uiIcon("server")}</span><span><small>${t("server")}</small><strong>${t("serverOperations")}</strong></span><b>›</b></button>
          <button type="button" class="home-shortcut audit" data-home-tab="audit"><span>${uiIcon("audit")}</span><span><small>${t("audit")}</small><strong>${t("recentActivity")}</strong></span><b>›</b></button>
        </div>
      </section>`;
    content.querySelector("[data-home-time]").onclick = openTimeControls;
    content.querySelectorAll("[data-home-gamemode]").forEach((button) => button.onclick = () => {
      state.changes = { ...state.changes, GAMEMODE: button.dataset.homeGamemode };
      getSettingsFeature().updateSaveLabel();
      render();
    });
    content.querySelectorAll("[data-home-tab]").forEach((button) => button.onclick = () => {
      state.tab = button.dataset.homeTab;
    });
  }

  return { render };
}

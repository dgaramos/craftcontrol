export function createHomeFeature({ state, content, t, getSettingsFeature }) {
  function render() {
    const modes = ["survival", "creative", "adventure"];
    const selected = state.changes.GAMEMODE || state.config.GAMEMODE || "survival";
    content.innerHTML = `
      <section class="home-actions block-panel">
        <div><span class="eyebrow">${t("quickActions")}</span><h3>${t("gameModeLabel")}</h3></div>
        <div class="home-game-modes" role="group" aria-label="${t("gameModeLabel")}">
          ${modes.map((mode) => `<button type="button" data-home-gamemode="${mode}" class="${mode === selected ? "active" : ""}">${t(mode)}</button>`).join("")}
        </div>
      </section>
      <section class="home-shortcuts" aria-label="${t("quickActions")}">
        <button type="button" data-home-tab="rules">${t("rules")}</button>
        <button type="button" data-home-tab="server">${t("settings")}</button>
        <button type="button" data-home-tab="audit">${t("audit")}</button>
      </section>`;
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

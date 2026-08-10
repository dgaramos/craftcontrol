import { persistTab } from "./route.js?v=7";

export function createNavigation({ state, $, t, uiIcon, render }) {
  const icons = { home: "home", world: "world", players: "players", analytics: "data", rules: "rules", server: "server" };

  function resetVerticalScroll() {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }

  function renderTabs() {
    const active = state.tab === "__time__" ? "world" : state.tab === "__players__" ? "players" : state.tab;
    const tabs = $("#tabs");
    tabs.innerHTML = state.tabs.map((tab) => `<button class="${tab === active ? "active" : ""}" data-tab="${tab}"><i>${uiIcon(icons[tab])}</i><span>${t(tab === "server" ? "settings" : tab)}</span></button>`).join("");
    tabs.querySelectorAll("button").forEach((button) => button.onclick = () => {
      state.tab = button.dataset.tab === "players" ? "__players__" : button.dataset.tab;
      persistTab(state.tab);
      renderTabs();
      render();
      resetVerticalScroll();
    });
  }

  function openPlayers() {
    state.tab = "__players__";
    persistTab(state.tab);
    renderTabs();
    render();
    resetVerticalScroll();
  }

  return { openPlayers, renderTabs };
}

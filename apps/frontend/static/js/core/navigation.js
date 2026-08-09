export function createNavigation({ state, $, t, uiIcon, render }) {
  const icons = { home: "home", world: "world", players: "players", analytics: "data", rules: "rules", server: "server" };

  function renderTabs() {
    const active = state.tab === "__time__" ? "world" : state.tab === "__players__" ? "players" : state.tab;
    const tabs = $("#tabs");
    tabs.innerHTML = state.tabs.map((tab) => `<button class="${tab === active ? "active" : ""}" data-tab="${tab}"><i>${uiIcon(icons[tab])}</i><span>${t(tab === "server" ? "settings" : tab)}</span></button>`).join("");
    tabs.querySelectorAll("button").forEach((button) => button.onclick = () => {
      state.tab = button.dataset.tab === "players" ? "__players__" : button.dataset.tab;
      renderTabs();
      render();
    });
  }

  function openPlayers() {
    state.tab = "__players__";
    renderTabs();
    render();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return { openPlayers, renderTabs };
}

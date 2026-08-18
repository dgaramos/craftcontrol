import { persistTab } from "./route.js?v=7";

export function createNavigation({ state, $, t, uiIcon }) {
  const icons = { home: "home", world: "world", players: "players", analytics: "data", rules: "rules", server: "server" };

  function resetVerticalScroll() {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }

  function renderTabs() {
    const active = state.tab === "__time__" ? "world" : state.tab === "__players__" ? "players" : state.tab;
    const tabs = $("#tabs");
    tabs.replaceChildren();
    const tpl = $("#tpl-nav-tab");
    state.tabs.forEach((tab) => {
      const clone = tpl.content.cloneNode(true);
      const button = clone.querySelector("button");
      button.className = tab === active ? "active" : "";
      button.dataset.tab = tab;
      button.querySelector("i").innerHTML = uiIcon(icons[tab]); // inline: uiIcon is internal trusted SVG markup
      button.querySelector("span").textContent = t(tab === "server" ? "settings" : tab);
      button.onclick = () => {
        state.tab = button.dataset.tab === "players" ? "__players__" : button.dataset.tab;
        persistTab(state.tab);
        resetVerticalScroll();
      };
      tabs.appendChild(clone);
    });
  }

  function openPlayers() {
    state.tab = "__players__";
    persistTab(state.tab);
    resetVerticalScroll();
  }

  return { openPlayers, renderTabs };
}

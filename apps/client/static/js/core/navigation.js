import { persistTab } from "./route.js?v=7";

export function createNavigation({ state, $, t, uiIcon }) {
  const icons = { home: "home", world: "world", players: "players", analytics: "data", rules: "rules", server: "server", audit: "audit" };

  function resetVerticalScroll() {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }

  function _bottomNavActive() {
    // Maps state.tab to the data-tab value used on #bottom-nav buttons.
    // Internal tabs (world, analytics, rules, audit, __time__) are reached via
    // the top horizontal nav; none of the 3 bottom-nav buttons should appear
    // active for them, so return null.
    if (state.tab === "__players__") return "__players__";
    if (state.tab === "server") return "server";
    if (state.tab === "home") return "home";
    return null;
  }

  function renderBottomNav() {
    const nav = $("#bottom-nav");
    if (!nav) return;
    const active = _bottomNavActive();
    nav.querySelectorAll("button[data-tab]").forEach((btn) => {
      btn.className = btn.dataset.tab === active ? "active" : "";
    });
  }

  // Wire bottom-nav button onclick handlers once on creation.
  (function _initBottomNav() {
    const nav = $("#bottom-nav");
    if (!nav) return;
    nav.querySelectorAll("button[data-tab]").forEach((btn) => {
      btn.onclick = () => {
        state.tab = btn.dataset.tab;
        persistTab(state.tab);
        resetVerticalScroll();
      };
    });
  })();

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
    renderBottomNav();
  }

  function openPlayers() {
    state.tab = "__players__";
    persistTab(state.tab);
    resetVerticalScroll();
  }

  state.subscribe("tab", renderBottomNav);

  return { openPlayers, renderTabs, renderBottomNav };
}

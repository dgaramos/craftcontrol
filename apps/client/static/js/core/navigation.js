import { persistTab } from "./route.js?v=8";
import { resetPanelScroll } from "./dom.js?v=8";

export function createNavigation({ state, $ }) {
  function resetVerticalScroll() {
    resetPanelScroll("auto");
  }

  function _bottomNavActive() {
    // Maps state.tab to the data-tab value used on #bottom-nav buttons.
    // Internal tabs (world, analytics, rules, audit, __time__) are reached via
    // the top horizontal nav; none of the 3 bottom-nav buttons should appear
    // active for them, so return null.
    if (state.tab === "__players__") return "__players__";
    if (["server", "__server_settings__", "__telemetry_pack__"].includes(state.tab)) return "server";
    if (state.tab === "home") return "home";
    return null;
  }

  function renderBottomNav() {
    const nav = $("#bottom-nav");
    if (!nav) return;
    const active = _bottomNavActive();
    nav.querySelectorAll("button[data-tab]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === active);
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

  function openPlayers() {
    state.tab = "__players__";
    persistTab(state.tab);
    resetVerticalScroll();
  }

  state.subscribe("tab", renderBottomNav);

  return { openPlayers, renderBottomNav };
}

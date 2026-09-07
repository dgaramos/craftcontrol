const routes = Object.freeze({
  home: "home",
  world: "world",
  players: "__players__",
  data: "analytics",
  rules: "rules",
  server: "server",
  time: "__time__",
});

const routeForTab = Object.fromEntries(Object.entries(routes).map(([route, tab]) => [tab, route]));

export function tabFromLocation(location = window.location) {
  const route = String(location.hash || "").replace(/^#\/?/, "").split(/[?&]/, 1)[0];
  return routes[route] || "home";
}

export function persistTab(tab, history = window.history, location = window.location) {
  const route = routeForTab[tab] || "home";
  const hash = `#/${route}`;
  if (location.hash !== hash) history.replaceState(null, "", hash);
}

/* Tabs reachable from the bottom nav. Landing on one is a fresh start, so the
   trail resets: the nav is a jump, not a step deeper. */
export const ROOT_TABS = Object.freeze(["home", "__players__", "server"]);

/**
 * Remembers how the user reached an inner screen.
 *
 * Inner screens have more than one entry point — Rules from Home and from the
 * Server hub, Time from Home and from World — so a hard-coded back destination
 * sends them somewhere they never were. The trail records the actual path and
 * unwinds it one step at a time.
 */
export function createNavTrail({ rootTabs = ROOT_TABS, limit = 16 } = {}) {
  const roots = new Set(rootTabs);
  let trail = [];
  let goingBack = false;

  return {
    /** Call on every tab change, with the value that was replaced. */
    record(value, previous) {
      if (goingBack) { goingBack = false; return; }
      if (roots.has(value)) { trail = []; return; }
      if (previous === undefined || previous === null || previous === value) return;
      trail.push(previous);
      if (trail.length > limit) trail.shift();
    },
    /** Where a back affordance would land, without unwinding. */
    peek() {
      return trail[trail.length - 1] || "home";
    },
    /** Unwinds one step and returns the destination. */
    back() {
      const target = trail.pop() || "home";
      goingBack = true;
      return target;
    },
    get depth() {
      return trail.length;
    },
  };
}

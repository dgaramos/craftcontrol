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

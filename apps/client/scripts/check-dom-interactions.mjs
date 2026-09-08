import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { connectInvalidation } from "../static/js/core/invalidation.js";
import { createNavigation } from "../static/js/core/navigation.js";
import { createI18n } from "../static/js/i18n/index.js";
import { createGameTerms } from "../static/js/i18n/game-terms.js";
import { createPlayerTelemetry } from "../static/js/features/players/telemetry.js";
import { createPlayerHistory } from "../static/js/features/players/history.js";
import { sessionMoment } from "../static/js/components/time.js";
import { tabFromLocation } from "../static/js/core/route.js";

global.window = {
  scrollTo: () => {},
  location: { hash: "#/home" },
  history: { replaceState: (_state, _title, hash) => { window.location.hash = hash; } },
};

const state = { tab: "home", tabs: ["home", "players", "analytics"], subscribe: () => {} };

// The shell navigates from the bottom nav; its buttons carry the target tab.
const bottomNavButtons = ["home", "__players__", "server"].map((tab) => ({
  dataset: { tab },
  onclick: null,
  classList: { toggle: () => {} },
}));
const bottomNav = { querySelectorAll: () => bottomNavButtons };
const navigation = createNavigation({
  state,
  $: (selector) => (selector === "#bottom-nav" ? bottomNav : null),
});
assert.ok(typeof navigation.renderBottomNav === "function", "bottom nav must render");

const playersBtn = bottomNavButtons.find((btn) => btn.dataset.tab === "__players__");
playersBtn.onclick();
assert.equal(state.tab, "__players__");
assert.equal(window.location.hash, "#/players");
assert.equal(tabFromLocation({ hash: "#/analytics" }), "home");
assert.equal(tabFromLocation({ hash: "#/data" }), "analytics");

let locale = "pt";
const i18n = createI18n(() => locale);
assert.equal(i18n.t("players"), "Jogadores");
locale = "en";
assert.equal(i18n.t("players"), "Players");
locale = "es";
assert.equal(i18n.t("players"), "Jugadores");

const gameTerms = createGameTerms({ getLocale: () => "pt", escapeHtml: (value) => String(value) });
const playerTelemetry = createPlayerTelemetry({
  state: { locale: "pt" },
  t: (key) => key,
  escapeHtml: (value) => String(value),
  gameTermMarkup: gameTerms.gameTermMarkup,
  blockTermMarkup: gameTerms.blockTermMarkup,
  dimensionName: gameTerms.dimensionName,
  formatRankingValue: (value) => String(value),
  uiIcon: () => "",
  gameIcon: () => "",
  formatDate: () => "agora",
});
assert.match(playerTelemetry.playerDataMarkup({
  name: "Alex",
  telemetry_updated_at: 1,
  telemetry: { dimensions: { overworld: 3 } },
}), /Mundo superior/);

const playerHistory = createPlayerHistory({
  state: { locale: "pt" },
  t: (key) => key,
  escapeHtml: (value) => String(value),
  gameLabel: (value) => String(value),
  gameIcon: () => "",
  gameTermMarkup: (value) => String(value),
  optionLabel: (value) => String(value),
  formatDate: () => "agora",
  formatDuration: () => "1m",
  sessionMoment: (timestamp) => sessionMoment(timestamp, "pt-BR"),
  timelineTimestamp: () => "",
});
assert.match(playerHistory.sessionsMarkup([{ connected_at: 1, disconnected_at: 61, duration_seconds: 60 }]), /<time datetime=/);

let listener;
let loads = 0;
let statuses = 0;
connectInvalidation({
  connectEventStream: (callback) => { listener = callback; },
  loadState: async () => { loads += 1; },
  refreshStatus: async () => ({ online: true }),
  setStatus: () => { statuses += 1; },
  schedule: (callback) => { callback(); return 1; },
  cancel: () => {},
});
listener({ topic: "player.joined" });
assert.equal(loads, 0);
listener({ topic: "state.changed" });
await Promise.resolve();
assert.equal(loads, 1);
listener({ topic: "server.started" });
await new Promise((resolve) => setImmediate(resolve));
assert.equal(loads, 2);
assert.equal(statuses, 1);

const root = new URL("../static/", import.meta.url);
const [auth, settings, players, analytics, css] = await Promise.all([
  readFile(new URL("js/auth.js", root), "utf8"),
  readFile(new URL("js/features/settings/index.js", root), "utf8"),
  readFile(new URL("js/features/players/workspace.js", root), "utf8"),
  readFile(new URL("js/features/analytics/index.js", root), "utf8"),
  readFile(new URL("app.css", root), "utf8"),
]);
assert.match(auth, /password-toggle/);
assert.match(settings, /addEventListener\("change"/);
assert.match(players, /player-roster-open/);
assert.match(analytics, /data-analytics-view/);
assert.match(css, /@media \(max-width:/);

const fetchCalls = [];
global.fetch = async (url, options = {}) => {
  fetchCalls.push({ url, options });
  if (url === "/api/auth/me") return { ok: true, status: 200, json: async () => ({ csrf_token: "fresh-token" }) };
  return { ok: true, status: 200, json: async () => ({ token: "invitation-token" }) };
};
const { api } = await import(`../static/js/api.js?interaction=${Date.now()}`);
await api("/api/auth/access/invite", { method: "POST", body: "{}" });
assert.equal(fetchCalls[0].url, "/api/auth/me");
assert.equal(fetchCalls[1].options.headers["X-CSRF-Token"], "fresh-token");

console.log("DOM interactions: navigation, auth, settings, players, analytics, responsive UI, SSE, i18n");

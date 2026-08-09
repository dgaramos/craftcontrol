import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { connectInvalidation } from "../static/js/core/invalidation.js";
import { createNavigation } from "../static/js/core/navigation.js";
import { createI18n } from "../static/js/i18n/index.js";

global.window = { scrollTo: () => {} };

const state = { tab: "home", tabs: ["home", "players", "analytics"] };
let rendered = 0;
let buttons = [];
const tabs = {
  set innerHTML(value) {
    this.markup = value;
    buttons = state.tabs.map((tab) => ({ dataset: { tab }, onclick: null }));
  },
  querySelectorAll: () => buttons,
};
const navigation = createNavigation({
  state,
  $: (selector) => selector === "#tabs" ? tabs : null,
  t: (key) => key,
  uiIcon: (name) => `<svg data-icon="${name}"></svg>`,
  render: () => { rendered += 1; },
});
navigation.renderTabs();
assert.match(tabs.markup, /data-tab="players"/);
buttons[1].onclick();
assert.equal(state.tab, "__players__");
assert.equal(rendered, 1);

let locale = "pt";
const i18n = createI18n(() => locale);
assert.equal(i18n.t("players"), "Jogadores");
locale = "en";
assert.equal(i18n.t("players"), "Players");
locale = "es";
assert.equal(i18n.t("players"), "Jugadores");

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
assert.match(players, /data-player-index/);
assert.match(analytics, /data-analytics-view/);
assert.match(css, /@media \(max-width:/);

console.log("DOM interactions: navigation, auth, settings, players, analytics, responsive UI, SSE, i18n");

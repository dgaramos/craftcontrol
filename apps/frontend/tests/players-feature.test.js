import { jest } from "@jest/globals";
import { createPlayersWorkspace } from "../static/js/features/players/workspace.js";
import { createPlayersFeature } from "../static/js/features/players/index.js";
import { makeEl, makeTemplateStub } from "./helpers.js";

function makePlayer(overrides = {}) {
  return {
    id: "abc123",
    name: "Alice",
    online: false,
    deaths_count: 2,
    total_play_seconds: 3600,
    operator: false,
    last_seen_at: 1000,
    connected_at: null,
    ...overrides,
  };
}

// Minimal stubs for the three templates used by workspace.js.
function makeWorkspaceTemplateStubs() {
  const overviewStatClone = makeEl({
    querySelector: (sel) => {
      if (sel === "span") {
        const span = makeEl({ querySelector: (s) => (s === "b" ? makeEl() : null), append: jest.fn() });
        return span;
      }
      return makeEl();
    },
  });
  const rosterRowClone = makeEl({
    querySelector: (sel) => {
      const el = makeEl({ classList: { add: jest.fn(), remove: jest.fn(), toggle: jest.fn() }, dataset: {} });
      return el;
    },
  });
  const screenClone = makeEl({
    querySelector: (sel) => makeEl({ placeholder: "" }),
  });
  return {
    "#tpl-players-screen": { content: { cloneNode: () => screenClone } },
    "#tpl-player-overview-stat": { content: { cloneNode: () => overviewStatClone } },
    "#tpl-player-roster-row": { content: { cloneNode: () => rosterRowClone } },
  };
}

function makeWorkspaceDeps(overrides = {}) {
  const elements = {};
  const templateStubs = makeWorkspaceTemplateStubs();
  const state = {
    locale: "en",
    user: { role: "viewer", capabilities: [] },
    ...overrides.state,
  };
  const $ = jest.fn((sel) => {
    if (sel in templateStubs) return templateStubs[sel];
    if (!elements[sel]) elements[sel] = makeEl();
    return elements[sel];
  });
  const content = {
    innerHTML: "",
    querySelector: jest.fn((sel) => {
      if (!elements[sel]) elements[sel] = makeEl();
      return elements[sel];
    }),
    querySelectorAll: jest.fn(() => []),
    replaceChildren: jest.fn(),
    insertAdjacentHTML: jest.fn(),
  };
  const t = (key) => key;
  const localized = (pt, en, es = en) => state.locale === "pt" ? pt : state.locale === "es" ? es : en;
  const api = jest.fn().mockResolvedValue({ players: [] });
  const escapeHtml = (s) => String(s ?? "");
  const toast = jest.fn();
  const playerSettingsMarkup = jest.fn(() => "");
  const bindSegmentedControls = jest.fn();
  const bindSettingFields = jest.fn();
  const formatDuration = (s) => `${s ?? 0}s`;
  const formatDate = (ts) => ts ? "2024-01-01" : "—";
  const renderPlayerDetail = jest.fn();
  return { state, $, content, t, localized, api, escapeHtml, toast, playerSettingsMarkup, bindSegmentedControls, bindSettingFields, formatDuration, formatDate, renderPlayerDetail, elements, ...overrides };
}

// ── workspace.js ──────────────────────────────────────────────────────────────

describe("renderPlayersPanel — happy path", () => {
  test("clones players-screen template into content", async () => {
    const deps = makeWorkspaceDeps();
    const renderPlayersPanel = createPlayersWorkspace(deps);
    await renderPlayersPanel();
    expect(deps.content.replaceChildren).toHaveBeenCalled();
  });

  test("empty player list renders noHistory message", async () => {
    const deps = makeWorkspaceDeps();
    const loadingEl = makeEl();
    deps.content.querySelector = jest.fn(() => loadingEl);
    const renderPlayersPanel = createPlayersWorkspace(deps);
    await renderPlayersPanel();
    expect(loadingEl.textContent).toBe("noHistory");
  });

  test("player list renders player cards", async () => {
    const deps = makeWorkspaceDeps();
    deps.api = jest.fn().mockResolvedValue({ players: [makePlayer()] });
    const loadingEl = makeEl({ className: "loading-players" });
    deps.content.querySelector = jest.fn((sel) => {
      if (sel === ".loading-players") return loadingEl;
      if (sel === ".player-toolbar") return makeEl({ hidden: true });
      return makeEl();
    });
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.content.querySelectorAll = jest.fn((sel) => {
      if (sel === "[data-player-filter]") return [makeEl({ dataset: { playerFilter: "all" } })];
      if (sel === "[data-player-index]") return [makeEl({ dataset: { playerIndex: "0" } })];
      return [];
    });
    const renderPlayersPanel = createPlayersWorkspace(deps);
    await renderPlayersPanel();
    // loadingEl was used as a container and its className changed
    expect(deps.api).toHaveBeenCalledWith("/api/players");
  });

  test("owner role also fetches /api/auth/access", async () => {
    const deps = makeWorkspaceDeps({ state: { locale: "en", user: { role: "owner", capabilities: [] } } });
    deps.api = jest.fn()
      .mockResolvedValueOnce({ players: [makePlayer()] })
      .mockResolvedValueOnce({ players: [] });
    const loadingEl = makeEl();
    deps.content.querySelector = jest.fn(() => loadingEl);
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    const renderPlayersPanel = createPlayersWorkspace(deps);
    await renderPlayersPanel();
    expect(deps.api).toHaveBeenCalledWith("/api/auth/access");
  });

  test("API error sets error message on loading element", async () => {
    const deps = makeWorkspaceDeps();
    deps.api = jest.fn().mockRejectedValue(new Error("server down"));
    const loadingEl = makeEl();
    deps.content.querySelector = jest.fn(() => loadingEl);
    const renderPlayersPanel = createPlayersWorkspace(deps);
    await renderPlayersPanel();
    expect(loadingEl.textContent).toBe("server down");
  });
});

describe("renderPlayersPanel — filters", () => {
  function setupWithPlayers(players) {
    const deps = makeWorkspaceDeps();
    deps.api = jest.fn().mockResolvedValue({ players });
    const filterButtons = [
      makeEl({ dataset: { playerFilter: "all" }, classList: { toggle: jest.fn(), add: jest.fn(), remove: jest.fn() } }),
      makeEl({ dataset: { playerFilter: "online" }, classList: { toggle: jest.fn(), add: jest.fn(), remove: jest.fn() } }),
    ];
    const loadingEl = makeEl();
    deps.content.querySelector = jest.fn((sel) => {
      if (sel === ".loading-players") return loadingEl;
      if (sel === ".player-toolbar") return makeEl({ hidden: true });
      return makeEl();
    });
    deps.content.querySelectorAll = jest.fn((sel) => {
      if (sel === "[data-player-filter]") return filterButtons;
      if (sel === "[data-player-index]") return [];
      return [];
    });
    const searchEl = makeEl({ value: "" });
    deps.$ = jest.fn((sel) => {
      if (sel === "#player-search") return searchEl;
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    return { deps, filterButtons, searchEl };
  }

  test("#player-search oninput is registered", async () => {
    const { deps, searchEl } = setupWithPlayers([makePlayer()]);
    const renderPlayersPanel = createPlayersWorkspace(deps);
    await renderPlayersPanel();
    expect(typeof searchEl.oninput).toBe("function");
  });

  test("filter button onclick is registered", async () => {
    const { deps, filterButtons } = setupWithPlayers([makePlayer()]);
    const renderPlayersPanel = createPlayersWorkspace(deps);
    await renderPlayersPanel();
    expect(typeof filterButtons[0].onclick).toBe("function");
  });
});

// ── index.js ─────────────────────────────────────────────────────────────────

describe("createPlayersFeature — factory wiring", () => {
  function makeFullDeps() {
    const state = { locale: "en", user: { role: "viewer", capabilities: [] }, analytics: { kind: "all", player: "", page: 1 }, tab: "players" };
    const $ = jest.fn(() => makeEl());
    const content = { innerHTML: "", querySelector: jest.fn(() => makeEl()), querySelectorAll: jest.fn(() => []) };
    const t = (key) => key;
    const localized = (pt, en, es = en) => state.locale === "pt" ? pt : state.locale === "es" ? es : en;
    const api = jest.fn().mockResolvedValue({ players: [] });
    const escapeHtml = (s) => String(s ?? "");
    const toast = jest.fn();
    const playerSettingsMarkup = jest.fn(() => "");
    const bindSegmentedControls = jest.fn();
    const bindSettingFields = jest.fn();
    const formatDuration = (s) => `${s}s`;
    const formatDate = () => "2024-01-01";
    const renderAnalyticsPanel = jest.fn();
    const renderTabs = jest.fn();
    const updateToggleLabel = jest.fn();
    const booleanControl = jest.fn(() => "");
    const panelAccessDetailMarkup = jest.fn(() => "");
    const bindPlayerAccess = jest.fn();
    const playerDataMarkup = jest.fn(() => "");
    const profileMarkup = jest.fn(() => "");
    const gameLabel = jest.fn((k) => k);
    const gameIcon = jest.fn(() => "");
    const gameTermMarkup = jest.fn((v) => String(v));
    const optionLabel = jest.fn((v) => v);
    const sessionMoment = jest.fn(() => "");
    const timelineTimestamp = jest.fn(() => "");
    const blockTermMarkup = jest.fn((v) => String(v));
    const blockIcon = jest.fn(() => "");
    const oreLabel = jest.fn((v) => v);
    const dimensionName = jest.fn((v) => String(v));
    const formatRankingValue = jest.fn((v) => String(v));
    const uiIcon = jest.fn(() => "");
    return {
      state, $, content, t, localized, api, escapeHtml, toast, playerSettingsMarkup, bindSegmentedControls,
      bindSettingFields, formatDuration, formatDate, renderAnalyticsPanel, renderTabs,
      updateToggleLabel, booleanControl, panelAccessDetailMarkup, bindPlayerAccess,
      playerDataMarkup, profileMarkup, gameLabel, gameIcon, gameTermMarkup, optionLabel,
      sessionMoment, timelineTimestamp, blockTermMarkup, blockIcon, oreLabel, dimensionName,
      formatRankingValue, uiIcon,
    };
  }

  test("returns renderPlayersPanel and renderPlayerDetail as functions", () => {
    const deps = makeFullDeps();
    const feature = createPlayersFeature(deps);
    expect(typeof feature.renderPlayersPanel).toBe("function");
    expect(typeof feature.renderPlayerDetail).toBe("function");
  });
});

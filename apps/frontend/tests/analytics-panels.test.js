import { jest } from "@jest/globals";
import { createCombatPanel } from "../static/js/features/analytics/combat.js";
import { createExplorationPanel } from "../static/js/features/analytics/exploration.js";
import { createTrendsPanel } from "../static/js/features/analytics/trends.js";
import { makeEl } from "./helpers.js";


function makeSharedDeps(stateOverrides = {}) {
  const elements = {};
  const $ = jest.fn((sel) => {
    if (!elements[sel]) elements[sel] = makeEl();
    return elements[sel];
  });
  const state = {
    locale: "en",
    analytics: {
      combatMetric: "mob_kills",
      explorationMetric: "distance",
      periodDays: 30,
      periodMetric: "play_seconds",
      ...stateOverrides,
    },
  };
  const content = { renderedMarkup: "", children: [], replaceChildren(...children) { this.children = children; this.renderedMarkup = children.filter((child) => typeof child === "string").join(""); }, querySelectorAll: jest.fn(() => []) };
  Object.defineProperty(content, "innerHTML", { get: () => content.renderedMarkup, set: (value) => { content.renderedMarkup = String(value); } });
  const t = (key) => key === "weekdayShort" ? ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] : key;
  const uiIcon = (name) => `<svg icon="${name}"/>`;
  const escapeHtml = (s) => String(s ?? "").replace(/</g, "&lt;");
  const gameTermMarkup = (v) => `<span>${String(v)}</span>`;
  const timelineTimestamp = (ts) => ts ? `<time>${ts}</time>` : "<span>—</span>";
  const formatRankingValue = (v, fmt) => String(v ?? 0);
  const formatDate = (ts) => ts ? "2024-01-01" : "—";
  const formatDuration = (s) => `${s ?? 0}s`;
  const dimensionName = (v) => String(v);
  const localeTag = () => "en-US";
  const analyticsViewSwitch = jest.fn(() => "");
  const bindAnalyticsViewSwitch = jest.fn();
  const openAnalyticsPlayer = jest.fn();
  const api = jest.fn().mockRejectedValue(new Error("no api"));
  return { state, content, t, uiIcon, escapeHtml, gameTermMarkup, timelineTimestamp, formatRankingValue, formatDate, formatDuration, dimensionName, localeTag, analyticsViewSwitch, bindAnalyticsViewSwitch, openAnalyticsPlayer, api, $, elements };
}

// ── combat.js ────────────────────────────────────────────────────────────────

describe("renderCombatPanel — happy path", () => {
  function combatResult(overrides = {}) {
    return {
      totals: { mob_kills: 10, player_kills: 2, deaths: 5, damage_dealt: 100.5, damage_taken: 80.0 },
      rankings: { mob_kills: [{ player: { id: "1", name: "Alice" }, value: 10 }] },
      breakdowns: { causes: [{ key: "fall", count: 3 }], opponents: [], projectiles: [] },
      pvp: [{ attacker: { id: "1", name: "Alice" }, victim: { id: "2", name: "Bob" }, count: 1 }],
      players: [{ player: { id: "1", name: "Alice" }, mob_kills: 5, player_kills: 1, deaths: 2, telemetry_available: true, updated_at: 1000, favorite_target: null }],
      top_targets: [],
      generated_at: 1000,
      ...overrides,
    };
  }

  test("content.innerHTML contains combat-screen", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockResolvedValue(combatResult());
    deps.elements["#combat-content"] = makeEl();
    const render = createCombatPanel(deps);
    await render();
    expect(deps.content.innerHTML).toContain("combat-screen");
  });

  test("combat target innerHTML is set after api resolves", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => {
      if (sel === "#combat-content") return target;
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn().mockResolvedValue(combatResult());
    const render = createCombatPanel(deps);
    await render();
    expect(target.innerHTML).toContain("combat-summary");
  });

  test("empty breakdowns renders noCombatEvidence zero state", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#combat-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue(combatResult({ breakdowns: { causes: [], opponents: [], projectiles: [] } }));
    const render = createCombatPanel(deps);
    await render();
    expect(target.innerHTML).toContain("noCombatEvidence");
  });

  test("breakdowns with entries renders ordered list", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#combat-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue(combatResult({
      breakdowns: { causes: [{ key: "fall", count: 5 }], opponents: [], projectiles: [] },
    }));
    const render = createCombatPanel(deps);
    await render();
    expect(target.innerHTML).toContain("fall");
  });

  test("pvp with entries renders duel rows", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#combat-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue(combatResult());
    const render = createCombatPanel(deps);
    await render();
    expect(target.innerHTML).toContain("Alice");
    expect(target.innerHTML).toContain("Bob");
  });

  test("player with telemetry_available renders structured source label", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#combat-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue(combatResult({
      players: [{ player: { id: "1", name: "Alice" }, mob_kills: 5, player_kills: 0, deaths: 0, telemetry_available: true, updated_at: 1000, favorite_target: null }],
    }));
    const render = createCombatPanel(deps);
    await render();
    expect(target.innerHTML).toContain("sourceStructured");
  });

  test("API error renders error message in target", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#combat-content" ? target : makeEl());
    deps.api = jest.fn().mockRejectedValue(new Error("network fail"));
    const render = createCombatPanel(deps);
    await render();
    expect(target.innerHTML).toContain("network fail");
  });
});

// ── exploration.js ────────────────────────────────────────────────────────────

describe("renderExplorationPanel — happy path", () => {
  function explorationResult(overrides = {}) {
    return {
      totals: { distance: 1000, dimensions: 2, dimension_visits: 5, active_seconds: 300, play_seconds: 600, sessions: 3 },
      rankings: { distance: [{ player: { id: "1", name: "Alice" }, value: 1000 }] },
      dimensions: [{ dimension: "overworld", distance: 1000, active_seconds: 300, first_seen_at: 1000, last_seen_at: 2000 }],
      transitions: [{ player: { id: "1", name: "Alice" }, from: "overworld", to: "nether", timestamp: 1500 }],
      players: [],
      generated_at: 1000,
      ...overrides,
    };
  }

  test("content.innerHTML contains exploration-screen", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockResolvedValue(explorationResult());
    deps.elements["#exploration-content"] = makeEl();
    const render = createExplorationPanel(deps);
    await render();
    expect(deps.content.innerHTML).toContain("exploration-screen");
  });

  test("empty ranking renders zero state", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#exploration-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue(explorationResult({ rankings: { distance: [] } }));
    const render = createExplorationPanel(deps);
    await render();
    expect(target.innerHTML).toContain("noExplorationEvidence");
  });

  test("ranking with entries renders leaderboard", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#exploration-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue(explorationResult());
    const render = createExplorationPanel(deps);
    await render();
    expect(target.innerHTML).toContain("Alice");
  });

  test("dimensions with entries renders dimension cards", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#exploration-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue(explorationResult());
    const render = createExplorationPanel(deps);
    await render();
    expect(target.innerHTML).toContain("overworld");
  });

  test("transitions with entries renders journey list", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#exploration-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue(explorationResult());
    const render = createExplorationPanel(deps);
    await render();
    expect(target.innerHTML).toContain("nether");
  });

  test("API error renders error message", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#exploration-content" ? target : makeEl());
    deps.api = jest.fn().mockRejectedValue(new Error("exploration api fail"));
    const render = createExplorationPanel(deps);
    await render();
    expect(target.innerHTML).toContain("exploration api fail");
  });
});

// ── trends.js ────────────────────────────────────────────────────────────────

describe("renderTrendsPanel — happy path", () => {
  function trendsResult(overrides = {}) {
    return {
      totals: { play_seconds: 3600, sessions: 5, blocks_broken: 100, blocks_placed: 50, mob_kills: 20, player_kills: 1, deaths: 3 },
      rankings: { play_seconds: [{ player: { id: "1", name: "Alice" }, value: 3600 }] },
      calendar: [{ day: "2024-01-15", play_seconds: 1800, sessions: 2 }],
      heatmap: [{ weekday: 1, hour: 14, seconds: 600 }],
      most_active_day: { day: "2024-01-15" },
      timezone: "UTC",
      generated_at: 1000,
      ...overrides,
    };
  }

  test("content.innerHTML contains trends-screen", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockResolvedValue(trendsResult());
    deps.elements["#trends-content"] = makeEl();
    deps.content.querySelectorAll = jest.fn(() => []);
    const render = createTrendsPanel(deps);
    await render();
    expect(deps.content.innerHTML).toContain("trends-screen");
  });

  test("calendarDate is exercised via most_active_day", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#trends-content" ? target : makeEl());
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.api = jest.fn().mockResolvedValue(trendsResult());
    const render = createTrendsPanel(deps);
    await render();
    // most_active_day.day = "2024-01-15" → calendarDate renders a date string
    expect(target.innerHTML).toContain("mostActiveDay");
  });

  test("heatmap with entries renders grid rows", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#trends-content" ? target : makeEl());
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.api = jest.fn().mockResolvedValue(trendsResult());
    const render = createTrendsPanel(deps);
    await render();
    expect(target.innerHTML).toContain("level-");
  });

  test("empty calendar renders gracefully", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#trends-content" ? target : makeEl());
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.api = jest.fn().mockResolvedValue(trendsResult({ calendar: [], heatmap: [] }));
    const render = createTrendsPanel(deps);
    await render();
    expect(target.innerHTML).toContain("trends-summary");
  });

  test("API error renders error message", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    deps.$ = jest.fn((sel) => sel === "#trends-content" ? target : makeEl());
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.api = jest.fn().mockRejectedValue(new Error("trends api fail"));
    const render = createTrendsPanel(deps);
    await render();
    expect(target.innerHTML).toContain("trends api fail");
  });

  test("switching periods reloads the trends data and marks the selected period", async () => {
    const deps = makeSharedDeps({ periodDays: 30 });
    const target = makeEl();
    const sevenDays = makeEl({ dataset: { periodDays: "7" }, classList: { toggle: jest.fn() } });
    const thirtyDays = makeEl({ dataset: { periodDays: "30" }, classList: { toggle: jest.fn() } });
    deps.$ = jest.fn((selector) => selector === "#trends-content" ? target : makeEl());
    deps.content.querySelectorAll = jest.fn((selector) => selector === "[data-period-days]" ? [sevenDays, thirtyDays] : []);
    deps.api = jest.fn().mockResolvedValue(trendsResult());

    await createTrendsPanel(deps)();
    sevenDays.onclick();
    await Promise.resolve();

    expect(deps.state.analytics.periodDays).toBe(7);
    expect(sevenDays.classList.toggle).toHaveBeenCalledWith("active", true);
    expect(thirtyDays.classList.toggle).toHaveBeenCalledWith("active", false);
    expect(deps.api).toHaveBeenLastCalledWith("/api/analytics/periods?days=7&limit=10");
  });

  test("renders calendar and heatmap values through DOM properties", async () => {
    const deps = makeSharedDeps();
    const target = makeEl();
    const calendar = makeEl({ append: jest.fn() });
    const heatmap = makeEl({ append: jest.fn() });
    target.querySelector = jest.fn((selector) => selector.includes("calendar") ? calendar : heatmap);
    deps.$ = jest.fn((sel) => sel === "#trends-content" ? target : makeEl());
    deps.content.querySelectorAll = jest.fn(() => []);
    deps.api = jest.fn().mockResolvedValue(trendsResult({
      calendar: [{ day: "2024-01-15", play_seconds: "bad", sessions: Infinity }],
      heatmap: [{ weekday: 1, hour: 14, seconds: NaN }, { weekday: 1, hour: 99, seconds: 20 }],
    }));
    const created = [];
    const previousDocument = globalThis.document;
    globalThis.document = {
      createRange: () => ({ createContextualFragment: () => ({}) }),
      createElement: (tag) => {
        const element = { tagName: tag, children: [], append(child) { this.children.push(child); }, textContent: "", className: "", title: "" };
        created.push(element);
        return element;
      },
    };
    try {
      await createTrendsPanel(deps)();
      expect(calendar.append).toHaveBeenCalled();
      expect(heatmap.append).toHaveBeenCalled();
      expect(created.some((node) => node.className === "level-0")).toBe(true);
      expect(created.some((node) => node.title.includes("14:00"))).toBe(true);
      expect(created.some((node) => node.title.includes("99"))).toBe(false);
    } finally {
      globalThis.document = previousDocument;
    }
  });
});

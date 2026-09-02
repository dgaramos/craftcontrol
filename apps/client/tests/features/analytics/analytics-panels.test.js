import { jest } from "@jest/globals";
import { createCombatPanel } from "../../../static/js/features/analytics/combat.js";
import { createExplorationPanel } from "../../../static/js/features/analytics/exploration.js";
import { createTrendsPanel } from "../../../static/js/features/analytics/trends.js";
import { createHealthPanel } from "../../../static/js/features/analytics/health.js";
import { findNodes, makeDom, makeEl } from "../../helpers.js";


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

  let savedDocument;

  beforeEach(() => {
    savedDocument = global.document;
    global.document = makeDom().document;
  });

  afterEach(() => {
    global.document = savedDocument;
  });

  test("renders API values through safe DOM properties", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockResolvedValue(trendsResult());

    await createTrendsPanel(deps)();

    const screen = deps.content.children[0];
    expect(screen.className).toBe("trends-screen");
    expect(findNodes(screen, (node) => node.textContent === "Alice")).toHaveLength(1);
    expect(findNodes(screen, (node) => node.className === "level-4").length).toBeGreaterThan(0);
  });

  test("keeps malformed values as safe zero-level DOM values", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockResolvedValue(trendsResult({
      rankings: { play_seconds: [{ player: { id: '<img src=x>', name: '<script>bad</script>' }, value: Infinity }] },
      calendar: [{ day: "2024-01-15", play_seconds: "bad", sessions: Infinity }],
      heatmap: [{ weekday: 1, hour: 14, seconds: NaN }, { weekday: 1, hour: 99, seconds: 20 }],
    }));

    await createTrendsPanel(deps)();

    const screen = deps.content.children[0];
    const malicious = findNodes(screen, (node) => node.textContent === "<script>bad</script>")[0];
    expect(malicious.tagName).toBe("button");
    expect(findNodes(screen, (node) => node.title?.includes("99:00"))).toHaveLength(0);
    expect(findNodes(screen, (node) => node.className === "level-0").length).toBeGreaterThan(0);
  });

  test("renders empty ranking and calendar without invalid classes", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockResolvedValue(trendsResult({ rankings: { play_seconds: [] }, calendar: [], heatmap: [] }));

    await createTrendsPanel(deps)();

    const screen = deps.content.children[0];
    expect(findNodes(screen, (node) => node.className === "trends-zero")).toHaveLength(1);
    expect(findNodes(screen, (node) => node.className.includes("level-NaN"))).toHaveLength(0);
  });

  test("normalizes an absent or malformed periods response", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockResolvedValue(null);

    await createTrendsPanel(deps)();

    const screen = deps.content.children[0];
    expect(findNodes(screen, (node) => node.className === "trends-zero")).toHaveLength(1);
    expect(findNodes(screen, (node) => node.textContent === "—").length).toBeGreaterThan(0);
  });

  test("keeps partial collections and invalid dates safe", async () => {
    const deps = makeSharedDeps();
    deps.t = (key) => key === "weekdayShort" ? "not-a-list" : key;
    deps.api = jest.fn().mockResolvedValue({
      rankings: { play_seconds: {} }, calendar: [{ day: null, play_seconds: -1, sessions: -1 }], heatmap: {}, totals: "invalid", timezone: null,
      most_active_day: { day: null }, generated_at: null,
    });

    await createTrendsPanel(deps)();

    const screen = deps.content.children[0];
    expect(findNodes(screen, (node) => node.title === "—")).toHaveLength(1);
    expect(findNodes(screen, (node) => node.className === "trends-zero")).toHaveLength(1);
  });

  test("handles missing ranking entries and message-less failures", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(trendsResult({ rankings: { play_seconds: [null] } }))
      .mockRejectedValueOnce(null);
    const render = createTrendsPanel(deps);
    await render();
    const refresh = findNodes(deps.content.children[0], (node) => node.id === "trends-refresh")[0];
    await refresh.onclick();
    expect(findNodes(deps.content.children[0], (node) => node.className === "analytics-empty")).toHaveLength(1);
  });

  test("renders API errors as text content", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockRejectedValue(new Error("<b>trends api fail</b>"));

    await createTrendsPanel(deps)();

    const error = findNodes(deps.content.children[0], (node) => node.textContent === "<b>trends api fail</b>")[0];
    expect(error.tagName).toBe("p");
  });

  test("switching periods reloads the trends data and marks the selected period", async () => {
    const deps = makeSharedDeps({ periodDays: 30 });
    deps.api = jest.fn().mockResolvedValue(trendsResult());

    await createTrendsPanel(deps)();
    const screen = deps.content.children[0];
    const [sevenDays, thirtyDays] = findNodes(screen, (node) => node.dataset.periodDays).sort((a, b) => Number(a.dataset.periodDays) - Number(b.dataset.periodDays));
    sevenDays.onclick();
    await Promise.resolve();

    expect(deps.state.analytics.periodDays).toBe(7);
    expect(sevenDays.className).toContain("active");
    expect(thirtyDays.className).not.toContain("active");
    expect(deps.api).toHaveBeenLastCalledWith("/api/analytics/periods?days=7&limit=10");
  });

  test("opens a ranking player and reloads when the metric changes", async () => {
    const deps = makeSharedDeps();
    deps.api = jest.fn().mockResolvedValue(trendsResult());

    await createTrendsPanel(deps)();

    const screen = deps.content.children[0];
    const player = findNodes(screen, (node) => node.dataset.periodPlayer === "1")[0];
    const metric = findNodes(screen, (node) => node.dataset.periodMetric === "sessions")[0];
    player.onclick();
    metric.onclick();
    await Promise.resolve();

    expect(deps.openAnalyticsPlayer).toHaveBeenCalledWith("1");
    expect(deps.state.analytics.periodMetric).toBe("sessions");
    expect(deps.api).toHaveBeenLastCalledWith("/api/analytics/periods?days=30&limit=10");
  });
});

// ── health.js ─────────────────────────────────────────────────────────────────

describe("renderHealthPanel", () => {
  function packResult(overrides = {}) {
    return {
      health: "healthy",
      sequence: "42",
      gap_count: 0,
      missing_events: 0,
      reset_count: 0,
      last_gap: null,
      last_error: null,
      last_response_at: 1000,
      last_snapshot_at: 900,
      runtime_version: "1.2.3",
      installed_version: "1.2.3",
      installed: true,
      source_version: "1.2.3",
      capabilities: { playerJoins: { supported: true }, movementSampling: { supported: false } },
      capability_status: "limited",
      capabilities_supported: 1,
      capabilities_total: 2,
      ...overrides,
    };
  }
  const activityResult = { total: 500, events: [], pages: 1, page: 1 };

  function makeDeps() {
    const content = { children: [], replaceChildren(...children) { this.children = children; } };
    const t = (key) => key;
    const uiIcon = (name) => `<svg icon="${name}"/>`;
    const escapeHtml = (s) => String(s ?? "").replace(/</g, "&lt;");
    const formatDate = (ts) => ts ? "2024-01-01" : "—";
    const analyticsViewSwitch = jest.fn(() => "");
    const bindAnalyticsViewSwitch = jest.fn();
    const api = jest.fn().mockRejectedValue(new Error("no api"));
    return { content, t, uiIcon, escapeHtml, formatDate, analyticsViewSwitch, bindAnalyticsViewSwitch, api };
  }

  let savedDocument;
  beforeEach(() => { savedDocument = global.document; global.document = makeDom().document; });
  afterEach(() => { global.document = savedDocument; });

  test("renders health-screen element as the first child of content", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult())
      .mockResolvedValueOnce(activityResult);
    await createHealthPanel(deps)();
    expect(deps.content.children[0].className).toBe("health-screen");
  });

  test("renders health-status section with badge for healthy pack", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult())
      .mockResolvedValueOnce(activityResult);
    await createHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.className === "health-status block-panel")).toHaveLength(1);
    expect(findNodes(screen, (n) => n.className?.includes("health-healthy"))).toHaveLength(1);
  });

  test("shows noPackHealth empty state when health is waiting and pack not installed", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult({ health: "waiting", installed: false }))
      .mockResolvedValueOnce(activityResult);
    await createHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.textContent === "noPackHealth")).toHaveLength(1);
  });

  test("renders last_gap value in volume section", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult({ gap_count: 2, missing_events: 3, last_gap: "5-7" }))
      .mockResolvedValueOnce(activityResult);
    await createHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.textContent === "5-7")).toHaveLength(1);
  });

  test("renders last_error paragraph when pack is degraded", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult({ health: "degraded", last_error: "sequence gap: expected 5, received 8" }))
      .mockResolvedValueOnce(activityResult);
    await createHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.textContent === "sequence gap: expected 5, received 8")).toHaveLength(1);
  });

  test("renders capability rows with supported and unsupported indicators", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult())
      .mockResolvedValueOnce(activityResult);
    await createHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.className?.includes("cap-supported"))).toHaveLength(1);
    expect(findNodes(screen, (n) => n.className?.includes("cap-unsupported"))).toHaveLength(1);
  });

  test("does not render capabilities section when capabilities is null or empty", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult({ capabilities: null }))
      .mockResolvedValueOnce(activityResult);
    await createHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.className === "health-capabilities block-panel")).toHaveLength(0);
  });

  test("renders analytics-empty with error text when API fails", async () => {
    const deps = makeDeps();
    deps.api = jest.fn().mockRejectedValue(new Error("pack api fail"));
    await createHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.textContent === "pack api fail")).toHaveLength(1);
  });

  test("calls both telemetry-pack and activity APIs on load", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult())
      .mockResolvedValueOnce(activityResult);
    await createHealthPanel(deps)();
    expect(deps.api).toHaveBeenCalledWith("/api/telemetry-pack");
    expect(deps.api).toHaveBeenCalledWith(expect.stringContaining("/api/analytics/activity"));
  });
});

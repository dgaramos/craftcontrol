import { jest } from "@jest/globals";
import { createTrendsPanel } from "../../../static/js/features/analytics/trends.js";
import { makeSharedDeps, makeDom, findNodes } from "../../helpers.js";

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

describe("createTrendsPanel", () => {
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

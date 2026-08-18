import { jest } from "@jest/globals";
import { createAnalyticsFeature } from "../static/js/features/analytics/index.js";
import { makeEl, makeAnalyticsDeps } from "./helpers.js";

describe("createAnalyticsFeature — factory setup", () => {
  test("returns a render function", () => {
    const deps = makeAnalyticsDeps();
    const feature = createAnalyticsFeature(deps);
    expect(typeof feature.render).toBe("function");
  });

  test("analyticsViewSwitch called during render sets content", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    // api returns empty results to avoid full DOM wiring
    deps.api = jest.fn().mockResolvedValue({ events: [], pages: 1, page: 1, total: 0, summary: {}, players: [] });
    deps.$ = jest.fn((sel) => {
      const el = makeEl({ value: "all" });
      return el;
    });
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(deps.content.innerHTML).toContain("analytics-screen");
  });

  test("render delegates to renderRankingsPanel for rankings kind", async () => {
    const deps = makeAnalyticsDeps({ kind: "rankings" });
    deps.api = jest.fn().mockResolvedValue({ metrics: { play_time: [{ player: { id: "1", name: "P" }, value: 100, source: "server" }] }, generated_at: 0 });
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(deps.content.innerHTML).toContain("rankings-screen");
  });

  test("analytics view switch resets page and requests render", async () => {
    const deps = makeAnalyticsDeps({ kind: "all", page: 4 });
    const switchButton = makeEl({ dataset: { analyticsView: "deaths" } });
    deps.content.querySelectorAll = jest.fn((selector) => selector === "[data-analytics-view]" ? [switchButton] : []);
    deps.api = jest.fn().mockResolvedValue({ events: [], pages: 1, page: 1, total: 0, summary: {}, players: [] });
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await render();
    switchButton.onclick();
    expect(deps.state.analytics.kind).toBe("deaths");
    expect(deps.state.analytics.page).toBe(1);
    expect(deps.requestRender).toHaveBeenCalled();
  });

  test("activity load-more restores the page and offers a retry after an append failure", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    const previousWindow = global.window;
    const target = makeEl();
    const sentinel = makeEl();
    const loadMore = makeEl();
    deps.$ = jest.fn((selector) => ({
      "#analytics-results": target,
      "#activity-scroll-sentinel": sentinel,
      "#activity-load-more": loadMore,
    })[selector] || makeEl());
    deps.api = jest.fn()
      .mockResolvedValueOnce({ events: [], pages: 2, page: 1, total: 1, summary: {} })
      .mockResolvedValueOnce({ players: [] })
      .mockRejectedValueOnce(new Error("next page unavailable"))
      .mockResolvedValueOnce({ players: [] });
    global.window = {};

    try {
      const { render } = createAnalyticsFeature(deps);
      await render();
      loadMore.onclick();
      await Promise.resolve();
      await Promise.resolve();

      expect(deps.state.analytics.page).toBe(1);
      expect(sentinel.innerHTML).toContain("next page unavailable");
      expect(loadMore.onclick).toEqual(expect.any(Function));
    } finally {
      global.window = previousWindow;
    }
  });

  test("render delegates to renderBlocksPanel for blocks kind", async () => {
    const deps = makeAnalyticsDeps({ kind: "blocks" });
    deps.api = jest.fn().mockResolvedValue({
      ores: { diamond: 5 },
      rankings: { miners: [], builders: [], ores: {} },
      top_broken: [],
      top_placed: [],
      players: [],
      totals: { broken: 10, placed: 5 },
      generated_at: 0,
    });
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(deps.content.innerHTML).toContain("blocks-screen");
  });

  test("render with kind=combat falls through to renderCombatPanel", async () => {
    const deps = makeAnalyticsDeps({ kind: "combat" });
    deps.api = jest.fn().mockRejectedValue(new Error("api error"));
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await expect(render()).resolves.toBeUndefined();
  });

  test("render with kind=exploration falls through", async () => {
    const deps = makeAnalyticsDeps({ kind: "exploration" });
    deps.api = jest.fn().mockRejectedValue(new Error("api error"));
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await expect(render()).resolves.toBeUndefined();
  });

  test("render with kind=trends falls through", async () => {
    const deps = makeAnalyticsDeps({ kind: "trends" });
    deps.api = jest.fn().mockRejectedValue(new Error("api error"));
    deps.$ = jest.fn(() => makeEl());
    const { render } = createAnalyticsFeature(deps);
    await expect(render()).resolves.toBeUndefined();
  });
});

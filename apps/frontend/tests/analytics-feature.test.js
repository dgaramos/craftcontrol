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

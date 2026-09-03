import { jest } from "@jest/globals";
import { createRankingsPanel } from "../../../static/js/features/analytics/rankings.js";
import { makeAnalyticsDeps, makeEl } from "../../helpers.js";

function makeDeps(stateOverrides = {}) {
  const base = makeAnalyticsDeps(stateOverrides);
  return { ...base, analyticsViewSwitch: () => "", bindAnalyticsViewSwitch: jest.fn() };
}

describe("createRankingsPanel", () => {
  test("falls back to the first metric for a populated category", async () => {
    const deps = makeDeps({ rankingCategory: "activity", rankingMetric: "missing" });
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#rankings-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({ metrics: {}, generated_at: 0 });
    await createRankingsPanel(deps)();
    expect(target.innerHTML).toContain("noRankingData");
    expect(deps.state.analytics.rankingMetric).toBe("play_time");
  });

  test("handles a category with no metric definitions", async () => {
    const deps = makeDeps({ rankingCategory: "combat", rankingMetric: "missing" });
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#rankings-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({ metrics: {}, generated_at: 0 });
    await createRankingsPanel(deps)();
    expect(target.innerHTML).toContain("noRankingData");
    expect(target.innerHTML).not.toContain("TypeError");
  });

  test("shows the API error", async () => {
    const deps = makeDeps();
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#rankings-content" ? target : makeEl());
    deps.api = jest.fn().mockRejectedValue(new Error("rankings unavailable"));
    await createRankingsPanel(deps)();
    expect(target.innerHTML).toContain("rankings unavailable");
  });
});

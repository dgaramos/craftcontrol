import { jest } from "@jest/globals";
import { createBlocksPanel } from "../static/js/features/analytics/blocks.js";
import { createRankingsPanel } from "../static/js/features/analytics/rankings.js";
import { makeAnalyticsDeps, makeEl } from "./helpers.js";

describe("analytics branch coverage", () => {
  const withBindings = (deps) => ({ ...deps, analyticsViewSwitch: () => "", bindAnalyticsViewSwitch: jest.fn() });

  test("blocks handles empty data, invalid ore selection and API error", async () => {
    const deps = withBindings(makeAnalyticsDeps({ blocksMode: "mining", selectedOre: "invalid" }));
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#blocks-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({ ores: { invalid: 4, iron: 2 }, rankings: { miners: [], ores: {} }, top_broken: [], players: [], totals: {} });
    await createBlocksPanel(deps)();
    expect(deps.state.analytics.selectedOre).toBe("iron");
    expect(target.innerHTML).toContain("noBlockData");

    deps.api.mockRejectedValueOnce(new Error("blocks unavailable"));
    await createBlocksPanel(deps)();
    expect(target.innerHTML).toContain("blocks unavailable");
  });

  test("rankings handles empty category and API error", async () => {
    const deps = withBindings(makeAnalyticsDeps({ rankingCategory: "activity", rankingMetric: "missing" }));
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#rankings-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({ metrics: {}, generated_at: 0 });
    await createRankingsPanel(deps)();
    expect(target.innerHTML).toContain("noRankingData");

    deps.api.mockRejectedValueOnce(new Error("rankings unavailable"));
    await createRankingsPanel(deps)();
    expect(target.innerHTML).toContain("rankings unavailable");
  });
});

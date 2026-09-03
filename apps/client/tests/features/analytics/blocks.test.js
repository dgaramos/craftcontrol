import { jest } from "@jest/globals";
import { createBlocksPanel } from "../../../static/js/features/analytics/blocks.js";
import { makeAnalyticsDeps, makeEl } from "../../helpers.js";

function makeDeps(stateOverrides = {}) {
  const base = makeAnalyticsDeps(stateOverrides);
  return { ...base, analyticsViewSwitch: () => "", bindAnalyticsViewSwitch: jest.fn() };
}

describe("createBlocksPanel", () => {
  test("handles empty data and an invalid ore selection", async () => {
    const deps = makeDeps({ blocksMode: "mining", selectedOre: "invalid" });
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#blocks-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({ ores: { invalid: 4, iron: 2 }, rankings: { miners: [], ores: {} }, top_broken: [], players: [], totals: {} });
    await createBlocksPanel(deps)();
    expect(deps.state.analytics.selectedOre).toBe("iron");
    expect(target.innerHTML).toContain("noBlockData");
  });

  test("shows the API error", async () => {
    const deps = makeDeps();
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#blocks-content" ? target : makeEl());
    deps.api = jest.fn().mockRejectedValue(new Error("blocks unavailable"));
    await createBlocksPanel(deps)();
    expect(target.innerHTML).toContain("blocks unavailable");
  });

  test("covers mining and building rankings with interactions", async () => {
    const deps = makeDeps({ blocksMode: "mining", selectedOre: "diamond" });
    const target = makeEl();
    const playerButton = makeEl({ dataset: { blockPlayer: "1" } });
    const oreButton = makeEl({ dataset: { ore: "iron" } });
    target.querySelectorAll = jest.fn((selector) => selector === "[data-block-player]" ? [playerButton] : [oreButton]);
    const modeButton = makeEl({ dataset: { blockMode: "building" }, classList: { toggle: jest.fn() } });
    deps.content.querySelectorAll = jest.fn((selector) => selector === "[data-block-mode]" ? [modeButton] : []);
    deps.$ = jest.fn((selector) => selector === "#blocks-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({ ores: { diamond: 4, iron: 2 }, rankings: { miners: [{ player: { id: "1", name: "A" }, value: 4 }], builders: [{ player: { id: "2", name: "B" }, value: 3 }], ores: { diamond: [{ player: { id: "1", name: "A" }, value: 2 }] } }, top_broken: [{ block: "stone", count: 4 }], top_placed: [{ block: "brick", count: 3 }], players: [{ player: { id: "1", name: "A" }, favorite_broken: { block: "stone", count: 2 }, favorite_placed: { block: "brick", count: 1 } }], totals: { broken: 4, placed: 3 }, generated_at: 1 });
    await createBlocksPanel(deps)();
    playerButton.onclick();
    oreButton.onclick();
    modeButton.onclick();
    await Promise.resolve();
    expect(deps.openAnalyticsPlayer).toHaveBeenCalledWith("1");
    expect(deps.state.analytics.blocksMode).toBe("building");
  });

  test("renders building-only data without ore ranking", async () => {
    const deps = makeDeps({ blocksMode: "building", selectedOre: "diamond" });
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#blocks-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({
      rankings: { builders: [{ player: { id: "2", name: "B" }, value: 3 }] },
      top_placed: [{ block: "brick", count: 3 }],
      players: [{ player: { id: "2", name: "B" }, favorite_placed: { block: "brick", count: 3 } }],
      totals: { placed: 3 },
    });
    await createBlocksPanel(deps)();
    expect(target.innerHTML).toContain("builders");
    expect(target.innerHTML).toContain("brick");
    expect(target.innerHTML).not.toContain("ore-section");
  });
});

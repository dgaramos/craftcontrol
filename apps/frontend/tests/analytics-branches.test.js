import { jest } from "@jest/globals";
import { createBlocksPanel } from "../static/js/features/analytics/blocks.js";
import { createRankingsPanel } from "../static/js/features/analytics/rankings.js";
import { createCombatPanel } from "../static/js/features/analytics/combat.js";
import { createExplorationPanel } from "../static/js/features/analytics/exploration.js";
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

  test("blocks covers mining and building rankings with interactions", async () => {
    const deps = withBindings(makeAnalyticsDeps({ blocksMode: "mining", selectedOre: "diamond" }));
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

  test("blocks renders building-only data without ore ranking", async () => {
    const deps = withBindings(makeAnalyticsDeps({ blocksMode: "building", selectedOre: "diamond" }));
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

  test("combat renders all evidence sections", async () => {
    const deps = withBindings(makeAnalyticsDeps({ combatMetric: "damage_dealt" }));
    const target = makeEl();
    const combatPlayer = makeEl({ dataset: { combatPlayer: "1" } });
    const combatMetric = makeEl({ dataset: { combatMetric: "deaths" } });
    target.querySelectorAll = jest.fn((selector) => selector.includes("combat-player") || selector.includes("block-player") ? [combatPlayer] : [combatMetric]);
    deps.$ = jest.fn((selector) => selector === "#combat-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({
      totals: { mob_kills: 1, player_kills: 2, deaths: 3, damage_dealt: 4, damage_taken: 5 },
      rankings: { damage_dealt: [{ player: { id: "1", name: "A" }, value: 4 }] },
      breakdowns: { causes: [{ key: "fall", count: 1 }], opponents: [{ key: "zombie", count: 1 }], projectiles: [{ key: "arrow", count: 1 }] },
      pvp: [{ attacker: { id: "1", name: "A" }, victim: { id: "2", name: "B" }, count: 1 }],
      top_targets: [{ target: "zombie", kills: 2 }],
      players: [{ player: { id: "1", name: "A" }, mob_kills: 1, player_kills: 1, deaths: 1, damage_dealt: 4, favorite_target: { target: "zombie" }, telemetry_available: true, updated_at: 1 }],
    });
    await createCombatPanel(deps)();
    combatPlayer.onclick();
    combatMetric.onclick();
    await Promise.resolve();
    expect(target.innerHTML).toContain("combat-summary");
    expect(deps.openAnalyticsPlayer).toHaveBeenCalledWith("1");
  });

  test("exploration renders dimensions, transitions and player favorites", async () => {
    const deps = withBindings(makeAnalyticsDeps({ explorationMetric: "active_seconds" }));
    const target = makeEl();
    const explorationPlayer = makeEl({ dataset: { explorationPlayer: "1" } });
    const explorationMetric = makeEl({ dataset: { explorationMetric: "sessions" } });
    target.querySelectorAll = jest.fn((selector) => selector.includes("exploration-player") ? [explorationPlayer] : [explorationMetric]);
    deps.$ = jest.fn((selector) => selector === "#exploration-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({
      totals: { distance: 10, dimensions: 2, dimension_visits: 3, active_seconds: 4, play_seconds: 5, sessions: 6 },
      rankings: { active_seconds: [{ player: { id: "1", name: "A" }, value: 4 }] },
      dimensions: [{ dimension: "overworld", distance: 10, active_seconds: 4, first_seen_at: 1, last_seen_at: 2 }],
      transitions: [{ player: { id: "1", name: "A" }, from: "overworld", to: "nether", timestamp: 2 }],
      players: [{ player: { id: "1", name: "A" }, favorite_dimension: "overworld", favorite_dimension_visits: 2 }],
    });
    await createExplorationPanel(deps)();
    explorationPlayer.onclick();
    explorationMetric.onclick();
    await Promise.resolve();
    expect(target.innerHTML).toContain("exploration-summary");
    expect(deps.openAnalyticsPlayer).toHaveBeenCalledWith("1");
  });

  test("exploration renders zero states for missing collections and falls back metric", async () => {
    const deps = withBindings(makeAnalyticsDeps({ explorationMetric: "unknown" }));
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#exploration-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({ totals: {} });
    await createExplorationPanel(deps)();
    expect(target.innerHTML).toContain("noExplorationEvidence");
    expect(target.innerHTML).toContain("distanceTraveled");
  });
});

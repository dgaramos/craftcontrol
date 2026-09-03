import { jest } from "@jest/globals";
import { createCombatPanel } from "../../../static/js/features/analytics/combat.js";
import { makeSharedDeps, makeEl } from "../../helpers.js";

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

describe("createCombatPanel", () => {
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
    deps.api = jest.fn().mockResolvedValue(combatResult({ breakdowns: { causes: [{ key: "fall", count: 5 }], opponents: [], projectiles: [] } }));
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

  test("renders all evidence sections with player interactions", async () => {
    const deps = makeSharedDeps({ combatMetric: "damage_dealt" });
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
});

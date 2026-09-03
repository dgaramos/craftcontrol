import { jest } from "@jest/globals";
import { createExplorationPanel } from "../../../static/js/features/analytics/exploration.js";
import { makeSharedDeps, makeEl } from "../../helpers.js";

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

describe("createExplorationPanel", () => {
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

  test("renders zero states for missing collections and falls back metric", async () => {
    const deps = makeSharedDeps({ explorationMetric: "unknown" });
    const target = makeEl();
    deps.$ = jest.fn((selector) => selector === "#exploration-content" ? target : makeEl());
    deps.api = jest.fn().mockResolvedValue({ totals: {} });
    await createExplorationPanel(deps)();
    expect(target.innerHTML).toContain("noExplorationEvidence");
    expect(target.innerHTML).toContain("distanceTraveled");
  });

  test("renders dimensions, transitions and player favorites with interactions", async () => {
    const deps = makeSharedDeps({ explorationMetric: "active_seconds" });
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
});

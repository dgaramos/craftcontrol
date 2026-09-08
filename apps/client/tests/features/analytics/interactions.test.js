import { jest } from "@jest/globals";
import { createInteractionsPanel } from "../../../static/js/features/analytics/interactions.js";
import { makeSharedDeps, makeEl } from "../../helpers.js";

function interactionsResult(overrides = {}) {
  return {
    generated_at: 1000,
    period: "lifetime",
    metrics: ["itemUse", "blockInteractions", "entityInteractions", "containerInteractions"],
    totals: { itemUse: 12, blockInteractions: 0, entityInteractions: 0, containerInteractions: 0 },
    top: { itemUse: [{ type: "minecraft:bow", count: 9 }], blockInteractions: [], entityInteractions: [], containerInteractions: [] },
    rankings: { itemUse: [{ player: { id: "1", name: "Alice" }, value: 12 }], blockInteractions: [], entityInteractions: [], containerInteractions: [] },
    players: [],
    availability: {
      itemUse: { enabled: true, supported: true },
      blockInteractions: { enabled: false, supported: null },
      entityInteractions: { enabled: true, supported: false },
      containerInteractions: { enabled: true, supported: null },
    },
    ...overrides,
  };
}

function panel(result = interactionsResult(), state = {}) {
  const deps = makeSharedDeps();
  const target = makeEl();
  deps.state.analytics = { ...deps.state.analytics, interactionMetric: "itemUse", ...state };
  deps.$ = jest.fn((selector) => (selector === "#interactions-content" ? target : makeEl()));
  deps.api = jest.fn().mockResolvedValue(result);
  return { deps, target, render: createInteractionsPanel(deps) };
}

describe("createInteractionsPanel", () => {
  test("renders the screen with the shared choice-group metric picker", async () => {
    const { deps, render } = panel();
    await render();
    expect(deps.content.innerHTML).toContain("interactions-screen");
    // The design system's selection control, not a bespoke one.
    expect(deps.content.innerHTML).toContain('class="choice-group interactions-metric-picker"');
    expect(deps.content.innerHTML).toContain('data-interaction-metric="containerInteractions"');
  });

  test("an enabled, supported metric shows its totals", async () => {
    const { target, render } = panel();
    await render();
    expect(target.innerHTML).toContain("interactions-summary");
    expect(target.innerHTML).toContain("minecraft:bow");
    expect(target.innerHTML).toContain("Alice");
  });

  test("a metric nobody enabled explains itself instead of showing a zero", async () => {
    const { target, render } = panel(interactionsResult(), { interactionMetric: "blockInteractions" });
    await render();
    expect(target.innerHTML).toContain("metricDisabled");
    expect(target.innerHTML).toContain("metricDisabledHelp");
    expect(target.innerHTML).not.toContain("interactions-summary");
  });

  test("an unsupported metric says the server cannot report it", async () => {
    const { target, render } = panel(interactionsResult(), { interactionMetric: "entityInteractions" });
    await render();
    expect(target.innerHTML).toContain("metricUnsupported");
    expect(target.innerHTML).not.toContain("interactions-summary");
  });

  test("an unconfirmed capability is neither zero nor unsupported", async () => {
    const { target, render } = panel(interactionsResult(), { interactionMetric: "containerInteractions" });
    await render();
    expect(target.innerHTML).toContain("metricUnconfirmed");
  });

  test("a metric the pack never mentioned is reported as unknown", async () => {
    const result = interactionsResult({ availability: {} });
    const { target, render } = panel(result);
    await render();
    expect(target.innerHTML).toContain("metricUnknown");
  });

  test("an enabled metric with nothing recorded says so, and still shows the total", async () => {
    const result = interactionsResult({
      totals: { itemUse: 0 }, top: { itemUse: [] }, rankings: { itemUse: [] },
    });
    const { target, render } = panel(result);
    await render();
    // Zero here is a measurement, so it is drawn — with the empty state naming
    // the window it covers.
    expect(target.innerHTML).toContain("interactions-summary");
    expect(target.innerHTML).toContain("noItemUseYet");
  });

  test("the availability card lists every metric's status", async () => {
    const { target, render } = panel();
    await render();
    expect(target.innerHTML).toContain("interactions-availability");
    expect(target.innerHTML).toContain("metricCollecting");
    expect(target.innerHTML).toContain("metricEnableHint");
  });

  test("an unknown stored metric falls back to the first one", async () => {
    const { deps, target, render } = panel(interactionsResult(), { interactionMetric: "chatCapture" });
    await render();
    expect(deps.state.analytics.interactionMetric).toBe("itemUse");
    expect(target.innerHTML).toContain("interactions-summary");
  });

  test("an API failure renders the message instead of an empty screen", async () => {
    const { deps, target, render } = panel();
    deps.api = jest.fn().mockRejectedValue(new Error("backend down"));
    await createInteractionsPanel(deps)();
    expect(target.innerHTML).toContain("backend down");
  });

  test("requests the analytics endpoint with a bounded limit", async () => {
    const { deps, render } = panel();
    await render();
    expect(deps.api).toHaveBeenCalledWith("/api/analytics/interactions?limit=10");
  });
});

import { jest } from "@jest/globals";
import { createPackHealthPanel } from "../../../static/js/features/server/health.js";
import { makeDom, findNodes } from "../../helpers.js";

function packResult(overrides = {}) {
  return {
    health: "healthy",
    sequence: "42",
    gap_count: 0,
    missing_events: 0,
    reset_count: 0,
    last_gap: null,
    last_error: null,
    last_response_at: 1000,
    last_snapshot_at: 900,
    runtime_version: "1.2.3",
    installed_version: "1.2.3",
    installed: true,
    source_version: "1.2.3",
    capabilities: { playerJoins: { supported: true }, movementSampling: { supported: false } },
    capability_status: "limited",
    capabilities_supported: 1,
    capabilities_total: 2,
    ...overrides,
  };
}

const activityResult = { total: 500, events: [], pages: 1, page: 1 };

function makeDeps() {
  // The panel now renders into the infrastructure screen's own container,
  // which it resolves the way every other card there does.
  const content = { children: [], replaceChildren(...children) { this.children = children; } };
  const t = (key) => key;
  const uiIcon = jest.fn((name, label = "") => `<svg icon="${name}" aria-label="${label}"/>`);
  const formatDate = (ts) => ts ? "2024-01-01" : "—";
  const api = jest.fn().mockRejectedValue(new Error("no api"));
  const $ = jest.fn((selector) => (selector === "#pack-health" ? content : null));
  return { content, $, t, uiIcon, formatDate, api };
}

describe("createPackHealthPanel", () => {
  let savedDocument;
  beforeEach(() => { savedDocument = global.document; global.document = makeDom().document; });
  afterEach(() => { global.document = savedDocument; });

  // Health, version and freshness are stated once by the screen header; this
  // panel is the detail behind them.
  test("renders health-screen element as the first child of content", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult())
      .mockResolvedValueOnce(activityResult);
    await createPackHealthPanel(deps)();
    expect(deps.content.children[0].className).toBe("health-screen");
  });


  test("shows noPackHealth empty state when health is waiting and pack not installed", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult({ health: "waiting", installed: false }))
      .mockResolvedValueOnce(activityResult);
    await createPackHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.textContent === "noPackHealth")).toHaveLength(1);
  });

  test("renders last_gap value in volume section", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult({ gap_count: 2, missing_events: 3, last_gap: "5-7" }))
      .mockResolvedValueOnce(activityResult);
    await createPackHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.textContent === "5-7")).toHaveLength(1);
  });


  test("renders capability rows with supported and unsupported indicators", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult())
      .mockResolvedValueOnce(activityResult);
    await createPackHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.className?.includes("cap-supported"))).toHaveLength(1);
    expect(findNodes(screen, (n) => n.className?.includes("cap-unsupported"))).toHaveLength(1);
    expect(deps.uiIcon).toHaveBeenCalledWith("check", "capabilitySupported");
    expect(deps.uiIcon).toHaveBeenCalledWith("close", "capabilityUnsupported");
  });

  test("does not render capabilities section when capabilities is null or empty", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult({ capabilities: null }))
      .mockResolvedValueOnce(activityResult);
    await createPackHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.className === "health-capabilities block-panel")).toHaveLength(0);
  });

  test("renders analytics-empty with error text when API fails", async () => {
    const deps = makeDeps();
    deps.api = jest.fn().mockRejectedValue(new Error("pack api fail"));
    await createPackHealthPanel(deps)();
    const screen = deps.content.children[0];
    expect(findNodes(screen, (n) => n.textContent === "pack api fail")).toHaveLength(1);
  });

  test("calls both telemetry-pack and activity APIs on load", async () => {
    const deps = makeDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce(packResult())
      .mockResolvedValueOnce(activityResult);
    await createPackHealthPanel(deps)();
    expect(deps.api).toHaveBeenCalledWith("/api/telemetry-pack");
    expect(deps.api).toHaveBeenCalledWith(expect.stringContaining("/api/analytics/activity"));
  });
});

describe("createPackHealthPanel outside its screen", () => {
  let savedDocument;
  beforeEach(() => { savedDocument = global.document; global.document = makeDom().document; });
  afterEach(() => { global.document = savedDocument; });

  test("does nothing when the infrastructure screen is not on display", async () => {
    // The server hub and the settings screen share this feature; only one of
    // them has the container, and the other must not fetch.
    const deps = makeDeps();
    deps.$ = jest.fn(() => null);
    await createPackHealthPanel(deps)();
    expect(deps.api).not.toHaveBeenCalled();
  });
});

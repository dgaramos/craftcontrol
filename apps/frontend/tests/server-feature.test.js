import { jest } from "@jest/globals";
import { createServerFeature } from "../static/js/features/server/index.js";
import { makeEl } from "./helpers.js";

function makeDeps(overrides = {}) {
  const elements = {};
  const state = { frontendVersion: "1.0.0", ...overrides.state };
  const $ = jest.fn((selector) => elements[selector] ||= makeEl());
  const content = makeEl();
  const api = jest.fn().mockResolvedValue({ installed: false, enabled: false, health: "waiting", capabilities: {} });
  return {
    state, content, $, elements, api, t: (key) => key, escapeHtml: (value) => String(value ?? ""),
    uiIcon: (name) => `<svg>${name}</svg>`, formatDate: (value) => value ? "2024-01-01" : "—",
    toast: jest.fn(), renderSettingsGroups: jest.fn(), ...overrides,
  };
}

describe("createServerFeature", () => {
  test("renders telemetry pack state and capability branches", async () => {
    const deps = makeDeps();
    deps.elements["#telemetry-pack-state"] = makeEl();
    deps.elements["#release-tags"] = makeEl();
    deps.api.mockResolvedValue({ installed: true, enabled: true, upgrade_available: true, health: "healthy", storage_status: "migrated", capability_status: "limited", capabilities: { playerJoins: { supported: true }, playerLeaves: { supported: false } }, capabilities_supported: 1, capabilities_total: 2, application: { version: "2", started_at: 1 }, runtime_version: "3", installed_version: "2", source_version: "4", storage_version: "1", sequence: 4, last_response_at: 1, last_snapshot_at: 1 });
    const feature = createServerFeature(deps);
    feature.renderServer();
    await new Promise((resolve) => queueMicrotask(resolve));
    expect(deps.elements["#telemetry-pack-state"].innerHTML).toContain("upgrade");
    expect(deps.elements["#release-tags"].innerHTML).toContain("API v2");
  });

  test("handles telemetry API failure", async () => {
    const deps = makeDeps();
    deps.elements["#telemetry-pack-state"] = makeEl();
    deps.api.mockRejectedValue(new Error("telemetry unavailable"));
    createServerFeature(deps).renderServer();
    await new Promise((resolve) => queueMicrotask(resolve));
    expect(deps.elements["#telemetry-pack-state"].textContent).toBe("telemetry unavailable");
  });

  test("renders release tags with and without frontend version", () => {
    const deps = makeDeps({ state: { frontendVersion: "" } });
    deps.elements["#release-tags"] = makeEl();
    const feature = createServerFeature(deps);
    feature.renderReleaseTags({ application: { version: "1", started_at: 1 }, runtime_version: "2", last_response_at: 1 });
    expect(deps.elements["#release-tags"].innerHTML).toContain("API v1");
    expect(deps.elements["#release-tags"].innerHTML).not.toContain("UI v");
  });
});

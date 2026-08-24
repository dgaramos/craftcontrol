/**
 * @jest-environment jsdom
 */

import { jest } from "@jest/globals";
import { createServerFeature } from "../static/js/features/server/index.js";
import { makeEl } from "./helpers.js";

function makeDeps(overrides = {}) {
  const elements = {};
  const state = { frontendVersion: "1.0.0", operationActive: false, ...overrides.state };
  const $ = jest.fn((selector) => elements[selector] ||= makeEl());
  const content = makeEl();
  const api = jest.fn().mockResolvedValue({ installed: false, enabled: false, health: "waiting", capabilities: {} });
  return {
    state, content, $, elements, api, t: (key) => key, escapeHtml: (value) => String(value ?? ""),
    uiIcon: (name) => `<svg>${name}</svg>`, formatDate: (value) => value ? "2024-01-01" : "—",
    toast: jest.fn(), getSettingsFeature: () => ({ renderSettingsGroups: jest.fn() }), ...overrides,
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

  test("renders local diagnostics when the owner panel requests them", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({ telemetry: { accepted: 4, rejected: 1, ingestion_duration_ms_average: 2.5 }, broker: { sse_connections: 3 } });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    expect(deps.elements["#diagnostics-state"].innerHTML).toContain("telemetryAccepted");
    expect(deps.elements["#diagnostics-state"].innerHTML).toContain("2.5 ms");
  });

  test("renders release tags with and without frontend version", () => {
    const deps = makeDeps({ state: { frontendVersion: "" } });
    deps.elements["#release-tags"] = makeEl();
    const feature = createServerFeature(deps);
    feature.renderReleaseTags({ application: { version: "1", started_at: 1 }, runtime_version: "2", last_response_at: 1 });
    expect(deps.elements["#release-tags"].innerHTML).toContain("API v1");
    expect(deps.elements["#release-tags"].innerHTML).not.toContain("UI v");
  });

  test("covers pack status, actions, and action failures", async () => {
    const savedConfirm = global.confirm;
    const deps = makeDeps();
    const install = makeEl({ dataset: { packAction: "install" } });
    const disable = makeEl({ dataset: { packAction: "disable" } });
    const rollback = makeEl({ dataset: { packAction: "rollback" } });
    deps.elements["#telemetry-pack-state"] = makeEl({ querySelectorAll: jest.fn(() => [install, disable, rollback]) });
    deps.elements["#release-tags"] = makeEl();
    deps.api = jest.fn()
      // Initial telemetry pack load and operations/latest.
      .mockResolvedValueOnce({ installed: false, enabled: false, health: "", storage_status: "not-required", capabilities: {}, application: {}, installed_version: "", runtime_version: "", source_version: "1" })
      .mockResolvedValueOnce({ operation: null })
      // install button click: restart_required; then telemetry reload; then rollback error
      .mockResolvedValueOnce({ restart_required: true })
      .mockResolvedValueOnce({ installed: false, enabled: false, health: "", storage_status: "not-required", capabilities: {}, application: {}, installed_version: "", runtime_version: "", source_version: "1" })
      .mockRejectedValueOnce(new Error("operation unavailable"));
    global.confirm = jest.fn().mockReturnValueOnce(false).mockReturnValue(true);

    try {
      const feature = createServerFeature(deps);
      feature.renderServer();
      await new Promise((resolve) => queueMicrotask(resolve));
      expect(deps.elements["#telemetry-pack-state"].innerHTML).toContain("installPack");
      await install.onclick();
      // confirm returns false — install was skipped; telemetry + operations = 2 initial calls.
      expect(deps.api).toHaveBeenCalledTimes(2);
      await disable.onclick();
      expect(deps.toast).toHaveBeenCalledWith("restartPackNotice");
      await rollback.onclick();
      expect(deps.toast).toHaveBeenCalledWith("operation unavailable", true);
      expect(rollback.disabled).toBe(false);
    } finally {
      global.confirm = savedConfirm;
    }
  });

  test("sets state.operationActive true for running/pending operations and false for terminal", async () => {
    const deps = makeDeps();
    deps.elements["#telemetry-pack-state"] = makeEl();
    deps.elements["#release-tags"] = makeEl();
    deps.elements["#operation-progress-container"] = makeEl();
    // renderServer fires loadTelemetryPack first, then initializeOperationProgress
    deps.api = jest.fn()
      .mockResolvedValueOnce({ installed: false, enabled: false, health: "", capabilities: {}, application: {}, source_version: "1" })
      .mockResolvedValueOnce({ operation: { operation_id: "op-1", state: "running", stages: [] } });
    const feature = createServerFeature(deps);
    feature.renderServer();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(deps.state.operationActive).toBe(true);
  });

  test("sets state.operationActive false when operation is in terminal state", async () => {
    const deps = makeDeps();
    deps.elements["#telemetry-pack-state"] = makeEl();
    deps.elements["#release-tags"] = makeEl();
    deps.elements["#operation-progress-container"] = makeEl();
    deps.api = jest.fn()
      .mockResolvedValueOnce({ installed: false, enabled: false, health: "", capabilities: {}, application: {}, source_version: "1" })
      .mockResolvedValueOnce({ operation: { operation_id: "op-1", state: "confirmed", stages: [] } });
    const feature = createServerFeature(deps);
    feature.renderServer();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(deps.state.operationActive).toBe(false);
  });

  test("initializeOperationProgress sets operationActive without requiring renderServer", async () => {
    const deps = makeDeps();
    deps.elements["#operation-progress-container"] = makeEl();
    deps.api = jest.fn()
      .mockResolvedValueOnce({ operation: { operation_id: "op-2", state: "pending", stages: [] } });
    const feature = createServerFeature(deps);
    await feature.initializeOperationProgress();
    expect(deps.state.operationActive).toBe(true);
  });

  test("returns early without DOM targets and accepts only valid frontend releases", async () => {
    const savedFetch = global.fetch;
    const deps = makeDeps();
    deps.$ = jest.fn(() => null);
    global.fetch = jest.fn()
      .mockResolvedValueOnce({ ok: false })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ service: "backend", version: "2" }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ service: "frontend", version: 2 }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ service: "frontend", version: "2.0.0" }) })
      .mockRejectedValueOnce(new Error("missing version"));
    try {
      const feature = createServerFeature(deps);
      feature.renderServer();
      await new Promise((resolve) => queueMicrotask(resolve));
      feature.renderReleaseTags({});
      await feature.loadFrontendVersion();
      await feature.loadFrontendVersion();
      await feature.loadFrontendVersion();
      await feature.loadFrontendVersion();
      await feature.loadFrontendVersion();
      expect(deps.state.frontendVersion).toBe("2.0.0");
    } finally {
      global.fetch = savedFetch;
    }
  });

  test("renders inactive packs, fallbacks, errors, and supported capabilities", async () => {
    const deps = makeDeps({ state: { frontendVersion: null } });
    const action = makeEl({ dataset: { packAction: "disable" } });
    deps.elements["#telemetry-pack-state"] = makeEl({ querySelectorAll: jest.fn(() => [action]) });
    deps.elements["#release-tags"] = makeEl();
    deps.api.mockResolvedValue({
      installed: true, enabled: false, upgrade_available: false, health: null, storage_status: "blocked", capabilities: { joins: { supported: true } },
      capability_status: "full", capabilities_supported: 1, capabilities_total: 1, application: null, installed_version: "4", runtime_version: "", source_version: null,
      installed_updated_at: null, last_response_at: null, last_snapshot_at: null, gap_count: null, missing_events: null, last_error: "pack warning",
    });
    createServerFeature(deps).renderServer();
    await new Promise((resolve) => queueMicrotask(resolve));
    expect(deps.elements["#telemetry-pack-state"].innerHTML).toContain("packInactive");
    expect(deps.elements["#telemetry-pack-state"].innerHTML).toContain("pack warning");
    expect(deps.elements["#telemetry-pack-state"].innerHTML).toContain("capabilityFull");
  });
});

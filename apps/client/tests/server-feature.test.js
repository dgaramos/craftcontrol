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
    deps.api.mockResolvedValue({
      telemetry: { accepted: 4, rejected: 1, duplicates: 2, old: 3, sequence: { lost: 2, gaps: 1, resets: 0 }, by_topic: { "blocks.changed": { accepted: 4, rejected: 1, duplicates: 1, old: 0, gaps: 1, resets: 0 } }, ingestion_duration_ms_average: 2.5, ingestion_duration_ms_max: 9 },
      broker: { sse_connections: 3, sse_connections_total: 8, events_by_topic: { "telemetry.started": 2 } },
      runtime_refreshing: true,
      telemetry_state: { status: "healthy", sequence: "10", expected_sequence: "11", gap_count: "0", missing_events: "0", reset_count: "0", last_snapshot_at: "1", last_event_at: "1" },
      persistence: { connections: 4, wait_ms_average: 1.5, wait_ms_max: 3, contention_failures: 0, retries: 2, database_size_bytes: 1024 },
      runtime: { refreshing: false, pending_gamerule_refreshes: 2, gamerule_worker_running: true, snapshot_running: false },
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    const rendered = deps.elements["#diagnostics-state"].children[0].textContent;
    expect(rendered).toContain("telemetryAccepted");
    expect(rendered).toContain("telemetryRejected");
    expect(rendered).toContain("telemetryDuplicates");
    expect(rendered).toContain("telemetryOld");
    expect(rendered).toContain("telemetryTopicDiagnostics");
    expect(rendered).toContain("telemetryLost2");
    expect(rendered).toContain("2.5 ms");
    expect(rendered).toContain("9 ms");
    expect(rendered).toContain("sseConnections3");
    expect(rendered).toContain("sseConnectionsTotal8");
    expect(rendered).toContain("runtimeRefreshingyes");
    expect(rendered).toContain("telemetry.started: 2");
    expect(rendered).toContain("3");
    expect(rendered).toContain("telemetryDetails");
    expect(rendered).toContain("diagnosticStatus: healthy");
    expect(rendered).toContain("persistenceDiagnostics");
    expect(rendered).toContain("sqliteWaitAverage: 1.5 ms");
    expect(rendered).toContain("sqliteRetries: 2");
    expect(rendered).toContain("sqliteDatabaseSize: 1024 B");
    expect(rendered).toContain("runtimeDiagnostics");
    expect(rendered).toContain("pendingGameruleRefreshes: 2");
  });

  test("hides diagnostics when its protected API request fails", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.elements["#diagnostics-state"].textContent = "stale";
    deps.api.mockRejectedValue(new Error("forbidden"));
    await createServerFeature(deps).loadDiagnostics();
    expect(deps.elements["#diagnostics-state"].textContent).toBe("");
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
      // Initial telemetry pack load.
      .mockResolvedValueOnce({ installed: false, enabled: false, health: "", storage_status: "not-required", capabilities: {}, application: {}, installed_version: "", runtime_version: "", source_version: "1" })
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
      // confirm returns false — install was skipped; operation initialization is
      // owned by application bootstrap rather than the Server area.
      expect(deps.api).toHaveBeenCalledTimes(1);
      await disable.onclick();
      expect(deps.toast).toHaveBeenCalledWith("restartPackNotice");
      await rollback.onclick();
      expect(deps.toast).toHaveBeenCalledWith("operation unavailable", true);
      expect(rollback.disabled).toBe(false);
    } finally {
      global.confirm = savedConfirm;
    }
  });

  test("sets state.operationActive true for running/pending operations", async () => {
    const deps = makeDeps();
    deps.elements["#operation-progress-container"] = makeEl();
    deps.api = jest.fn().mockResolvedValue({ operation: { operation_id: "op-1", state: "running", stages: [] } });
    const feature = createServerFeature(deps);
    await feature.initializeOperationProgress();
    expect(deps.state.operationActive).toBe(true);
  });

  test("does not reopen a dismissed drawer when the Server area renders", async () => {
    const deps = makeDeps();
    deps.elements["#telemetry-pack-state"] = makeEl();
    deps.elements["#operation-drawer"] = makeEl({ open: false });
    deps.api = jest.fn().mockResolvedValue({ operation: { operation_id: "op-1", state: "confirmed", stages: [] } });
    const feature = createServerFeature(deps);
    await feature.initializeOperationProgress();
    feature.renderServer();
    expect(deps.elements["#operation-drawer"].showModal).not.toHaveBeenCalled();
  });

  test("initializeOperationProgress sets operationActive without requiring renderServer", async () => {
    const deps = makeDeps();
    deps.elements["#operation-progress-container"] = makeEl();
    deps.api = jest.fn()
      .mockResolvedValueOnce({ operation: { operation_id: "op-2", state: "pending", stages: [] } });
    const feature = createServerFeature(deps);
    await feature.initializeOperationProgress();
    expect(deps.state.operationActive).toBe(true);
    expect(deps.elements["#operation-drawer"].showModal).toHaveBeenCalledTimes(1);
    expect(deps.elements["#operation-indicator"].hidden).toBe(false);
    expect(deps.elements["#operation-indicator-label"].textContent).toBe("opState_pending");
  });

  test("opens the drawer for a new active SSE operation after it was dismissed", async () => {
    const savedEventSource = global.EventSource;
    const listeners = {};
    const eventSource = { addEventListener: jest.fn((type, listener) => { listeners[type] = listener; }), onerror: null };
    global.EventSource = jest.fn(() => eventSource);
    localStorage.clear();
    try {
      const deps = makeDeps();
      deps.elements["#operation-progress-container"] = makeEl();
      deps.elements["#operation-indicator"] = makeEl();
      deps.elements["#operation-indicator-label"] = makeEl();
      deps.elements["#operation-drawer"] = makeEl({ open: false });
      deps.api = jest.fn().mockResolvedValue({ operation: null });
      const feature = createServerFeature(deps);
      await feature.initializeOperationProgress();

      listeners.operation({ data: JSON.stringify({ operation_id: "op-4", state: "running", stages: [] }) });

      expect(deps.state.operationActive).toBe(true);
      expect(deps.elements["#operation-drawer"].showModal).toHaveBeenCalledTimes(1);
      expect(deps.elements["#operation-indicator"].hidden).toBe(false);
    } finally {
      global.EventSource = savedEventSource;
      localStorage.clear();
    }
  });

  test("keeps terminal operation details available from the persistent indicator", async () => {
    const deps = makeDeps();
    deps.elements["#operation-progress-container"] = makeEl();
    deps.elements["#operation-indicator"] = makeEl();
    deps.elements["#operation-indicator-label"] = makeEl();
    deps.elements["#operation-drawer"] = makeEl({ open: false });
    deps.api = jest.fn().mockResolvedValue({ operation: { operation_id: "op-3", state: "failed", stages: [], terminal_error: "restart failed" } });

    const feature = createServerFeature(deps);
    await feature.initializeOperationProgress();

    expect(deps.state.operationActive).toBe(false);
    expect(deps.elements["#operation-indicator"].hidden).toBe(false);
    expect(deps.elements["#operation-indicator-label"].textContent).toBe("opState_failed");
    feature.openOperationDrawer();
    expect(deps.elements["#operation-drawer"].showModal).toHaveBeenCalledTimes(1);
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

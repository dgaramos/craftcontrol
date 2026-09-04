/**
 * @jest-environment jsdom
 */

import { jest } from "@jest/globals";
import { createServerFeature } from "../../../static/js/features/server/index.js";
import { makeEl } from "../../helpers.js";

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
      broker: { sse_connections: 3, sse_connections_total: 8, sse_reconnections: 5, events_by_topic: { "telemetry.started": 2 } },
      runtime_refreshing: true,
      telemetry_state: { status: "healthy", sequence: "10", expected_sequence: "11", gap_count: "0", missing_events: "0", reset_count: "0", last_snapshot_at: "1", last_event_at: "1" },
      persistence: { connections: 4, wait_ms_average: 1.5, wait_ms_max: 3, contention_failures: 0, retries: 2, database_size_bytes: 1024 },
      runtime: { refreshing: false, pending_gamerule_refreshes: 2, gamerule_worker_running: true, snapshot_running: false },
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    const rendered = deps.elements["#diagnostics-state"].children.map((c) => c.textContent).join(" ");
    expect(rendered).toContain("diagUpdatedAt");
    expect(rendered).toContain("diagKeyMetrics");
    expect(rendered).toContain("telemetryRejected");
    expect(rendered).toContain("sqliteConnections");
    expect(rendered).toContain("sqliteContentionFailures");
    expect(rendered).toContain("reconciliationCount");
    expect(rendered).toContain("sqliteWaitAverage");
    expect(rendered).toContain("telemetryTopicDiagnostics");
    expect(rendered).toContain("telemetryDetails");
    expect(rendered).toContain("diagnosticStatus");
    expect(rendered).toContain("healthy");
    expect(rendered).toContain("persistenceDiagnostics");
    expect(rendered).toContain("sqliteWaitAverage");
    expect(rendered).toContain("2 ms");
    expect(rendered).toContain("sqliteRetries");
    expect(rendered).toContain("1.0 KB");
    expect(rendered).toContain("diagRuntimeSection");
    expect(rendered).toContain("pendingGameruleRefreshes");
  });

  test("hides diagnostics when its protected API request fails", async () => {
    const deps = makeDeps();
    const diagEl = makeEl();
    diagEl.textContent = "stale";
    deps.elements["#diagnostics-state"] = diagEl;
    deps.api.mockRejectedValue(new Error("forbidden"));
    await createServerFeature(deps).loadDiagnostics();
    expect(diagEl.textContent).toBe("");
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

  // --- issue #276: batch and snapshot diagnostics sub-panels ---

  test("renders block batch diagnostics sub-panel when data is present", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({
      telemetry: {
        accepted: 1, rejected: 0, duplicates: 0, old: 0,
        sequence: { lost: 0, gaps: 0, resets: 0 }, by_topic: {},
        ingestion_duration_ms_average: 0, ingestion_duration_ms_max: 0,
        blocks: { count: 3, total_blocks_declared: 12, max_blocks_declared: 7 },
        snapshots: { count: 2, duration_ms_total: 50, duration_ms_max: 30, last_player_count: 2 },
      },
      broker: { sse_connections: 0, sse_connections_total: 0, events_by_topic: {} },
      runtime_refreshing: false,
      telemetry_state: { status: "healthy", sequence: "1", expected_sequence: "2", gap_count: "0", missing_events: "0", reset_count: "0", last_snapshot_at: null, last_event_at: null },
      persistence: { connections: 1, wait_ms_average: 0, wait_ms_max: 0, contention_failures: 0, retries: 0, database_size_bytes: 512 },
      runtime: { refreshing: false, pending_gamerule_refreshes: 0, gamerule_worker_running: false, snapshot_running: false },
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    const rendered = deps.elements["#diagnostics-state"].children.map((c) => c.textContent).join(" ");
    expect(rendered).toContain("diagKeyMetrics");
    expect(rendered).toContain("persistenceDiagnostics");
    expect(rendered).toContain("512 B");
  });

  test("renders snapshot reconciliation diagnostics sub-panel when data is present", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({
      telemetry: {
        accepted: 1, rejected: 0, duplicates: 0, old: 0,
        sequence: { lost: 0, gaps: 0, resets: 0 }, by_topic: {},
        ingestion_duration_ms_average: 0, ingestion_duration_ms_max: 0,
        blocks: { count: 0, total_blocks_declared: 0, max_blocks_declared: 0 },
        snapshots: { count: 2, duration_ms_total: 80, duration_ms_max: 50, last_player_count: null },
      },
      broker: { sse_connections: 0, sse_connections_total: 0, events_by_topic: {} },
      runtime_refreshing: false,
      telemetry_state: { status: "healthy", sequence: "1", expected_sequence: "2", gap_count: "0", missing_events: "0", reset_count: "0", last_snapshot_at: null, last_event_at: null },
      persistence: { connections: 1, wait_ms_average: 0, wait_ms_max: 0, contention_failures: 0, retries: 0, database_size_bytes: 512 },
      runtime: { refreshing: false, pending_gamerule_refreshes: 0, gamerule_worker_running: false, snapshot_running: false },
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    const rendered = deps.elements["#diagnostics-state"].children.map((c) => c.textContent).join(" ");
    expect(rendered).toContain("diagKeyMetrics");
    expect(rendered).toContain("persistenceDiagnostics");
    expect(rendered).toContain("telemetryDetails");
  });

  test("diagnostics sub-panels render with zero values without errors", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({
      telemetry: {
        accepted: 0, rejected: 0, duplicates: 0, old: 0,
        sequence: { lost: 0, gaps: 0, resets: 0 }, by_topic: {},
        ingestion_duration_ms_average: 0, ingestion_duration_ms_max: 0,
        blocks: { count: 0, total_blocks_declared: 0, max_blocks_declared: 0 },
        snapshots: { count: 0, duration_ms_total: 0, duration_ms_max: 0, last_player_count: null },
      },
      broker: { sse_connections: 0, sse_connections_total: 0, events_by_topic: {} },
      runtime_refreshing: false,
      telemetry_state: null,
      persistence: null,
      runtime: null,
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    expect(deps.elements["#diagnostics-state"].children[0]).toBeTruthy();
  });

  test("i18n catalogs contain batch and snapshot diagnostic keys", async () => {
    const [{ en }, { pt }, { es }] = await Promise.all([
      import("../../../static/js/i18n/en.js"),
      import("../../../static/js/i18n/pt.js"),
      import("../../../static/js/i18n/es.js"),
    ]);
    const requiredKeys = ["batchDiagnostics", "batchCount", "batchTotalBlocks", "batchMaxBlocks", "snapshotDiagnostics", "snapshotCount", "snapshotDurationTotal", "snapshotDurationMax", "snapshotLastPlayerCount", "diagUpdatedAt", "diagKeyMetrics", "diagRuntimeSection"];
    for (const key of requiredKeys) {
      expect({ key, locale: "en", value: en[key] }).toMatchObject({ key, locale: "en", value: expect.any(String) });
      expect({ key, locale: "pt", value: pt[key] }).toMatchObject({ key, locale: "pt", value: expect.any(String) });
      expect({ key, locale: "es", value: es[key] }).toMatchObject({ key, locale: "es", value: expect.any(String) });
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

  test("renders reconciliation sub-panel when data is present", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({
      telemetry: { accepted: 0, rejected: 0, duplicates: 0, old: 0, sequence: { lost: 0, gaps: 0, resets: 0 }, by_topic: {}, ingestion_duration_ms_average: 0, ingestion_duration_ms_max: 0 },
      broker: { sse_connections: 0, sse_connections_total: 0, events_by_topic: {} },
      runtime_refreshing: false,
      telemetry_state: { status: null, sequence: null, expected_sequence: null, gap_count: null, missing_events: null, reset_count: null, last_snapshot_at: null, last_event_at: null },
      persistence: { connections: 0, wait_ms_average: 0, wait_ms_max: 0, contention_failures: 0, retries: 0, database_size_bytes: null },
      runtime: {
        refreshing: false, pending_gamerule_refreshes: 0, gamerule_worker_running: false, snapshot_running: false,
        reconciliation: { count: 7, duration_ms_total: 350.5, duration_ms_max: 120.0, duration_ms_last: 45.2 },
      },
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    const rendered = deps.elements["#diagnostics-state"].children.map((c) => c.textContent).join(" ");
    expect(rendered).toContain("diagRuntimeSection");
    expect(rendered).toContain("reconciliationCount");
    expect(rendered).toContain("351 ms");
    expect(rendered).toContain("120 ms");
    expect(rendered).toContain("45 ms");
  });

  test("domain freshness sub-panel renders with empty domains without errors", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({
      telemetry: { accepted: 0, rejected: 0, duplicates: 0, old: 0, sequence: { lost: 0, gaps: 0, resets: 0 }, by_topic: {}, ingestion_duration_ms_average: 0, ingestion_duration_ms_max: 0 },
      broker: { sse_connections: 0, sse_connections_total: 0, events_by_topic: {} },
      runtime_refreshing: false,
      telemetry_state: { status: null, sequence: null, expected_sequence: null, gap_count: null, missing_events: null, reset_count: null, last_snapshot_at: null, last_event_at: null },
      persistence: { connections: 0, wait_ms_average: 0, wait_ms_max: 0, contention_failures: 0, retries: 0, database_size_bytes: null },
      runtime: { refreshing: false, pending_gamerule_refreshes: 0, gamerule_worker_running: false, snapshot_running: false, reconciliation: { count: 0, duration_ms_total: 0, duration_ms_max: 0, duration_ms_last: 0 } },
      domains: {},
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    expect(deps.elements["#diagnostics-state"].children[0]).toBeTruthy();
  });

  test("domain freshness sub-panel shows Fresh badge for non-stale domain", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({
      telemetry: { accepted: 0, rejected: 0, duplicates: 0, old: 0, sequence: { lost: 0, gaps: 0, resets: 0 }, by_topic: {}, ingestion_duration_ms_average: 0, ingestion_duration_ms_max: 0 },
      broker: { sse_connections: 0, sse_connections_total: 0, events_by_topic: {} },
      runtime_refreshing: false,
      telemetry_state: { status: null, sequence: null, expected_sequence: null, gap_count: null, missing_events: null, reset_count: null, last_snapshot_at: null, last_event_at: null },
      persistence: { connections: 0, wait_ms_average: 0, wait_ms_max: 0, contention_failures: 0, retries: 0, database_size_bytes: null },
      runtime: { refreshing: false, pending_gamerule_refreshes: 0, gamerule_worker_running: false, snapshot_running: false, reconciliation: { count: 0, duration_ms_total: 0, duration_ms_max: 0, duration_ms_last: 0 } },
      domains: { settings: { observed_at: 1700000000, age_seconds: 60, stale: false } },
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    const rendered = deps.elements["#diagnostics-state"].children.map((c) => c.textContent).join(" ");
    expect(rendered).toContain("domainFresh");
    expect(rendered).toContain("domainFreshness");
  });

  test("domain freshness sub-panel shows Stale badge for stale domain", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({
      telemetry: { accepted: 0, rejected: 0, duplicates: 0, old: 0, sequence: { lost: 0, gaps: 0, resets: 0 }, by_topic: {}, ingestion_duration_ms_average: 0, ingestion_duration_ms_max: 0 },
      broker: { sse_connections: 0, sse_connections_total: 0, events_by_topic: {} },
      runtime_refreshing: false,
      telemetry_state: { status: null, sequence: null, expected_sequence: null, gap_count: null, missing_events: null, reset_count: null, last_snapshot_at: null, last_event_at: null },
      persistence: { connections: 0, wait_ms_average: 0, wait_ms_max: 0, contention_failures: 0, retries: 0, database_size_bytes: null },
      runtime: { refreshing: false, pending_gamerule_refreshes: 0, gamerule_worker_running: false, snapshot_running: false, reconciliation: { count: 0, duration_ms_total: 0, duration_ms_max: 0, duration_ms_last: 0 } },
      domains: { gamerules: { observed_at: 1700000000, age_seconds: 1500, stale: true } },
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    const rendered = deps.elements["#diagnostics-state"].children.map((c) => c.textContent).join(" ");
    expect(rendered).toContain("domainStale");
  });

  test("i18n catalogs contain domain freshness keys", async () => {
    const [{ en }, { pt }, { es }] = await Promise.all([
      import("../../../static/js/i18n/en.js"),
      import("../../../static/js/i18n/pt.js"),
      import("../../../static/js/i18n/es.js"),
    ]);
    const requiredKeys = ["domainFreshness", "domainObservedAt", "domainAgeSeconds", "domainStale", "domainFresh"];
    for (const key of requiredKeys) {
      expect({ key, locale: "en", value: en[key] }).toMatchObject({ key, locale: "en", value: expect.any(String) });
      expect({ key, locale: "pt", value: pt[key] }).toMatchObject({ key, locale: "pt", value: expect.any(String) });
      expect({ key, locale: "es", value: es[key] }).toMatchObject({ key, locale: "es", value: expect.any(String) });
    }
  });

  test("renders reconciliation sub-panel with zeros without errors", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api.mockResolvedValue({
      telemetry: { accepted: 0, rejected: 0, duplicates: 0, old: 0, sequence: { lost: 0, gaps: 0, resets: 0 }, by_topic: {}, ingestion_duration_ms_average: 0, ingestion_duration_ms_max: 0 },
      broker: { sse_connections: 0, sse_connections_total: 0, events_by_topic: {} },
      runtime_refreshing: false,
      telemetry_state: { status: null, sequence: null, expected_sequence: null, gap_count: null, missing_events: null, reset_count: null, last_snapshot_at: null, last_event_at: null },
      persistence: { connections: 0, wait_ms_average: 0, wait_ms_max: 0, contention_failures: 0, retries: 0, database_size_bytes: null },
      runtime: {
        refreshing: false, pending_gamerule_refreshes: 0, gamerule_worker_running: false, snapshot_running: false,
        reconciliation: { count: 0, duration_ms_total: 0, duration_ms_max: 0, duration_ms_last: 0 },
      },
    });
    const feature = createServerFeature(deps);
    await feature.loadDiagnostics();
    // Must render without throwing; reconciliation group must appear with count key
    const rendered = deps.elements["#diagnostics-state"].children.map((c) => c.textContent).join(" ");
    expect(rendered).toContain("diagRuntimeSection");
    expect(rendered).toContain("reconciliationCount");
  });
});

describe("createServerFeature — renderReleaseTags", () => {
  test("returns early when #release-tags element is absent", () => {
    const $ = jest.fn(() => null);
    const deps = {
      state: { frontendVersion: null },
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $,
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "—",
      toast: jest.fn(),
      getSettingsFeature: () => ({ renderSettingsGroups: jest.fn() }),
    };
    const { renderReleaseTags } = createServerFeature(deps);
    expect(() => renderReleaseTags({})).not.toThrow();
  });

  test("sets innerHTML on release-tags element", () => {
    const releaseEl = { innerHTML: "" };
    const $ = jest.fn((sel) => sel === "#release-tags" ? releaseEl : null);
    const deps = {
      state: { frontendVersion: "1.2.3" },
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $,
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "2024-01-01",
      toast: jest.fn(),
      getSettingsFeature: () => ({ renderSettingsGroups: jest.fn() }),
    };
    const { renderReleaseTags } = createServerFeature(deps);
    renderReleaseTags({ application: { version: "2.0.0", started_at: 0 }, runtime_version: "1.0", last_response_at: 0 });
    expect(releaseEl.innerHTML).toContain("1.2.3");
    expect(releaseEl.innerHTML).toContain("2.0.0");
  });
});

describe("createServerFeature — loadFrontendVersion", () => {
  test("updates state.frontendVersion on success", async () => {
    const state = { frontendVersion: null };
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: jest.fn().mockResolvedValue({ service: "frontend", version: "3.1.4" }),
    });
    global.fetch = mockFetch;
    const deps = {
      state,
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $: jest.fn(() => null),
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "—",
      toast: jest.fn(),
      getSettingsFeature: () => ({ renderSettingsGroups: jest.fn() }),
    };
    const { loadFrontendVersion } = createServerFeature(deps);
    await loadFrontendVersion();
    expect(state.frontendVersion).toBe("3.1.4");
  });

  test("ignores non-ok responses", async () => {
    const state = { frontendVersion: null };
    global.fetch = jest.fn().mockResolvedValue({ ok: false });
    const deps = {
      state,
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $: jest.fn(() => null),
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "—",
      toast: jest.fn(),
      getSettingsFeature: () => ({ renderSettingsGroups: jest.fn() }),
    };
    const { loadFrontendVersion } = createServerFeature(deps);
    await loadFrontendVersion();
    expect(state.frontendVersion).toBeNull();
  });

  test("swallows fetch errors silently", async () => {
    const state = { frontendVersion: null };
    global.fetch = jest.fn().mockRejectedValue(new Error("network"));
    const deps = {
      state,
      content: { innerHTML: "", querySelectorAll: jest.fn(() => []) },
      t: (k) => k,
      api: jest.fn(),
      $: jest.fn(() => null),
      escapeHtml: (s) => String(s ?? ""),
      uiIcon: () => "",
      formatDate: () => "—",
      toast: jest.fn(),
      getSettingsFeature: () => ({ renderSettingsGroups: jest.fn() }),
    };
    const { loadFrontendVersion } = createServerFeature(deps);
    await expect(loadFrontendVersion()).resolves.toBeUndefined();
    expect(state.frontendVersion).toBeNull();
  });

  test("diagnostics: invalid last_snapshot_at (null, string, NaN) does not throw", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    for (const bad of [null, "not-a-number", NaN, undefined]) {
      deps.api = jest.fn().mockResolvedValue({
        telemetry: { by_topic: {} }, persistence: {}, runtime: {},
        telemetry_state: { last_snapshot_at: bad },
      });
      await expect(createServerFeature(deps).loadDiagnostics()).resolves.toBeUndefined();
    }
  });

  function diagText(deps) {
    return deps.elements["#diagnostics-state"].children.map((c) => c.textContent || c.innerHTML || "").join(" ");
  }

  function diagInnerHTML(deps) {
    return deps.elements["#diagnostics-state"].children.map((c) => {
      if (typeof c.innerHTML === "string") return c.innerHTML;
      if (typeof c.textContent === "string") return c.textContent;
      return "";
    }).join(" ");
  }

  test("diagnostics: makeTopicsTable highlights rejected > 0 with anomaly class", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api = jest.fn().mockResolvedValue({
      telemetry: { by_topic: { "player.joined": { accepted: 5, rejected: 2, duplicates: 0, out_of_order: 0 } } },
      persistence: {}, runtime: {}, telemetry_state: {},
    });
    await createServerFeature(deps).loadDiagnostics();
    // topicsSection is a real jsdom element — find it among the children stored by the replaceChildren mock
    const topicsSection = deps.elements["#diagnostics-state"].children.find(
      (c) => c?.innerHTML?.includes("diag-topics")
    );
    expect(topicsSection?.innerHTML ?? "").toContain("diag-topic-anomaly");
  });

  test("diagnostics: makeTopicsTable reads v.duplicates field", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api = jest.fn().mockResolvedValue({
      telemetry: { by_topic: { "snap.started": { accepted: 1, rejected: 0, duplicates: 3, out_of_order: 0 } } },
      persistence: {}, runtime: {}, telemetry_state: {},
    });
    await createServerFeature(deps).loadDiagnostics();
    const topicsSection = deps.elements["#diagnostics-state"].children.find(
      (c) => c?.innerHTML?.includes("diag-topics")
    );
    expect(topicsSection?.innerHTML ?? "").toContain(">3<");
  });

  test("diagnostics: formatRelativeTime clamps negative diff to 0 (no throw on future timestamp)", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    const futureTs = Math.floor(Date.now() / 1000) + 600;
    deps.api = jest.fn().mockResolvedValue({
      telemetry: { by_topic: {} }, persistence: {}, runtime: {},
      telemetry_state: { last_snapshot_at: futureTs },
    });
    // Must not throw; snapshot tile must render a value starting with "0"
    await expect(createServerFeature(deps).loadDiagnostics()).resolves.toBeUndefined();
    const kpiSection = deps.elements["#diagnostics-state"].children.find(
      (c) => c?.innerHTML?.includes("diag-kpi-grid")
    );
    // t() returns the key literal in tests, so formatRelativeTime produces "0timeAgoSeconds"
    expect(kpiSection?.innerHTML ?? "").toContain(">0timeAgoSeconds<");
  });

  test("diagnostics: formatAge boundary at exactly 60s shows minutes format", async () => {
    const deps = makeDeps();
    deps.elements["#diagnostics-state"] = makeEl();
    deps.api = jest.fn().mockResolvedValue({
      telemetry: { by_topic: {} }, persistence: {}, runtime: {},
      telemetry_state: {},
      domains: { telemetry: { age_seconds: 60, stale: false } },
    });
    await createServerFeature(deps).loadDiagnostics();
    const rendered = diagText(deps);
    expect(rendered).toContain("1m 0s");
  });
});

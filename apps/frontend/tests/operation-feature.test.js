/**
 * Tests for the operation lifecycle progress component (issue #192).
 */

import { jest } from "@jest/globals";
import { createOperationFeature } from "../static/js/features/server/operation.js";

function makeDeps(overrides = {}) {
  return {
    api: jest.fn().mockResolvedValue({ operation: null }),
    t: (key) => key,
    escapeHtml: (v) => String(v ?? ""),
    formatDate: (v) => (v ? "2024-01-01 14:30" : "—"),
    uiIcon: (name) => `<svg>${name}</svg>`,
    ...overrides,
  };
}

function makeOperation(overrides = {}) {
  return {
    operation_id: "op-1",
    server_id: "default",
    state: "running",
    requested_changes: { SERVER_NAME: "MyWorld" },
    stages: [
      { stage: "review", result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
      { stage: "backup_verify", result: "running", started_at: 1700000002, completed_at: null, evidence: { backup_path: "/backups/world" }, error: null },
      { stage: "prepare", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
      { stage: "restart", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
      { stage: "health_wait", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
      { stage: "verify", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
      { stage: "confirm", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
    ],
    created_at: 1700000000,
    updated_at: 1700000002,
    completed_at: null,
    terminal_error: null,
    observation: {},
    correlation_id: null,
    ...overrides,
  };
}

describe("createOperationFeature — renderOperation", () => {
  test("renders running operation with completed and active stages", () => {
    const feature = createOperationFeature(makeDeps());
    const html = feature.renderOperation(makeOperation());
    expect(html).toContain("op-state-running");
    expect(html).toContain("op-stage-completed");
    expect(html).toContain("op-stage-running");
    expect(html).toContain("1/7");
  });

  test("renders confirmed terminal state", () => {
    const feature = createOperationFeature(makeDeps());
    const op = makeOperation({
      state: "confirmed",
      stages: [
        { stage: "review", result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
        { stage: "backup_verify", result: "completed", started_at: 1700000001, completed_at: 1700000002, evidence: {}, error: null },
        { stage: "prepare", result: "completed", started_at: 1700000002, completed_at: 1700000003, evidence: {}, error: null },
        { stage: "restart", result: "completed", started_at: 1700000003, completed_at: 1700000004, evidence: {}, error: null },
        { stage: "health_wait", result: "completed", started_at: 1700000004, completed_at: 1700000005, evidence: {}, error: null },
        { stage: "verify", result: "completed", started_at: 1700000005, completed_at: 1700000006, evidence: {}, error: null },
        { stage: "confirm", result: "completed", started_at: 1700000006, completed_at: 1700000007, evidence: {}, error: null },
      ],
      completed_at: 1700000007,
    });
    const html = feature.renderOperation(op);
    expect(html).toContain("op-state-confirmed");
    expect(html).toContain("7/7");
  });

  test("renders failed stage with error", () => {
    const feature = createOperationFeature(makeDeps());
    const op = makeOperation({
      state: "failed",
      terminal_error: "Backup verification failed",
      stages: [
        { stage: "review", result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
        { stage: "backup_verify", result: "failed", started_at: 1700000001, completed_at: 1700000002, evidence: {}, error: "Backup verification failed" },
        { stage: "prepare", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
        { stage: "restart", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
        { stage: "health_wait", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
        { stage: "verify", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
        { stage: "confirm", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
      ],
    });
    const html = feature.renderOperation(op);
    expect(html).toContain("op-state-failed");
    expect(html).toContain("op-stage-failed");
    expect(html).toContain("Backup verification failed");
  });

  test("renders divergent state with observation", () => {
    const feature = createOperationFeature(makeDeps());
    const op = makeOperation({
      state: "divergent",
      terminal_error: "Configuration mismatch after restart",
      observation: { observed_value: "old-name", expected_value: "MyWorld" },
      stages: [
        { stage: "review", result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
        { stage: "backup_verify", result: "completed", started_at: 1700000001, completed_at: 1700000002, evidence: {}, error: null },
        { stage: "prepare", result: "completed", started_at: 1700000002, completed_at: 1700000003, evidence: {}, error: null },
        { stage: "restart", result: "completed", started_at: 1700000003, completed_at: 1700000004, evidence: {}, error: null },
        { stage: "health_wait", result: "completed", started_at: 1700000004, completed_at: 1700000005, evidence: {}, error: null },
        { stage: "verify", result: "completed", started_at: 1700000005, completed_at: 1700000006, evidence: {}, error: null },
        { stage: "confirm", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
      ],
    });
    const html = feature.renderOperation(op);
    expect(html).toContain("op-state-divergent");
    expect(html).toContain("Configuration mismatch after restart");
    expect(html).toContain("observed value");
  });

  test("renders skipped stages", () => {
    const feature = createOperationFeature(makeDeps());
    const op = makeOperation({
      state: "confirmed",
      stages: [
        { stage: "review", result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
        { stage: "backup_verify", result: "skipped", started_at: null, completed_at: 1700000002, evidence: { skip_reason: "no world data" }, error: null },
        { stage: "prepare", result: "completed", started_at: 1700000002, completed_at: 1700000003, evidence: {}, error: null },
        { stage: "restart", result: "completed", started_at: 1700000003, completed_at: 1700000004, evidence: {}, error: null },
        { stage: "health_wait", result: "completed", started_at: 1700000004, completed_at: 1700000005, evidence: {}, error: null },
        { stage: "verify", result: "completed", started_at: 1700000005, completed_at: 1700000006, evidence: {}, error: null },
        { stage: "confirm", result: "completed", started_at: 1700000006, completed_at: 1700000007, evidence: {}, error: null },
      ],
      completed_at: 1700000007,
    });
    const html = feature.renderOperation(op);
    expect(html).toContain("op-stage-skipped");
    expect(html).toContain("op-stage-completed");
  });

  test("renders requested changes in collapsible section", () => {
    const feature = createOperationFeature(makeDeps());
    const html = feature.renderOperation(makeOperation({ requested_changes: { SERVER_NAME: "TestWorld", MAX_PLAYERS: 20 } }));
    expect(html).toContain("opChanges");
    expect(html).toContain("SERVER_NAME");
    expect(html).toContain("TestWorld");
    expect(html).toContain("MAX_PLAYERS");
  });

  test("renders evidence from active stage", () => {
    const feature = createOperationFeature(makeDeps());
    const html = feature.renderOperation(makeOperation());
    expect(html).toContain("backup path");
    expect(html).toContain("/backups/world");
  });

  test("returns empty string for null operation", () => {
    const feature = createOperationFeature(makeDeps());
    expect(feature.renderOperation(null)).toBe("");
  });

  test("handles operation with no stages array", () => {
    const feature = createOperationFeature(makeDeps());
    const html = feature.renderOperation({ ...makeOperation(), stages: null });
    expect(html).toContain("op-stage-bar");
  });
});

describe("createOperationFeature — initialize and SSE", () => {
  test("loads from storage and falls back to latest", async () => {
    const api = jest.fn().mockResolvedValue({ operation: makeOperation() });
    const feature = createOperationFeature(makeDeps({ api }));
    const mockEventSource = { addEventListener: jest.fn(), onerror: null };
    const savedES = global.EventSource;
    global.EventSource = jest.fn(() => mockEventSource);
    try {
      await feature.initialize();
      expect(api).toHaveBeenCalled();
      expect(feature.getOperation()).toBeTruthy();
    } finally {
      global.EventSource = savedES;
    }
  });

  test("setUpdateCallback is called when SSE event arrives", async () => {
    const api = jest.fn().mockResolvedValue({ operation: null });
    const feature = createOperationFeature(makeDeps({ api }));
    const callback = jest.fn();
    feature.setUpdateCallback(callback);

    // Simulate connecting stream — we override EventSource
    const listeners = {};
    const mockEventSource = {
      addEventListener: jest.fn((type, fn) => { listeners[type] = fn; }),
      onerror: null,
    };
    const savedES = global.EventSource;
    global.EventSource = jest.fn(() => mockEventSource);
    try {
      feature.connectStream();
      // Simulate an operation SSE event
      const op = makeOperation();
      listeners["operation"]({ data: JSON.stringify(op) });
      expect(callback).toHaveBeenCalledWith(expect.objectContaining({ operation_id: "op-1" }));
    } finally {
      global.EventSource = savedES;
    }
  });

  test("ignores malformed SSE data", async () => {
    const feature = createOperationFeature(makeDeps());
    const callback = jest.fn();
    feature.setUpdateCallback(callback);

    const listeners = {};
    const mockEventSource = { addEventListener: jest.fn((type, fn) => { listeners[type] = fn; }), onerror: null };
    const savedES = global.EventSource;
    global.EventSource = jest.fn(() => mockEventSource);
    try {
      feature.connectStream();
      listeners["operation"]({ data: "not-json{{" });
      expect(callback).not.toHaveBeenCalled();
    } finally {
      global.EventSource = savedES;
    }
  });

  test("does not open a second EventSource if already connected", () => {
    const feature = createOperationFeature(makeDeps());
    const mockEventSource = { addEventListener: jest.fn(), onerror: null };
    const savedES = global.EventSource;
    global.EventSource = jest.fn(() => mockEventSource);
    try {
      feature.connectStream();
      feature.connectStream();
      expect(global.EventSource).toHaveBeenCalledTimes(1);
    } finally {
      global.EventSource = savedES;
    }
  });
});

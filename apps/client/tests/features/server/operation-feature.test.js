/**
 * @jest-environment jsdom
 */

/**
 * Tests for the operation lifecycle progress component (issue #192).
 *
 * renderOperation now returns a DocumentFragment (or null), not an HTML string.
 * Tests mount the fragment into a container element and query the DOM.
 */

import { jest } from "@jest/globals";
import { createOperationFeature, confirmedExpiresAt, isExpiredOperation, isUnresponsiveOperation, unresponsiveAt, nextOperationTransition, UNRESPONSIVE_AFTER_MS } from "../../../static/js/features/server/operation.js";
import { makeStorage } from "../../helpers.js";
import { makeOperation } from "../../factories.js";

function makeDeps(overrides = {}) {
  return {
    api: jest.fn().mockResolvedValue({ operation: null }),
    t: (key) => key,
    formatDate: (v) => (v ? "2024-01-01 14:30" : "—"),
    uiIcon: (name) => `<svg>${name}</svg>`,
    storage: makeStorage(),
    ...overrides,
  };
}


/** Mount a renderOperation result into a fresh div for DOM querying. */
function mount(feature, op) {
  const container = document.createElement("div");
  const frag = feature.renderOperation(op);
  if (frag) container.appendChild(frag);
  return container;
}

describe("createOperationFeature — renderOperation", () => {
  test("renders running operation with completed and active stages", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeOperation());
    expect(el.querySelector(".op-state-running")).not.toBeNull();
    expect(el.querySelector(".op-stage-completed")).not.toBeNull();
    expect(el.querySelector(".op-stage-running")).not.toBeNull();
    expect(el.querySelector(".op-counter").textContent).toBe("1/7");
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
    const el = mount(feature, op);
    expect(el.querySelector(".op-state-confirmed")).not.toBeNull();
    expect(el.querySelector(".op-counter").textContent).toBe("7/7");
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
    const el = mount(feature, op);
    expect(el.querySelector(".op-state-failed")).not.toBeNull();
    expect(el.querySelector(".op-stage-failed")).not.toBeNull();
    // API-derived error text must appear in the DOM as text, not HTML
    const errorEls = el.querySelectorAll(".op-error-text");
    const errorTexts = Array.from(errorEls).map((e) => e.textContent);
    expect(errorTexts.some((t) => t.includes("Backup verification failed"))).toBe(true);
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
    const el = mount(feature, op);
    expect(el.querySelector(".op-state-divergent")).not.toBeNull();
    // terminal_error via textContent (in .op-error-text, not the icon slot)
    const terminalErrorSpan = el.querySelector(".op-terminal .op-error-text");
    expect(terminalErrorSpan.textContent).toBe("Configuration mismatch after restart");
    // observation key rendered as "observed value" (underscores → spaces)
    const dts = Array.from(el.querySelectorAll(".op-terminal dt")).map((dt) => dt.textContent);
    expect(dts).toContain("observed value");
  });

  test("renders the reconciled observed state instead of raw reconciliation data", () => {
    const feature = createOperationFeature(makeDeps({
      t: (key) => ({
        opObservedState: "Observed server state",
        opReconciliation_diverged: "differs from the requested configuration",
      })[key] || key,
    }));
    const el = mount(feature, makeOperation({
      state: "divergent",
      observation: { reconciliation_result: { state: "diverged" } },
    }));
    expect(el.querySelector(".op-reconciliation").textContent).toContain("differs from the requested configuration");
    expect(el.querySelector(".op-terminal").textContent).not.toContain("[object Object]");
  });

  test("renders structured evidence and observations without object coercion", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeOperation({
      state: "divergent",
      stages: [
        { stage: "review", result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
        { stage: "backup_verify", result: "running", started_at: 1700000002, completed_at: null, evidence: { backup: { verified: true, files: ["world.zip"] } }, error: null },
      ],
      observation: {
        observed_at: 1700000000000,
        observed_settings: { gamemode: "survival", configuration_checked_at: 1700000000, observedAt: 1700000000, checkedTime: 1700000000 },
      },
    }));

    expect(el.textContent).not.toContain("[object Object]");
    expect(el.textContent).toContain("verified");
    expect(el.textContent).toContain("survival");
    expect(el.querySelectorAll(".op-structured-value").length).toBeGreaterThan(0);
    expect(el.textContent).not.toContain("1700000000000");
    expect(el.textContent).not.toContain("1700000000");
    expect(el.textContent).toContain("2024-01-01 14:30");
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
    const el = mount(feature, op);
    expect(el.querySelector(".op-stage-skipped")).not.toBeNull();
    expect(el.querySelector(".op-stage-completed")).not.toBeNull();
  });

  test("renders requested changes in collapsible section", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeOperation({ requested_changes: { SERVER_NAME: "TestWorld", MAX_PLAYERS: 20 } }));
    const details = el.querySelector(".op-changes");
    expect(details).not.toBeNull();
    expect(details.querySelector("summary").textContent).toBe("opChanges");
    const liTexts = Array.from(details.querySelectorAll("li")).map((li) => li.textContent);
    expect(liTexts.some((t) => t.includes("SERVER_NAME"))).toBe(true);
    expect(liTexts.some((t) => t.includes("TestWorld"))).toBe(true);
    expect(liTexts.some((t) => t.includes("MAX_PLAYERS"))).toBe(true);
  });

  test("renders evidence from active stage", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeOperation());
    // backup_path evidence from the running backup_verify stage
    const dds = Array.from(el.querySelectorAll(".op-active-stage dd")).map((dd) => dd.textContent);
    expect(dds).toContain("/backups/world");
    const dts = Array.from(el.querySelectorAll(".op-active-stage dt")).map((dt) => dt.textContent);
    expect(dts).toContain("backup path");
    expect(el.querySelector(".op-active-stage .op-evidence-details > summary").textContent).toBe("opEvidence");
  });

  test("returns null for null operation", () => {
    const feature = createOperationFeature(makeDeps());
    expect(feature.renderOperation(null)).toBeNull();
  });

  test("handles operation with no stages array", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, { ...makeOperation(), stages: null });
    expect(el.querySelector(".op-stage-bar")).not.toBeNull();
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

  test("onopen re-fetches latest and calls onUpdate after reconnect", async () => {
    const op = makeOperation();
    const api = jest.fn().mockResolvedValue({ operation: op });
    const feature = createOperationFeature(makeDeps({ api }));
    const callback = jest.fn();
    feature.setUpdateCallback(callback);

    let capturedOnopen = null;
    const mockEventSource = {
      addEventListener: jest.fn(),
      onerror: null,
      set onopen(fn) { capturedOnopen = fn; },
    };
    const savedES = global.EventSource;
    global.EventSource = jest.fn(() => mockEventSource);
    try {
      feature.connectStream();
      expect(capturedOnopen).toBeTruthy();
      await capturedOnopen();
      expect(api).toHaveBeenCalledWith("/api/operations/latest");
      expect(callback).toHaveBeenCalledWith(expect.objectContaining({ operation_id: "op-1" }));
    } finally {
      global.EventSource = savedES;
    }
  });

  test("onopen does not overwrite currentOperation when SSE event arrives before /latest resolves", async () => {
    const opFromSSE = makeOperation({ operation_id: "op-sse", state: "confirmed" });
    const opFromLatest = makeOperation({ operation_id: "op-latest", state: "running" });

    let resolveLatest;
    const latestPromise = new Promise((resolve) => { resolveLatest = resolve; });
    const api = jest.fn().mockReturnValue(latestPromise);

    const feature = createOperationFeature(makeDeps({ api }));
    const callback = jest.fn();
    feature.setUpdateCallback(callback);

    const listeners = {};
    let capturedOnopen = null;
    const mockEventSource = {
      addEventListener: jest.fn((type, fn) => { listeners[type] = fn; }),
      onerror: null,
      set onopen(fn) { capturedOnopen = fn; },
    };
    const savedES = global.EventSource;
    global.EventSource = jest.fn(() => mockEventSource);
    try {
      feature.connectStream();

      // Start the onopen handler (it will await loadLatest which is pending)
      const openPromise = capturedOnopen();

      // SSE event arrives while /latest is still in-flight
      listeners["operation"]({ data: JSON.stringify(opFromSSE) });

      // Now /latest resolves with an older snapshot
      resolveLatest({ operation: opFromLatest });
      await openPromise;

      // The SSE-delivered operation should win; /latest must not overwrite it
      expect(feature.getOperation().operation_id).toBe("op-sse");
    } finally {
      global.EventSource = savedES;
    }
  });

  test("loadFromStorage rejects a non-UUID stored id without calling api", async () => {
    const api = jest.fn().mockRejectedValue(new Error("offline"));
    const storage = makeStorage({ "craftcontrol-operation-id": "../../etc/passwd" });
    const feature = createOperationFeature(makeDeps({ api, storage }));
    await feature.initialize();
    const storageCall = api.mock.calls.find((c) => c[0].includes("etc"));
    expect(storageCall).toBeUndefined();
  });

  test("initialize prefers the latest API operation over a stored historical id", async () => {
    const latest = makeOperation({ operation_id: "op-latest" });
    const api = jest.fn().mockResolvedValue({ operation: latest });
    const storage = makeStorage({ "craftcontrol-operation-id": "123e4567-e89b-42d3-a456-426614174000" });
    const feature = createOperationFeature(makeDeps({ api, storage }));
    await feature.initialize();
    expect(feature.getOperation()).toBe(latest);
    expect(api).toHaveBeenCalledWith("/api/operations/latest");
    expect(api).toHaveBeenCalledTimes(1);
  });

  test("initialize clears a stored historical id when the API has no operation", async () => {
    const api = jest.fn().mockResolvedValue({ operation: null });
    const storage = makeStorage({ "craftcontrol-operation-id": "123e4567-e89b-42d3-a456-426614174000" });
    const feature = createOperationFeature(makeDeps({ api, storage }));
    await feature.initialize();
    expect(feature.getOperation()).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith("craftcontrol-operation-id");
  });
});

describe("createOperationFeature — recovery actions (issue #194)", () => {
  function makeTerminalOp(state, extra = {}) {
    return makeOperation({
      state,
      stages: [
        { stage: "review", result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
        { stage: "backup_verify", result: "completed", started_at: 1700000001, completed_at: 1700000002, evidence: {}, error: null },
        { stage: "prepare", result: "completed", started_at: 1700000002, completed_at: 1700000003, evidence: {}, error: null },
        { stage: "restart", result: "completed", started_at: 1700000003, completed_at: 1700000004, evidence: {}, error: null },
        { stage: "health_wait", result: "completed", started_at: 1700000004, completed_at: 1700000005, evidence: {}, error: null },
        { stage: "verify", result: state === "confirmed" ? "completed" : state, started_at: 1700000005, completed_at: state === "confirmed" ? 1700000006 : null, evidence: {}, error: state === "failed" ? "something went wrong" : null },
        { stage: "confirm", result: state === "confirmed" ? "completed" : "pending", started_at: null, completed_at: null, evidence: {}, error: null },
      ],
      completed_at: 1700000010,
      ...extra,
    });
  }

  test("failed operation renders reconcile and retry buttons", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeTerminalOp("failed"));
    expect(el.querySelector('[data-op-action="reconcile"]')).not.toBeNull();
    expect(el.querySelector('[data-op-action="retry"]')).not.toBeNull();
  });

  test("divergent operation renders reconcile and retry buttons", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeTerminalOp("divergent"));
    expect(el.querySelector('[data-op-action="reconcile"]')).not.toBeNull();
    expect(el.querySelector('[data-op-action="retry"]')).not.toBeNull();
  });

  test("confirmed operation does not render recovery buttons", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeTerminalOp("confirmed"));
    expect(el.querySelector('[data-op-action="reconcile"]')).toBeNull();
    expect(el.querySelector('[data-op-action="retry"]')).toBeNull();
  });

  test("operation with parent_operation_id renders parent link placeholder", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeTerminalOp("failed", { parent_operation_id: "abcd1234-dead-beef-cafe-000000000000" }));
    expect(el.querySelector(".op-parent-link")).not.toBeNull();
    expect(el.querySelector(".op-parent-id")).not.toBeNull();
    // parent_operation_id must NOT be present in the DOM at render time —
    // it is injected later by bindRecoveryActions via textContent.
    expect(el.querySelector(".op-parent-id").textContent).toBe("");
    // The raw UUID must not appear anywhere in serialised markup
    expect(el.innerHTML).not.toContain("abcd1234");
  });

  test("operation without parent_operation_id does not render parent link", () => {
    const feature = createOperationFeature(makeDeps());
    const el = mount(feature, makeTerminalOp("failed"));
    expect(el.querySelector(".op-parent-link")).toBeNull();
  });

  // recovery button buttons no longer carry data-op-id; operation_id comes from closure
  function makeButton(action) {
    const btn = { dataset: { opAction: action }, disabled: false, onclick: null };
    return btn;
  }

  function makeContainer(buttons, parentIdEl = null) {
    return {
      querySelector: (sel) => (sel === ".op-parent-id" ? parentIdEl : null),
      querySelectorAll: () => buttons,
    };
  }

  async function initWithOp(api, op) {
    const feature = createOperationFeature(makeDeps({ api }));
    // seed currentOperation via initialize → api returns op
    await feature.initialize();
    return feature;
  }

  test("bindRecoveryActions calls reconcile endpoint and invokes onUpdate", async () => {
    const failedOp = makeTerminalOp("failed", { operation_id: "op-1" });
    const reconcileResult = makeTerminalOp("confirmed", { operation_id: "op-1" });
    const api = jest.fn()
      .mockResolvedValueOnce({ operation: failedOp })   // initialize → /latest
      .mockResolvedValueOnce({ operation: reconcileResult }); // reconcile
    const feature = await initWithOp(api, failedOp);
    let updatedOp = null;
    feature.setUpdateCallback((op) => { updatedOp = op; });

    const btn = makeButton("reconcile");
    feature.bindRecoveryActions(makeContainer([btn]));
    await btn.onclick();

    expect(api).toHaveBeenCalledWith("/api/operations/op-1/reconcile", { method: "POST" });
    expect(updatedOp).toBe(reconcileResult);
  });

  test("bindRecoveryActions calls retry endpoint and updates current operation", async () => {
    const failedOp = makeTerminalOp("failed", { operation_id: "op-1" });
    const retryResult = makeTerminalOp("running", { operation_id: "op-2", parent_operation_id: "op-1" });
    const api = jest.fn()
      .mockResolvedValueOnce({ operation: failedOp })
      .mockResolvedValueOnce({ operation: retryResult });
    const feature = await initWithOp(api, failedOp);
    let updatedOp = null;
    feature.setUpdateCallback((op) => { updatedOp = op; });

    const btn = makeButton("retry");
    feature.bindRecoveryActions(makeContainer([btn]));
    await btn.onclick();

    expect(api).toHaveBeenCalledWith("/api/operations/op-1/retry", { method: "POST" });
    expect(updatedOp).toBe(retryResult);
  });

  test("bindRecoveryActions sets parent-id textContent via DOM, not innerHTML", async () => {
    const failedOp = makeTerminalOp("failed", { operation_id: "op-1", parent_operation_id: "abcd1234-dead-beef-cafe-000000000000" });
    const api = jest.fn().mockResolvedValue({ operation: failedOp });
    const feature = await initWithOp(api, failedOp);

    const parentEl = { textContent: "" };
    feature.bindRecoveryActions(makeContainer([], parentEl));

    expect(parentEl.textContent).toBe("abcd1234");
  });

  test("bindRecoveryActions does nothing when container is null", () => {
    const feature = createOperationFeature(makeDeps());
    expect(() => feature.bindRecoveryActions(null)).not.toThrow();
  });

  test("bindRecoveryActions shows toast on api error", async () => {
    const failedOp = makeTerminalOp("failed", { operation_id: "op-1" });
    const api = jest.fn()
      .mockResolvedValueOnce({ operation: failedOp })
      .mockRejectedValueOnce(Object.assign(new Error("server error"), { status: 500 }));
    const toast = jest.fn();
    const feature = createOperationFeature(makeDeps({ api, toast }));
    await feature.initialize();

    const btn = makeButton("reconcile");
    feature.bindRecoveryActions(makeContainer([btn]));
    await btn.onclick();

    expect(toast).toHaveBeenCalled();
  });

  test("bindRecoveryActions shows conflict toast on 409", async () => {
    const failedOp = makeTerminalOp("failed", { operation_id: "op-1" });
    const api = jest.fn()
      .mockResolvedValueOnce({ operation: failedOp })
      .mockRejectedValueOnce(Object.assign(new Error("conflict"), { status: 409 }));
    const toast = jest.fn();
    const feature = createOperationFeature(makeDeps({ api, toast }));
    await feature.initialize();

    const btn = makeButton("retry");
    feature.bindRecoveryActions(makeContainer([btn]));
    await btn.onclick();

    expect(toast).toHaveBeenCalledWith("opRetryConflict", true);
  });

  test("bindRecoveryActions disables all buttons during request and re-enables after", async () => {
    const failedOp = makeTerminalOp("failed", { operation_id: "op-1" });
    let resolveApi;
    const api = jest.fn()
      .mockResolvedValueOnce({ operation: failedOp })
      .mockReturnValueOnce(new Promise((r) => { resolveApi = r; }));
    const feature = await initWithOp(api, failedOp);

    const btn1 = makeButton("reconcile");
    const btn2 = makeButton("retry");
    const container = makeContainer([btn1, btn2]);
    feature.bindRecoveryActions(container);

    const clickPromise = btn1.onclick();
    // both buttons should be disabled while the request is in flight
    expect(btn1.disabled).toBe(true);
    expect(btn2.disabled).toBe(true);

    resolveApi({ operation: makeTerminalOp("confirmed", { operation_id: "op-1" }) });
    await clickPromise;
    expect(btn1.disabled).toBe(false);
    expect(btn2.disabled).toBe(false);
  });
});

describe("createOperationFeature — divergent stage rendering", () => {
  test("stage with result divergent renders as op-stage-divergent", () => {
    const feature = createOperationFeature(makeDeps());
    const op = makeOperation({
      state: "divergent",
      stages: [
        { stage: "review", result: "completed", started_at: 1700000000, completed_at: 1700000001, evidence: {}, error: null },
        { stage: "backup_verify", result: "completed", started_at: 1700000001, completed_at: 1700000002, evidence: {}, error: null },
        { stage: "prepare", result: "completed", started_at: 1700000002, completed_at: 1700000003, evidence: {}, error: null },
        { stage: "restart", result: "completed", started_at: 1700000003, completed_at: 1700000004, evidence: {}, error: null },
        { stage: "health_wait", result: "completed", started_at: 1700000004, completed_at: 1700000005, evidence: {}, error: null },
        { stage: "verify", result: "divergent", started_at: 1700000005, completed_at: null, evidence: { observed: "old" }, error: "value mismatch" },
        { stage: "confirm", result: "pending", started_at: null, completed_at: null, evidence: {}, error: null },
      ],
    });
    const el = mount(feature, op);
    expect(el.querySelector(".op-stage-divergent")).not.toBeNull();
    // stage error via textContent in active stage panel
    const errorSpans = Array.from(el.querySelectorAll(".op-active-stage .op-error-text"));
    expect(errorSpans.some((s) => s.textContent.includes("value mismatch"))).toBe(true);
    // evidence key "observed" must appear as a dt
    const dts = Array.from(el.querySelectorAll(".op-active-stage dt")).map((dt) => dt.textContent);
    expect(dts).toContain("observed");
  });
});

describe("confirmed operations expire after their retention window", () => {
  const HOUR = 60 * 60 * 1000;
  const finishedAt = "2026-09-06T12:00:00Z";
  const finishedMs = Date.parse(finishedAt);

  test("a confirmed operation expires once the window closes", () => {
    const op = makeOperation({ state: "confirmed", completed_at: finishedAt });
    expect(isExpiredOperation(op, finishedMs + HOUR - 1000)).toBe(false);
    expect(isExpiredOperation(op, finishedMs + HOUR)).toBe(true);
  });

  test("failed and divergent operations never expire — they still need a decision", () => {
    const long = finishedMs + 100 * HOUR;
    expect(isExpiredOperation(makeOperation({ state: "failed", completed_at: finishedAt }), long)).toBe(false);
    expect(isExpiredOperation(makeOperation({ state: "divergent", completed_at: finishedAt }), long)).toBe(false);
    expect(isExpiredOperation(makeOperation({ state: "running" }), long)).toBe(false);
    expect(isExpiredOperation(null, long)).toBe(false);
  });

  test("a confirmed operation without a usable timestamp is kept", () => {
    const op = makeOperation({ state: "confirmed", completed_at: null, updated_at: null });
    expect(isExpiredOperation(op, Date.now())).toBe(false);
    expect(confirmedExpiresAt(op)).toBeNull();
  });

  test("getOperation hides an expired operation and forgets its stored id", async () => {
    const storage = makeStorage();
    storage.setItem("craftcontrol-operation-id", "op-1");
    const stale = makeOperation({ state: "confirmed", completed_at: new Date(Date.now() - 2 * HOUR).toISOString() });
    const feature = createOperationFeature(makeDeps({
      storage,
      api: jest.fn().mockResolvedValue({ operation: stale }),
    }));
    await feature.initialize();

    expect(feature.getOperation()).toBeNull();
    expect(storage.getItem("craftcontrol-operation-id")).toBeNull();
  });

  test("getOperation keeps a recently confirmed operation", async () => {
    const fresh = makeOperation({ state: "confirmed", completed_at: new Date(Date.now() - 60 * 1000).toISOString() });
    const feature = createOperationFeature(makeDeps({ api: jest.fn().mockResolvedValue({ operation: fresh }) }));
    await feature.initialize();

    expect(feature.getOperation()).toEqual(fresh);
  });
});

describe("a live operation that stops reporting is unresponsive, not in progress", () => {
  const MINUTE = 60 * 1000;
  const touchedAt = "2026-09-06T12:00:00Z";
  const touchedMs = Date.parse(touchedAt);

  test("running stays live while the backend keeps heartbeating updated_at", () => {
    const op = makeOperation({ state: "running", updated_at: touchedAt });
    // The backend writes a health observation every 5s and budgets 300s for the
    // health wait, so minutes of silence must never be called dead.
    expect(isUnresponsiveOperation(op, touchedMs + 5 * MINUTE)).toBe(false);
    expect(isUnresponsiveOperation(op, touchedMs + 14 * MINUTE)).toBe(false);
  });

  test("running becomes unresponsive once the window closes", () => {
    const op = makeOperation({ state: "running", updated_at: touchedAt });
    expect(isUnresponsiveOperation(op, touchedMs + UNRESPONSIVE_AFTER_MS)).toBe(true);
    expect(unresponsiveAt(op)).toBe(touchedMs + UNRESPONSIVE_AFTER_MS);
  });

  test("pending is covered too — it never reached a stage", () => {
    const op = makeOperation({ state: "pending", updated_at: touchedAt });
    expect(isUnresponsiveOperation(op, touchedMs + UNRESPONSIVE_AFTER_MS)).toBe(true);
  });

  test("terminal states are never unresponsive", () => {
    const far = touchedMs + 100 * 60 * MINUTE;
    for (const opState of ["confirmed", "failed", "divergent"]) {
      expect(isUnresponsiveOperation(makeOperation({ state: opState, updated_at: touchedAt }), far)).toBe(false);
    }
    expect(isUnresponsiveOperation(null, far)).toBe(false);
    expect(unresponsiveAt(null)).toBeNull();
  });

  test("an operation without a usable timestamp is never called unresponsive", () => {
    const op = makeOperation({ state: "running", updated_at: null, created_at: null });
    expect(isUnresponsiveOperation(op, Date.now())).toBe(false);
  });

  test("nextOperationTransition reports whichever change applies", () => {
    const running = makeOperation({ state: "running", updated_at: touchedAt });
    expect(nextOperationTransition(running)).toBe(touchedMs + UNRESPONSIVE_AFTER_MS);
    const confirmed = makeOperation({ state: "confirmed", completed_at: touchedAt });
    expect(nextOperationTransition(confirmed)).toBe(confirmedExpiresAt(confirmed));
    expect(nextOperationTransition(makeOperation({ state: "failed", completed_at: touchedAt }))).toBeNull();
  });
});

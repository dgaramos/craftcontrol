/**
 * @jest-environment jsdom
 */

import { jest } from "@jest/globals";
import { createServerFeature } from "../../../static/js/features/server/index.js";
import { makeEl } from "../../helpers.js";

const PACK = {
  installed: true, enabled: true, upgrade_available: true, health: "healthy",
  runtime_version: "0.6.0", installed_version: "0.6.0", source_version: "0.6.0",
  storage_version: "3", storage_status: "not-required", sequence: 42,
  gap_count: 0, missing_events: 0, last_response_at: 1000, last_snapshot_at: 900,
  capabilities: { itemUse: { supported: true } }, capabilities_supported: 1,
  capabilities_total: 1, application: { version: "2", started_at: 1 },
};
const METRICS = { itemUse: true, blockInteractions: false, entityInteractions: false, containerInteractions: false };

function makeDeps({ pack = PACK, metrics = METRICS, targets = {}, fail = {} } = {}) {
  const elements = { ...targets };
  const $ = jest.fn((selector) => elements[selector] ||= makeEl());
  const content = makeEl();
  const api = jest.fn((path, options) => {
    if (path === "/api/telemetry-pack") {
      return fail.pack ? Promise.reject(fail.pack) : Promise.resolve(pack);
    }
    if (path === "/api/telemetry/collection") {
      if (options?.method === "POST") return fail.post ? Promise.reject(fail.post) : Promise.resolve({});
      return fail.collection ? Promise.reject(fail.collection) : Promise.resolve({ metrics, available: Object.keys(metrics) });
    }
    if (path === "/api/diagnostics") return Promise.resolve({ telemetry: {}, broker: {}, telemetry_state: {}, persistence: {}, runtime: {} });
    return Promise.resolve({ restart_required: true });
  });
  return {
    state: { batch: (run) => run() }, content, $, elements, api,
    t: (key) => key, escapeHtml: (value) => String(value ?? ""),
    uiIcon: (name) => `<svg>${name}</svg>`, formatDate: (value) => value ? "2024-01-01" : "—",
    toast: jest.fn(), getSettingsFeature: () => ({ renderSettingsGroups: jest.fn() }),
  };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("the Telemetry Pack screen", () => {
  test("asks its questions in order: does it work, what may it collect, what is installed", async () => {
    const deps = makeDeps();
    await createServerFeature(deps).renderTelemetryPack();
    const markup = deps.content.innerHTML;
    expect(markup.indexOf('id="pack-status"')).toBeLessThan(markup.indexOf("pack-collection"));
    expect(markup.indexOf("pack-collection")).toBeLessThan(markup.indexOf('id="pack-install"'));
    // Detail and diagnostics are folded away, not stacked on top.
    expect(markup.indexOf('id="pack-install"')).toBeLessThan(markup.indexOf('id="pack-health"'));
    expect(markup).toContain("technicalDetails");
    expect(markup).toContain('id="diagnostics-state"');
  });

  test("the status line answers whether the pack is working", async () => {
    const status = makeEl();
    const deps = makeDeps({ targets: { "#pack-status": status } });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(status.innerHTML).toContain("v0.6.0");
    expect(status.innerHTML).toContain("health-healthy");
    expect(status.innerHTML).toContain("packActive");
    expect(status.innerHTML).toContain("lastResponse");
  });

  test("a degraded pack shows its error beside the status", async () => {
    const status = makeEl();
    const deps = makeDeps({
      pack: { ...PACK, health: "degraded", last_error: "sequence gap: expected 9, received 12" },
      targets: { "#pack-status": status },
    });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(status.innerHTML).toContain("sequence gap: expected 9, received 12");
  });

  test("installation offers the action the state calls for", async () => {
    const install = makeEl();
    const deps = makeDeps({ targets: { "#pack-install": install } });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(install.innerHTML).toContain("upgradePack");
    expect(install.innerHTML).toContain("disablePack");
    expect(install.innerHTML).toContain("upgradeAvailable");
  });

  test("a pack that is not installed is offered installation instead", async () => {
    const install = makeEl();
    const deps = makeDeps({
      pack: { ...PACK, installed: false, enabled: false, upgrade_available: false },
      targets: { "#pack-install": install },
    });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(install.innerHTML).toContain("installPack");
    expect(install.innerHTML).not.toContain("disablePack");
  });

  test("a pack action confirms, runs, and re-reads the screen", async () => {
    const savedConfirm = global.confirm;
    const upgrade = makeEl({ dataset: { packAction: "upgrade" } });
    const install = makeEl({ querySelectorAll: jest.fn(() => [upgrade]) });
    const deps = makeDeps({ targets: { "#pack-install": install } });
    global.confirm = jest.fn().mockReturnValueOnce(false).mockReturnValue(true);
    try {
      await createServerFeature(deps).renderTelemetryPack();
      await settle();

      await upgrade.onclick();
      expect(deps.api).not.toHaveBeenCalledWith("/api/telemetry-pack/upgrade", expect.anything());

      await upgrade.onclick();
      expect(deps.api).toHaveBeenCalledWith("/api/telemetry-pack/upgrade", { method: "POST" });
      expect(deps.toast).toHaveBeenCalledWith("restartPackNotice");
      // The folded panels describe the installation that just changed, so they
      // are re-read rather than left showing the numbers from before it.
      expect(deps.api.mock.calls.filter(([path]) => path === "/api/diagnostics").length).toBeGreaterThan(1);
      expect(deps.api.mock.calls.filter(([path]) => path === "/api/analytics/activity?kind=all&days=0&page=1&page_size=1").length).toBeGreaterThan(1);
    } finally { global.confirm = savedConfirm; }
  });

  test("a failed pack action reports the reason and gives the button back", async () => {
    const savedConfirm = global.confirm;
    const rollback = makeEl({ dataset: { packAction: "rollback" }, disabled: false });
    const install = makeEl({ querySelectorAll: jest.fn(() => [rollback]) });
    const deps = makeDeps({ targets: { "#pack-install": install } });
    const packRead = deps.api;
    deps.api = jest.fn((path, options) => (path === "/api/telemetry-pack/rollback"
      ? Promise.reject(new Error("Rollback requires the server to be offline"))
      : packRead(path, options)));
    global.confirm = jest.fn(() => true);
    try {
      await createServerFeature(deps).renderTelemetryPack();
      await settle();
      await rollback.onclick();
      expect(deps.toast).toHaveBeenCalledWith("Rollback requires the server to be offline", true);
      expect(rollback.disabled).toBe(false);
    } finally { global.confirm = savedConfirm; }
  });

  test("an action that needs no restart says so instead", async () => {
    const savedConfirm = global.confirm;
    const disable = makeEl({ dataset: { packAction: "disable" } });
    const install = makeEl({ querySelectorAll: jest.fn(() => [disable]) });
    const deps = makeDeps({ targets: { "#pack-install": install } });
    const packRead = deps.api;
    deps.api = jest.fn((path, options) => (path === "/api/telemetry-pack/disable"
      ? Promise.resolve({ changed: true })
      : packRead(path, options)));
    global.confirm = jest.fn(() => true);
    try {
      await createServerFeature(deps).renderTelemetryPack();
      await settle();
      await disable.onclick();
      expect(deps.toast).toHaveBeenCalledWith("operationDone");
    } finally { global.confirm = savedConfirm; }
  });

  test("a pack with no versions yet renders placeholders rather than blanks", async () => {
    const status = makeEl();
    const install = makeEl();
    const deps = makeDeps({
      pack: { installed: false, enabled: false, source_version: "0.6.0" },
      targets: { "#pack-status": status, "#pack-install": install },
    });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(status.innerHTML).toContain("v—");
    expect(status.innerHTML).toContain("waiting");
    expect(install.innerHTML).toContain("packUpToDate");
  });

  test("a failed pack read replaces the status with the reason", async () => {
    const status = makeEl();
    const deps = makeDeps({ fail: { pack: new Error("pack unavailable") }, targets: { "#pack-status": status } });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(status.textContent).toBe("pack unavailable");
  });

  test("the diagnostics dashboard is filled by this screen", async () => {
    const diagnostics = makeEl();
    const deps = makeDeps({ targets: { "#diagnostics-state": diagnostics } });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(deps.api).toHaveBeenCalledWith("/api/diagnostics");
  });
});

describe("opt-in collection on the Telemetry Pack screen", () => {
  function withSwitches(options = {}) {
    const target = makeEl();
    const rows = [];
    target.querySelectorAll = jest.fn(() => rows);
    const deps = makeDeps({ ...options, targets: { "#telemetry-metrics": target, ...options.targets } });
    return { deps, target, rows };
  }

  test("lists every metric with the control its state implies", async () => {
    const { deps, target } = withSwitches();
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(target.innerHTML).toContain("metricCollecting");
    expect(target.innerHTML).toContain("metricDisabled");
    // The control offers the opposite of the current state, per metric.
    expect(target.innerHTML).toContain('data-metric="itemUse" data-metric-enabled="false"');
    expect(target.innerHTML).toContain('data-metric="blockInteractions" data-metric-enabled="true"');
  });

  test("an enabled metric the runtime cannot deliver is labelled unsupported and can still be turned off", async () => {
    const { deps, target } = withSwitches({ pack: { ...PACK, capabilities: { itemUse: { supported: false } } } });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(target.innerHTML).toContain("metricUnsupported");
    // What is on must be stoppable, even when the runtime cannot deliver it.
    expect(target.innerHTML).toContain('data-metric="itemUse" data-metric-enabled="false" type="button">metricDisable');
  });

  test("a metric this server cannot report is not offered for activation", async () => {
    // Turning it on would collect nothing and read as unavailable in
    // Analytics, so the control is withheld rather than left to disappoint.
    const { deps, target } = withSwitches({
      metrics: { ...METRICS, itemUse: false },
      pack: { ...PACK, capabilities: { itemUse: { supported: false } } },
    });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(target.innerHTML).toContain('data-metric="itemUse" data-metric-enabled="true" type="button" disabled');
    expect(target.innerHTML).toContain("metricUnsupported");
  });

  test("a capability the pack has not probed yet never blocks the control", async () => {
    // `containerInteractions` is only probed on the first block interaction; an
    // absent capability is unknown, not unsupported.
    const { deps, target } = withSwitches({ pack: { ...PACK, capabilities: {} } });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(target.innerHTML).not.toContain("disabled");
    expect(target.innerHTML).not.toContain("metricUnsupported");
  });

  test("switching a metric posts the opposite state and re-reads the card", async () => {
    const { deps, target, rows } = withSwitches({ metrics: { itemUse: false, blockInteractions: false, entityInteractions: false, containerInteractions: false } });
    const note = makeEl();
    const button = makeEl({ dataset: { metric: "itemUse", metricEnabled: "true" }, disabled: false });
    button.closest = jest.fn(() => makeEl({ querySelector: jest.fn(() => note) }));
    rows.push(button);
    await createServerFeature(deps).renderTelemetryPack();
    await settle();

    await button.onclick();
    expect(deps.api).toHaveBeenCalledWith("/api/telemetry/collection", {
      method: "POST",
      body: JSON.stringify({ metric: "itemUse", enabled: true }),
    });
    // The row says the request is in flight rather than flipping to a state the
    // pack has not confirmed.
    expect(note.textContent).toBe("metricPending");
    expect(deps.toast).toHaveBeenCalledWith("metricChanged");
    expect(target.innerHTML).toContain("itemUseMetric");
  });

  test("a refused switch reports the reason and gives the control back", async () => {
    const { deps, rows } = withSwitches({ fail: { post: new Error("container bedrock not found") } });
    const button = makeEl({ dataset: { metric: "itemUse", metricEnabled: "false" }, disabled: false });
    button.closest = jest.fn(() => makeEl({ querySelector: jest.fn(() => null) }));
    rows.push(button);
    await createServerFeature(deps).renderTelemetryPack();
    await settle();

    await button.onclick();
    expect(deps.toast).toHaveBeenCalledWith("container bedrock not found", true);
    expect(button.disabled).toBe(false);
  });

  test("a failed collection read shows the reason instead of an empty card", async () => {
    const { deps, target } = withSwitches({ fail: { collection: new Error("metrics unavailable") } });
    await createServerFeature(deps).renderTelemetryPack();
    await settle();
    expect(target.textContent).toBe("metrics unavailable");
  });
});

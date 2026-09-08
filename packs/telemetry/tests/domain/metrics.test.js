import { test, expect, describe } from "@jest/globals";
import { METRICS, applyMetricCommand, emptyMetrics, metricKey, parseMetrics } from "../../behavior_pack/scripts/domain/metrics.js";

/** The full state with only the named metrics on. */
const all = (overrides = {}) => ({ ...emptyMetrics(), ...overrides });

describe("metric state", () => {
  test("every known metric starts disabled", () => {
    expect(METRICS).toEqual(["itemUse", "blockInteractions", "entityInteractions", "containerInteractions"]);
    expect(Object.values(emptyMetrics())).toEqual(METRICS.map(() => false));
  });

  test("persisted state reads back as written", () => {
    expect(parseMetrics(all({ itemUse: true }))).toEqual(all({ itemUse: true }));
  });

  test.each([
    ["a corrupt value", "not-an-object"],
    ["a null value", null],
    ["an array", []],
    ["a truthy non-boolean", { itemUse: 1 }],
    ["a missing metric", {}],
  ])("%s never enables collection", (_label, persisted) => {
    // Anything but an explicit `true` must read as disabled: a damaged
    // property may not opt a server in by accident.
    expect(parseMetrics(persisted)).toEqual(all());
  });

  test("an unknown persisted name is dropped rather than carried", () => {
    expect(parseMetrics({ itemUse: true, chatCapture: true })).toEqual(all({ itemUse: true }));
  });
});

describe("metric commands", () => {
  test("enable turns one metric on and reports the change", () => {
    expect(applyMetricCommand(emptyMetrics(), "enable itemUse")).toEqual({
      metrics: all({ itemUse: true }), changed: true, error: null,
    });
  });

  test("disable turns it back off", () => {
    expect(applyMetricCommand(all({ itemUse: true }), "disable itemUse")).toEqual({
      metrics: all(), changed: true, error: null,
    });
  });

  test("re-enabling an enabled metric is understood but changes nothing", () => {
    expect(applyMetricCommand(all({ itemUse: true }), "enable itemUse")).toEqual({
      metrics: all({ itemUse: true }), changed: false, error: null,
    });
  });

  test("status reports the current state without changing it", () => {
    expect(applyMetricCommand(all({ itemUse: true }), "status")).toEqual({
      metrics: all({ itemUse: true }), changed: false, error: null,
    });
  });

  test.each([
    ["an unknown metric", "enable chatCapture", /unknown metric: chatCapture/],
    ["an unknown verb", "collect itemUse", /unknown metric command: collect/],
    ["an empty message", "", /unknown metric command/],
    ["a metric-less verb", "enable", /unknown metric: \(none\)/],
    ["a missing message", undefined, /unknown metric command/],
  ])("%s is refused and leaves the state alone", (_label, message, expected) => {
    const result = applyMetricCommand(all({ itemUse: true }), message);
    expect(result.metrics).toEqual(all({ itemUse: true }));
    expect(result.changed).toBe(false);
    expect(result.error).toMatch(expected);
  });

  test("extra whitespace in a command is tolerated", () => {
    expect(applyMetricCommand(emptyMetrics(), "  enable   itemUse  ").metrics).toEqual(all({ itemUse: true }));
  });
});

test.each(["blockInteractions", "entityInteractions", "containerInteractions"])(
  "%s is enabled on its own and leaves the others alone", (metric) => {
    const result = applyMetricCommand(emptyMetrics(), `enable ${metric}`);
    expect(result.metrics[metric]).toBe(true);
    expect(Object.entries(result.metrics).filter(([, on]) => on)).toHaveLength(1);
  });

describe("map keys", () => {
  test.each(["minecraft:diamond_sword", "minecraft:potion", "someaddon:magic_wand", "minecraft:oak_door"])(
    "%s is a namespaced identifier and may be stored", (identifier) => {
      expect(metricKey(identifier)).toBe(identifier);
    });

  test.each([
    ["a custom item name", "Excalibur"],
    ["a name with spaces", "minecraft:my sword"],
    ["a formatted name", "§cDeath Bringer"],
    ["an unqualified id", "diamond_sword"],
    ["a capitalized id", "Minecraft:Diamond_Sword"],
    ["a non-string", 42],
    ["an empty string", ""],
  ])("%s is discarded rather than stored", (_label, value) => {
    // The identifier shape is the privacy boundary: player-authored text
    // cannot match it, so a custom name can never become a map key.
    expect(metricKey(value)).toBeNull();
  });

  test("an absurdly long identifier is discarded", () => {
    expect(metricKey(`minecraft:${"a".repeat(200)}`)).toBeNull();
  });
});

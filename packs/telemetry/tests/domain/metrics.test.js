import { test, expect, describe } from "@jest/globals";
import { METRICS, applyMetricCommand, emptyMetrics, metricKey, parseMetrics } from "../../behavior_pack/scripts/domain/metrics.js";

describe("metric state", () => {
  test("every known metric starts disabled", () => {
    expect(emptyMetrics()).toEqual({ itemUse: false });
    expect(METRICS).toContain("itemUse");
  });

  test("persisted state reads back as written", () => {
    expect(parseMetrics({ itemUse: true })).toEqual({ itemUse: true });
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
    expect(parseMetrics(persisted)).toEqual({ itemUse: false });
  });

  test("an unknown persisted name is dropped rather than carried", () => {
    expect(parseMetrics({ itemUse: true, chatCapture: true })).toEqual({ itemUse: true });
  });
});

describe("metric commands", () => {
  test("enable turns one metric on and reports the change", () => {
    expect(applyMetricCommand(emptyMetrics(), "enable itemUse")).toEqual({
      metrics: { itemUse: true }, changed: true, error: null,
    });
  });

  test("disable turns it back off", () => {
    expect(applyMetricCommand({ itemUse: true }, "disable itemUse")).toEqual({
      metrics: { itemUse: false }, changed: true, error: null,
    });
  });

  test("re-enabling an enabled metric is understood but changes nothing", () => {
    expect(applyMetricCommand({ itemUse: true }, "enable itemUse")).toEqual({
      metrics: { itemUse: true }, changed: false, error: null,
    });
  });

  test("status reports the current state without changing it", () => {
    expect(applyMetricCommand({ itemUse: true }, "status")).toEqual({
      metrics: { itemUse: true }, changed: false, error: null,
    });
  });

  test.each([
    ["an unknown metric", "enable chatCapture", /unknown metric: chatCapture/],
    ["an unknown verb", "collect itemUse", /unknown metric command: collect/],
    ["an empty message", "", /unknown metric command/],
    ["a metric-less verb", "enable", /unknown metric: \(none\)/],
    ["a missing message", undefined, /unknown metric command/],
  ])("%s is refused and leaves the state alone", (_label, message, expected) => {
    const result = applyMetricCommand({ itemUse: true }, message);
    expect(result.metrics).toEqual({ itemUse: true });
    expect(result.changed).toBe(false);
    expect(result.error).toMatch(expected);
  });

  test("extra whitespace in a command is tolerated", () => {
    expect(applyMetricCommand(emptyMetrics(), "  enable   itemUse  ").metrics).toEqual({ itemUse: true });
  });
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

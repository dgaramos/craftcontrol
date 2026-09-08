/**
 * The opt-in metric policy, checked against the pack (#273).
 *
 * `docs/telemetry-metrics.md` decides what the pack may collect before #274 and
 * #275 collect anything. A policy nothing verifies is a policy that drifts, so
 * these tests fail when the pack and the document disagree — and they keep
 * failing as the new metrics land, because they assert absences.
 */

import { test } from "@jest/globals";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { MAX_BLOCK_TYPES, MAX_METRIC_TYPES, emptyPlayer } from "../../behavior_pack/scripts/model.js";
import { METRICS } from "../../behavior_pack/scripts/domain/metrics.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const POLICY = readFileSync(join(ROOT, "docs", "telemetry-metrics.md"), "utf8");

/** Everything the policy forbids, as it would appear in a state key. */
const FORBIDDEN_KEY_PARTS = [
  "inventory", "slot", "enchant", "durability", "component",
  "customname", "displayname", "chat", "message", "sign", "book",
  "coordinate", "position",
];

function stateKeys(value, prefix = "") {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value).flatMap(([key, nested]) => [
    `${prefix}${key}`,
    ...stateKeys(nested, `${prefix}${key}.`),
  ]);
}

test("player state carries nothing the policy forbids", () => {
  const keys = stateKeys(emptyPlayer("Steve", 0)).map((key) => key.toLowerCase());
  for (const key of keys) {
    for (const forbidden of FORBIDDEN_KEY_PARTS) {
      assert.ok(!key.includes(forbidden), `player state exposes "${key}", forbidden by the metric policy`);
    }
  }
});

test("the policy names each exclusion, so removing one is a visible edit", () => {
  for (const excluded of ["inventory", "slot", "enchantment", "custom item", "chat", "continuous location"]) {
    assert.ok(POLICY.toLowerCase().includes(excluded), `policy no longer excludes ${excluded}`);
  }
});

test("interaction metrics carry no coordinates", () => {
  // Movement sampling stays the only positional signal; an interaction that
  // recorded where it happened would rebuild a player's path.
  assert.match(POLICY, /interaction metrics carry no coordinates/i);
  const keys = Object.keys(emptyPlayer("Steve", 0));
  assert.ok(!keys.includes("x") && !keys.includes("location"));
});

test("the bound the policy states is the bound the pack applies", () => {
  assert.equal(MAX_BLOCK_TYPES, 128);
  assert.equal(MAX_METRIC_TYPES, 24);
  assert.ok(POLICY.includes("128"));
  assert.ok(POLICY.includes("(24)"), "the policy must state the bound opt-in metric maps actually use");
  assert.ok(POLICY.includes("30 KB"));
});

test("every metric the pack knows is named by the policy and declares a capability", () => {
  for (const metric of METRICS) {
    assert.ok(POLICY.includes(`\`${metric}\``), `the policy does not describe the ${metric} metric`);
    assert.match(POLICY, new RegExp(`\\| \`${metric}\` \\|`), `the policy declares no capability for ${metric}`);
  }
});

test("eviction drops the smallest counts and leaves the totals exact", () => {
  assert.match(POLICY, /the lowest counts are\s+dropped/);
  assert.match(POLICY, /counters that accompany\s+them stay exact/);
});

test("every metric ships disabled and is enabled on its own", () => {
  assert.match(POLICY, /Every metric ships disabled/);
  assert.match(POLICY, /Each metric is independent/);
});

test("an unsupported metric is unavailable rather than zero", () => {
  // Zero is a measurement; a missing capability is the absence of one.
  assert.match(POLICY, /\*\*unavailable, not zero\*\*/);
});

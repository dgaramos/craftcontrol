import assert from "node:assert/strict";
import { getMockDynamicProperty, setMockDynamicProperty, world } from "@minecraft/server";
import { STATE_KEY } from "../behavior_pack/scripts/model.js";
import { flush, loadState } from "../behavior_pack/scripts/store.js";

// Arrange: seed corrupt state so loadState() sets blocked = true
const corrupt = "{not-json";
setMockDynamicProperty(STATE_KEY, corrupt);

const errors = [];
console.error = (line) => errors.push(String(line));

// Trigger loadState to set the blocked flag
loadState();

// Record write calls issued after the blocked state is established
const writtenKeys = [];
const originalSet = world.setDynamicProperty.bind(world);
world.setDynamicProperty = (key, value) => {
  writtenKeys.push(key);
  return originalSet(key, value);
};

// Act: flush with blocked = true (force=true to bypass the dirty guard)
flush(true);

// Assert: no DynamicProperty was written
assert.equal(writtenKeys.length, 0, `expected no writes when blocked, got: ${writtenKeys.join(", ")}`);

// Assert: the original corrupt value is still intact
assert.equal(getMockDynamicProperty(STATE_KEY), corrupt);

// Assert: an error log was emitted mentioning persistence blocked
assert.ok(
  errors.some((line) => line.includes("persistence blocked")),
  `expected a "persistence blocked" error log, got: ${JSON.stringify(errors)}`,
);

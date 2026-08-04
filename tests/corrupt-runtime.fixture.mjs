import assert from "node:assert/strict";
import { getMockDynamicProperty, setMockDynamicProperty, system, world } from "@minecraft/server";
import { STATE_KEY } from "../behavior_pack/scripts/model.js";

const corrupt = "{not-json";
setMockDynamicProperty(STATE_KEY, corrupt);
const errors = [];
console.error = (line) => errors.push(String(line));

await import("../behavior_pack/scripts/main.js");
world.afterEvents.playerJoin.emit({ playerName: "VonCrush" });
for (const interval of system.intervals) interval();

assert.equal(getMockDynamicProperty(STATE_KEY), corrupt);
assert.ok(errors.some((line) => line.includes("invalid persisted state")));
assert.ok(errors.some((line) => line.includes("persistence blocked")));

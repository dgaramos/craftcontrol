import assert from "node:assert/strict";
import { world } from "@minecraft/server";

delete world.afterEvents.entityHurt;
delete world.afterEvents.playerDimensionChange;
const output = [];
console.warn = (line) => output.push(String(line));

await import("../behavior_pack/scripts/main.js");

const envelopes = output.filter((line) => line.includes("[BEDROCK_TELEMETRY]")).map((line) => JSON.parse(line.slice(line.indexOf("{"))));
const started = envelopes.find((item) => item.type === "telemetry.started");
assert.equal(started.data.capabilities.damageAggregates.supported, false);
assert.equal(started.data.capabilities.dimensionChanges.supported, false);
assert.equal(started.data.capabilities.blocksBroken.supported, true);
assert.equal(started.data.capabilities.snapshotRequests.supported, true);
assert.ok(output.some((line) => line.includes("[BEDROCK_TELEMETRY_CAPABILITY] unavailable: damageAggregates")));
assert.ok(output.some((line) => line.includes("[BEDROCK_TELEMETRY_CAPABILITY] unavailable: dimensionChanges")));

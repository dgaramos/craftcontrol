import assert from "node:assert/strict";
import { getMockDynamicProperty, setMockDynamicProperty } from "@minecraft/server";
import { STATE_BACKUP_KEY, STATE_KEY, playerStateKey } from "../../behavior_pack/scripts/model.js";
import { captureConsole } from "./console-capture.mjs";

const legacy = JSON.stringify({ schema: 1, sequence: 9, players: { voncrush: { name: "VonCrush", deaths: 4, blocksBroken: 12 } } });
setMockDynamicProperty(STATE_KEY, legacy);
const capture = captureConsole("warn");
const { lines: output } = capture;

await import("../../behavior_pack/scripts/main.js");

const migrated = JSON.parse(getMockDynamicProperty(STATE_KEY));
const shard = JSON.parse(getMockDynamicProperty(playerStateKey("voncrush")));
assert.equal(getMockDynamicProperty(STATE_BACKUP_KEY), legacy);
assert.equal(migrated.storageVersion, 3);
assert.equal(migrated.sequence, 10);
assert.equal(migrated.players, undefined);
assert.equal(shard.storageVersion, 3);
assert.equal(shard.player.deaths, 4);
assert.equal(shard.player.blocksBroken, 12);
assert.ok(output.some((line) => line.includes("[BEDROCK_TELEMETRY_MIGRATION] storage 0 -> 3 complete")));
const started = output.filter((line) => line.includes("[BEDROCK_TELEMETRY]")).map((line) => JSON.parse(line.slice(line.indexOf("{")))).find((item) => item.type === "telemetry.started");
assert.equal(started.data.storage.status, "migrated");
assert.equal(started.data.storage.storageVersion, 3);
capture.restore();

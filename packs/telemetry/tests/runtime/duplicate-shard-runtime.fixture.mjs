import assert from "node:assert/strict";
import { getMockDynamicProperty, setMockDynamicProperty } from "@minecraft/server";
import { STATE_KEY, playerStateKey } from "../../behavior_pack/scripts/model.js";
import { captureConsole } from "./console-capture.mjs";

const metadata = JSON.stringify({ storageVersion: 3, sequence: 7 });
const shard = JSON.stringify({ storageVersion: 3, sequence: 9, key: "voncrush", player: { name: "VonCrush" } });
setMockDynamicProperty(STATE_KEY, metadata);
setMockDynamicProperty(playerStateKey("voncrush"), shard);
setMockDynamicProperty(playerStateKey("duplicate"), shard);
const capture = captureConsole("error");

const { flush, loadState, storageStatus } = await import("../../behavior_pack/scripts/adapters/store.js");
loadState();

assert.equal(storageStatus().persistenceBlocked, true);
flush(true);
assert.equal(getMockDynamicProperty(STATE_KEY), metadata);
assert.equal(getMockDynamicProperty(playerStateKey("voncrush")), shard);
assert.equal(getMockDynamicProperty(playerStateKey("duplicate")), shard);
assert.ok(capture.lines.some((line) => line.includes("duplicate player shard")));
capture.restore();

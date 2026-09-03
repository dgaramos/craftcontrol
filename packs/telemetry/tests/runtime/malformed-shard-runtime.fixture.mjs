import assert from "node:assert/strict";
import { getMockDynamicProperty, setMockDynamicProperty } from "@minecraft/server";
import { STATE_KEY, playerStateKey } from "../../behavior_pack/scripts/model.js";
import { captureConsole } from "./console-capture.mjs";

const metadata = JSON.stringify({ storageVersion: 3, sequence: 7 });
const malformed = "{not-json";
setMockDynamicProperty(STATE_KEY, metadata);
setMockDynamicProperty(playerStateKey("voncrush"), malformed);
const capture = captureConsole("error");

const { flush, loadState, storageStatus } = await import("../../behavior_pack/scripts/adapters/store.js");
const state = loadState();

assert.deepEqual(state.players, {});
assert.equal(storageStatus().persistenceBlocked, true);
flush(true);
assert.equal(getMockDynamicProperty(STATE_KEY), metadata);
assert.equal(getMockDynamicProperty(playerStateKey("voncrush")), malformed);
assert.ok(capture.lines.some((line) => line.includes("invalid persisted state")));
assert.ok(capture.lines.some((line) => line.includes("persistence blocked")));
capture.restore();

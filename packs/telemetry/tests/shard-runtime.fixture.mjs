import assert from "node:assert/strict";
import { getMockDynamicProperty, setMockDynamicProperty } from "@minecraft/server";
import { STATE_KEY, playerStateKey } from "../behavior_pack/scripts/model.js";

setMockDynamicProperty(STATE_KEY, JSON.stringify({ storageVersion: 3, sequence: 7 }));
setMockDynamicProperty(playerStateKey("voncrush"), JSON.stringify({
  storageVersion: 3,
  sequence: 9,
  key: "voncrush",
  player: { name: "VonCrush", deaths: 5, blocksBroken: 20 },
}));

const { flush, loadState, storageStatus } = await import("../behavior_pack/scripts/store.js");
const state = loadState();
assert.equal(state.sequence, 9);
assert.equal(state.players.voncrush.deaths, 5);
assert.equal(storageStatus().status, "not-required");
flush();
assert.equal(JSON.parse(getMockDynamicProperty(STATE_KEY)).sequence, 9);

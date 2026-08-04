import assert from "node:assert/strict";
import { getMockDynamicProperty, setMockDynamicProperty } from "@minecraft/server";
import { STATE_KEY, playerStateKey } from "../behavior_pack/scripts/model.js";

const shardKey = playerStateKey("voncrush");
const original = JSON.stringify({ storageVersion: 2, sequence: 1, key: "voncrush", player: { name: "VonCrush", deaths: 2 } });
setMockDynamicProperty(STATE_KEY, JSON.stringify({ storageVersion: 2, sequence: 1 }));
setMockDynamicProperty(shardKey, original);
const errors = [];
console.error = (line) => errors.push(String(line));

const { flush, mutatePlayer } = await import("../behavior_pack/scripts/store.js");
mutatePlayer("VonCrush", (state) => { state.players.voncrush.oversized = "x".repeat(31000); });
flush();

assert.equal(getMockDynamicProperty(shardKey), original);
assert.ok(errors.some((line) => line.includes("refusing unsafe write")));

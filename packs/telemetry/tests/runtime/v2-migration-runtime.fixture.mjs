import assert from "node:assert/strict";
import { getMockDynamicProperty, setMockDynamicProperty } from "@minecraft/server";
import { PLAYER_BACKUP_V2_PREFIX, STATE_BACKUP_V2_KEY, STATE_KEY, playerStateKey } from "../../behavior_pack/scripts/model.js";

const meta = JSON.stringify({ storageVersion: 2, sequence: 7 });
const shard = JSON.stringify({ storageVersion: 2, sequence: 9, key: "voncrush", player: { name: "VonCrush", mobKills: 12, distance: 42 } });
setMockDynamicProperty(STATE_KEY, meta);
setMockDynamicProperty(playerStateKey("voncrush"), shard);

const output = [];
console.warn = (line) => output.push(String(line));
await import("../../behavior_pack/scripts/main.js");

const migratedMeta = JSON.parse(getMockDynamicProperty(STATE_KEY));
const migratedShard = JSON.parse(getMockDynamicProperty(playerStateKey("voncrush")));
assert.equal(getMockDynamicProperty(STATE_BACKUP_V2_KEY), meta);
assert.equal(getMockDynamicProperty(`${PLAYER_BACKUP_V2_PREFIX}voncrush`), shard);
assert.equal(migratedMeta.storageVersion, 3);
assert.equal(migratedShard.storageVersion, 3);
assert.equal(migratedShard.player.mobKills, 12);
assert.equal(migratedShard.player.distance, 42);
assert.deepEqual(migratedShard.player.killsByType, {});
assert.deepEqual(migratedShard.player.distanceByDimension, {});
assert.ok(output.some((line) => line.includes("storage 2 -> 3 complete")));

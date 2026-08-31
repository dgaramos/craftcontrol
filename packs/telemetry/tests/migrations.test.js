import { test } from "@jest/globals";
import assert from "node:assert/strict";
import { migrateShardedV2, migrateState } from "../behavior_pack/scripts/migrations.js";

test("migrates legacy schema state without resetting counters", () => {
  const legacy = {
    schema: 1,
    sequence: 42,
    players: {
      voncrush: { name: "VonCrush", aliases: ["VonCrush"], firstSeenAt: 10, lastSeenAt: 20, deaths: 7, blocksBroken: 99 },
    },
  };
  const result = migrateState(legacy);
  assert.equal(result.migratedFrom, 0);
  assert.equal(result.state.storageVersion, 3);
  assert.equal(result.state.sequence, 42);
  assert.equal(result.state.players.voncrush.deaths, 7);
  assert.equal(result.state.players.voncrush.blocksBroken, 99);
  assert.equal(result.state.players.voncrush.mobKills, 0);
  assert.deepEqual(result.state.players.voncrush.killsByType, {});
  assert.deepEqual(result.state.players.voncrush.distanceByDimension, {});
  assert.deepEqual(legacy.players.voncrush, { name: "VonCrush", aliases: ["VonCrush"], firstSeenAt: 10, lastSeenAt: 20, deaths: 7, blocksBroken: 99 });
});

test("migrates monolithic storage v1 independently from protocol schema", () => {
  const current = { storageVersion: 1, sequence: 3, players: {} };
  const result = migrateState(current);
  assert.equal(result.migratedFrom, 1);
  assert.deepEqual(result.state, { storageVersion: 3, sequence: 3, players: {} });
});

test("migrates sharded storage v2 and preserves source shards for backup", () => {
  const raw = JSON.stringify({ storageVersion: 2, sequence: 9, key: "voncrush", player: { name: "VonCrush", mobKills: 7 } });
  const result = migrateShardedV2({ storageVersion: 2, sequence: 7 }, [["bedrock_telemetry:player:voncrush", raw]]);
  assert.equal(result.migratedFrom, 2);
  assert.equal(result.state.storageVersion, 3);
  assert.equal(result.state.sequence, 9);
  assert.equal(result.state.players.voncrush.mobKills, 7);
  assert.deepEqual(result.state.players.voncrush.killsByType, {});
  assert.equal(result.backups[0][1], raw);
});

test("rejects unknown and future storage versions", () => {
  assert.throws(() => migrateState({ storageVersion: 4, sequence: 0, players: {} }), /unsupported storage version/);
  assert.throws(() => migrateState({ schema: 99, sequence: 0, players: {} }), /unrecognized legacy/);
});

import { validatePlayerShard } from "../behavior_pack/scripts/migrations.js";
import { STORAGE_VERSION } from "../behavior_pack/scripts/versions.js";

test("validatePlayerShard rejects wrong storageVersion", () => {
  assert.throws(() => validatePlayerShard({ storageVersion: STORAGE_VERSION - 1, key: "voncrush", sequence: 1, player: {} }), /unsupported player shard version/);
  assert.throws(() => validatePlayerShard(null), /unsupported player shard version/);
});

test("validatePlayerShard rejects missing or empty key", () => {
  assert.throws(() => validatePlayerShard({ storageVersion: STORAGE_VERSION, key: "", sequence: 1, player: { name: "VonCrush" } }), /invalid player shard key/);
  assert.throws(() => validatePlayerShard({ storageVersion: STORAGE_VERSION, sequence: 1, player: { name: "VonCrush" } }), /invalid player shard key/);
});

test("validatePlayerShard rejects non-integer sequence", () => {
  assert.throws(() => validatePlayerShard({ storageVersion: STORAGE_VERSION, key: "voncrush", sequence: -1, player: { name: "VonCrush" } }), /invalid player shard sequence/);
  assert.throws(() => validatePlayerShard({ storageVersion: STORAGE_VERSION, key: "voncrush", sequence: 1.5, player: { name: "VonCrush" } }), /invalid player shard sequence/);
});

test("migrateShardedV2 rejects invalid metadata", () => {
  assert.throws(() => migrateShardedV2(null, []), /invalid storage v2 metadata/);
  assert.throws(() => migrateShardedV2({ storageVersion: 1, sequence: 0 }, []), /invalid storage v2 metadata/);
  assert.throws(() => migrateShardedV2({ storageVersion: 2, sequence: -1 }, []), /invalid storage v2 metadata/);
});

test("migrateShardedV2 rejects shard with wrong storageVersion", () => {
  const shard = JSON.stringify({ storageVersion: 1, key: "voncrush", sequence: 1, player: { name: "VonCrush" } });
  assert.throws(() => migrateShardedV2({ storageVersion: 2, sequence: 0 }, [["bedrock_telemetry:player:voncrush", shard]]), /invalid storage v2 player shard/);
});

test("migrateShardedV2 rejects shard with non-integer sequence", () => {
  const shard = JSON.stringify({ storageVersion: 2, key: "voncrush", sequence: -5, player: { name: "VonCrush" } });
  assert.throws(() => migrateShardedV2({ storageVersion: 2, sequence: 0 }, [["bedrock_telemetry:player:voncrush", shard]]), /invalid storage v2 player shard/);
});

test("migrateShardedV2 rejects duplicate player key across shards", () => {
  const shard = JSON.stringify({ storageVersion: 2, key: "voncrush", sequence: 1, player: { name: "VonCrush" } });
  assert.throws(
    () => migrateShardedV2({ storageVersion: 2, sequence: 0 }, [
      ["bedrock_telemetry:player:voncrush", shard],
      ["bedrock_telemetry:player:voncrush2", shard],
    ]),
    /invalid storage v2 player shard/
  );
});

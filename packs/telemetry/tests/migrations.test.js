import test from "node:test";
import assert from "node:assert/strict";
import { migrateState, validateState } from "../behavior_pack/scripts/migrations.js";

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
  assert.equal(result.state.storageVersion, 2);
  assert.equal(result.state.sequence, 42);
  assert.equal(result.state.players.voncrush.deaths, 7);
  assert.equal(result.state.players.voncrush.blocksBroken, 99);
  assert.equal(result.state.players.voncrush.mobKills, 0);
  assert.deepEqual(legacy.players.voncrush, { name: "VonCrush", aliases: ["VonCrush"], firstSeenAt: 10, lastSeenAt: 20, deaths: 7, blocksBroken: 99 });
});

test("migrates monolithic storage v1 independently from protocol schema", () => {
  const current = { storageVersion: 1, sequence: 3, players: {} };
  const result = migrateState(current);
  assert.equal(result.migratedFrom, 1);
  assert.deepEqual(result.state, { storageVersion: 2, sequence: 3, players: {} });
});

test("rejects unknown and future storage versions", () => {
  assert.throws(() => migrateState({ storageVersion: 3, sequence: 0, players: {} }), /unsupported storage version/);
  assert.throws(() => migrateState({ schema: 99, sequence: 0, players: {} }), /unrecognized legacy/);
});

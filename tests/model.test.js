import test from "node:test";
import assert from "node:assert/strict";
import { emptyState, ensurePlayer, horizontalDistance, incrementMap } from "../behavior_pack/scripts/model.js";

test("creates and updates a persistent player record", () => {
  const state = emptyState();
  const player = ensurePlayer(state, "VonCrush", 100);
  player.deaths += 1;
  assert.equal(ensurePlayer(state, "VonCrush", 200).deaths, 1);
  assert.equal(player.firstSeenAt, 100);
  assert.equal(player.lastSeenAt, 200);
});

test("caps high-cardinality maps to their most frequent values", () => {
  const values = {};
  incrementMap(values, "stone", 10, 2);
  incrementMap(values, "dirt", 5, 2);
  incrementMap(values, "sand", 1, 2);
  assert.deepEqual(values, { stone: 10, dirt: 5 });
});

test("measures horizontal movement without vertical inflation", () => {
  assert.equal(horizontalDistance({ x: 0, y: 0, z: 0 }, { x: 3, y: 100, z: 4 }), 5);
});

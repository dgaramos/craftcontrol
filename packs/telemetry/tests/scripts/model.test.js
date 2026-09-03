import { test } from "@jest/globals";
import assert from "node:assert/strict";
import { emptyState, ensurePlayer, horizontalDistance, incrementMap, observeDimension, round } from "../../behavior_pack/scripts/model.js";

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

test("rounds telemetry values to stable precision", () => {
  assert.equal(round(1.23456789), 1.23);
});

test("ensurePlayer appends name to aliases when same player returns with a different display name", () => {
  const state = emptyState();
  ensurePlayer(state, "VonCrush", 100);
  const player = ensurePlayer(state, "voncrush", 200);
  assert.ok(player.aliases.includes("VonCrush"));
  assert.ok(player.aliases.includes("voncrush"));
});

test("observeDimension ignores falsy dimension", () => {
  const stats = { dimensions: {}, firstDimensionVisitAt: {}, lastDimensionVisitAt: {} };
  observeDimension(stats, null, 1000);
  assert.deepEqual(stats.dimensions, {});
});

test("observeDimension records first and last visit timestamps", () => {
  const stats = { dimensions: {}, firstDimensionVisitAt: {}, lastDimensionVisitAt: {} };
  observeDimension(stats, "overworld", 1000);
  assert.equal(stats.firstDimensionVisitAt.overworld, 1000);
  assert.equal(stats.lastDimensionVisitAt.overworld, 1000);
  observeDimension(stats, "overworld", 2000);
  assert.equal(stats.firstDimensionVisitAt.overworld, 1000);
  assert.equal(stats.lastDimensionVisitAt.overworld, 2000);
});

test("observeDimension increments dimension counter only on incrementVisit or first visit", () => {
  const stats = { dimensions: {}, firstDimensionVisitAt: {}, lastDimensionVisitAt: {} };
  observeDimension(stats, "nether", 100, false);
  assert.equal(stats.dimensions.nether, 1);
  observeDimension(stats, "nether", 200, false);
  assert.equal(stats.dimensions.nether, 1);
  observeDimension(stats, "nether", 300, true);
  assert.equal(stats.dimensions.nether, 2);
});

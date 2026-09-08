/**
 * The performance bounds the metric policy promises (#274).
 *
 * `docs/telemetry-metrics.md` says a metric that exceeds the shard budget or
 * grows the flush is disabled rather than shipped slower, and that the
 * measurement decides. These tests are that measurement: they fail when item
 * use — or the interaction metrics that follow it — would stop fitting.
 */

import { test, expect } from "@jest/globals";
import { MAX_BLOCK_TYPES, MAX_METRIC_TYPES, emptyPlayer, incrementMap } from "../../behavior_pack/scripts/model.js";
import { STORAGE_VERSION } from "../../behavior_pack/scripts/versions.js";

// The store refuses to write a shard above this, so a shard that does not fit
// is a shard that is silently not persisted. It is a hard bound, not a target.
const SHARD_BUDGET_BYTES = 30000;

// `minecraft:waxed_weathered_cut_copper_stairs` is 43 characters. Filling every
// map with identifiers that long is the worst case a real world can produce.
const LONGEST_IDENTIFIER = 43;

const BLOCK_MAPS = ["brokenByType", "placedByType", "killsByType"];
// Every map epic #21 adds, including the three #275 still owes.
const METRIC_MAPS = ["usedByType", "interactedBlocksByType", "interactedEntitiesByType", "openedContainersByType"];

function identifiers(prefix, count, length) {
  return Array.from({ length: count }, (_, index) =>
    `minecraft:${prefix}${String(index).padStart(3, "0")}`.padEnd(length, "x").slice(0, length));
}

function fullPlayer({ metricMaps = METRIC_MAPS, length = LONGEST_IDENTIFIER } = {}) {
  const player = emptyPlayer("VonCrush", 1788831282726);
  for (const field of BLOCK_MAPS) {
    for (const id of identifiers(field, MAX_BLOCK_TYPES * 2, length)) incrementMap(player[field], id, 999999);
  }
  for (const field of metricMaps) {
    player[field] ??= {};
    for (const id of identifiers(field, MAX_METRIC_TYPES * 2, length)) incrementMap(player[field], id, 999999, MAX_METRIC_TYPES);
  }
  for (const field of ["dimensions", "distanceByDimension", "activeTimeByDimension", "firstDimensionVisitAt", "lastDimensionVisitAt"]) {
    for (const id of identifiers(field, 16, length)) incrementMap(player[field], id, 1788831282726, 8);
  }
  return player;
}

const shardBytes = (player) =>
  JSON.stringify({ storageVersion: STORAGE_VERSION, sequence: 999999, key: "voncrush", player }).length;

test("a player shard with item use enabled and every map full fits the budget", () => {
  expect(shardBytes(fullPlayer({ metricMaps: ["usedByType"] }))).toBeLessThan(SHARD_BUDGET_BYTES);
});

test("the budget still holds once the interaction metrics of #275 land", () => {
  // The bound was chosen from this number, not the other way round: at 128
  // entries these four maps overflow the shard by more than 50%.
  expect(shardBytes(fullPlayer())).toBeLessThan(SHARD_BUDGET_BYTES);
});

test("128-entry metric maps would overflow the shard, which is why they are smaller", () => {
  const overflowing = emptyPlayer("VonCrush", 1788831282726);
  for (const field of [...BLOCK_MAPS, ...METRIC_MAPS]) {
    overflowing[field] ??= {};
    for (const id of identifiers(field, 200, LONGEST_IDENTIFIER)) incrementMap(overflowing[field], id, 999999);
  }
  expect(shardBytes(overflowing)).toBeGreaterThan(SHARD_BUDGET_BYTES);
  expect(MAX_METRIC_TYPES).toBeLessThan(MAX_BLOCK_TYPES);
});

test("eviction costs the long tail and never the total", () => {
  const player = emptyPlayer("VonCrush", 0);
  let used = 0;
  for (const id of identifiers("item", 500, 30)) {
    player.itemsUsed += 1;
    used += 1;
    incrementMap(player.usedByType, id, 1, MAX_METRIC_TYPES);
  }
  expect(Object.keys(player.usedByType)).toHaveLength(MAX_METRIC_TYPES);
  // The counter is exact even though the breakdown is not: a panel may say how
  // many items were used, and only the per-type split is a top list.
  expect(player.itemsUsed).toBe(used);
});

test("per-event cost stays flat as the map saturates", () => {
  // incrementMap sorts on overflow, so the guard that matters is that the sort
  // is over the bound and not over everything ever seen. A quadratic
  // regression here fires on a busy server, not in a fixture.
  const player = emptyPlayer("VonCrush", 0);
  const identifierPool = identifiers("item", 5000, 30);
  const measure = (from, to) => {
    const started = process.hrtime.bigint();
    for (let index = from; index < to; index += 1) incrementMap(player.usedByType, identifierPool[index % identifierPool.length], 1, MAX_METRIC_TYPES);
    return Number(process.hrtime.bigint() - started);
  };
  measure(0, 20000);                       // warm up and saturate the map
  const early = Math.max(measure(20000, 40000), 1);
  const late = Math.max(measure(40000, 60000), 1);
  expect(late / early).toBeLessThan(5);
});

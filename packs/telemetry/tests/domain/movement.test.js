import assert from "node:assert/strict";
import { test } from "@jest/globals";
import { samplePlayerMovement } from "../../behavior_pack/scripts/domain/movement.js";

function makePlayer(id, x, z, dimension = "minecraft:overworld") {
  return { id, name: `Player_${id}`, location: { x, y: 64, z }, dimension: { id: dimension } };
}

test("accumulates distance when player moves within threshold", () => {
  const positions = new Map();
  const player = makePlayer("p1", 0, 0);

  // First tick: no previous — just stores position, no accumulation.
  const calls1 = [];
  samplePlayerMovement(positions, player, (dim, dist) => calls1.push({ dim, dist }));
  assert.equal(calls1.length, 0, "first tick must not accumulate");

  // Move 10 blocks along z.
  player.location = { x: 0, y: 64, z: 10 };
  const calls2 = [];
  samplePlayerMovement(positions, player, (dim, dist) => calls2.push({ dim, dist }));
  assert.equal(calls2.length, 1, "second tick must call onDistance");
  assert.equal(calls2[0].dim, "minecraft:overworld");
  assert.ok(Math.abs(calls2[0].dist - 10) < 0.01, `distance should be ~10, got ${calls2[0].dist}`);
});

test("does not accumulate on first tick (no previous position)", () => {
  const positions = new Map();
  const player = makePlayer("p2", 50, 50);
  const calls = [];
  samplePlayerMovement(positions, player, (dim, dist) => calls.push({ dim, dist }));
  assert.equal(calls.length, 0, "first tick must not call onDistance");
  assert.ok(positions.has("p2"), "position must be stored after first tick");
});

test("does not accumulate on teleport exceeding 128 blocks", () => {
  const positions = new Map();
  const player = makePlayer("p3", 0, 0);
  samplePlayerMovement(positions, player, () => {}); // first tick, stores position

  player.location = { x: 200, y: 64, z: 0 };
  const calls = [];
  samplePlayerMovement(positions, player, (dim, dist) => calls.push({ dim, dist }));
  assert.equal(calls.length, 0, "teleport >128 blocks must not accumulate");
});

test("does not accumulate on dimension mismatch between ticks", () => {
  const positions = new Map();
  const player = makePlayer("p4", 100, 100, "minecraft:nether");
  samplePlayerMovement(positions, player, () => {}); // records in nether

  player.dimension = { id: "minecraft:overworld" };
  player.location = { x: 101, y: 64, z: 100 };
  const calls = [];
  samplePlayerMovement(positions, player, (dim, dist) => calls.push({ dim, dist }));
  assert.equal(calls.length, 0, "dimension mismatch must not accumulate");
});

test("does not accumulate when player stands still (distance == 0)", () => {
  const positions = new Map();
  const player = makePlayer("p5", 10, 10);
  samplePlayerMovement(positions, player, () => {}); // first tick

  const calls = [];
  samplePlayerMovement(positions, player, (dim, dist) => calls.push({ dim, dist }));
  assert.equal(calls.length, 0, "standing still must not accumulate");
});

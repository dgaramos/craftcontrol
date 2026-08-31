import assert from "node:assert/strict";
import { test } from "@jest/globals";
import { trackGameModes, removePlayer } from "../behavior_pack/scripts/domain/gamemode.js";

function makePlayer(id, name, gameMode) {
  return {
    id,
    name,
    getGameMode: gameMode !== undefined ? () => gameMode : undefined,
  };
}

test("emits player.gamemode.changed when mode transitions from previous value", () => {
  const gameModes = new Map();
  const published = [];
  const publish = (type, playerName, data) => published.push({ type, playerName, data });
  const readGameMode = (player) => (player.getGameMode ? player.getGameMode() : null);

  const player = makePlayer("p1", "VonCrush", "survival");

  // First cycle: no previous — should store without publishing
  trackGameModes(gameModes, [player], readGameMode, publish);
  assert.equal(published.length, 0, "first cycle must not publish a change event");
  assert.equal(gameModes.get("p1"), "survival");

  // Second cycle: same mode — no event
  trackGameModes(gameModes, [player], readGameMode, publish);
  assert.equal(published.length, 0, "same mode must not publish a change event");

  // Third cycle: mode changes to creative
  player.getGameMode = () => "creative";
  trackGameModes(gameModes, [player], readGameMode, publish);
  assert.equal(published.length, 1, "mode change must publish exactly one event");
  assert.equal(published[0].type, "player.gamemode.changed");
  assert.equal(published[0].playerName, "VonCrush");
  assert.equal(published[0].data.previous, "survival");
  assert.equal(published[0].data.current, "creative");
  assert.equal(gameModes.get("p1"), "creative");
});

test("does not publish when readGameMode returns null (capability unsupported)", () => {
  const gameModes = new Map();
  const published = [];
  const publish = (type, playerName, data) => published.push({ type, playerName, data });
  const readGameMode = () => null;

  const player = makePlayer("p2", "Craft", "survival");

  trackGameModes(gameModes, [player], readGameMode, publish);
  trackGameModes(gameModes, [player], readGameMode, publish);
  assert.equal(published.length, 0, "null readGameMode must never publish");
  assert.equal(gameModes.size, 0, "null readGameMode must not store state");
});

test("removePlayer cleans up offline player state so no stale change is emitted on rejoin", () => {
  const gameModes = new Map();
  const published = [];
  const publish = (type, playerName, data) => published.push({ type, playerName, data });
  const readGameMode = (player) => player.getGameMode();

  const player = makePlayer("p3", "Offline", "survival");

  // Establish state
  trackGameModes(gameModes, [player], readGameMode, publish);
  assert.ok(gameModes.has("p3"));

  // Player leaves
  removePlayer(gameModes, "p3");
  assert.ok(!gameModes.has("p3"), "state must be removed on leave");

  // Player rejoins with same mode — no stale event expected
  trackGameModes(gameModes, [player], readGameMode, publish);
  assert.equal(published.length, 0, "rejoin after removePlayer must not emit a change event");
});

test("handles mix of players with and without getGameMode in a single cycle", () => {
  const gameModes = new Map();
  const published = [];
  const publish = (type, playerName, data) => published.push({ type, playerName, data });
  const readGameMode = (player) => (player.getGameMode ? player.getGameMode() : null);

  const supported = makePlayer("p4", "Supported", "creative");
  const unsupported = makePlayer("p5", "Unsupported"); // no getGameMode

  // First cycle: establish state for supported player
  trackGameModes(gameModes, [supported, unsupported], readGameMode, publish);
  assert.equal(gameModes.size, 1, "only the supported player must have stored state");
  assert.equal(gameModes.get("p4"), "creative");

  // Second cycle: supported player changes mode, unsupported remains silent
  supported.getGameMode = () => "survival";
  trackGameModes(gameModes, [supported, unsupported], readGameMode, publish);
  assert.equal(published.length, 1, "only the supported player emits the event");
  assert.equal(published[0].playerName, "Supported");
});

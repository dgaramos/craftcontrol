import { jest, beforeEach, test, expect } from "@jest/globals";

// Mocks must be declared before any dynamic import of modules that depend on them.

const mockMutatePlayer = jest.fn((name, cb) => cb({ players: {} }));
const mockFlush = jest.fn();
const mockLoadState = jest.fn(() => ({ sequence: 0, players: {} }));
const mockStorageStatus = jest.fn(() => ({ persistenceBlocked: false }));
const mockNextSequence = jest.fn(() => 1);

jest.unstable_mockModule("../behavior_pack/scripts/adapters/store.js", () => ({
  mutatePlayer: mockMutatePlayer,
  flush: mockFlush,
  loadState: mockLoadState,
  storageStatus: mockStorageStatus,
  nextSequence: mockNextSequence,
}));

const mockPublish = jest.fn();
const mockPublishBlockChanges = jest.fn();
const mockPublishSnapshot = jest.fn();
const mockQueueBlockChange = jest.fn();

jest.unstable_mockModule("../behavior_pack/scripts/adapters/transport.js", () => ({
  publish: mockPublish,
  publishBlockChanges: mockPublishBlockChanges,
  publishSnapshot: mockPublishSnapshot,
  queueBlockChange: mockQueueBlockChange,
}));

let capturedSamplingCallback = null;
const mockStartMovementSampling = jest.fn((cb) => { capturedSamplingCallback = cb; });
const mockSubscribeWorldEvent = jest.fn();
const mockSubscribeScriptEvents = jest.fn();
const mockProbeGameModeReading = jest.fn();
const mockReadGameMode = jest.fn(() => null);
const mockCapabilitySnapshot = jest.fn(() => ({}));

jest.unstable_mockModule("../behavior_pack/scripts/adapters/capabilities.js", () => ({
  startMovementSampling: mockStartMovementSampling,
  subscribeWorldEvent: mockSubscribeWorldEvent,
  subscribeScriptEvents: mockSubscribeScriptEvents,
  probeGameModeReading: mockProbeGameModeReading,
  readGameMode: mockReadGameMode,
  capabilitySnapshot: mockCapabilitySnapshot,
}));

// samplePlayerMovement immediately calls onDistance to exercise the callback in main.js
const mockSamplePlayerMovement = jest.fn((positions, player, onDistance) => {
  onDistance("minecraft:overworld", 10);
});

jest.unstable_mockModule("../behavior_pack/scripts/domain/movement.js", () => ({
  samplePlayerMovement: mockSamplePlayerMovement,
}));

const mockTrackGameModes = jest.fn();
const mockRemovePlayer = jest.fn();

jest.unstable_mockModule("../behavior_pack/scripts/domain/gamemode.js", () => ({
  trackGameModes: mockTrackGameModes,
  removePlayer: mockRemovePlayer,
}));

const { world } = await import("@minecraft/server");

// Import main.js to trigger module-level subscriptions and startMovementSampling.
// domain/events.js is NOT mocked — it runs for real, calling the mocked subscribeWorldEvent.
await import("../behavior_pack/scripts/main.js");

// Capture event handlers before beforeEach clears mock call records.
// worldEventHandlers[signal] is the lambda from events.js that delegates to the main.js handler.
const worldEventHandlers = Object.fromEntries(
  mockSubscribeWorldEvent.mock.calls.map(([signal, , handler]) => [signal, handler])
);

beforeEach(() => {
  jest.clearAllMocks();
  mockMutatePlayer.mockImplementation((name, cb) => cb({ players: {} }));
  mockReadGameMode.mockReturnValue(null);
  mockSamplePlayerMovement.mockImplementation((positions, player, onDistance) => {
    onDistance("minecraft:overworld", 10);
  });
  world.players = [];
});

// ---------------------------------------------------------------------------
// Movement sampling
// ---------------------------------------------------------------------------

test("movement sampling callback updates distance stats for each live player", () => {
  const player = { id: "p1", name: "VonCrush", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  world.players = [player];

  capturedSamplingCallback();

  expect(mockSamplePlayerMovement).toHaveBeenCalledWith(
    expect.any(Map),
    player,
    expect.any(Function),
  );
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
});

test("movement sampling callback skips stats update when samplePlayerMovement yields no distance", () => {
  mockSamplePlayerMovement.mockImplementation(() => {});
  const player = { id: "p2", name: "Craft", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  world.players = [player];

  capturedSamplingCallback();

  expect(mockSamplePlayerMovement).toHaveBeenCalled();
  expect(mockMutatePlayer).not.toHaveBeenCalled();
});

// ---------------------------------------------------------------------------
// World event handlers (via events.js delegation)
// ---------------------------------------------------------------------------

test("onPlayerJoin increments joins and publishes player.joined", () => {
  worldEventHandlers.playerJoin({ playerName: "VonCrush" });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockPublish).toHaveBeenCalledWith("player.joined", "VonCrush");
});

test("onPlayerLeave calls removePlayer and publishes player.left", () => {
  worldEventHandlers.playerLeave({ playerId: "p1", playerName: "VonCrush" });
  expect(mockRemovePlayer).toHaveBeenCalledWith(expect.any(Map), "p1");
  expect(mockPublish).toHaveBeenCalledWith("player.left", "VonCrush");
});

test("onPlayerSpawn records position and publishes respawn when not initial spawn", () => {
  const player = { id: "p1", name: "VonCrush", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  worldEventHandlers.playerSpawn({ player, initialSpawn: false });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockPublish).toHaveBeenCalledWith("player.respawned", "VonCrush");
});

test("onPlayerSpawn does not publish respawn on initial spawn", () => {
  const player = { id: "p1", name: "VonCrush", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  worldEventHandlers.playerSpawn({ player, initialSpawn: true });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockPublish).not.toHaveBeenCalled();
});

test("onEntityDie updates victim and killer stats and publishes entity.died", () => {
  const event = {
    deadEntity: { typeId: "minecraft:player", name: "VonCrush" },
    damageSource: {
      cause: "entity_attack",
      damagingEntity: { typeId: "minecraft:player", name: "Craft" },
      damagingProjectile: null,
    },
  };
  worldEventHandlers.entityDie(event);
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockMutatePlayer).toHaveBeenCalledWith("Craft", expect.any(Function));
  expect(mockPublish).toHaveBeenCalledWith("entity.died", "VonCrush", expect.objectContaining({ victim: "VonCrush" }));
});

test("onEntityDie handles mob kill when killer hits non-player", () => {
  const event = {
    deadEntity: { typeId: "minecraft:zombie", name: undefined },
    damageSource: {
      cause: "entity_attack",
      damagingEntity: { typeId: "minecraft:player", name: "Craft" },
      damagingProjectile: null,
    },
  };
  worldEventHandlers.entityDie(event);
  expect(mockMutatePlayer).toHaveBeenCalledWith("Craft", expect.any(Function));
});

test("onEntityHurt updates damageTaken for victim and damageDealt for attacker", () => {
  const event = {
    hurtEntity: { typeId: "minecraft:player", name: "VonCrush" },
    damageSource: { damagingEntity: { typeId: "minecraft:player", name: "Craft" } },
    damage: 5,
  };
  worldEventHandlers.entityHurt(event);
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockMutatePlayer).toHaveBeenCalledWith("Craft", expect.any(Function));
});

test("onPlayerBreakBlock updates blocksBroken and queues block change", () => {
  const event = {
    player: { name: "VonCrush" },
    brokenBlockPermutation: { type: { id: "minecraft:stone" } },
  };
  worldEventHandlers.playerBreakBlock(event);
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockQueueBlockChange).toHaveBeenCalledWith("VonCrush", "broken", "minecraft:stone");
});

test("onPlayerPlaceBlock updates blocksPlaced and queues block change", () => {
  const event = {
    player: { name: "VonCrush" },
    block: { typeId: "minecraft:dirt" },
  };
  worldEventHandlers.playerPlaceBlock(event);
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockQueueBlockChange).toHaveBeenCalledWith("VonCrush", "placed", "minecraft:dirt");
});

test("onPlayerDimensionChange records new position and publishes dimension change", () => {
  const event = {
    player: { id: "p1", name: "VonCrush" },
    toLocation: { x: 10, y: 64, z: 20 },
    fromDimension: { id: "minecraft:overworld" },
    toDimension: { id: "minecraft:nether" },
  };
  worldEventHandlers.playerDimensionChange(event);
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockPublish).toHaveBeenCalledWith("player.dimension.changed", "VonCrush", {
    from: "minecraft:overworld",
    to: "minecraft:nether",
  });
});

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
await import("../behavior_pack/scripts/main.js");

// Capture event handlers before beforeEach clears mock call records.
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

test("movement sampling callback updates distance stats for each live player", () => {
  const player = { id: "p1", name: "VonCrush", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  world.players = [player];

  capturedSamplingCallback();

  expect(mockSamplePlayerMovement).toHaveBeenCalledWith(
    expect.any(Map),
    player,
    expect.any(Function),
  );
  // mutatePlayer is called to persist the distance update
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
});

test("playerLeave handler calls removePlayer to clean up game mode state", () => {
  worldEventHandlers.playerLeave({ playerId: "p1", playerName: "VonCrush" });
  expect(mockRemovePlayer).toHaveBeenCalledWith(expect.any(Map), "p1");
});

test("movement sampling callback skips stats update when samplePlayerMovement yields no distance", () => {
  mockSamplePlayerMovement.mockImplementation(() => {}); // no onDistance call
  const player = { id: "p2", name: "Craft", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  world.players = [player];

  capturedSamplingCallback();

  expect(mockSamplePlayerMovement).toHaveBeenCalled();
  expect(mockMutatePlayer).not.toHaveBeenCalled();
});

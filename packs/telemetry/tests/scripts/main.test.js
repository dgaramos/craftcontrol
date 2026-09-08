import { jest, beforeEach, test, expect } from "@jest/globals";
import { world } from "@minecraft/server";
import { startTelemetryRuntime } from "../../behavior_pack/scripts/main.js";

const emptyStats = () => ({ joins: 0, deaths: 0, playerKills: 0, mobKills: 0, killsByType: {}, damageTaken: 0, damageDealt: 0, blocksBroken: 0, brokenByType: {}, blocksPlaced: 0, placedByType: {}, itemsUsed: 0, usedByType: {}, distance: 0, distanceByDimension: {}, activeTimeByDimension: {} });
const mockSystem = { run: jest.fn(), runTimeout: jest.fn() };
const mockEnsurePlayer = jest.fn((state, name) => {
  state.players[name] ??= emptyStats();
  return state.players[name];
});
const mockIncrementMap = jest.fn((map, key, amount = 1) => { map[key] = (map[key] || 0) + amount; });
const mockObserveDimension = jest.fn();
const mockRound = jest.fn((value) => value);
const mockMutatePlayer = jest.fn((name, callback) => callback({ players: {} }));
const mockFlush = jest.fn();
const mockLoadState = jest.fn(() => ({ sequence: 0, players: {} }));
const mockStorageStatus = jest.fn(() => ({ persistenceBlocked: false }));
const mockPublish = jest.fn();
const mockPublishBlockChanges = jest.fn();
const mockPublishSnapshot = jest.fn();
const mockQueueBlockChange = jest.fn();
const mockQueueItemUse = jest.fn();
const mockPublishItemUse = jest.fn();
const mockPublishMetrics = jest.fn();
const mockApplyMetrics = jest.fn(() => ({ itemUse: true }));
const mockMetricsSnapshot = jest.fn(() => ({ itemUse: false }));
const mockMetricEnabled = jest.fn(() => false);
const mockMetricKey = jest.fn((value) => (typeof value === "string" && value.includes(":") ? value : null));
const mockCapabilitySnapshot = jest.fn(() => ({}));
const mockProbeGameModeReading = jest.fn();
const mockReadGameMode = jest.fn(() => null);
const mockSubscribeScriptEvents = jest.fn();
const mockTrackGameModes = jest.fn();
const mockRemovePlayer = jest.fn();
const mockRegisterEvents = jest.fn();

let capturedHandlers;
let capturedSamplingCallback;

const mockStartMovementSampling = jest.fn((callback) => { capturedSamplingCallback = callback; });
const mockSamplePlayerMovement = jest.fn((positions, player, onDistance) => {
  onDistance("minecraft:overworld", 10);
});

function startRuntime() {
  startTelemetryRuntime({
    system: mockSystem,
    world,
    ensurePlayer: mockEnsurePlayer,
    incrementMap: mockIncrementMap,
    observeDimension: mockObserveDimension,
    round: mockRound,
    flush: mockFlush,
    loadState: mockLoadState,
    mutatePlayer: mockMutatePlayer,
    storageStatus: mockStorageStatus,
    publish: mockPublish,
    publishBlockChanges: mockPublishBlockChanges,
    publishSnapshot: mockPublishSnapshot,
    queueBlockChange: mockQueueBlockChange,
    queueItemUse: mockQueueItemUse,
    publishItemUse: mockPublishItemUse,
    publishMetrics: mockPublishMetrics,
    applyMetrics: mockApplyMetrics,
    metricsSnapshot: mockMetricsSnapshot,
    metricEnabled: mockMetricEnabled,
    metricKey: mockMetricKey,
    capabilitySnapshot: mockCapabilitySnapshot,
    probeGameModeReading: mockProbeGameModeReading,
    readGameMode: mockReadGameMode,
    startMovementSampling: mockStartMovementSampling,
    subscribeScriptEvents: mockSubscribeScriptEvents,
    samplePlayerMovement: mockSamplePlayerMovement,
    trackGameModes: mockTrackGameModes,
    removePlayer: mockRemovePlayer,
    registerEvents: mockRegisterEvents,
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  capturedHandlers = undefined;
  capturedSamplingCallback = undefined;
  mockRegisterEvents.mockImplementation((handlers) => { capturedHandlers = handlers; });
  mockMutatePlayer.mockImplementation((name, callback) => callback({ players: {} }));
  mockReadGameMode.mockReturnValue(null);
  mockMetricEnabled.mockReturnValue(false);
  mockApplyMetrics.mockReturnValue({ itemUse: true });
  mockMetricsSnapshot.mockReturnValue({ itemUse: false });
  mockSamplePlayerMovement.mockImplementation((positions, player, onDistance) => { onDistance("minecraft:overworld", 10); });
  world.players = [];
  startRuntime();
});

test("runtime injects event registration and movement sampling collaborators", () => {
  expect(mockRegisterEvents).toHaveBeenCalledWith(expect.any(Object));
  expect(capturedHandlers).toEqual(expect.objectContaining({ onPlayerJoin: expect.any(Function), onEntityDie: expect.any(Function) }));
  expect(mockStartMovementSampling).toHaveBeenCalledWith(expect.any(Function), 100);
  expect(capturedSamplingCallback).toEqual(expect.any(Function));
});

test("script event collaborator schedules a snapshot only for the sync event", () => {
  const callback = mockSubscribeScriptEvents.mock.calls[0][0];
  callback({ id: "bedrock_telemetry:sync" });
  callback({ id: "unrelated:event" });

  expect(mockSystem.run).toHaveBeenCalledTimes(1);
  expect(mockSystem.run).toHaveBeenCalledWith(mockPublishSnapshot);
});

// -- opt-in item use --------------------------------------------------------

const useEvent = (typeId = "minecraft:bow", name = "VonCrush") => ({
  source: { name }, itemStack: { typeId },
});

test("onPlayerUseItem collects nothing while the metric is disabled", () => {
  // The subscription exists so the capability can be reported; the owner's
  // decision is what turns counting on.
  capturedHandlers.onPlayerUseItem(useEvent());
  expect(mockMutatePlayer).not.toHaveBeenCalled();
  expect(mockQueueItemUse).not.toHaveBeenCalled();
});

test("onPlayerUseItem counts the use and queues the batch once enabled", () => {
  mockMetricEnabled.mockReturnValue(true);
  capturedHandlers.onPlayerUseItem(useEvent());
  expect(mockMetricEnabled).toHaveBeenCalledWith("itemUse");
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockIncrementMap).toHaveBeenCalledWith(expect.any(Object), "minecraft:bow", 1, 24);
  expect(mockQueueItemUse).toHaveBeenCalledWith("VonCrush", "minecraft:bow");
});

test("onPlayerUseItem discards an identifier the policy will not store", () => {
  mockMetricEnabled.mockReturnValue(true);
  capturedHandlers.onPlayerUseItem(useEvent("Excalibur"));
  expect(mockMutatePlayer).not.toHaveBeenCalled();
  expect(mockQueueItemUse).not.toHaveBeenCalled();
});

test("onPlayerUseItem ignores an event with no item or no player", () => {
  mockMetricEnabled.mockReturnValue(true);
  capturedHandlers.onPlayerUseItem({ source: { name: "VonCrush" } });
  capturedHandlers.onPlayerUseItem({ itemStack: { typeId: "minecraft:bow" } });
  expect(mockMutatePlayer).not.toHaveBeenCalled();
});

test("the metrics script event applies the command and announces the result", () => {
  const callback = mockSubscribeScriptEvents.mock.calls[0][0];
  callback({ id: "bedrock_telemetry:metrics", message: "enable itemUse" });
  const scheduled = mockSystem.run.mock.calls.at(-1)[0];
  scheduled();

  expect(mockApplyMetrics).toHaveBeenCalledWith("enable itemUse");
  expect(mockPublishMetrics).toHaveBeenCalledWith({ itemUse: true });
});

test("a refused metric command announces nothing", () => {
  mockApplyMetrics.mockReturnValue(null);
  const callback = mockSubscribeScriptEvents.mock.calls[0][0];
  callback({ id: "bedrock_telemetry:metrics", message: "enable chatCapture" });
  mockSystem.run.mock.calls.at(-1)[0]();

  expect(mockPublishMetrics).not.toHaveBeenCalled();
});

test("the five-second cycle drains pending item use", () => {
  capturedSamplingCallback();
  expect(mockPublishItemUse).toHaveBeenCalled();
});

test("telemetry.started reports which metrics are enabled", () => {
  // The startup announcement is scheduled, not immediate.
  mockSystem.runTimeout.mock.calls.at(-1)[0]();
  expect(mockPublish).toHaveBeenCalledWith("telemetry.started", null, expect.objectContaining({
    metrics: { itemUse: false },
  }));
});

test("movement sampling callback updates distance stats for each live player", () => {
  const player = { id: "p1", name: "VonCrush", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  world.players = [player];
  capturedSamplingCallback();
  expect(mockSamplePlayerMovement).toHaveBeenCalledWith(expect.any(Map), player, expect.any(Function));
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockFlush).toHaveBeenCalled();
});

test("movement sampling callback skips stats update when samplePlayerMovement yields no distance", () => {
  mockSamplePlayerMovement.mockImplementation(() => {});
  world.players = [{ id: "p2", name: "Craft", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } }];
  capturedSamplingCallback();
  expect(mockSamplePlayerMovement).toHaveBeenCalled();
  expect(mockMutatePlayer).not.toHaveBeenCalled();
});

test("onPlayerJoin increments joins and publishes player.joined", () => {
  capturedHandlers.onPlayerJoin({ playerName: "VonCrush" });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockPublish).toHaveBeenCalledWith("player.joined", "VonCrush");
});

test("onPlayerLeave calls removePlayer and publishes player.left", () => {
  capturedHandlers.onPlayerLeave({ playerId: "p1", playerName: "VonCrush" });
  expect(mockRemovePlayer).toHaveBeenCalledWith(expect.any(Map), "p1");
  expect(mockPublish).toHaveBeenCalledWith("player.left", "VonCrush");
});

test("onPlayerSpawn records position and publishes respawn when not initial spawn", () => {
  const player = { id: "p1", name: "VonCrush", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  capturedHandlers.onPlayerSpawn({ player, initialSpawn: false });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockPublish).toHaveBeenCalledWith("player.respawned", "VonCrush");
});

test("onPlayerSpawn does not publish respawn on initial spawn", () => {
  const player = { id: "p1", name: "VonCrush", location: { x: 0, y: 64, z: 0 }, dimension: { id: "minecraft:overworld" } };
  capturedHandlers.onPlayerSpawn({ player, initialSpawn: true });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockPublish).not.toHaveBeenCalled();
});

test("onEntityDie updates victim and killer stats and publishes entity.died", () => {
  capturedHandlers.onEntityDie({ deadEntity: { typeId: "minecraft:player", name: "VonCrush" }, damageSource: { cause: "entity_attack", damagingEntity: { typeId: "minecraft:player", name: "Craft" }, damagingProjectile: null } });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockMutatePlayer).toHaveBeenCalledWith("Craft", expect.any(Function));
  expect(mockPublish).toHaveBeenCalledWith("entity.died", "VonCrush", expect.objectContaining({ victim: "VonCrush" }));
});

test("onEntityDie handles mob kill when killer hits non-player", () => {
  capturedHandlers.onEntityDie({ deadEntity: { typeId: "minecraft:zombie" }, damageSource: { cause: "entity_attack", damagingEntity: { typeId: "minecraft:player", name: "Craft" }, damagingProjectile: null } });
  expect(mockMutatePlayer).toHaveBeenCalledWith("Craft", expect.any(Function));
});

test("onEntityDie accepts absent optional damage entities", () => {
  capturedHandlers.onEntityDie({
    deadEntity: { typeId: "minecraft:player", name: "VonCrush" },
    damageSource: { cause: "fall" },
  });

  expect(mockPublish).toHaveBeenCalledWith("entity.died", "VonCrush", expect.objectContaining({ killer: null, killerType: null, projectileType: null }));
});

test("onEntityHurt updates damageTaken for victim and damageDealt for attacker", () => {
  capturedHandlers.onEntityHurt({ hurtEntity: { typeId: "minecraft:player", name: "VonCrush" }, damageSource: { damagingEntity: { typeId: "minecraft:player", name: "Craft" } }, damage: 5 });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockMutatePlayer).toHaveBeenCalledWith("Craft", expect.any(Function));
});

test("onPlayerBreakBlock updates blocksBroken and queues block change", () => {
  capturedHandlers.onPlayerBreakBlock({ player: { name: "VonCrush" }, brokenBlockPermutation: { type: { id: "minecraft:stone" } } });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockQueueBlockChange).toHaveBeenCalledWith("VonCrush", "broken", "minecraft:stone");
});

test("onPlayerPlaceBlock updates blocksPlaced and queues block change", () => {
  capturedHandlers.onPlayerPlaceBlock({ player: { name: "VonCrush" }, block: { typeId: "minecraft:dirt" } });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockQueueBlockChange).toHaveBeenCalledWith("VonCrush", "placed", "minecraft:dirt");
});

test("onPlayerDimensionChange records new position and publishes dimension change", () => {
  capturedHandlers.onPlayerDimensionChange({ player: { id: "p1", name: "VonCrush" }, toLocation: { x: 10, y: 64, z: 20 }, fromDimension: { id: "minecraft:overworld" }, toDimension: { id: "minecraft:nether" } });
  expect(mockMutatePlayer).toHaveBeenCalledWith("VonCrush", expect.any(Function));
  expect(mockPublish).toHaveBeenCalledWith("player.dimension.changed", "VonCrush", { from: "minecraft:overworld", to: "minecraft:nether" });
});

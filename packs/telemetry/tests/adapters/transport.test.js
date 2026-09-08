import { jest, beforeEach, describe, test, expect } from "@jest/globals";
import { suppressConsoleWarn } from "../helpers.mjs";
import { capturedTelemetryRecords } from "../factories.mjs";

// @minecraft/server is resolved to tests/minecraft-server.mock.js via
// moduleNameMapper in jest.config.js. Transport collaborators are injected
// directly, so this test does not replace internal pack modules.

const mockNextSequence = jest.fn(() => 1);
const mockLoadState = jest.fn(() => ({ sequence: 0, players: {} }));
const mockFlush = jest.fn();
const mockStorageStatus = jest.fn(() => ({ persistenceBlocked: false }));

const mockCapabilitySnapshot = jest.fn(() => ({}));
const mockReadGameMode = jest.fn(() => null);
const mockMetricsSnapshot = jest.fn(() => ({ itemUse: false, blockInteractions: false, entityInteractions: false, containerInteractions: false }));

const { world } = await import("@minecraft/server");
const { configureTransport, resetTransport, publish, queueBlockChange, publishBlockChanges, publishInteractions, publishItemUse, publishMetrics, publishSnapshot, queueInteraction, queueItemUse } =
  await import("../../behavior_pack/scripts/adapters/transport.js");

beforeEach(() => {
  jest.clearAllMocks();
  mockNextSequence.mockReturnValue(1);
  mockLoadState.mockReturnValue({ sequence: 0, players: {} });
  mockStorageStatus.mockReturnValue({ persistenceBlocked: false });
  mockCapabilitySnapshot.mockReturnValue({});
  mockReadGameMode.mockReturnValue(null);
  mockMetricsSnapshot.mockReturnValue({ itemUse: false, blockInteractions: false, entityInteractions: false, containerInteractions: false });
  world.players = [];
  resetTransport();
  configureTransport({
    world,
    nextSequence: mockNextSequence,
    loadState: mockLoadState,
    flush: mockFlush,
    storageStatus: mockStorageStatus,
    capabilitySnapshot: mockCapabilitySnapshot,
    readGameMode: mockReadGameMode,
    metricsSnapshot: mockMetricsSnapshot,
  });
});

// ---------------------------------------------------------------------------
// publish
// ---------------------------------------------------------------------------

describe("publish", () => {
  test("returns an envelope with the correct shape", () => {
    mockNextSequence.mockReturnValue(7);
    const before = Date.now();
    const envelope = publish("player.join", "VonCrush", { extra: 1 });
    const after = Date.now();

    expect(envelope.schema).toBeDefined();
    expect(envelope.sequence).toBe(7);
    expect(envelope.type).toBe("player.join");
    expect(envelope.timestamp).toBeGreaterThanOrEqual(before);
    expect(envelope.timestamp).toBeLessThanOrEqual(after);
    expect(envelope.player).toEqual({ name: "VonCrush" });
    expect(envelope.data).toEqual({ extra: 1 });
  });

  test("sets player to null when no player is supplied", () => {
    const envelope = publish("snapshot.started", null);
    expect(envelope.player).toBeNull();
  });

  test("defaults data to an empty object when omitted", () => {
    const envelope = publish("snapshot.finished", null);
    expect(envelope.data).toEqual({});
  });

  test("calls nextSequence once per publish", () => {
    publish("player.join", "Alice");
    publish("player.leave", "Bob");
    expect(mockNextSequence).toHaveBeenCalledTimes(2);
  });
});

// ---------------------------------------------------------------------------
// queueBlockChange
// ---------------------------------------------------------------------------

describe("queueBlockChange", () => {
  test("creates broken and placed buckets on first call", () => {
    queueBlockChange("Alice", "broken", "stone");
    const warn = suppressConsoleWarn();
    publishBlockChanges();
    const logged = capturedTelemetryRecords(warn);
    const blocksMsg = logged.find((c) => c.type === "blocks.changed");
    expect(blocksMsg.player).toEqual({ name: "Alice" });
    expect(blocksMsg.data).toEqual({
      broken: { total: 1, byType: { stone: 1 } },
      placed: { total: 0, byType: {} },
    });
    warn.mockRestore();
  });

  test("accumulates total and byType across multiple calls for the same player", () => {
    queueBlockChange("Alice", "broken", "stone");
    queueBlockChange("Alice", "broken", "stone");
    queueBlockChange("Alice", "broken", "dirt");
    const warn = suppressConsoleWarn();
    publishBlockChanges();
    const logged = capturedTelemetryRecords(warn);
    const blocksMsg = logged.find((c) => c.type === "blocks.changed");
    expect(blocksMsg.data.broken).toEqual({ total: 3, byType: { stone: 2, dirt: 1 } });
    warn.mockRestore();
  });

  test("tracks placed blocks independently from broken blocks", () => {
    queueBlockChange("Bob", "placed", "oak_log");
    const warn = suppressConsoleWarn();
    publishBlockChanges();
    const logged = capturedTelemetryRecords(warn);
    const blocksMsg = logged.find((c) => c.type === "blocks.changed");
    expect(blocksMsg.data.placed).toEqual({ total: 1, byType: { oak_log: 1 } });
    expect(blocksMsg.data.broken).toEqual({ total: 0, byType: {} });
    warn.mockRestore();
  });

  test("tracks multiple players independently", () => {
    queueBlockChange("Alice", "broken", "stone");
    queueBlockChange("Bob", "placed", "oak_log");
    const warn = suppressConsoleWarn();
    publishBlockChanges();
    const logged = capturedTelemetryRecords(warn);
    const blocksMsgs = logged.filter((c) => c.type === "blocks.changed");
    expect(blocksMsgs).toHaveLength(2);
    const aliceMsg = blocksMsgs.find((c) => c.player.name === "Alice");
    const bobMsg = blocksMsgs.find((c) => c.player.name === "Bob");
    expect(aliceMsg.data.broken.total).toBe(1);
    expect(bobMsg.data.placed.total).toBe(1);
    warn.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// publishBlockChanges
// ---------------------------------------------------------------------------

describe("publishBlockChanges", () => {
  test("emits blocks.changed for each queued player", () => {
    queueBlockChange("Alice", "broken", "stone");
    queueBlockChange("Bob", "broken", "dirt");
    const warn = suppressConsoleWarn();
    publishBlockChanges();
    const logged = capturedTelemetryRecords(warn);
    const blocksMsgs = logged.filter((c) => c.type === "blocks.changed");
    expect(blocksMsgs).toHaveLength(2);
    warn.mockRestore();
  });

  test("clears pendingBlocks after emitting — a second call emits nothing", () => {
    queueBlockChange("Alice", "broken", "stone");
    const warn = suppressConsoleWarn();
    publishBlockChanges();
    warn.mockClear();
    publishBlockChanges();
    const logged = capturedTelemetryRecords(warn);
    expect(logged.filter((c) => c.type === "blocks.changed")).toHaveLength(0);
    warn.mockRestore();
  });

  test("does nothing when pendingBlocks is empty", () => {
    const warn = suppressConsoleWarn();
    publishBlockChanges();
    const logged = capturedTelemetryRecords(warn);
    expect(logged.filter((c) => c.type === "blocks.changed")).toHaveLength(0);
    warn.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// publishSnapshot
// ---------------------------------------------------------------------------

describe("publishSnapshot", () => {
  test("calls flush(true) and loadState", () => {
    publishSnapshot();
    expect(mockFlush).toHaveBeenCalledWith(true);
    expect(mockLoadState).toHaveBeenCalled();
  });

  test("calls world.getAllPlayers to resolve live players", () => {
    const spy = jest.spyOn(world, "getAllPlayers");
    publishSnapshot();
    expect(spy).toHaveBeenCalled();
    spy.mockRestore();
  });

  test("drains pending block changes before snapshotting", () => {
    queueBlockChange("Alice", "broken", "stone");
    const warn = suppressConsoleWarn();
    publishSnapshot();
    const logged = capturedTelemetryRecords(warn);
    const types = logged.map((c) => c.type);
    expect(types).toContain("blocks.changed");
    expect(types.indexOf("blocks.changed")).toBeLessThan(types.indexOf("snapshot.started"));
    // pendingBlocks is clear — a second publishBlockChanges emits nothing
    warn.mockClear();
    publishBlockChanges();
    const after = capturedTelemetryRecords(warn);
    expect(after.filter((c) => c.type === "blocks.changed")).toHaveLength(0);
    warn.mockRestore();
  });

  test("logs snapshot.started with player count, storage, and capabilities", () => {
    mockLoadState.mockReturnValue({ sequence: 5, players: { alice: { name: "Alice" }, bob: { name: "Bob" } } });
    mockStorageStatus.mockReturnValue({ persistenceBlocked: false });
    mockCapabilitySnapshot.mockReturnValue({ gameModeReading: { supported: true } });
    const warn = suppressConsoleWarn();
    publishSnapshot();
    const logged = capturedTelemetryRecords(warn);
    const started = logged.find((c) => c.type === "snapshot.started");
    expect(started).toBeDefined();
    expect(started.data.players).toBe(2);
    expect(started.data.storage).toEqual({ persistenceBlocked: false });
    expect(started.data.capabilities).toEqual({ gameModeReading: { supported: true } });
    warn.mockRestore();
  });

  test("logs snapshot.player for an online player with gameMode", () => {
    world.players = [{ name: "Alice" }];
    mockReadGameMode.mockReturnValue("survival");
    mockLoadState.mockReturnValue({ sequence: 1, players: { alice: { name: "Alice", deaths: 0 } } });
    const warn = suppressConsoleWarn();
    publishSnapshot();
    const logged = capturedTelemetryRecords(warn);
    const playerMsg = logged.find((c) => c.type === "snapshot.player");
    expect(playerMsg).toBeDefined();
    expect(playerMsg.player).toEqual({ name: "Alice" });
    expect(playerMsg.data.gameMode).toBe("survival");
    warn.mockRestore();
  });

  test("logs snapshot.player without gameMode for an offline player", () => {
    world.players = [];
    mockLoadState.mockReturnValue({ sequence: 1, players: { alice: { name: "Alice", deaths: 2 } } });
    const warn = suppressConsoleWarn();
    publishSnapshot();
    const logged = capturedTelemetryRecords(warn);
    const playerMsg = logged.find((c) => c.type === "snapshot.player");
    expect(playerMsg).toBeDefined();
    expect(playerMsg.data).not.toHaveProperty("gameMode");
    warn.mockRestore();
  });

  test("logs snapshot.player without gameMode for an online player on an unsupported runtime", () => {
    world.players = [{ name: "Alice" }];
    mockReadGameMode.mockReturnValue(null);
    mockLoadState.mockReturnValue({ sequence: 1, players: { alice: { name: "Alice", deaths: 0 } } });
    const warn = suppressConsoleWarn();
    expect(() => publishSnapshot()).not.toThrow();
    const logged = capturedTelemetryRecords(warn);
    const playerMsg = logged.find((c) => c.type === "snapshot.player");
    expect(playerMsg).toBeDefined();
    expect(playerMsg.data).not.toHaveProperty("gameMode");
    warn.mockRestore();
  });

  test("logs snapshot.finished with empty data and null player", () => {
    const warn = suppressConsoleWarn();
    publishSnapshot();
    const logged = capturedTelemetryRecords(warn);
    const finished = logged.find((c) => c.type === "snapshot.finished");
    expect(finished).toBeDefined();
    expect(finished.data).toEqual({});
    expect(finished.player).toBeNull();
    warn.mockRestore();
  });
});

describe("opt-in item use", () => {
  test("coalesces a player's item uses into one batched envelope", () => {
    queueItemUse("Alice", "minecraft:bow");
    queueItemUse("Alice", "minecraft:bow");
    queueItemUse("Alice", "minecraft:potion");
    const warn = suppressConsoleWarn();
    publishItemUse();
    const logged = capturedTelemetryRecords(warn);
    warn.mockRestore();

    // One line per player per interval, the same shape blocks.changed uses.
    expect(logged).toHaveLength(1);
    expect(logged[0].type).toBe("items.used");
    expect(logged[0].player).toEqual({ name: "Alice" });
    expect(logged[0].data).toEqual({ total: 3, byType: { "minecraft:bow": 2, "minecraft:potion": 1 } });
  });

  test("publishes one envelope per player", () => {
    queueItemUse("Alice", "minecraft:bow");
    queueItemUse("Bob", "minecraft:bow");
    const warn = suppressConsoleWarn();
    publishItemUse();
    const logged = capturedTelemetryRecords(warn);
    warn.mockRestore();
    expect(logged.map((record) => record.player.name).sort()).toEqual(["Alice", "Bob"]);
  });

  test("publishes nothing when no item was used", () => {
    const warn = suppressConsoleWarn();
    publishItemUse();
    expect(capturedTelemetryRecords(warn)).toEqual([]);
    warn.mockRestore();
  });

  test("drains the pending batch so a use is never published twice", () => {
    queueItemUse("Alice", "minecraft:bow");
    const warn = suppressConsoleWarn();
    publishItemUse();
    publishItemUse();
    expect(capturedTelemetryRecords(warn)).toHaveLength(1);
    warn.mockRestore();
  });

  test("a snapshot drains pending item use before reading the state", () => {
    queueItemUse("Alice", "minecraft:bow");
    const warn = suppressConsoleWarn();
    publishSnapshot();
    const logged = capturedTelemetryRecords(warn);
    warn.mockRestore();
    const items = logged.findIndex((record) => record.type === "items.used");
    const started = logged.findIndex((record) => record.type === "snapshot.started");
    expect(items).toBeGreaterThanOrEqual(0);
    expect(items).toBeLessThan(started);
  });
});

describe("metric announcements", () => {
  test("snapshot.started reports which metrics are enabled", () => {
    mockMetricsSnapshot.mockReturnValue({ itemUse: true });
    const warn = suppressConsoleWarn();
    publishSnapshot();
    const logged = capturedTelemetryRecords(warn);
    warn.mockRestore();
    expect(logged.find((record) => record.type === "snapshot.started").data.metrics).toEqual({ itemUse: true });
  });

  test("a metric change is announced on its own topic", () => {
    const warn = suppressConsoleWarn();
    publishMetrics({ itemUse: true });
    const logged = capturedTelemetryRecords(warn);
    warn.mockRestore();
    expect(logged[0].type).toBe("metrics.changed");
    expect(logged[0].player).toBeNull();
    expect(logged[0].data).toEqual({ metrics: { itemUse: true } });
  });
});

describe("opt-in interactions", () => {
  test("coalesces the three kinds into one envelope per player", () => {
    queueInteraction("Alice", "block", "minecraft:oak_door");
    queueInteraction("Alice", "block", "minecraft:oak_door");
    queueInteraction("Alice", "entity", "minecraft:villager");
    queueInteraction("Alice", "container", "minecraft:chest");
    const warn = suppressConsoleWarn();
    publishInteractions();
    const logged = capturedTelemetryRecords(warn);
    warn.mockRestore();

    expect(logged).toHaveLength(1);
    expect(logged[0].type).toBe("interactions.changed");
    expect(logged[0].data).toEqual({
      block: { total: 2, byType: { "minecraft:oak_door": 2 } },
      entity: { total: 1, byType: { "minecraft:villager": 1 } },
      container: { total: 1, byType: { "minecraft:chest": 1 } },
    });
  });

  test("an envelope carries empty buckets for the kinds that saw nothing", () => {
    queueInteraction("Alice", "entity", "minecraft:villager");
    const warn = suppressConsoleWarn();
    publishInteractions();
    const logged = capturedTelemetryRecords(warn);
    warn.mockRestore();
    expect(logged[0].data.block).toEqual({ total: 0, byType: {} });
    expect(logged[0].data.container).toEqual({ total: 0, byType: {} });
  });

  test("carries no coordinates", () => {
    queueInteraction("Alice", "block", "minecraft:chest");
    const warn = suppressConsoleWarn();
    publishInteractions();
    const emitted = JSON.stringify(capturedTelemetryRecords(warn));
    warn.mockRestore();
    for (const forbidden of ["\"x\"", "\"y\"", "\"z\"", "location"]) expect(emitted).not.toContain(forbidden);
  });

  test("publishes nothing when nobody interacted", () => {
    const warn = suppressConsoleWarn();
    publishInteractions();
    expect(capturedTelemetryRecords(warn)).toEqual([]);
    warn.mockRestore();
  });

  test("drains the batch so an interaction is never published twice", () => {
    queueInteraction("Alice", "block", "minecraft:chest");
    const warn = suppressConsoleWarn();
    publishInteractions();
    publishInteractions();
    expect(capturedTelemetryRecords(warn)).toHaveLength(1);
    warn.mockRestore();
  });

  test("a snapshot drains pending interactions before reading the state", () => {
    queueInteraction("Alice", "block", "minecraft:chest");
    const warn = suppressConsoleWarn();
    publishSnapshot();
    const logged = capturedTelemetryRecords(warn);
    warn.mockRestore();
    const interactions = logged.findIndex((record) => record.type === "interactions.changed");
    const started = logged.findIndex((record) => record.type === "snapshot.started");
    expect(interactions).toBeGreaterThanOrEqual(0);
    expect(interactions).toBeLessThan(started);
  });
});

import { jest, beforeEach, describe, test, expect } from "@jest/globals";

// @minecraft/server is resolved to tests/minecraft-server.mock.js via
// moduleNameMapper in jest.config.js.
//
// store.js and capabilities.js are replaced with controlled stubs using
// jest.unstable_mockModule, which must be declared before any dynamic import
// of the modules that depend on them.
//
// The module-level pendingBlocks Map in transport.js is drained in beforeEach
// by calling publishBlockChanges(), which calls pendingBlocks.clear().

const mockNextSequence = jest.fn(() => 1);
const mockLoadState = jest.fn(() => ({ sequence: 0, players: {} }));
const mockFlush = jest.fn();
const mockStorageStatus = jest.fn(() => ({ persistenceBlocked: false }));

const mockCapabilitySnapshot = jest.fn(() => ({}));
const mockReadGameMode = jest.fn(() => null);

jest.unstable_mockModule("../behavior_pack/scripts/store.js", () => ({
  nextSequence: mockNextSequence,
  loadState: mockLoadState,
  flush: mockFlush,
  storageStatus: mockStorageStatus,
}));

jest.unstable_mockModule("../behavior_pack/scripts/capabilities.js", () => ({
  capabilitySnapshot: mockCapabilitySnapshot,
  readGameMode: mockReadGameMode,
}));

// Import the modules once. transport.js gets the same world object we hold a
// reference to because all imports share the same module instance within a
// single Jest worker run (no resetModules).
const { world } = await import("@minecraft/server");
const { publish, queueBlockChange, publishBlockChanges, publishSnapshot } =
  await import("../behavior_pack/scripts/transport.js");

beforeEach(() => {
  jest.clearAllMocks();
  mockNextSequence.mockReturnValue(1);
  mockLoadState.mockReturnValue({ sequence: 0, players: {} });
  mockStorageStatus.mockReturnValue({ persistenceBlocked: false });
  mockCapabilitySnapshot.mockReturnValue({});
  mockReadGameMode.mockReturnValue(null);
  // Drain the module-level pendingBlocks so each test starts clean.
  world.players = [];
  publishBlockChanges();
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
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishBlockChanges();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
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
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishBlockChanges();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    const blocksMsg = logged.find((c) => c.type === "blocks.changed");
    expect(blocksMsg.data.broken).toEqual({ total: 3, byType: { stone: 2, dirt: 1 } });
    warn.mockRestore();
  });

  test("tracks placed blocks independently from broken blocks", () => {
    queueBlockChange("Bob", "placed", "oak_log");
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishBlockChanges();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    const blocksMsg = logged.find((c) => c.type === "blocks.changed");
    expect(blocksMsg.data.placed).toEqual({ total: 1, byType: { oak_log: 1 } });
    expect(blocksMsg.data.broken).toEqual({ total: 0, byType: {} });
    warn.mockRestore();
  });

  test("tracks multiple players independently", () => {
    queueBlockChange("Alice", "broken", "stone");
    queueBlockChange("Bob", "placed", "oak_log");
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishBlockChanges();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
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
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishBlockChanges();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    const blocksMsgs = logged.filter((c) => c.type === "blocks.changed");
    expect(blocksMsgs).toHaveLength(2);
    warn.mockRestore();
  });

  test("clears pendingBlocks after emitting — a second call emits nothing", () => {
    queueBlockChange("Alice", "broken", "stone");
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishBlockChanges();
    warn.mockClear();
    publishBlockChanges();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    expect(logged.filter((c) => c.type === "blocks.changed")).toHaveLength(0);
    warn.mockRestore();
  });

  test("does nothing when pendingBlocks is empty", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishBlockChanges();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
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
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishSnapshot();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    const types = logged.map((c) => c.type);
    expect(types).toContain("blocks.changed");
    expect(types.indexOf("blocks.changed")).toBeLessThan(types.indexOf("snapshot.started"));
    // pendingBlocks is clear — a second publishBlockChanges emits nothing
    warn.mockClear();
    publishBlockChanges();
    const after = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    expect(after.filter((c) => c.type === "blocks.changed")).toHaveLength(0);
    warn.mockRestore();
  });

  test("logs snapshot.started with player count, storage, and capabilities", () => {
    mockLoadState.mockReturnValue({ sequence: 5, players: { alice: { name: "Alice" }, bob: { name: "Bob" } } });
    mockStorageStatus.mockReturnValue({ persistenceBlocked: false });
    mockCapabilitySnapshot.mockReturnValue({ gameModeReading: { supported: true } });
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishSnapshot();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
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
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishSnapshot();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    const playerMsg = logged.find((c) => c.type === "snapshot.player");
    expect(playerMsg).toBeDefined();
    expect(playerMsg.player).toEqual({ name: "Alice" });
    expect(playerMsg.data.gameMode).toBe("survival");
    warn.mockRestore();
  });

  test("logs snapshot.player without gameMode for an offline player", () => {
    world.players = [];
    mockLoadState.mockReturnValue({ sequence: 1, players: { alice: { name: "Alice", deaths: 2 } } });
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishSnapshot();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    const playerMsg = logged.find((c) => c.type === "snapshot.player");
    expect(playerMsg).toBeDefined();
    expect(playerMsg.data).not.toHaveProperty("gameMode");
    warn.mockRestore();
  });

  test("logs snapshot.player without gameMode for an online player on an unsupported runtime", () => {
    world.players = [{ name: "Alice" }];
    mockReadGameMode.mockReturnValue(null);
    mockLoadState.mockReturnValue({ sequence: 1, players: { alice: { name: "Alice", deaths: 0 } } });
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    expect(() => publishSnapshot()).not.toThrow();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    const playerMsg = logged.find((c) => c.type === "snapshot.player");
    expect(playerMsg).toBeDefined();
    expect(playerMsg.data).not.toHaveProperty("gameMode");
    warn.mockRestore();
  });

  test("logs snapshot.finished with empty data and null player", () => {
    const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
    publishSnapshot();
    const logged = warn.mock.calls.map(([msg]) =>
      JSON.parse(msg.replace(/^\[BEDROCK_TELEMETRY\] /, ""))
    );
    const finished = logged.find((c) => c.type === "snapshot.finished");
    expect(finished).toBeDefined();
    expect(finished.data).toEqual({});
    expect(finished.player).toBeNull();
    warn.mockRestore();
  });
});

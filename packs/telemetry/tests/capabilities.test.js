import { jest, beforeEach, describe, test, expect } from "@jest/globals";

// Reset module registry and re-import for each test so module-level state
// (capabilities object, gameModeProbed flag) is fresh every time.
let subscribeWorldEvent;
let subscribeScriptEvents;
let startMovementSampling;
let readGameMode;
let probeGameModeReading;
let capabilitySnapshot;

let mockWorld;
let mockSystem;

beforeEach(async () => {
  jest.resetModules();

  // Build fresh signal helpers inline so each test starts clean.
  const makeSignal = () => ({
    subscribe: jest.fn(),
  });

  mockWorld = {
    afterEvents: {
      playerJoin: makeSignal(),
      playerLeave: makeSignal(),
    },
    getAllPlayers: jest.fn(() => []),
  };

  mockSystem = {
    afterEvents: {
      scriptEventReceive: makeSignal(),
    },
    run: jest.fn(),
    runInterval: jest.fn(),
  };

  jest.unstable_mockModule("@minecraft/server", () => ({
    world: mockWorld,
    system: mockSystem,
  }));

  ({
    subscribeWorldEvent,
    subscribeScriptEvents,
    startMovementSampling,
    readGameMode,
    probeGameModeReading,
    capabilitySnapshot,
  } = await import("../behavior_pack/scripts/adapters/capabilities.js"));
});

// ---------------------------------------------------------------------------
// subscribeWorldEvent
// ---------------------------------------------------------------------------

describe("subscribeWorldEvent", () => {
  test("returns true and records supported capability when signal exists", () => {
    const handler = jest.fn();
    const result = subscribeWorldEvent("playerJoin", "playerJoinEvents", handler);

    expect(result).toBe(true);
    expect(mockWorld.afterEvents.playerJoin.subscribe).toHaveBeenCalledWith(handler);
    expect(capabilitySnapshot()).toEqual(
      expect.objectContaining({ playerJoinEvents: { supported: true } })
    );
  });

  test("returns false and records unsupported when signal is missing", () => {
    const result = subscribeWorldEvent("unknownSignal", "unknownCap", jest.fn());

    expect(result).toBe(false);
    expect(capabilitySnapshot()).toEqual(
      expect.objectContaining({ unknownCap: { supported: false } })
    );
  });

  test("returns false and records error when subscribe throws", () => {
    mockWorld.afterEvents.playerJoin.subscribe.mockImplementation(() => {
      throw new Error("subscribe failed");
    });

    const result = subscribeWorldEvent("playerJoin", "playerJoinEvents", jest.fn());

    expect(result).toBe(false);
    const snap = capabilitySnapshot();
    expect(snap.playerJoinEvents.supported).toBe(false);
    expect(snap.playerJoinEvents.error).toMatch("subscribe failed");
  });

  test("returns false when afterEvents is absent", () => {
    mockWorld.afterEvents = undefined;
    const result = subscribeWorldEvent("playerJoin", "playerJoinEvents", jest.fn());
    expect(result).toBe(false);
  });

  test("returns false when signal exists but has no subscribe function", () => {
    mockWorld.afterEvents.playerJoin = { subscribe: "not-a-function" };
    const result = subscribeWorldEvent("playerJoin", "playerJoinEvents", jest.fn());
    expect(result).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// subscribeScriptEvents
// ---------------------------------------------------------------------------

describe("subscribeScriptEvents", () => {
  test("returns true and subscribes handler when scriptEventReceive and run exist", () => {
    const handler = jest.fn();
    const result = subscribeScriptEvents(handler);

    expect(result).toBe(true);
    expect(mockSystem.afterEvents.scriptEventReceive.subscribe).toHaveBeenCalledWith(handler);
    expect(capabilitySnapshot()).toEqual(
      expect.objectContaining({ snapshotRequests: { supported: true } })
    );
  });

  test("returns false when scriptEventReceive is missing", () => {
    mockSystem.afterEvents = {};
    const result = subscribeScriptEvents(jest.fn());
    expect(result).toBe(false);
    expect(capabilitySnapshot().snapshotRequests.supported).toBe(false);
  });

  test("returns false when system.run is not a function", () => {
    delete mockSystem.run;
    const result = subscribeScriptEvents(jest.fn());
    expect(result).toBe(false);
  });

  test("returns false and records error when subscribe throws", () => {
    mockSystem.afterEvents.scriptEventReceive.subscribe.mockImplementation(() => {
      throw new Error("script event error");
    });

    const result = subscribeScriptEvents(jest.fn());
    expect(result).toBe(false);
    expect(capabilitySnapshot().snapshotRequests.error).toMatch("script event error");
  });
});

// ---------------------------------------------------------------------------
// startMovementSampling
// ---------------------------------------------------------------------------

describe("startMovementSampling", () => {
  test("returns true and calls runInterval when runtime is capable", () => {
    const handler = jest.fn();
    const result = startMovementSampling(handler, 20);

    expect(result).toBe(true);
    expect(mockSystem.runInterval).toHaveBeenCalledWith(handler, 20);
    expect(capabilitySnapshot().movementSampling.supported).toBe(true);
  });

  test("returns false when runInterval is not a function", () => {
    delete mockSystem.runInterval;
    const result = startMovementSampling(jest.fn(), 20);
    expect(result).toBe(false);
    expect(capabilitySnapshot().movementSampling.supported).toBe(false);
  });

  test("returns false when getAllPlayers is not a function", () => {
    mockWorld.getAllPlayers = "not-a-function";
    const result = startMovementSampling(jest.fn(), 20);
    expect(result).toBe(false);
  });

  test("returns false and records error when runInterval throws", () => {
    mockSystem.runInterval.mockImplementation(() => {
      throw new Error("interval error");
    });

    const result = startMovementSampling(jest.fn(), 20);
    expect(result).toBe(false);
    expect(capabilitySnapshot().movementSampling.error).toMatch("interval error");
  });
});

// ---------------------------------------------------------------------------
// readGameMode
// ---------------------------------------------------------------------------

describe("readGameMode", () => {
  test("returns the game mode string for survival", () => {
    const player = { getGameMode: () => "survival" };
    expect(readGameMode(player)).toBe("survival");
  });

  test("returns the game mode string for creative", () => {
    const player = { getGameMode: () => "creative" };
    expect(readGameMode(player)).toBe("creative");
  });

  test("returns the game mode string for adventure", () => {
    const player = { getGameMode: () => "adventure" };
    expect(readGameMode(player)).toBe("adventure");
  });

  test("returns null for an unrecognised mode", () => {
    const player = { getGameMode: () => "spectator" };
    expect(readGameMode(player)).toBeNull();
  });

  test("returns null when getGameMode is not a function", () => {
    expect(readGameMode({ getGameMode: "string" })).toBeNull();
  });

  test("returns null when player is null", () => {
    expect(readGameMode(null)).toBeNull();
  });

  test("returns null when getGameMode throws", () => {
    const player = {
      getGameMode: () => { throw new Error("boom"); },
    };
    expect(readGameMode(player)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// probeGameModeReading
// ---------------------------------------------------------------------------

describe("probeGameModeReading", () => {
  test("records supported=true when at least one player has getGameMode", () => {
    const players = [{ getGameMode: jest.fn() }, {}];
    probeGameModeReading(players);
    expect(capabilitySnapshot().gameModeReading.supported).toBe(true);
  });

  test("records supported=false when no player has getGameMode", () => {
    probeGameModeReading([{}, {}]);
    expect(capabilitySnapshot().gameModeReading.supported).toBe(false);
  });

  test("does nothing when the player list is empty", () => {
    probeGameModeReading([]);
    expect(capabilitySnapshot().gameModeReading).toBeUndefined();
  });

  test("only records once — second call is a no-op", () => {
    probeGameModeReading([{ getGameMode: jest.fn() }]);
    probeGameModeReading([{}]); // would flip to false if not guarded
    expect(capabilitySnapshot().gameModeReading.supported).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// capabilitySnapshot
// ---------------------------------------------------------------------------

describe("capabilitySnapshot", () => {
  test("returns an empty object before any capability is recorded", () => {
    expect(capabilitySnapshot()).toEqual({});
  });

  test("returns keys in sorted order", () => {
    subscribeWorldEvent("playerJoin", "zzz", jest.fn());
    probeGameModeReading([{ getGameMode: jest.fn() }]);
    subscribeScriptEvents(jest.fn());

    const keys = Object.keys(capabilitySnapshot());
    expect(keys).toEqual([...keys].sort());
  });
});

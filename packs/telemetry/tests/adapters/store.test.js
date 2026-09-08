import { beforeEach, describe, expect, test, jest } from "@jest/globals";
import { suppressConsoleError, suppressConsoleWarn } from "../helpers.mjs";
import { playerShard, playerSnapshot, storageMetadata } from "../factories.mjs";
import { METRICS_KEY, STATE_KEY, PLAYER_STATE_PREFIX, STATE_BACKUP_KEY, STATE_BACKUP_V1_KEY, STATE_BACKUP_V2_KEY, playerKey, playerStateKey } from "../../behavior_pack/scripts/model.js";
import { STORAGE_VERSION } from "../../behavior_pack/scripts/versions.js";

// store.js uses module-level mutable state. Each test reloads both the mock
// and store.js together so they share the same fresh `properties` Map.
async function loadStore() {
  jest.resetModules();
  const mock = await import("../minecraft-server.mock.js");
  const store = await import("../../behavior_pack/scripts/adapters/store.js");
  return { mock, store };
}

beforeEach(() => {
  jest.resetModules();
});

// ---------------------------------------------------------------------------
// loadState — persistence paths
// ---------------------------------------------------------------------------

describe("loadState", () => {
  test("returns empty state when no dynamic property is stored", async () => {
    const { store } = await loadStore();
    const state = store.loadState();
    expect(state.storageVersion).toBe(STORAGE_VERSION);
    expect(state.sequence).toBe(0);
    expect(state.players).toEqual({});
  });

  test("loads sharded v3 state from dynamic properties", async () => {
    const { mock, store } = await loadStore();
    const key = playerKey("VonCrush");
    mock.setMockDynamicProperty(STATE_KEY, JSON.stringify(storageMetadata({ sequence: 5 })));
    mock.setMockDynamicProperty(playerStateKey(key), JSON.stringify(playerShard({
      sequence: 5, key,
      player: playerSnapshot({ firstSeenAt: 1, lastSeenAt: 2, joins: 2, deaths: 1, mobKills: 3, blocksBroken: 10, blocksPlaced: 5 }),
    })));

    const state = store.loadState();
    expect(state.sequence).toBe(5);
    expect(state.players[key]).toBeDefined();
    expect(state.players[key].name).toBe("VonCrush");
    expect(state.players[key].mobKills).toBe(3);
  });

  test("returns same reference on subsequent calls (singleton cache)", async () => {
    const { store } = await loadStore();
    const first = store.loadState();
    const second = store.loadState();
    expect(first).toBe(second);
  });

  test("sets blocked and returns empty state when raw data is corrupt JSON", async () => {
    const { mock, store } = await loadStore();
    mock.setMockDynamicProperty(STATE_KEY, "not-json{{");
    const state = store.loadState();
    expect(state.players).toEqual({});
    const status = store.storageStatus();
    expect(status.persistenceBlocked).toBe(true);
    expect(status.status).toBe("blocked");
  });
});

// ---------------------------------------------------------------------------
// storageStatus
// ---------------------------------------------------------------------------

describe("storageStatus", () => {
  test("reports not-required when no migration is needed", async () => {
    const { store } = await loadStore();
    const status = store.storageStatus();
    expect(status.status).toBe("not-required");
    expect(status.persistenceBlocked).toBe(false);
    expect(status.storageVersion).toBe(STORAGE_VERSION);
  });

  test("reports migrated after a legacy v0 migration", async () => {
    const { mock, store } = await loadStore();
    const legacy = JSON.stringify({
      schema: 1, sequence: 10,
      players: { voncrush: { name: "VonCrush", aliases: ["VonCrush"], firstSeenAt: 1, lastSeenAt: 2, deaths: 0 } },
    });
    mock.setMockDynamicProperty(STATE_KEY, legacy);

    const status = store.storageStatus();
    expect(status.status).toBe("migrated");
    expect(status.migratedFrom).toBe(0);
    const backup0 = mock.getMockDynamicProperty(STATE_BACKUP_KEY);
    expect(typeof backup0).toBe("string");
    expect(backup0).toBe(legacy); // backup preserves exact original raw state
  });

  test("reports migrated after a v1 migration", async () => {
    const { mock, store } = await loadStore();
    const raw1 = JSON.stringify({ storageVersion: 1, sequence: 3, players: {} });
    mock.setMockDynamicProperty(STATE_KEY, raw1);

    const status = store.storageStatus();
    expect(status.status).toBe("migrated");
    expect(status.migratedFrom).toBe(1);
    const backup1 = mock.getMockDynamicProperty(STATE_BACKUP_V1_KEY);
    expect(typeof backup1).toBe("string");
    expect(backup1).toBe(raw1); // backup preserves exact original raw state
  });

  test("reports migrated after a sharded v2 migration", async () => {
    const { mock, store } = await loadStore();
    const key = playerKey("VonCrush");
    const raw2Meta = JSON.stringify({ storageVersion: 2, sequence: 7 });
    mock.setMockDynamicProperty(STATE_KEY, raw2Meta);
    mock.setMockDynamicProperty(
      `${PLAYER_STATE_PREFIX}${encodeURIComponent(key)}`,
      JSON.stringify({ storageVersion: 2, sequence: 7, key, player: { name: "VonCrush", mobKills: 5 } }),
    );

    const status = store.storageStatus();
    expect(status.status).toBe("migrated");
    expect(status.migratedFrom).toBe(2);
    const backup2 = mock.getMockDynamicProperty(STATE_BACKUP_V2_KEY);
    expect(typeof backup2).toBe("string");
    expect(backup2).toBe(raw2Meta); // backup preserves exact original meta
  });
});

// ---------------------------------------------------------------------------
// mutate / mutatePlayer / nextSequence
// ---------------------------------------------------------------------------

describe("mutate", () => {
  test("applies callback and marks meta dirty so flush persists new sequence", async () => {
    const { mock, store } = await loadStore();
    store.loadState();
    store.mutate((s) => { s.sequence = 42; });
    store.flush(true);
    const raw = mock.getMockDynamicProperty(STATE_KEY);
    expect(typeof raw).toBe("string");
    expect(JSON.parse(raw).sequence).toBe(42);
  });
});

describe("mutatePlayer", () => {
  test("marks the player key dirty so flush persists it", async () => {
    const { mock, store } = await loadStore();
    const state = store.loadState();
    const name = "VonCrush";
    const key = playerKey(name);
    state.players[key] = playerSnapshot({ name });
    store.mutatePlayer(name, (s) => { s.players[key].deaths += 1; });
    store.flush();
    const shardRaw = mock.getMockDynamicProperty(playerStateKey(key));
    expect(typeof shardRaw).toBe("string");
    const shard = JSON.parse(shardRaw);
    expect(shard.player.deaths).toBe(1);
    expect(shard.key).toBe(key);
  });
});

describe("nextSequence", () => {
  test("increments sequence in state and returns new value", async () => {
    const { store } = await loadStore();
    store.loadState();
    expect(store.nextSequence()).toBe(1);
    expect(store.nextSequence()).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// flush — happy path, blocked path, no-op path
// ---------------------------------------------------------------------------

describe("flush", () => {
  test("is a no-op when nothing is dirty and force is false", async () => {
    const { mock, store } = await loadStore();
    store.loadState();
    store.flush(false);
    expect(mock.getMockDynamicProperty(STATE_KEY)).toBeUndefined();
  });

  test("writes meta and player shards when dirty via mutatePlayer", async () => {
    const { mock, store } = await loadStore();
    const state = store.loadState();
    const name = "TestPlayer";
    const key = playerKey(name);
    state.players[key] = playerSnapshot({ name });
    store.mutatePlayer(name, (s) => { s.players[key].joins += 1; });
    store.flush();
    expect(typeof mock.getMockDynamicProperty(STATE_KEY)).toBe("string");
    expect(typeof mock.getMockDynamicProperty(playerStateKey(key))).toBe("string");
  });

  test("force flag writes even when nothing is explicitly dirty", async () => {
    const { mock, store } = await loadStore();
    store.loadState();
    store.flush(true);
    expect(typeof mock.getMockDynamicProperty(STATE_KEY)).toBe("string");
  });

  test("skips persistence and logs error when blocked", async () => {
    const { mock, store } = await loadStore();
    mock.setMockDynamicProperty(STATE_KEY, "{bad");
    const consoleSpy = suppressConsoleError();
    store.loadState(); // triggers blocked
    store.flush(true);
    // STATE_KEY must remain the corrupt string — nothing new written
    expect(mock.getMockDynamicProperty(STATE_KEY)).toBe("{bad");
    expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining("persistence blocked"));
    consoleSpy.mockRestore();
  });

  test("logs error when setDynamicProperty throws during flush", async () => {
    const { mock, store } = await loadStore();
    store.loadState();
    // Intercept setDynamicProperty to throw after loadState succeeds (not blocked)
    const original = mock.world.setDynamicProperty.bind(mock.world);
    mock.world.setDynamicProperty = () => { throw new Error("quota exceeded"); };
    const consoleSpy = suppressConsoleError();
    store.flush(true);
    expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining("quota exceeded"));
    consoleSpy.mockRestore();
    mock.world.setDynamicProperty = original;
  });

  test("clears dirtyPlayers after a successful flush", async () => {
    const { mock, store } = await loadStore();
    const state = store.loadState();
    const name = "Alpha";
    const key = playerKey(name);
    state.players[key] = {
      name, aliases: [name], firstSeenAt: 0, lastSeenAt: 0,
      joins: 0, deaths: 0, playerKills: 0, mobKills: 0, blocksBroken: 0, blocksPlaced: 0,
      damageDealt: 0, damageTaken: 0, distance: 0, dimensions: {}, brokenByType: {},
      placedByType: {}, killsByType: {}, distanceByDimension: {}, activeTimeByDimension: {},
      firstDimensionVisitAt: {}, lastDimensionVisitAt: {},
    };
    store.mutatePlayer(name, (s) => { s.players[key].joins = 1; });
    store.flush();
    // Now clear the stored value to detect a second spurious write
    mock.clearMockDynamicProperties();
    // A second flush with no further mutations must be a no-op
    store.flush(false);
    expect(mock.getMockDynamicProperty(STATE_KEY)).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// opt-in metrics — persistence of the owner's decision
// ---------------------------------------------------------------------------

describe("metrics", () => {
  test("a pack that was never told anything collects nothing", async () => {
    const { store } = await loadStore();
    expect(store.metricsSnapshot()).toEqual({ itemUse: false });
    expect(store.metricEnabled("itemUse")).toBe(false);
  });

  test("enabling a metric persists it so it survives a restart", async () => {
    const { mock, store } = await loadStore();
    expect(store.applyMetrics("enable itemUse")).toEqual({ itemUse: true });
    expect(JSON.parse(mock.getMockDynamicProperty(METRICS_KEY))).toEqual({ itemUse: true });

    // A fresh process reading the same world keeps the decision. Reloading the
    // modules gives the mock a clean property map, so the persisted value is
    // carried over the way the world file carries it across a restart.
    const persisted = mock.getMockDynamicProperty(METRICS_KEY);
    const restarted = await loadStore();
    restarted.mock.setMockDynamicProperty(METRICS_KEY, persisted);
    expect(restarted.store.metricEnabled("itemUse")).toBe(true);
  });

  test("disabling a metric persists too", async () => {
    const { mock, store } = await loadStore();
    store.applyMetrics("enable itemUse");
    expect(store.applyMetrics("disable itemUse")).toEqual({ itemUse: false });
    expect(JSON.parse(mock.getMockDynamicProperty(METRICS_KEY))).toEqual({ itemUse: false });
  });

  test("an unknown command warns and leaves collection untouched", async () => {
    const { mock, store } = await loadStore();
    const warn = suppressConsoleWarn();
    expect(store.applyMetrics("enable chatCapture")).toBeNull();
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("unknown metric: chatCapture"));
    warn.mockRestore();
    expect(store.metricEnabled("itemUse")).toBe(false);
    expect(mock.getMockDynamicProperty(METRICS_KEY)).toBeUndefined();
  });

  test("status reports the current state without writing", async () => {
    const { mock, store } = await loadStore();
    expect(store.applyMetrics("status")).toEqual({ itemUse: false });
    expect(mock.getMockDynamicProperty(METRICS_KEY)).toBeUndefined();
  });

  test("a corrupt persisted value reads as disabled and is reported", async () => {
    jest.resetModules();
    const mock = await import("../minecraft-server.mock.js");
    mock.clearMockDynamicProperties();
    mock.setMockDynamicProperty(METRICS_KEY, "{not json");
    const store = await import("../../behavior_pack/scripts/adapters/store.js");
    const error = suppressConsoleError();
    expect(store.metricsSnapshot()).toEqual({ itemUse: false });
    expect(error).toHaveBeenCalledWith(expect.stringContaining("invalid persisted metrics"));
    error.mockRestore();
  });

  test("a failed write is reported and the decision still applies this session", async () => {
    const { mock, store } = await loadStore();
    const original = mock.world.setDynamicProperty.bind(mock.world);
    mock.world.setDynamicProperty = () => { throw new Error("quota exceeded"); };
    const error = suppressConsoleError();
    expect(store.applyMetrics("enable itemUse")).toEqual({ itemUse: true });
    expect(error).toHaveBeenCalledWith(expect.stringContaining("failed to persist metrics"));
    error.mockRestore();
    mock.world.setDynamicProperty = original;
    expect(store.metricEnabled("itemUse")).toBe(true);
  });
});

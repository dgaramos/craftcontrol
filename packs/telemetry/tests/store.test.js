import { beforeEach, describe, expect, test, jest } from "@jest/globals";
import { suppressConsoleError } from "./helpers.mjs";
import { STATE_KEY, PLAYER_STATE_PREFIX, STATE_BACKUP_KEY, STATE_BACKUP_V1_KEY, STATE_BACKUP_V2_KEY, playerKey, playerStateKey } from "../behavior_pack/scripts/model.js";
import { STORAGE_VERSION } from "../behavior_pack/scripts/versions.js";

// store.js uses module-level mutable state. Each test reloads both the mock
// and store.js together so they share the same fresh `properties` Map.
async function loadStore() {
  jest.resetModules();
  const mock = await import("./minecraft-server.mock.js");
  const store = await import("../behavior_pack/scripts/adapters/store.js");
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
    mock.setMockDynamicProperty(STATE_KEY, JSON.stringify({ storageVersion: 3, sequence: 5 }));
    mock.setMockDynamicProperty(playerStateKey(key), JSON.stringify({
      storageVersion: 3, sequence: 5, key,
      player: {
        name: "VonCrush", aliases: ["VonCrush"], firstSeenAt: 1, lastSeenAt: 2,
        joins: 2, deaths: 1, playerKills: 0, mobKills: 3, blocksBroken: 10, blocksPlaced: 5,
        damageDealt: 0, damageTaken: 0, distance: 0, dimensions: {}, brokenByType: {},
        placedByType: {}, killsByType: {}, distanceByDimension: {}, activeTimeByDimension: {},
        firstDimensionVisitAt: {}, lastDimensionVisitAt: {},
      },
    }));

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
    state.players[key] = {
      name, aliases: [name], firstSeenAt: 0, lastSeenAt: 0,
      joins: 0, deaths: 0, playerKills: 0, mobKills: 0, blocksBroken: 0, blocksPlaced: 0,
      damageDealt: 0, damageTaken: 0, distance: 0, dimensions: {}, brokenByType: {},
      placedByType: {}, killsByType: {}, distanceByDimension: {}, activeTimeByDimension: {},
      firstDimensionVisitAt: {}, lastDimensionVisitAt: {},
    };
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
    state.players[key] = {
      name, aliases: [name], firstSeenAt: 0, lastSeenAt: 0,
      joins: 0, deaths: 0, playerKills: 0, mobKills: 0, blocksBroken: 0, blocksPlaced: 0,
      damageDealt: 0, damageTaken: 0, distance: 0, dimensions: {}, brokenByType: {},
      placedByType: {}, killsByType: {}, distanceByDimension: {}, activeTimeByDimension: {},
      firstDimensionVisitAt: {}, lastDimensionVisitAt: {},
    };
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

import { world } from "@minecraft/server";
import { STATE_BACKUP_KEY, STATE_KEY, emptyState } from "./model.js";
import { migrateState } from "./migrations.js";
import { STORAGE_VERSION } from "./versions.js";

let state;
let dirty = false;
let blocked = false;
let migration = { status: "not-required", storageVersion: STORAGE_VERSION, migratedFrom: null };

function serialize(candidate) {
  const value = JSON.stringify(candidate);
  if (value.length > 30000) throw new Error(`state is ${value.length} bytes; refusing unsafe write`);
  return value;
}

export function loadState() {
  if (state) return state;
  const raw = world.getDynamicProperty(STATE_KEY);
  if (typeof raw !== "string") return (state = emptyState());
  try {
    const parsed = JSON.parse(raw);
    const result = migrateState(parsed);
    state = result.state;
    if (result.migratedFrom !== null) {
      const serialized = serialize(state);
      if (typeof world.getDynamicProperty(STATE_BACKUP_KEY) !== "string") world.setDynamicProperty(STATE_BACKUP_KEY, raw);
      world.setDynamicProperty(STATE_KEY, serialized);
      migration = { status: "migrated", storageVersion: STORAGE_VERSION, migratedFrom: result.migratedFrom };
      console.warn(`[BEDROCK_TELEMETRY_MIGRATION] storage ${result.migratedFrom} -> ${STORAGE_VERSION} complete`);
    }
  } catch (error) {
    console.error(`[BEDROCK_TELEMETRY_ERROR] invalid persisted state: ${error}`);
    blocked = true;
    migration = { status: "blocked", storageVersion: STORAGE_VERSION, migratedFrom: null, error: String(error) };
    state = emptyState();
  }
  return state;
}

export function storageStatus() {
  loadState();
  return { ...migration, persistenceBlocked: blocked };
}

export function mutate(callback) {
  const result = callback(loadState());
  dirty = true;
  return result;
}

export function nextSequence() {
  return mutate((current) => ++current.sequence);
}

export function flush(force = false) {
  if (!dirty && !force) return;
  if (blocked) {
    console.error("[BEDROCK_TELEMETRY_ERROR] persistence blocked; preserving original state");
    return;
  }
  try {
    world.setDynamicProperty(STATE_KEY, serialize(loadState()));
    dirty = false;
  } catch (error) {
    console.error(`[BEDROCK_TELEMETRY_ERROR] ${error}`);
  }
}

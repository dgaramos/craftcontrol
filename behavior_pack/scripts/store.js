import { world } from "@minecraft/server";
import { STATE_KEY, emptyState } from "./model.js";

let state;
let dirty = false;

export function loadState() {
  if (state) return state;
  const raw = world.getDynamicProperty(STATE_KEY);
  if (typeof raw !== "string") return (state = emptyState());
  try {
    const parsed = JSON.parse(raw);
    state = parsed?.schema === 1 && parsed.players ? parsed : emptyState();
  } catch (error) {
    console.error(`[BEDROCK_TELEMETRY_ERROR] invalid persisted state: ${error}`);
    state = emptyState();
  }
  return state;
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
  const serialized = JSON.stringify(loadState());
  if (serialized.length > 30000) {
    console.error(`[BEDROCK_TELEMETRY_ERROR] state is ${serialized.length} bytes; refusing unsafe write`);
    return;
  }
  world.setDynamicProperty(STATE_KEY, serialized);
  dirty = false;
}

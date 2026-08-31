import { system, world } from "@minecraft/server";

const capabilities = {};

function record(name, supported, error = null) {
  capabilities[name] = { supported, ...(error ? { error: String(error) } : {}) };
  if (!supported) console.warn(`[BEDROCK_TELEMETRY_CAPABILITY] unavailable: ${name}${error ? ` (${error})` : ""}`);
  return supported;
}

export function subscribeWorldEvent(signal, capability, handler) {
  try {
    const source = world.afterEvents?.[signal];
    if (!source || typeof source.subscribe !== "function") return record(capability, false);
    source.subscribe(handler);
    return record(capability, true);
  } catch (error) {
    return record(capability, false, error);
  }
}

export function subscribeScriptEvents(handler) {
  try {
    const source = system.afterEvents?.scriptEventReceive;
    if (!source || typeof source.subscribe !== "function" || typeof system.run !== "function") return record("snapshotRequests", false);
    source.subscribe(handler);
    return record("snapshotRequests", true);
  } catch (error) {
    return record("snapshotRequests", false, error);
  }
}

export function startMovementSampling(handler, interval) {
  try {
    if (typeof system.runInterval !== "function" || typeof world.getAllPlayers !== "function") return record("movementSampling", false);
    system.runInterval(handler, interval);
    return record("movementSampling", true);
  } catch (error) {
    return record("movementSampling", false, error);
  }
}

let gameModeProbed = false;

export function readGameMode(player) {
  try {
    if (typeof player?.getGameMode !== "function") {
      if (!gameModeProbed) { gameModeProbed = true; record("gameModeReading", false); }
      return null;
    }
    const mode = player.getGameMode();
    if (!gameModeProbed) { gameModeProbed = true; record("gameModeReading", true); }
    if (mode === "survival" || mode === "creative" || mode === "adventure") return mode;
    return null;
  } catch (error) {
    if (!gameModeProbed) { gameModeProbed = true; record("gameModeReading", false, error); }
    return null;
  }
}

export function capabilitySnapshot() {
  return Object.fromEntries(Object.entries(capabilities).sort(([left], [right]) => left.localeCompare(right)));
}

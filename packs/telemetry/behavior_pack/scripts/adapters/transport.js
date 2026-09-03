import { world } from "@minecraft/server";
import { LOG_PREFIX, SCHEMA_VERSION } from "../model.js";
import { flush, loadState, nextSequence, storageStatus } from "./store.js";
import { capabilitySnapshot, readGameMode } from "./capabilities.js";

const pendingBlocks = new Map();
const productionDependencies = { world, flush, loadState, nextSequence, storageStatus, capabilitySnapshot, readGameMode };
let dependencies = productionDependencies;

export function configureTransport(overrides = {}) {
  dependencies = { ...productionDependencies, ...overrides };
}

export function resetTransport() {
  pendingBlocks.clear();
  dependencies = productionDependencies;
}

export function publish(type, player, data = {}) {
  const envelope = {
    schema: SCHEMA_VERSION,
    sequence: dependencies.nextSequence(),
    type,
    timestamp: Date.now(),
    player: player ? { name: player } : null,
    data,
  };
  console.warn(`${LOG_PREFIX} ${JSON.stringify(envelope)}`);
  return envelope;
}

export function queueBlockChange(player, kind, blockType) {
  const pending = pendingBlocks.get(player) || {
    broken: { total: 0, byType: {} },
    placed: { total: 0, byType: {} },
  };
  const bucket = pending[kind];
  bucket.total += 1;
  bucket.byType[blockType] = (bucket.byType[blockType] || 0) + 1;
  pendingBlocks.set(player, pending);
}

export function publishBlockChanges() {
  for (const [player, data] of pendingBlocks) publish("blocks.changed", player, data);
  pendingBlocks.clear();
}

export function publishSnapshot() {
  publishBlockChanges();
  dependencies.flush(true);
  const state = dependencies.loadState();
  console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.started", timestamp: Date.now(), player: null, data: { players: Object.keys(state.players).length, storage: dependencies.storageStatus(), capabilities: dependencies.capabilitySnapshot() } })}`);
  const livePlayers = new Map(dependencies.world.getAllPlayers().map((p) => [p.name, p]));
  for (const player of Object.values(state.players)) {
    const live = livePlayers.get(player.name);
    const gameMode = live ? dependencies.readGameMode(live) : null;
    const data = gameMode !== null ? { ...player, gameMode } : { ...player };
    console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.player", timestamp: Date.now(), player: { name: player.name }, data })}`);
  }
  console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.finished", timestamp: Date.now(), player: null, data: {} })}`);
}

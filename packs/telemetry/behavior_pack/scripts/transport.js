import { LOG_PREFIX, SCHEMA_VERSION } from "./model.js";
import { flush, loadState, nextSequence, storageStatus } from "./store.js";
import { capabilitySnapshot } from "./capabilities.js";

const pendingBlocks = new Map();

export function publish(type, player, data = {}) {
  const envelope = {
    schema: SCHEMA_VERSION,
    sequence: nextSequence(),
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
  flush(true);
  const state = loadState();
  console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.started", timestamp: Date.now(), player: null, data: { players: Object.keys(state.players).length, storage: storageStatus(), capabilities: capabilitySnapshot() } })}`);
  for (const player of Object.values(state.players)) {
    console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.player", timestamp: Date.now(), player: { name: player.name }, data: player })}`);
  }
  console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.finished", timestamp: Date.now(), player: null, data: {} })}`);
}

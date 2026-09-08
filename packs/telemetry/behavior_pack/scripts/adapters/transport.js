import { world } from "@minecraft/server";
import { LOG_PREFIX, SCHEMA_VERSION } from "../model.js";
import { flush, loadState, metricsSnapshot, nextSequence, storageStatus } from "./store.js";
import { capabilitySnapshot, readGameMode } from "./capabilities.js";

const pendingBlocks = new Map();
const pendingItems = new Map();
const pendingInteractions = new Map();
const productionDependencies = { world, flush, loadState, metricsSnapshot, nextSequence, storageStatus, capabilitySnapshot, readGameMode };
let dependencies = productionDependencies;

export function configureTransport(overrides = {}) {
  dependencies = { ...productionDependencies, ...overrides };
}

export function resetTransport() {
  pendingBlocks.clear();
  pendingItems.clear();
  pendingInteractions.clear();
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

/**
 * Accumulate one item use for the next five-second batch.
 *
 * Item use fires far more often than a join or a death, so it travels as a
 * batched aggregate for the same reason block changes do: one line per player
 * per interval instead of one line per action.
 */
export function queueItemUse(player, itemType) {
  const pending = pendingItems.get(player) || { total: 0, byType: {} };
  pending.total += 1;
  pending.byType[itemType] = (pending.byType[itemType] || 0) + 1;
  pendingItems.set(player, pending);
}

export function publishItemUse() {
  for (const [player, data] of pendingItems) publish("items.used", player, data);
  pendingItems.clear();
}

/**
 * Accumulate one interaction for the next five-second batch.
 *
 * `kind` is "block", "entity" or "container"; the type is a namespaced
 * identifier the caller already validated. No coordinates travel with it —
 * where a player interacted is not collected (docs/telemetry-metrics.md).
 */
export function queueInteraction(player, kind, type) {
  const pending = pendingInteractions.get(player) || {
    block: { total: 0, byType: {} },
    entity: { total: 0, byType: {} },
    container: { total: 0, byType: {} },
  };
  const bucket = pending[kind];
  bucket.total += 1;
  bucket.byType[type] = (bucket.byType[type] || 0) + 1;
  pendingInteractions.set(player, pending);
}

export function publishInteractions() {
  for (const [player, data] of pendingInteractions) publish("interactions.changed", player, data);
  pendingInteractions.clear();
}

export function publishMetrics(metrics) {
  return publish("metrics.changed", null, { metrics });
}

export function publishSnapshot() {
  publishBlockChanges();
  publishItemUse();
  publishInteractions();
  dependencies.flush(true);
  const state = dependencies.loadState();
  console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.started", timestamp: Date.now(), player: null, data: { players: Object.keys(state.players).length, storage: dependencies.storageStatus(), capabilities: dependencies.capabilitySnapshot(), metrics: dependencies.metricsSnapshot() } })}`);
  const livePlayers = new Map(dependencies.world.getAllPlayers().map((p) => [p.name, p]));
  for (const player of Object.values(state.players)) {
    const live = livePlayers.get(player.name);
    const gameMode = live ? dependencies.readGameMode(live) : null;
    const data = gameMode !== null ? { ...player, gameMode } : { ...player };
    console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.player", timestamp: Date.now(), player: { name: player.name }, data })}`);
  }
  console.warn(`${LOG_PREFIX} ${JSON.stringify({ schema: SCHEMA_VERSION, sequence: state.sequence, type: "snapshot.finished", timestamp: Date.now(), player: null, data: {} })}`);
}

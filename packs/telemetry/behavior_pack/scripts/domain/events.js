import { subscribeWorldEvent } from "../adapters/capabilities.js";

/**
 * Register all world-event subscriptions grouped by domain.
 *
 * @param {object} handlers - Named callbacks for each event.
 *   Each callback receives the raw Bedrock event object.
 *   Missing callbacks are silently skipped so callers may omit
 *   handlers they do not need.
 * @param {Function} [handlers.onPlayerJoin]
 * @param {Function} [handlers.onPlayerLeave]
 * @param {Function} [handlers.onPlayerSpawn]
 * @param {Function} [handlers.onEntityDie]
 * @param {Function} [handlers.onEntityHurt]
 * @param {Function} [handlers.onPlayerBreakBlock]
 * @param {Function} [handlers.onPlayerPlaceBlock]
 * @param {Function} [handlers.onPlayerDimensionChange]
 * @param {Function} [handlers.onPlayerUseItem]
 */
export function registerEvents(handlers = {}, subscribe = subscribeWorldEvent) {
  // Player lifecycle
  subscribe("playerJoin", "playerJoins", (event) => {
    handlers.onPlayerJoin?.(event);
  });

  subscribe("playerLeave", "playerLeaves", (event) => {
    handlers.onPlayerLeave?.(event);
  });

  subscribe("playerSpawn", "playerRespawns", (event) => {
    handlers.onPlayerSpawn?.(event);
  });

  subscribe("playerDimensionChange", "dimensionChanges", (event) => {
    handlers.onPlayerDimensionChange?.(event);
  });

  // Combat
  subscribe("entityDie", "deathsAndKills", (event) => {
    handlers.onEntityDie?.(event);
  });

  subscribe("entityHurt", "damageAggregates", (event) => {
    handlers.onEntityHurt?.(event);
  });

  // Block events
  subscribe("playerBreakBlock", "blocksBroken", (event) => {
    handlers.onPlayerBreakBlock?.(event);
  });

  subscribe("playerPlaceBlock", "blocksPlaced", (event) => {
    handlers.onPlayerPlaceBlock?.(event);
  });

  // Opt-in metrics. The subscription is what the capability reports; whether
  // anything is counted is the owner's separate decision (docs/telemetry-metrics.md).
  subscribe("itemUse", "itemUse", (event) => {
    handlers.onPlayerUseItem?.(event);
  });
}

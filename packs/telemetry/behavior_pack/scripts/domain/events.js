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
 */
export function registerEvents(handlers = {}) {
  // Player lifecycle
  subscribeWorldEvent("playerJoin", "playerJoins", (event) => {
    handlers.onPlayerJoin?.(event);
  });

  subscribeWorldEvent("playerLeave", "playerLeaves", (event) => {
    handlers.onPlayerLeave?.(event);
  });

  subscribeWorldEvent("playerSpawn", "playerRespawns", (event) => {
    handlers.onPlayerSpawn?.(event);
  });

  subscribeWorldEvent("playerDimensionChange", "dimensionChanges", (event) => {
    handlers.onPlayerDimensionChange?.(event);
  });

  // Combat
  subscribeWorldEvent("entityDie", "deathsAndKills", (event) => {
    handlers.onEntityDie?.(event);
  });

  subscribeWorldEvent("entityHurt", "damageAggregates", (event) => {
    handlers.onEntityHurt?.(event);
  });

  // Block events
  subscribeWorldEvent("playerBreakBlock", "blocksBroken", (event) => {
    handlers.onPlayerBreakBlock?.(event);
  });

  subscribeWorldEvent("playerPlaceBlock", "blocksPlaced", (event) => {
    handlers.onPlayerPlaceBlock?.(event);
  });
}

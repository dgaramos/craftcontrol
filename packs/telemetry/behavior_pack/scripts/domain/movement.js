import { horizontalDistance } from "../model.js";

const DISTANCE_MAX = 128;

/**
 * Sample one player's movement for a single tick.
 *
 * Reads the player's previous position from `positions`, writes the current
 * position back, and calls `onDistance(dimension, distance)` only when the
 * horizontal displacement is within the valid range (0 < distance <= 128) and
 * both samples are in the same dimension.
 *
 * Guards (no accumulation):
 *   - First tick: no previous position in the Map.
 *   - Dimension mismatch: previous and current dimension ids differ.
 *   - Teleport: horizontal distance > 128 blocks.
 *   - Standing still: horizontal distance == 0.
 *
 * @param {Map} positions - Mutable Map<playerId, {x, z, dimension}>.
 * @param {object} player - Live player object with .id, .location, .dimension.
 * @param {function} onDistance - Called with (dimensionId: string, distance: number).
 */
export function samplePlayerMovement(positions, player, onDistance) {
  const previous = positions.get(player.id);
  const current = { ...player.location, dimension: player.dimension.id };
  positions.set(player.id, current);

  if (!previous || previous.dimension !== current.dimension) return;

  const distance = horizontalDistance(previous, current);
  if (distance <= 0 || distance > DISTANCE_MAX) return;

  onDistance(current.dimension, distance);
}

/**
 * Game mode tracking domain logic.
 *
 * Keeps a per-player game mode state in `gameModes` (Map<playerId, gameMode>)
 * and publishes a "player.gamemode.changed" event when the mode transitions.
 * Delegates capability detection and mode reading to the injected `readGameMode`
 * function so this module has no direct dependency on the Bedrock adapter.
 */

/**
 * Sample game modes for all live players and publish change events.
 *
 * For each player in `livePlayers`:
 *   - Calls `readGameMode(player)` — returns a mode string or null when
 *     the capability is unsupported.
 *   - On the first observation (no previous entry) the mode is stored without
 *     emitting an event.
 *   - On a mode transition the injected `publish` callback is called with
 *     ("player.gamemode.changed", player.name, { previous, current }).
 *   - When `readGameMode` returns null the player's state is not updated.
 *
 * @param {Map} gameModes    - Mutable Map<playerId, string> tracking last known modes.
 * @param {object[]} livePlayers - Live player objects with .id and .name properties.
 * @param {function} readGameMode - (player) => string | null
 * @param {function} publish  - (type, playerName, data) => void
 */
export function trackGameModes(gameModes, livePlayers, readGameMode, publish) {
  for (const player of livePlayers) {
    const current = readGameMode(player);
    if (current === null) continue;

    const previous = gameModes.get(player.id);
    if (previous !== undefined && previous !== current) {
      publish("player.gamemode.changed", player.name, { previous, current });
    }
    gameModes.set(player.id, current);
  }
}

/**
 * Remove a player's game mode state when they disconnect.
 *
 * Prevents stale state from causing spurious change events on rejoin.
 *
 * @param {Map} gameModes - Mutable Map<playerId, string>.
 * @param {string} playerId - The player's unique identifier.
 */
export function removePlayer(gameModes, playerId) {
  gameModes.delete(playerId);
}

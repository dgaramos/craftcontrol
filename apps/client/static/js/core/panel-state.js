/**
 * Pure presentation rules for the shell chrome.
 *
 * These decisions lived inside the composition root, which no test imports, so
 * they were only ever covered by contracts that grep the source. Both had
 * already shipped bugs: the indicator bars showed together, and the world icons
 * were rewritten on every clock tick. Keeping them here makes the rules
 * checkable on their own.
 */

/**
 * Decides which single indicator bar is on screen.
 *
 * An operation outranks pending changes — running, or gone silent and needing a
 * decision, it is what stands between the operator and applying them. Never
 * both at once.
 */
export function indicatorState({ changesCount = 0, operationActive = false, operationStalled = false } = {}) {
  const showOperation = Boolean(operationActive || operationStalled);
  return {
    showOperation,
    showChanges: changesCount > 0 && !showOperation,
    stalled: Boolean(operationStalled),
  };
}

/** True while the Minecraft clock is in its night window. */
export function isNightTick(daytime) {
  return Number.isFinite(daytime) && daytime >= 13000 && daytime < 23000;
}

/**
 * The sprite symbols and weather key for the world cells.
 *
 * Clear weather follows the clock — sun by day, moon by night — while rain and
 * thunder read the same whatever the hour.
 */
export function worldPresentation({ weather, daytime } = {}) {
  const night = isNightTick(daytime);
  const timeIcon = night ? "ui-moon" : "ui-sun";
  if (weather === "rain") return { timeIcon, weatherIcon: "ui-rain", weatherKey: "rain" };
  if (weather === "thunder") return { timeIcon, weatherIcon: "ui-thunder", weatherKey: "thunder" };
  return { timeIcon, weatherIcon: timeIcon, weatherKey: night ? "clear-night" : "clear" };
}

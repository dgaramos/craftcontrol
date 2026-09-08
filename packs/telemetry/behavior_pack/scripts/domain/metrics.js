/**
 * Opt-in metric policy (docs/telemetry-metrics.md).
 *
 * Pure decisions only: which metrics exist, what a command means, and which
 * map keys may be stored. Persistence lives in adapters/store.js and the
 * counting lives in main.js, so this module can be reasoned about — and
 * tested — without a runtime.
 */

/** Every metric this pack knows. A name outside this list is refused. */
export const METRICS = ["itemUse"];

/**
 * A Minecraft namespaced identifier: lowercase namespace, colon, path.
 *
 * The shape is the privacy boundary, not a formality. A player-authored name
 * carries capitals, spaces or formatting codes and cannot match, so a custom
 * item name can never become a map key.
 */
const IDENTIFIER = /^[a-z0-9_]+:[a-z0-9_./-]+$/;
const IDENTIFIER_MAX_LENGTH = 112;

export function emptyMetrics() {
  return Object.fromEntries(METRICS.map((name) => [name, false]));
}

/**
 * Read persisted metric state, defaulting anything unrecognized to disabled.
 *
 * A corrupt or partial value must not enable collection by accident, so every
 * unknown name is dropped and every non-boolean reads as `false`.
 */
export function parseMetrics(value) {
  const source = value !== null && typeof value === "object" && !Array.isArray(value) ? value : {};
  return Object.fromEntries(METRICS.map((name) => [name, source[name] === true]));
}

/**
 * Interpret one `bedrock_telemetry:metrics` command.
 *
 * Accepts `enable <metric>`, `disable <metric>` and `status`. Returns the
 * resulting state plus whether it differs from the current one; an
 * unrecognized command returns an error and changes nothing.
 */
export function applyMetricCommand(current, message) {
  const [verb = "", name = ""] = String(message ?? "").trim().split(/\s+/);
  const metrics = parseMetrics(current);
  if (verb === "status" && !name) return { metrics, changed: false, error: null };
  if (verb !== "enable" && verb !== "disable") return { metrics, changed: false, error: `unknown metric command: ${verb || "(empty)"}` };
  if (!METRICS.includes(name)) return { metrics, changed: false, error: `unknown metric: ${name || "(none)"}` };
  const enabled = verb === "enable";
  return { metrics: { ...metrics, [name]: enabled }, changed: metrics[name] !== enabled, error: null };
}

/** Return the identifier when it may be stored as a map key, otherwise null. */
export function metricKey(value) {
  if (typeof value !== "string" || value.length > IDENTIFIER_MAX_LENGTH) return null;
  return IDENTIFIER.test(value) ? value : null;
}

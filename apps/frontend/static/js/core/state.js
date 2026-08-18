import { tabFromLocation } from "./route.js?v=7";

const storedLocale = localStorage.getItem("craftcontrol-locale") || localStorage.getItem("manager-locale");

export function createState(initialState) {
  const subscriptions = new Map();
  const pending = new Set();
  let batching = 0;
  const target = { ...initialState };

  const notify = (key, value, previous) => {
    if (Object.is(value, previous)) return;
    if (batching) { pending.add(key); return; }
    subscriptions.get(key)?.forEach((callback) => callback(value, previous));
  };

  Object.defineProperties(target, {
    subscribe: { enumerable: false, value(key, callback) {
      if (typeof callback !== "function") throw new TypeError("State subscription must be a function");
      const callbacks = subscriptions.get(key) || new Set();
      callbacks.add(callback);
      subscriptions.set(key, callbacks);
      return () => callbacks.delete(callback);
    } },
    batch: { enumerable: false, value(callback) {
      batching += 1;
      try { return callback(); }
      finally {
        batching -= 1;
        if (!batching) {
          [...pending].forEach((key) => subscriptions.get(key)?.forEach((listener) => listener(target[key])));
          pending.clear();
        }
      }
    } },
  });

  return new Proxy(target, {
    set(object, key, value) {
      const previous = object[key];
      object[key] = value;
      notify(key, value, previous);
      return true;
    },
  });
}

export const state = createState({
  schema: null, config: {}, gamerules: {}, players: [], online: 0, maxPlayers: 0,
  changes: {}, tab: tabFromLocation(), tabs: ["home", "world", "players", "analytics", "rules", "server"], status: null, updatedAt: 0, domains: {},
  analytics: { kind: "all", player: "", source: "all", search: "", days: 0, page: 1, rankingCategory: "activity", rankingMetric: "play_time", blocksMode: "mining", selectedOre: "diamond", combatMetric: "mob_kills", explorationMetric: "distance", periodDays: 30, periodMetric: "play_seconds" },
  locale: ["pt", "en", "es"].includes(storedLocale) ? storedLocale : "pt",
  user: null, frontendVersion: null,
});

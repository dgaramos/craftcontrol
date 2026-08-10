import { tabFromLocation } from "./route.js?v=7";

const storedLocale = localStorage.getItem("craftcontrol-locale") || localStorage.getItem("manager-locale");

export const state = {
  schema: null, config: {}, gamerules: {}, players: [], online: 0, maxPlayers: 0,
  changes: {}, tab: tabFromLocation(), tabs: ["home", "world", "players", "analytics", "rules", "server"], status: null, updatedAt: 0, domains: {},
  analytics: { kind: "all", player: "", source: "all", search: "", days: 0, page: 1, rankingCategory: "activity", rankingMetric: "play_time", blocksMode: "mining", selectedOre: "diamond", combatMetric: "mob_kills", explorationMetric: "distance", periodDays: 30, periodMetric: "play_seconds" },
  locale: ["pt", "en", "es"].includes(storedLocale) ? storedLocale : "pt",
  user: null, frontendVersion: null,
};

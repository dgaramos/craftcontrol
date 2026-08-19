/**
 * Structural contract tests for the players feature.
 * Mirrors the 6 Python tests removed from tests/test_brand.py (issue #159).
 */

import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { join, dirname } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const FRONTEND = join(__dirname, "..");
const PLAYERS = join(FRONTEND, "static", "js", "features", "players");
const SETTINGS = join(FRONTEND, "static", "js", "features", "settings");
const COMPONENTS = join(FRONTEND, "static", "js", "components");

function playersSource() {
  return ["access", "feedback", "history", "index", "profile", "telemetry", "time", "workspace"]
    .flatMap((name) => {
      try {
        return [readFileSync(join(PLAYERS, `${name}.js`), "utf8")];
      } catch {
        return [];
      }
    })
    .join("\n");
}

const composition = readFileSync(join(FRONTEND, "static", "js", "composition.js"), "utf8");
const historyJs = readFileSync(join(PLAYERS, "history.js"), "utf8");
const timeJs = readFileSync(join(COMPONENTS, "time.js"), "utf8");
const settingsJs = readFileSync(join(SETTINGS, "index.js"), "utf8");
const indexJs = readFileSync(join(PLAYERS, "index.js"), "utf8");

// ── 1. test_player_workspace_separates_roster_profile_and_permission_scopes ──

describe("player workspace separates roster, profile and permission scopes", () => {
  test('profile.js renders class="player-detail-screen"', () => {
    const profile = readFileSync(join(PLAYERS, "profile.js"), "utf8");
    expect(profile).toContain('class="player-detail-screen"');
  });

  test('players source includes "Minecraft permission" label', () => {
    expect(playersSource()).toContain("Minecraft permission");
  });

  test('players source includes "CraftControl access" label', () => {
    expect(playersSource()).toContain("CraftControl access");
  });

  test('settings index renders class="player-server-settings"', () => {
    expect(settingsJs).toContain('class="player-server-settings');
  });

  test('settings index includes bilingual "Somente leitura" read-only badge', () => {
    expect(settingsJs).toContain("Somente leitura");
    expect(settingsJs).toContain("Read only");
  });
});

// ── 2. test_player_profile_consolidates_authoritative_individual_analytics ───

describe("player profile consolidates authoritative individual analytics", () => {
  test('telemetry.js renders class="player-data-workspace"', () => {
    const telemetry = readFileSync(join(PLAYERS, "telemetry.js"), "utf8");
    expect(telemetry).toContain('class="player-data-workspace"');
  });

  test("telemetry.js references stats.killsByType", () => {
    const telemetry = readFileSync(join(PLAYERS, "telemetry.js"), "utf8");
    expect(telemetry).toContain("stats.killsByType");
  });

  test("telemetry.js references stats.brokenByType", () => {
    const telemetry = readFileSync(join(PLAYERS, "telemetry.js"), "utf8");
    expect(telemetry).toContain("stats.brokenByType");
  });

  test("telemetry.js references stats.placedByType", () => {
    const telemetry = readFileSync(join(PLAYERS, "telemetry.js"), "utf8");
    expect(telemetry).toContain("stats.placedByType");
  });

  test("telemetry.js references stats.dimensions", () => {
    const telemetry = readFileSync(join(PLAYERS, "telemetry.js"), "utf8");
    expect(telemetry).toContain("stats.dimensions");
  });

  test('profile.js renders id="compare-player-data"', () => {
    const profile = readFileSync(join(PLAYERS, "profile.js"), "utf8");
    expect(profile).toContain('id="compare-player-data"');
  });

  test("profile.js sets state.analytics.player = profile.name", () => {
    const profile = readFileSync(join(PLAYERS, "profile.js"), "utf8");
    expect(profile).toContain("state.analytics.player = profile.name");
  });

  test('history.js renders class="player-record-drawer"', () => {
    expect(historyJs).toContain('class="player-record-drawer"');
  });

  test('history.js mentions "permanent aggregates" explaining non-authoritative history', () => {
    expect(historyJs).toContain("permanent aggregates");
  });
});

// ── 3. test_player_feature_separates_workspace_profile_access_history_and_telemetry ──

describe("player feature separates workspace, profile, access, history and telemetry", () => {
  const modules = {
    workspace: "createPlayersWorkspace",
    profile: "createPlayerProfile",
    access: "createPlayerAccess",
    history: "createPlayerHistory",
    telemetry: "createPlayerTelemetry",
  };

  for (const [name, factory] of Object.entries(modules)) {
    test(`${name}.js exports ${factory}`, () => {
      const source = readFileSync(join(PLAYERS, `${name}.js`), "utf8");
      expect(source).toContain(`export function ${factory}`);
    });

    test(`index.js imports from ./${name}.js?v=7`, () => {
      expect(indexJs).toContain(`from "./${name}.js?v=7"`);
    });
  }

  test('composition.js imports from "./features/players/index.js?v=7"', () => {
    expect(composition).toContain('from "./features/players/index.js?v=7"');
  });

  test("composition.js does not inline renderPlayerCards", () => {
    expect(composition).not.toContain("function renderPlayerCards");
  });

  test("composition.js does not inline bindPlayerAccess", () => {
    expect(composition).not.toContain("function bindPlayerAccess");
  });

  test("composition.js does not inline deathHistoryMarkup", () => {
    expect(composition).not.toContain("function deathHistoryMarkup");
  });

  test("composition.js does not inline playerDataMarkup", () => {
    expect(composition).not.toContain("function playerDataMarkup");
  });
});

// ── 4. test_composition_defines_player_settings_markup_before_passing_to_players_feature ──

describe("composition defines playerSettingsMarkup before passing to createPlayersFeature", () => {
  test("composition.js contains function playerSettingsMarkup", () => {
    expect(composition).toContain("function playerSettingsMarkup");
  });

  test("playerSettingsMarkup is defined before it is passed to createPlayersFeature (regression #155/#156)", () => {
    const definitionPos = composition.indexOf("function playerSettingsMarkup");
    const usagePos = composition.indexOf("playerSettingsMarkup,");
    expect(definitionPos).toBeGreaterThanOrEqual(0);
    expect(usagePos).toBeGreaterThanOrEqual(0);
    expect(definitionPos).toBeLessThan(usagePos);
  });
});

// ── 5. test_player_timeline_separates_action_from_localized_timestamp ────────

describe("player timeline separates action from localized timestamp", () => {
  test('history.js uses class="timeline-action" for the action column', () => {
    expect(historyJs).toContain('class="timeline-action"');
  });

  test('time.js renders class="timeline-timestamp"', () => {
    expect(timeJs).toContain('class="timeline-timestamp"');
  });

  test('time.js formats dates with month: "short"', () => {
    expect(timeJs).toContain('month: "short"');
  });
});

// ── 6. test_recent_sessions_have_distinct_state_duration_and_period_layout ───

describe("recent sessions have distinct state, duration and period layout", () => {
  test('history.js renders class="session-state"', () => {
    expect(historyJs).toContain('class="session-state"');
  });

  test('history.js renders class="session-duration"', () => {
    expect(historyJs).toContain('class="session-duration"');
  });

  test('history.js renders class="session-period"', () => {
    expect(historyJs).toContain('class="session-period"');
  });

  test("history.js handles session.disconnected_at for ended sessions", () => {
    expect(historyJs).toContain("session.disconnected_at");
  });
});

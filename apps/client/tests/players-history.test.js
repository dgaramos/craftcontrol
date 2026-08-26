import { createPlayerHistory } from "../static/js/features/players/history.js";

function makeDeps(locale = "en") {
  const state = { locale };
  const t = (key) => key;
  const escapeHtml = (s) => String(s).replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const gameLabel = (value, kind) => String(value);
  const gameIcon = () => `<svg/>`;
  const gameTermMarkup = (value) => `<span>${escapeHtml(String(value))}</span>`;
  const optionLabel = (v) => v;
  const formatDate = (ts) => ts ? "2024-01-01" : "—";
  const formatDuration = (s) => `${s}s`;
  const sessionMoment = (ts) => ts ? `<time>${ts}</time>` : "—";
  const timelineTimestamp = (ts) => ts ? `<time>${ts}</time>` : "<span>—</span>";
  return { state, t, escapeHtml, gameLabel, gameIcon, gameTermMarkup, optionLabel, formatDate, formatDuration, sessionMoment, timelineTimestamp };
}

describe("createPlayerHistory — historyMarkup", () => {
  test("returns empty message for no events", () => {
    const { historyMarkup } = createPlayerHistory(makeDeps());
    expect(historyMarkup([])).toContain("noHistory");
  });

  test("renders timeline list for events", () => {
    const { historyMarkup } = createPlayerHistory(makeDeps());
    const events = [{ topic: "player.connected", timestamp: 1700000000, payload: {} }];
    const html = historyMarkup(events);
    expect(html).toContain("timeline-list");
    expect(html).toContain("Joined the server");
  });

  test("renders pt labels in pt locale", () => {
    const { historyMarkup } = createPlayerHistory(makeDeps("pt"));
    const events = [{ topic: "player.connected", timestamp: 1700000000, payload: {} }];
    const html = historyMarkup(events);
    expect(html).toContain("Entrou no servidor");
  });

  test("renders death event", () => {
    const { historyMarkup } = createPlayerHistory(makeDeps());
    const events = [{ topic: "player.death", timestamp: 1700000000, payload: { cause: "fall" } }];
    const html = historyMarkup(events);
    expect(html).toContain("Died");
    expect(html).toContain("fall");
  });

  test("unknown topic falls back to topic string", () => {
    const { historyMarkup } = createPlayerHistory(makeDeps());
    const events = [{ topic: "custom.event", timestamp: 1700000000, payload: {} }];
    const html = historyMarkup(events);
    expect(html).toContain("custom.event");
  });

  test("inferred payload adds inferred note", () => {
    const { historyMarkup } = createPlayerHistory(makeDeps());
    const events = [{ topic: "player.disconnected", timestamp: 1700000000, payload: { inferred: true } }];
    const html = historyMarkup(events);
    expect(html).toContain("Inferred from server state");
  });

  test("handles missing evidence and permission changes", () => {
    const { historyMarkup } = createPlayerHistory(makeDeps("pt"));
    const html = historyMarkup([{}, { topic: "player.permission.changed", payload: { cause: "fire", inferred: true } }]);
    expect(html).toContain("event");
    expect(html).toContain("Permissão alterada");
    expect(html).toContain("Encerramento inferido");
  });
});

describe("createPlayerHistory — sessionsMarkup", () => {
  test("returns empty message for no sessions", () => {
    const { sessionsMarkup } = createPlayerHistory(makeDeps());
    expect(sessionsMarkup([])).toContain("noHistory");
  });

  test("renders active session", () => {
    const { sessionsMarkup } = createPlayerHistory(makeDeps());
    const sessions = [{ active: true, duration_seconds: 120, connected_at: 1700000000 }];
    const html = sessionsMarkup(sessions);
    expect(html).toContain("is-active");
    expect(html).toContain("Session in progress");
  });

  test("renders ended session", () => {
    const { sessionsMarkup } = createPlayerHistory(makeDeps());
    const sessions = [{ active: false, inferred: false, duration_seconds: 60, connected_at: 1700000000, disconnected_at: 1700000060 }];
    const html = sessionsMarkup(sessions);
    expect(html).toContain("Session ended");
    expect(html).toContain("normalExit");
  });

  test("renders inferred session", () => {
    const { sessionsMarkup } = createPlayerHistory(makeDeps());
    const sessions = [{ active: false, inferred: true, duration_seconds: 60, connected_at: 1700000000 }];
    const html = sessionsMarkup(sessions);
    expect(html).toContain("is-inferred");
    expect(html).toContain("inferredExit");
  });

  test("close_reason appears when not disconnect", () => {
    const { sessionsMarkup } = createPlayerHistory(makeDeps());
    const sessions = [{ active: false, inferred: false, duration_seconds: 60, connected_at: 1700000000, close_reason: "timeout" }];
    const html = sessionsMarkup(sessions);
    expect(html).toContain("timeout");
  });

  test("renders Portuguese current and closed session labels", () => {
    const { sessionsMarkup } = createPlayerHistory(makeDeps("pt"));
    const html = sessionsMarkup([{ active: true, duration_seconds: 1, connected_at: 1 }, { active: false, inferred: false, duration_seconds: 1, connected_at: 1, disconnected_at: 2, close_reason: "disconnect" }]);
    expect(html).toContain("Sessão em andamento");
    expect(html).toContain("Sessão encerrada");
    expect(html).not.toContain(" · disconnect");
  });
});

describe("createPlayerHistory — deathHistoryMarkup", () => {
  test("returns no deaths message for empty events", () => {
    const { deathHistoryMarkup } = createPlayerHistory(makeDeps());
    expect(deathHistoryMarkup([])).toContain("noDeaths");
  });

  test("renders death events", () => {
    const { deathHistoryMarkup } = createPlayerHistory(makeDeps());
    const events = [{ topic: "player.death", timestamp: 1700000000, payload: { cause: "fall" }, source: "server" }];
    const html = deathHistoryMarkup(events);
    expect(html).toContain("death-history");
    expect(html).toContain("fall");
  });

  test("ignores non-death events", () => {
    const { deathHistoryMarkup } = createPlayerHistory(makeDeps());
    const events = [{ topic: "player.connected", timestamp: 1700000000, payload: {} }];
    expect(deathHistoryMarkup(events)).toContain("noDeaths");
  });

  test("behavior pack source shows telemetrySource", () => {
    const { deathHistoryMarkup } = createPlayerHistory(makeDeps());
    const events = [{ topic: "player.death", timestamp: 1700000000, payload: { cause: "fall" }, source: "behavior-pack" }];
    const html = deathHistoryMarkup(events);
    expect(html).toContain("telemetrySource");
  });

  test("renders killer variants, projectile evidence, and fallback values", () => {
    const { deathHistoryMarkup } = createPlayerHistory(makeDeps());
    const html = deathHistoryMarkup([{ topic: "player.death", timestamp: 1, payload: { cause: "projectile", killerType: "skeleton", projectileType: "arrow" }, source: "behavior-pack" }, { topic: "player.death", timestamp: 2, payload: {}, source: "server" }]);
    expect(html).toContain("skeleton");
    expect(html).toContain("arrow");
    expect(html).toContain("—");
  });
});

describe("createPlayerHistory — profileMarkup", () => {
  test("renders profile markup for a basic profile", () => {
    const { profileMarkup } = createPlayerHistory(makeDeps());
    const profile = {
      name: "TestPlayer",
      permission: "member",
      last_death_at: 1700000000,
      aliases: ["TestPlayer"],
      history: [],
      sessions: [],
      online: false,
      last_seen_at: 1700000000,
    };
    const html = profileMarkup(profile);
    expect(html).toContain("player-records");
    expect(html).toContain("member");
  });

  test("filters out current name from aliases", () => {
    const { profileMarkup } = createPlayerHistory(makeDeps());
    const profile = {
      name: "UNIQUEXYZ",
      permission: "member",
      last_death_at: 0,
      aliases: ["UNIQUEXYZ", "OldName"],
      history: [],
      sessions: [],
    };
    const html = profileMarkup(profile);
    expect(html).toContain("OldName");
    // UNIQUEXYZ should not appear in the aliases section (it's filtered out)
    const aliasSection = html.match(/aliases.*?<\/div>/s)?.[0] || "";
    expect(aliasSection).not.toContain("UNIQUEXYZ");
  });

  test("counts death events", () => {
    const { profileMarkup } = createPlayerHistory(makeDeps());
    const profile = {
      name: "Player",
      permission: "member",
      last_death_at: 0,
      aliases: [],
      history: [
        { topic: "player.death", timestamp: 1, payload: {} },
        { topic: "player.connected", timestamp: 2, payload: {} },
      ],
      sessions: [],
    };
    const html = profileMarkup(profile);
    expect(html).toContain("<b>1</b>");
  });

  test("uses collection fallbacks for incomplete profiles", () => {
    const { profileMarkup } = createPlayerHistory(makeDeps("pt"));
    const html = profileMarkup({ name: "Player", permission: "", aliases: null, history: null, sessions: null, last_death_at: null });
    expect(html).toContain("member");
    expect(html).toContain("—");
  });
});

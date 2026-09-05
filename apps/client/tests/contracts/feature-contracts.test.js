import { readFileSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = resolve(__dirname, "..", "..");
const STATIC = join(FRONTEND, "static");
const JS = join(STATIC, "js");

function frontendScript() {
  return [
    readFileSync(join(STATIC, "app.js"), "utf8"),
    readFileSync(join(JS, "composition.js"), "utf8"),
    readFileSync(join(JS, "features", "settings", "index.js"), "utf8"),
  ].join("\n");
}

describe("feature contracts — world/rules/server/auth boundaries", () => {
  test("world/index.js exports createWorldFeature", () => {
    const module = readFileSync(join(JS, "features", "world", "index.js"), "utf8");
    expect(module).toContain("function createWorldFeature");
  });

  test("rules/index.js exports createRulesFeature", () => {
    const module = readFileSync(join(JS, "features", "rules", "index.js"), "utf8");
    expect(module).toContain("function createRulesFeature");
  });

  test("server/index.js exports createServerFeature", () => {
    const module = readFileSync(join(JS, "features", "server", "index.js"), "utf8");
    expect(module).toContain("function createServerFeature");
  });

  test("auth/bootstrap.js exports startAuthenticatedApplication", () => {
    const module = readFileSync(join(JS, "features", "auth", "bootstrap.js"), "utf8");
    expect(module).toContain("function startAuthenticatedApplication");
  });

  test("composition.js delegates world via getWorldFeature", () => {
    const script = frontendScript();
    expect(script).toContain("getWorldFeature().renderWorld()");
  });

  test("composition.js delegates rules via getRulesFeature", () => {
    const script = frontendScript();
    expect(script).toContain("getRulesFeature().renderRules()");
  });

  test("composition.js delegates server via getServerFeature", () => {
    const script = frontendScript();
    expect(script).toContain("getServerFeature().renderServer()");
  });

  test("composition.js routes analytics tab to renderAnalyticsPanel", () => {
    const script = frontendScript();
    expect(script).toContain('state.tab === "analytics"');
    expect(script).toContain("renderAnalyticsPanel()");
  });

  test("composition.js routes audit tab to getAuditFeature().renderAuditPanel", () => {
    const script = frontendScript();
    expect(script).toContain('state.tab === "audit"');
    expect(script).toContain("getAuditFeature().renderAuditPanel()");
  });

  test("composition.js routes __time__ tab to getWorldFeature().renderTimePanel", () => {
    const script = frontendScript();
    expect(script).toContain('state.tab === "__time__"');
    expect(script).toContain("getWorldFeature().renderTimePanel()");
  });

  test("composition.js routes __players__ tab to renderPlayersPanel", () => {
    const script = frontendScript();
    expect(script).toContain('state.tab === "__players__"');
    expect(script).toContain("renderPlayersPanel()");
  });

  test("composition.js does not inline renderTimePanel", () => {
    const script = frontendScript();
    expect(script).not.toContain("function renderTimePanel");
  });

  test("composition.js does not inline loadTelemetryPack", () => {
    const script = frontendScript();
    expect(script).not.toContain("function loadTelemetryPack");
  });

  test("composition.js does not inline requireSession().then", () => {
    const script = frontendScript();
    expect(script).not.toContain("requireSession().then");
  });
});

describe("feature contracts — deaths localisation and layout", () => {
  test("game-terms.js has entityExplosion entry with mob sprite", () => {
    const terms = readFileSync(join(JS, "i18n", "game-terms.js"), "utf8");
    expect(terms).toContain('entityExplosion: ["creeper", "Explosão de criatura", "Entity explosion"]');
  });

  test("game-terms.js has skeleton entry with mob sprite", () => {
    const terms = readFileSync(join(JS, "i18n", "game-terms.js"), "utf8");
    expect(terms).toContain('skeleton: ["skeleton", "Esqueleto", "Skeleton"]');
  });

  test("game-terms.js references craftcontrol-mobs.svg mob sprites", () => {
    const terms = readFileSync(join(JS, "i18n", "game-terms.js"), "utf8");
    expect(terms).toContain("/static/craftcontrol-mobs.svg#mob-");
  });

  test("history.js has death-entry-header class", () => {
    const history = readFileSync(join(JS, "features", "players", "history.js"), "utf8");
    expect(history).toContain('class="death-entry-header"');
  });

  test("players.css has .death-source rule", () => {
    const stylesheet = readFileSync(join(STATIC, "players.css"), "utf8");
    expect(stylesheet).toContain(".death-source");
  });

  test("index.html has release-tags element", () => {
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(template).toContain('id="release-tags"');
  });
});

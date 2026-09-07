import { readFileSync, readdirSync } from "fs";
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

describe("feature contracts — pending changes and operation indicators", () => {
  /* The reactive state proxy only traps top-level assignment. Mutating
     state.changes in place silently skips every "changes" subscriber, which
     leaves the pending-changes bar on screen with an empty drawer behind it. */
  function everyModule() {
    const files = [];
    const walk = (dir) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const full = join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (entry.name.endsWith(".js")) files.push([full, readFileSync(full, "utf8")]);
      }
    };
    walk(JS);
    files.push([join(STATIC, "app.js"), readFileSync(join(STATIC, "app.js"), "utf8")]);
    return files;
  }

  test("no module mutates state.changes in place", () => {
    const offenders = everyModule()
      .filter(([, source]) => /delete\s+state\.changes\[/.test(source) || /state\.changes\[[^\]]+\]\s*=[^=]/.test(source))
      .map(([file]) => file);
    expect(offenders).toEqual([]);
  });

  /* The UA rule for [hidden] is display:none, but ANY author `display` rule
     beats it. This project hit that four separate times (footer, players list,
     bottom sheet, and both indicator bars, which stayed permanently visible
     because .indicator-bar sets display:flex). One global rule settles it. */
  test("the hidden attribute wins over component display rules", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    expect(css).toMatch(/^\[hidden\]\s*\{[^}]*display:\s*none\s*!important/m);
  });

  /* The world clock ticks 10x a second. Rewriting the href of a <use> that
     points at an external sprite re-resolves the reference and makes the icon
     flicker, so the write must be conditional. */
  test("the world icons are only rewritten when the symbol changes", () => {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    expect(composition).toContain('if (useEl.getAttribute("href") !== href) useEl.setAttribute("href", href)');
    expect(composition).not.toMatch(/\$\("#world-(time|weather)-icon"\)\.setAttribute/);
  });

  test("exactly one indicator bar shows, with the operation outranking changes", () => {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    expect(composition).toContain("const showOperation = opActive || opStalled");
    expect(composition).toContain("opBar.hidden = !showOperation");
    expect(composition).toContain("changesBar.hidden = changesCount === 0 || showOperation");
  });

  test("operations carry both a retention window and an unresponsive window", () => {
    const operation = readFileSync(join(JS, "features", "server", "operation.js"), "utf8");
    expect(operation).toContain("CONFIRMED_RETENTION_MS");
    expect(operation).toContain("isExpiredOperation");
    expect(operation).toContain("UNRESPONSIVE_AFTER_MS");
    expect(operation).toContain("isUnresponsiveOperation");
  });

  /* An unresponsive operation must never count as active, or the app stays
     locked out of restart, stop, time controls and applying changes. */
  test("only a live, responding operation sets state.operationActive", () => {
    const server = readFileSync(join(JS, "features", "server", "index.js"), "utf8");
    expect(server).toContain("state.operationActive = live && !stalled");
    const offenders = [readFileSync(join(JS, "composition.js"), "utf8"), server]
      .filter((source) => /state\.operationActive\s*=\s*!!\(op/.test(source));
    expect(offenders).toEqual([]);
  });
});

import { readFileSync, readdirSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = resolve(__dirname, "..", "..");
const ANALYTICS = join(FRONTEND, "static", "js", "features", "analytics");
const I18N = join(FRONTEND, "static", "js", "i18n");

function frontendScript() {
  return [
    readFileSync(join(FRONTEND, "static", "app.js"), "utf8"),
    readFileSync(join(FRONTEND, "static", "js", "composition.js"), "utf8"),
    readFileSync(join(FRONTEND, "static", "js", "features", "settings", "index.js"), "utf8"),
  ].join("\n");
}

function analyticsJs() {
  const files = readdirSync(ANALYTICS)
    .filter((f) => f.endsWith(".js"))
    .sort();
  return files.map((f) => readFileSync(join(ANALYTICS, f), "utf8")).join("\n");
}

function i18nCatalogs() {
  return ["pt", "en", "es"]
    .map((locale) => readFileSync(join(I18N, `${locale}.js`), "utf8"))
    .join("\n");
}

describe("analytics activity and deaths have a feature boundary", () => {
  test("activity.js exports createActivityView", () => {
    const activity = readFileSync(join(ANALYTICS, "activity.js"), "utf8");
    expect(activity).toContain("export function createActivityView");
  });

  test("index.js imports activity.js with versioned query and delegates to activityView", () => {
    const index = readFileSync(join(ANALYTICS, "index.js"), "utf8");
    expect(index).toContain('from "./activity.js?v=7"');
    expect(index).toContain("activityView.eventsMarkup");
    expect(index).toContain("activityView.showDeathDetails");
  });

  test("bundle does not inline analyticsEventsMarkup or showDeathDetails", () => {
    const script = frontendScript();
    expect(script).not.toContain("function analyticsEventsMarkup");
    expect(script).not.toContain("function showDeathDetails");
  });

  test("bundle imports analytics feature from versioned path", () => {
    const script = frontendScript();
    expect(script).toContain('from "./features/analytics/index.js?v=8"');
  });
});

describe("analytics has dedicated bilingual mobile workspace", () => {
  test("i18n catalogs contain bilingual activity and panel strings", () => {
    const pt = readFileSync(join(I18N, "pt.js"), "utf8");
    const en = readFileSync(join(I18N, "en.js"), "utf8");
    const es = readFileSync(join(I18N, "es.js"), "utf8");

    // Keys that must be explicitly defined in pt and en (es inherits from en via spread)
    for (const catalog of [pt, en]) {
      expect(catalog).toContain("rankingsTitle");
      expect(catalog).toContain("combatEmptyHelp");
      expect(catalog).toContain("explorationEmptyHelp");
      expect(catalog).toContain("collectionStarted");
    }
    // es defines its own rankingsTitle override
    expect(es).toContain("rankingsTitle");

    // Locale-specific visible strings validated per catalog
    expect(pt).toContain("Atividade do servidor");
    expect(pt).toContain("Fim da linha do tempo");
    expect(en).toContain("Server activity");
    expect(en).toContain("End of timeline");
    expect(es).toContain("Fin de la línea de tiempo");
  });

  test("analytics JS contains view-switch tuples for all panels", () => {
    const analytics = analyticsJs();
    expect(analytics).toContain('["deaths", "deaths", "deathsView"]');
    expect(analytics).toContain('["combat", "combat", "combatView"]');
    expect(analytics).toContain('["exploration", "exploration", "explorationView"]');
    expect(analytics).toContain('["trends", "periods", "trendsView"]');
  });

  test("analytics.css has mobile layout and panel-specific selectors", () => {
    const stylesheet = readFileSync(join(FRONTEND, "static", "analytics.css"), "utf8");
    expect(stylesheet).toContain("@media (max-width: 480px)");
    expect(stylesheet).toContain(".podium-place.rank-1");
    expect(stylesheet).toContain(".combat-zero");
    expect(stylesheet).toContain(".exploration-zero");
    expect(stylesheet).toContain(".heatmap-grid");
    expect(stylesheet).toContain(".trends-main-grid { display: grid; min-width: 0");
    expect(stylesheet).toContain(".calendar-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }");
    expect(stylesheet).toContain(".heatmap-scroll { width: 100%; max-width: 100%");
    expect(stylesheet).toContain(".activity-scroll-sentinel");
  });

  test("template includes analytics.css and analytics data attributes", () => {
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(template).toContain("analytics.css");
    const activity = readFileSync(join(ANALYTICS, "activity.js"), "utf8");
    expect(activity).toContain("data-analytics-player=");
    const analytics = analyticsJs();
    expect(analytics).toContain('id="analytics-death-dialog"');
  });
});

describe("activity timeline loads incrementally and stops at the last page", () => {
  test("index.js implements intersection observer pagination without next-button", () => {
    const analytics = readFileSync(join(ANALYTICS, "index.js"), "utf8");
    expect(analytics).toContain("const hasMore = result.page < result.pages");
    expect(analytics).toContain("new window.IntersectionObserver");
    expect(analytics).toContain("if (loadingActivity) return");
    expect(analytics).toContain("activityObserver?.disconnect()");
    expect(analytics).toContain("activityTimelineEnd");
    expect(analytics).not.toContain('id="analytics-next"');
  });
});

describe("analytics panels are owned by separate feature modules", () => {
  const panels = {
    rankings: "createRankingsPanel",
    blocks: "createBlocksPanel",
    combat: "createCombatPanel",
    exploration: "createExplorationPanel",
    trends: "createTrendsPanel",
  };

  for (const [name, factory] of Object.entries(panels)) {
    test(`${name}.js exports ${factory} and index.js imports it with versioned path`, () => {
      const module = readFileSync(join(ANALYTICS, `${name}.js`), "utf8");
      expect(module).toContain(`export function ${factory}`);
      const index = readFileSync(join(ANALYTICS, "index.js"), "utf8");
      expect(index).toContain(`from "./${name}.js?v=7"`);
    });
  }

  test("bundle exports createAnalyticsFeature without inlining panel render functions", () => {
    const script = frontendScript();
    expect(script).toContain("createAnalyticsFeature");
    expect(script).not.toContain("async function renderRankingsPanel");
    expect(script).not.toContain("async function renderBlocksPanel");
    expect(script).not.toContain("async function renderCombatPanel");
    expect(script).not.toContain("async function renderExplorationPanel");
    expect(script).not.toContain("async function renderTrendsPanel");
  });
});

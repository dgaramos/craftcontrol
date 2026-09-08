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

function compositionScript() {
  return readFileSync(join(JS, "composition.js"), "utf8");
}

describe("brand contracts — entrypoint structure", () => {
  test("app.js is only bootstrap and composition (≤5 lines)", () => {
    const entrypoint = readFileSync(join(STATIC, "app.js"), "utf8");
    expect(entrypoint.split("\n").length).toBeLessThanOrEqual(5);
  });

  test("app.js calls startApplication", () => {
    const entrypoint = readFileSync(join(STATIC, "app.js"), "utf8");
    expect(entrypoint).toContain("startApplication");
  });

  test("composition.js exports createNavigation", () => {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    expect(composition).toContain("createNavigation");
  });

  test("composition.js exports connectInvalidation", () => {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    expect(composition).toContain("connectInvalidation");
  });

  test("settings feature exports createSettingsFeature", () => {
    const settings = readFileSync(join(JS, "features", "settings", "index.js"), "utf8");
    expect(settings).toContain("createSettingsFeature");
  });
});

describe("brand contracts — CSRF and API versioning", () => {
  test("api.js attaches X-CSRF-Token header", () => {
    const api = readFileSync(join(JS, "api.js"), "utf8");
    expect(api).toContain('headers["X-CSRF-Token"] = csrfToken');
  });

  test("api.js validates csrf_token type", () => {
    const api = readFileSync(join(JS, "api.js"), "utf8");
    expect(api).toContain('typeof data.csrf_token === "string"');
  });

  test("composition.js references api.js?v=7", () => {
    const script = compositionScript();
    expect(script).toContain("./api.js?v=7");
  });

  test("auth.js references api.js?v=7", () => {
    const auth = readFileSync(join(JS, "auth.js"), "utf8");
    expect(auth).toContain("./api.js?v=7");
  });
});

describe("brand contracts — mobile scroll behaviour", () => {
  test("the shell has one navigation, with no legacy tab strip left behind", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    // #tabs was hidden and rebuilt on every tab change; the bottom nav is the
    // only navigation the shell renders.
    expect(css).not.toContain("#tabs");
    expect(template).not.toContain('id="tabs"');
    expect(template).not.toContain("tpl-nav-tab");
    expect(css).toMatch(/\.bottom-nav \{/);
  });

  test("app.css sets overscroll-behavior-y: none", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    expect(css).toContain("overscroll-behavior-y: none");
  });

  /* iPadOS parks the page past the end of the content when the document is
     scrollable at all, which drags the whole shell — and the bottom nav with
     it — out of place. The shell owns the viewport instead. */
  test("the document itself never scrolls", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    const body = css.match(/\nbody \{[^}]*\}/)[0];
    expect(body).toContain("height: 100%");
    expect(body).toContain("overflow: hidden");
    expect(body).not.toContain("min-height: 100vh");
  });

  test("the shell is pinned to the viewport, not sized by a viewport unit", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    const shell = css.match(/\.shell \{[^}]*\}/)[0];
    expect(shell).toContain("position: fixed");
    expect(shell).toContain("inset: 0");
    expect(shell).not.toContain("100dvh");
  });

  test("the scroll container contains its overscroll", () => {
    const css = readFileSync(join(STATIC, "app.css"), "utf8");
    const main = css.match(/\nmain \{[^}]*\}/)[0];
    expect(main).toContain("overflow-y: auto");
    expect(main).toContain("overscroll-behavior-y: contain");
  });

  /* <main> is the scroll container in the mobile shell, so window.scrollTo is a
     no-op: a screen opened after scrolling would appear already scrolled down. */
  test("tab changes reset the scroll container, not the window", () => {
    const nav = readFileSync(join(JS, "core", "navigation.js"), "utf8");
    expect(nav).toContain("resetPanelScroll");
    expect(nav).not.toContain("window.scrollTo");
    const dom = readFileSync(join(JS, "core", "dom.js"), "utf8");
    expect(dom).toContain("export function resetPanelScroll");
  });

  test("index.html references app.css?v=57", () => {
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(template).toContain("/static/app.css?v=57");
  });

  test("index.html references app.js?v=100", () => {
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(template).toContain("/static/app.js?v=100");
  });

  test("index.html links the self-hosted display and body fonts", () => {
    const template = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");
    expect(template).toContain("/static/fonts.css");
  });

  test("fonts.css self-hosts Oxanium and Geist without an external origin", () => {
    const fonts = readFileSync(join(FRONTEND, "static", "fonts.css"), "utf8");
    expect(fonts).toContain("font-family: 'Oxanium'");
    expect(fonts).toContain("font-family: 'Geist'");
    expect(fonts).not.toContain("https://");
  });

  test("app.css resolves the display and body font tokens", () => {
    const css = readFileSync(join(FRONTEND, "static", "app.css"), "utf8");
    expect(css).toContain("--font-display: Oxanium");
    expect(css).toContain("--font-body: Geist");
  });
});

describe("brand contracts — core module ownership (state and dom)", () => {
  test("composition.js imports from core/state.js?v=8", () => {
    const script = compositionScript();
    expect(script).toContain('from "./core/state.js?v=8"');
  });

  test("composition.js imports from core/dom.js?v=7", () => {
    const script = compositionScript();
    expect(script).toContain('from "./core/dom.js?v=7"');
  });

  test("core/state.js exports state", () => {
    const state = readFileSync(join(JS, "core", "state.js"), "utf8");
    expect(state).toContain("export const state");
  });

  test("core/dom.js exports escapeHtml", () => {
    const dom = readFileSync(join(JS, "core", "dom.js"), "utf8");
    expect(dom).toContain("export function escapeHtml");
  });

  test("composition.js does not inline state", () => {
    const script = compositionScript();
    expect(script).not.toContain("const state = {");
  });

  test("composition.js does not inline escapeHtml", () => {
    const script = compositionScript();
    expect(script).not.toContain("function escapeHtml");
  });
});

describe("brand contracts — component module ownership (feedback and time)", () => {
  test("composition.js imports from components/feedback.js?v=7", () => {
    const script = compositionScript();
    expect(script).toContain('from "./components/feedback.js?v=7"');
  });

  test("composition.js imports from components/time.js?v=9", () => {
    const script = compositionScript();
    expect(script).toContain('from "./components/time.js?v=9"');
  });

  test("components/feedback.js exports toast", () => {
    const feedback = readFileSync(join(JS, "components", "feedback.js"), "utf8");
    expect(feedback).toContain("export function toast");
  });

  test("components/time.js exports timelineTimestamp", () => {
    const time = readFileSync(join(JS, "components", "time.js"), "utf8");
    expect(time).toContain("export function timelineTimestamp");
  });

  test("components/time.js exports formatDuration", () => {
    const time = readFileSync(join(JS, "components", "time.js"), "utf8");
    expect(time).toContain("export function formatDuration");
  });

  test("composition.js does not inline toast", () => {
    const script = compositionScript();
    expect(script).not.toContain("function toast");
  });

  test("composition.js does not inline formatDuration", () => {
    const script = compositionScript();
    expect(script).not.toContain("function formatDuration");
  });
});

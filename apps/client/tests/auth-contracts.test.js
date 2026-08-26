/**
 * Structural contract tests for auth accessibility and i18n.
 * Mirrors test_authentication_can_reveal_passwords_accessibly removed from tests/test_brand.py (issue #161).
 */

import { readFileSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const FRONTEND = resolve(__dirname, "..");
const STATIC = join(FRONTEND, "static");
const JS = join(STATIC, "js");

const authScript = readFileSync(join(JS, "auth.js"), "utf8");
const authCss = readFileSync(join(STATIC, "auth.css"), "utf8");
const indexTemplate = readFileSync(join(FRONTEND, "templates", "index.html"), "utf8");

describe("auth contracts — password toggle accessibility", () => {
  test("auth.js has password-toggle class", () => {
    expect(authScript).toContain("password-toggle");
  });

  test("auth.js uses aria-pressed on the toggle button", () => {
    expect(authScript).toContain("aria-pressed");
  });

  test('auth.js renders class="auth-switch" for login/claim navigation', () => {
    expect(authScript).toContain('class="auth-switch"');
  });

  test("auth.js separates login and claim forms (no hidden claim form id)", () => {
    expect(authScript).not.toContain('id="claim-form" hidden');
  });

  test("auth.js uses words.claimTitle for the claim screen heading", () => {
    expect(authScript).toContain("words.claimTitle");
  });

  test("auth.js derives the form from the claim flag (login/claim branch)", () => {
    expect(authScript).toContain("const form = claim");
  });

  test("auth.js accesses the form via overlay.querySelector", () => {
    expect(authScript).toContain('overlay.querySelector("form")');
  });

  test("auth.js includes PT showPassword translation", () => {
    expect(authScript).toContain('showPassword: "Mostrar senha"');
  });

  test("auth.js includes EN showPassword translation", () => {
    expect(authScript).toContain('showPassword: "Show password"');
  });

  test("auth.js includes ES showPassword translation", () => {
    expect(authScript).toContain('showPassword: "Mostrar contraseña"');
  });

  test("auth.css hides form[hidden] inside auth-card", () => {
    expect(authCss).toContain(".auth-card form[hidden]");
  });

  test("auth.css defines .password-toggle style", () => {
    expect(authCss).toContain(".password-toggle");
  });
});

describe("auth contracts — ui-eye icon in SVG sprite", () => {
  test("craftcontrol-ui.svg contains ui-eye symbol", () => {
    const svgSource = readFileSync(join(STATIC, "craftcontrol-ui.svg"), "utf8");
    expect(svgSource).toContain('id="ui-eye"');
  });
});

describe("auth contracts — account workspace usability", () => {
  test("identity actions use distinct original password and sessions icons", () => {
    const svgSource = readFileSync(join(STATIC, "craftcontrol-ui.svg"), "utf8");
    expect(svgSource).toContain('id="ui-password"');
    expect(svgSource).toContain('id="ui-sessions"');
    expect(indexTemplate).toMatch(/id="change-password"[^>]*>\s*<svg[^>]*>\s*<use[^>]*#ui-password/);
    expect(indexTemplate).toMatch(/id="manage-sessions"[^>]*>\s*<svg[^>]*>\s*<use[^>]*#ui-sessions/);
  });

  test("keeps account action icons touch-sized when their labels collapse", () => {
    expect(authCss).toContain("#identity button .cc-icon");
    expect(authCss).toContain("min-height: 44px");
  });

  test("renders session cards with separated metadata and revoke actions", () => {
    expect(authScript).toContain('className = "session-item-copy"');
    expect(authScript).toContain('className = "session-item-action"');
    expect(authCss).toContain(".session-item-action .danger");
    expect(authCss).toContain(".session-item-copy");
    expect(authCss).toContain("overflow-wrap: anywhere");
  });
});

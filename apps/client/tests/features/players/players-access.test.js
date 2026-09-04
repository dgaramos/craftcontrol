import { jest } from "@jest/globals";
import { createPlayerAccess } from "../../../static/js/features/players/access.js";

function makeDeps(locale = "en", role = "owner") {
  const state = { locale, user: { role } };
  const escapeHtml = (s) => String(s).replace(/</g, "&lt;");
  const t = (key) => key;
  const $ = jest.fn(() => null);
  const api = jest.fn();
  const toast = jest.fn();
  const renderPlayersPanel = jest.fn();
  return { state, escapeHtml, t, $, api, toast, renderPlayersPanel };
}

function getAccess(deps = makeDeps()) {
  return createPlayerAccess(deps);
}

// ── panelAccessHeroRow ──────────────────────────────────────────────────────

describe("panelAccessHeroRow — non-owner viewer", () => {
  test("shows read-only badge and no-access label for non-owner with no account", () => {
    const deps = makeDeps("en", "operator");
    const { panelAccessHeroRow } = createPlayerAccess(deps);
    const html = panelAccessHeroRow({ name: "P" }, null);
    expect(html).toContain("read-only-badge");
    expect(html).toContain("No access");
  });

  test("shows pt no-access label", () => {
    const deps = makeDeps("pt", "viewer");
    const { panelAccessHeroRow } = createPlayerAccess(deps);
    const html = panelAccessHeroRow({ name: "P" }, null);
    expect(html).toContain("Sem acesso");
  });

  test("shows active account role to non-owners", () => {
    const deps = makeDeps("en", "viewer");
    const { panelAccessHeroRow } = createPlayerAccess(deps);
    const html = panelAccessHeroRow({ name: "P" }, { status: "active", role: "operator", active_sessions: 0 });
    expect(html).toContain("operator");
  });

  test("shows session count in hero row", () => {
    const deps = makeDeps("en", "viewer");
    const { panelAccessHeroRow } = createPlayerAccess(deps);
    const html = panelAccessHeroRow({ name: "P" }, { status: "active", role: "viewer", active_sessions: 3 });
    expect(html).toContain("3 active sessions");
  });
});

describe("panelAccessHeroRow — owner", () => {
  test("shows role select for owner", () => {
    const deps = makeDeps("en", "owner");
    const { panelAccessHeroRow } = createPlayerAccess(deps);
    const html = panelAccessHeroRow({ name: "Hero" }, null);
    expect(html).toContain('id="detail-access-role"');
  });

  test("pre-selects viewer role", () => {
    const account = { status: "active", role: "viewer", active_sessions: 1 };
    const { panelAccessHeroRow } = getAccess();
    const html = panelAccessHeroRow({ name: "Hero" }, account);
    expect(html).toContain('value="viewer" selected');
    expect(html).toContain("1 active session");
  });

  test("pre-selects operator role", () => {
    const account = { status: "active", role: "operator", active_sessions: 0 };
    const { panelAccessHeroRow } = getAccess();
    const html = panelAccessHeroRow({ name: "Hero" }, account);
    expect(html).toContain('value="operator" selected');
  });

  test("shows correct role in select", () => {
    const account = { status: "active", role: "owner", active_sessions: 2 };
    const { panelAccessHeroRow } = getAccess();
    const html = panelAccessHeroRow({ name: "Hero" }, account);
    expect(html).toContain('value="owner" selected');
    expect(html).toContain("2 active sessions");
  });
});

// ── panelAccessDetailMarkup ─────────────────────────────────────────────────

describe("panelAccessDetailMarkup — non-owner", () => {
  test("returns empty string for non-owner", () => {
    const deps = makeDeps("en", "operator");
    const { panelAccessDetailMarkup } = createPlayerAccess(deps);
    expect(panelAccessDetailMarkup({ name: "P" }, null, "Panel Access")).toBe("");
  });

  test("returns empty string for viewer", () => {
    const deps = makeDeps("pt", "viewer");
    const { panelAccessDetailMarkup } = createPlayerAccess(deps);
    expect(panelAccessDetailMarkup({ name: "P" }, null, "Acesso")).toBe("");
  });
});

describe("panelAccessDetailMarkup — owner, no account", () => {
  test("shows Generate access button", () => {
    const html = getAccess().panelAccessDetailMarkup({ name: "Hero" }, null, "Panel Access");
    expect(html).toContain("Generate access");
    expect(html).not.toContain("Suspend access");
  });

  test("shows pt generate access", () => {
    const deps = makeDeps("pt", "owner");
    const { panelAccessDetailMarkup } = createPlayerAccess(deps);
    const html = panelAccessDetailMarkup({ name: "Hero" }, null, "Título");
    expect(html).toContain("Gerar acesso");
  });
});

describe("panelAccessDetailMarkup — owner, active account", () => {
  test("shows Generate recovery and Suspend access buttons", () => {
    const account = { status: "active", role: "viewer", active_sessions: 1 };
    const html = getAccess().panelAccessDetailMarkup({ name: "Hero" }, account, "Panel Access");
    expect(html).toContain("Generate recovery");
    expect(html).toContain("Suspend access");
  });

  test("compact card contains invite and access-code elements", () => {
    const account = { status: "active", role: "operator", active_sessions: 0 };
    const html = getAccess().panelAccessDetailMarkup({ name: "Hero" }, account, "Panel Access");
    expect(html).toContain('id="detail-access-invite"');
    expect(html).toContain('id="detail-access-code"');
  });

  test("compact card uses player-access-compact class", () => {
    const html = getAccess().panelAccessDetailMarkup({ name: "Hero" }, null, "Panel Access");
    expect(html).toContain("player-access-compact");
  });
});

// ── bindPlayerAccess ────────────────────────────────────────────────────────

describe("createPlayerAccess — bindPlayerAccess", () => {
  test("returns without binding when invite element is absent", () => {
    const deps = makeDeps();
    deps.$ = jest.fn(() => null);
    const { bindPlayerAccess } = createPlayerAccess(deps);
    expect(() => bindPlayerAccess({ name: "P" }, null)).not.toThrow();
  });

  test("invites, copies tokens, and reports invitation errors", async () => {
    const savedNavigator = global.navigator;
    const deps = makeDeps("pt");
    const invite = { onclick: null };
    const role = { value: "operator" };
    const code = { textContent: "" };
    const copy = { onclick: null };
    const output = { hidden: true, querySelector: (selector) => selector === "code" ? code : copy };
    deps.$ = jest.fn((selector) => ({ "#detail-access-invite": invite, "#detail-access-role": role, "#detail-access-code": output, "#detail-access-suspend": null })[selector]);
    deps.api.mockResolvedValueOnce({ token: "once-token" }).mockRejectedValueOnce(new Error("invite failed"));
    global.navigator = { clipboard: { writeText: jest.fn().mockResolvedValue() } };
    try {
      const { bindPlayerAccess } = createPlayerAccess(deps);
      bindPlayerAccess({ name: "Player One" }, null);
      await invite.onclick();
      expect(code.textContent).toBe("once-token");
      expect(output.hidden).toBe(false);
      await copy.onclick();
      expect(deps.toast).toHaveBeenCalledWith("Código copiado");
      await invite.onclick();
      expect(deps.toast).toHaveBeenCalledWith("invite failed", true);
    } finally {
      global.navigator = savedNavigator;
    }
  });

  test("reports clipboard rejection without an unhandled promise", async () => {
    const savedNavigator = global.navigator;
    const deps = makeDeps();
    const invite = { onclick: null };
    const role = { value: "viewer" };
    const code = { textContent: "" };
    const copy = { onclick: null };
    const output = { hidden: true, querySelector: (selector) => selector === "code" ? code : copy };
    deps.$ = jest.fn((selector) => ({ "#detail-access-invite": invite, "#detail-access-role": role, "#detail-access-code": output, "#detail-access-suspend": null })[selector]);
    deps.api.mockResolvedValue({ token: "once-token" });
    global.navigator = { clipboard: { writeText: jest.fn().mockRejectedValue(new Error("denied")) } };
    try {
      createPlayerAccess(deps).bindPlayerAccess({ name: "Player One" }, null);
      await invite.onclick();
      await copy.onclick();
      expect(deps.toast).toHaveBeenCalledWith("Could not copy code", true);
    } finally {
      global.navigator = savedNavigator;
    }
  });

  test("suspends confirmed access and handles cancellation and errors", async () => {
    const savedConfirm = global.confirm;
    const deps = makeDeps();
    const invite = { onclick: null };
    const suspend = { onclick: null };
    deps.$ = jest.fn((selector) => ({ "#detail-access-invite": invite, "#detail-access-suspend": suspend })[selector] || null);
    deps.api.mockResolvedValueOnce({}).mockRejectedValueOnce(new Error("suspend failed"));
    global.confirm = jest.fn().mockReturnValueOnce(false).mockReturnValue(true);
    try {
      const { bindPlayerAccess } = createPlayerAccess(deps);
      bindPlayerAccess({ name: "A/B" }, { status: "active" });
      await suspend.onclick();
      expect(deps.api).not.toHaveBeenCalled();
      await suspend.onclick();
      expect(deps.renderPlayersPanel).toHaveBeenCalled();
      await suspend.onclick();
      expect(deps.toast).toHaveBeenCalledWith("suspend failed", true);
    } finally {
      global.confirm = savedConfirm;
    }
  });
});

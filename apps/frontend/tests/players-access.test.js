import { jest } from "@jest/globals";
import { createPlayerAccess } from "../static/js/features/players/access.js";

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

function getMarkup(deps = makeDeps()) {
  const { panelAccessDetailMarkup } = createPlayerAccess(deps);
  return panelAccessDetailMarkup;
}

describe("panelAccessDetailMarkup — non-owner viewer", () => {
  test("shows read-only message for non-owner", () => {
    const deps = makeDeps("en", "operator");
    const { panelAccessDetailMarkup } = createPlayerAccess(deps);
    const html = panelAccessDetailMarkup({ name: "P" }, null, "Panel Access");
    expect(html).toContain("Only owners can manage panel access.");
    expect(html).toContain("No access");
  });

  test("shows pt read-only message", () => {
    const deps = makeDeps("pt", "viewer");
    const { panelAccessDetailMarkup } = createPlayerAccess(deps);
    const html = panelAccessDetailMarkup({ name: "P" }, null, "Acesso");
    expect(html).toContain("Somente owners podem gerenciar acesso ao painel.");
  });

  test("shows an active account role to non-owners", () => {
    const deps = makeDeps("en", "viewer");
    expect(createPlayerAccess(deps).panelAccessDetailMarkup({ name: "P" }, { status: "active", role: "operator" }, "Access")).toContain("operator");
  });
});

describe("panelAccessDetailMarkup — owner, no account", () => {
  test("shows Generate access button", () => {
    const html = getMarkup()({ name: "Hero" }, null, "Panel Access");
    expect(html).toContain("Generate access");
    expect(html).toContain("No active access");
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
    const html = getMarkup()({ name: "Hero" }, account, "Panel Access");
    expect(html).toContain("Generate recovery");
    expect(html).toContain("Suspend access");
    expect(html).toContain("viewer");
    expect(html).toContain("1 active sessions");
  });

  test("operator role appears in select", () => {
    const account = { status: "active", role: "operator", active_sessions: 0 };
    const html = getMarkup()({ name: "Hero" }, account, "Panel Access");
    expect(html).toContain('value="operator"');
  });

  test("shows correct role in status", () => {
    const account = { status: "active", role: "owner", active_sessions: 2 };
    const html = getMarkup()({ name: "Hero" }, account, "Panel Access");
    expect(html).toContain("owner");
  });
});

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

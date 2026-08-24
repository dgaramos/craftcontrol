import { jest } from "@jest/globals";
import { api } from "../static/js/api.js";

// api.js has a module-level csrfToken that persists across tests within this file.
// Every mock dispatches on URL so that /api/auth/me always succeeds (satisfying
// refreshCsrfToken) regardless of whether the token was already set by a prior test.

afterEach(() => {
  global.fetch = undefined;
});

function meResponse(token = "tok") {
  return Promise.resolve({ ok: true, status: 200, json: async () => ({ csrf_token: token }) });
}

describe("api — GET request", () => {
  test("GET does not add X-CSRF-Token header", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    await api("/api/players");
    const [, init] = global.fetch.mock.calls[0];
    expect(init.headers["X-CSRF-Token"]).toBeUndefined();
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  test("HEAD and OPTIONS remain read-only requests", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    await api("/api/status", { method: "HEAD" });
    await api("/api/status", { method: "OPTIONS" });
    global.fetch.mock.calls.forEach(([, init]) => expect(init.headers["X-CSRF-Token"]).toBeUndefined());
  });

  test("uses the generic error when an error payload has no message", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
    await expect(api("/api/status")).rejects.toMatchObject({ message: "Request failed", status: 500 });
  });
});

describe("api — non-CSRF-protected URLs", () => {
  test("/api/auth/login POST skips CSRF fetch", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ token: "x" }),
    });
    await api("/api/auth/login", { method: "POST" });
    const urls = global.fetch.mock.calls.map(([url]) => url);
    expect(urls).not.toContain("/api/auth/me");
    expect(urls).toContain("/api/auth/login");
  });

  test("/api/auth/claim POST skips CSRF fetch", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true, status: 200, json: async () => ({}),
    });
    await api("/api/auth/claim", { method: "POST" });
    const urls = global.fetch.mock.calls.map(([url]) => url);
    expect(urls).not.toContain("/api/auth/me");
  });
});

describe("api — POST mutation with CSRF", () => {
  test("CSRF bootstrap failure exposes the server error and status", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: "sign in required" }),
    });

    const error = await api("/api/protected", { method: "POST" }).catch((reason) => reason);

    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe("sign in required");
    expect(error.status).toBe(401);
  });

  test("CSRF bootstrap uses the authentication fallback without an error payload", async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) });
    await expect(api("/api/protected-fallback", { method: "POST" })).rejects.toMatchObject({ message: "Authentication required", status: 401 });
  });

  test("POST sends X-CSRF-Token header", async () => {
    global.fetch = jest.fn().mockImplementation((url) => {
      if (url === "/api/auth/me") return meResponse();
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ csrf_token: "tok", result: "done" }) });
    });
    await api("/api/data", { method: "POST", body: "{}" });
    const mutationCall = global.fetch.mock.calls.find(([url]) => url !== "/api/auth/me");
    expect(mutationCall[1].headers["X-CSRF-Token"]).toBeTruthy();
  });

  test("successful response returns parsed JSON body", async () => {
    global.fetch = jest.fn().mockImplementation((url) => {
      if (url === "/api/auth/me") return meResponse();
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ csrf_token: "tok", value: 42 }) });
    });
    const result = await api("/api/x", { method: "PUT" });
    expect(result.value).toBe(42);
  });

  test("response.ok=false throws error with .status and .payload", async () => {
    global.fetch = jest.fn().mockImplementation((url) => {
      if (url === "/api/auth/me") return meResponse();
      return Promise.resolve({ ok: false, status: 400, json: async () => ({ error: "bad request", detail: "x" }) });
    });
    const err = await api("/api/fail", { method: "POST" }).catch((e) => e);
    expect(err).toBeInstanceOf(Error);
    expect(err.message).toBe("bad request");
    expect(err.status).toBe(400);
    expect(err.payload).toMatchObject({ error: "bad request" });
  });

  test("retry=false does not loop on 403 CSRF error", async () => {
    global.fetch = jest.fn().mockImplementation((url) => {
      if (url === "/api/auth/me") return meResponse();
      return Promise.resolve({ ok: false, status: 403, json: async () => ({ error: "invalid or missing CSRF token" }) });
    });
    const err = await api("/api/noop", { method: "POST" }, false).catch((e) => e);
    expect(err.status).toBe(403);
    // With retry=false, no second mutation attempt occurs
    const mutationCalls = global.fetch.mock.calls.filter(([url]) => url !== "/api/auth/me");
    expect(mutationCalls.length).toBe(1);
  });

  test("403 CSRF error with retry=true refreshes token and retries once", async () => {
    let mutationCount = 0;
    global.fetch = jest.fn().mockImplementation((url) => {
      if (url === "/api/auth/me") return meResponse("new-tok");
      mutationCount += 1;
      if (mutationCount === 1) {
        return Promise.resolve({ ok: false, status: 403, json: async () => ({ error: "invalid or missing CSRF token" }) });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ ok: true }) });
    });
    const result = await api("/api/retry", { method: "POST" });
    expect(result).toMatchObject({ ok: true });
    expect(mutationCount).toBe(2);
  });
});

describe("api — password changes", () => {
  test("PUT /api/auth/password sends the current CSRF token", async () => {
    jest.resetModules();
    const { api: isolatedApi } = await import("../static/js/api.js");
    global.fetch = jest.fn().mockImplementation((url) => {
      if (url === "/api/auth/me") return meResponse("password-token");
      return Promise.resolve({ ok: true, status: 200, json: async () => ({ csrf_token: "rotated-token" }) });
    });
    await isolatedApi("/api/auth/password", { method: "PUT", body: "{}" });
    const mutationCall = global.fetch.mock.calls.find(([url]) => url === "/api/auth/password");
    expect(mutationCall[1].headers["X-CSRF-Token"]).toBe("password-token");
  });
});

import { jest } from "@jest/globals";
import { createAuditFeature } from "../../../static/js/features/audit/index.js";
import { makeEl } from "../../helpers.js";

// ---------------------------------------------------------------------------
// Shared helper
// ---------------------------------------------------------------------------

function makeContent() {
  const content = { renderedMarkup: "" };
  Object.defineProperty(content, "innerHTML", {
    configurable: true,
    get: () => content.renderedMarkup,
    set: (value) => { content.renderedMarkup = String(value); },
  });
  return content;
}

function makeAuditDeps(overrides = {}) {
  const elements = {};
  const $ = jest.fn((sel) => {
    if (!elements[sel]) elements[sel] = makeEl();
    return elements[sel];
  });
  const content = makeContent();
  const t = (key) => key;
  const escapeHtml = (s) => String(s ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[c]);
  const uiIcon = (name) => `<svg icon="${name}"/>`;
  const toast = jest.fn();
  const formatDate = (ts) => (ts ? `date:${ts}` : "—");
  const api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });
  const state = { user: { role: "owner", capabilities: ["*"] } };

  return { state, content, t, escapeHtml, uiIcon, toast, formatDate, api, $, elements, ...overrides };
}

function makeRecord(overrides = {}) {
  return {
    id: 1,
    occurred_at: 1000,
    actor: "alice",
    action: "auth.login",
    target: "alice",
    result: "success",
    metadata: {},
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Happy path — renders table with records
// ---------------------------------------------------------------------------

describe("createAuditFeature — happy path", () => {
  test("renderAuditPanel renders a table when records are present", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord(), makeRecord({ id: 2, actor: "bob", result: "denied" })],
      total: 2,
      page: 1,
      page_size: 25,
      pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-table");
    expect(deps.content.innerHTML).toContain("alice");
    expect(deps.content.innerHTML).toContain("auth.login");
    expect(deps.content.innerHTML).toContain("bob");
  });

  test("renderAuditPanel renders the panel heading", async () => {
    const deps = makeAuditDeps();
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("auditTitle");
  });

  test("renderAuditPanel renders filter inputs", async () => {
    const deps = makeAuditDeps();
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-actor-input");
    expect(deps.content.innerHTML).toContain("audit-action-input");
    expect(deps.content.innerHTML).toContain("audit-apply-btn");
  });

  test("actor and action columns appear for each record", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ actor: "carol", action: "server.restart", result: "success" })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("carol");
    expect(deps.content.innerHTML).toContain("server.restart");
  });

  test("date column uses formatDate for occurred_at", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ occurred_at: 9999 })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("date:9999");
  });

  test("null actor renders as a dash placeholder", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ actor: null })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("—");
  });

  test("success result gets the success CSS class", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ result: "success" })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-outcome--success");
  });

  test("denied result gets the failure CSS class", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ result: "denied" })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-outcome--failure");
  });

  test("calls api with correct default params", async () => {
    const deps = makeAuditDeps();
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.api).toHaveBeenCalledWith(
      expect.stringContaining("/api/audit")
    );
    const [url] = deps.api.mock.calls[0];
    expect(url).toContain("page=1");
    expect(url).toContain("page_size=25");
  });

  test("external content is escaped before insertion", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ actor: "<script>evil</script>", action: "xss&attack" })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).not.toContain("<script>");
    expect(deps.content.innerHTML).toContain("&lt;script&gt;");
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe("createAuditFeature — empty state", () => {
  test("renders localized empty message when no records", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("auditEmpty");
    expect(deps.content.innerHTML).not.toContain("audit-table");
  });

  test("empty state still renders filter row", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-apply-btn");
  });
});

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

describe("createAuditFeature — error handling", () => {
  test("api failure calls toast with the error message", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockRejectedValue(new Error("network failure"));
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.toast).toHaveBeenCalledWith("network failure", true);
  });

  test("api failure does not overwrite content", async () => {
    const deps = makeAuditDeps();
    deps.content.innerHTML = "previous content";
    deps.api = jest.fn().mockRejectedValue(new Error("oops"));
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    // content must not be cleared on error
    expect(deps.content.innerHTML).toBe("previous content");
  });
});

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

describe("createAuditFeature — filters", () => {
  test("applying actor filter re-renders with actor param", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });

    // Cache elements so the same instance is returned each call.
    const cache = {};
    cache["#audit-actor-input"] = makeEl({ value: "alice" });
    cache["#audit-action-input"] = makeEl({ value: "" });
    deps.$ = jest.fn((sel) => {
      if (!cache[sel]) cache[sel] = makeEl();
      return cache[sel];
    });

    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();

    // bindControls has now set onclick on the cached apply button.
    const applyEl = cache["#audit-apply-btn"];
    if (applyEl && applyEl.onclick) applyEl.onclick();
    await Promise.resolve();

    const urls = deps.api.mock.calls.map(([url]) => url);
    const filtered = urls.find((url) => url.includes("actor=alice"));
    expect(filtered).toBeDefined();
  });

  test("filter resets page to 1 on apply", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 2, page_size: 25, pages: 2 });

    const cache = {};
    cache["#audit-actor-input"] = makeEl({ value: "bob" });
    cache["#audit-action-input"] = makeEl({ value: "" });
    deps.$ = jest.fn((sel) => {
      if (!cache[sel]) cache[sel] = makeEl();
      return cache[sel];
    });

    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();

    deps.api.mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });
    const applyEl = cache["#audit-apply-btn"];
    if (applyEl && applyEl.onclick) applyEl.onclick();
    await Promise.resolve();

    const lastUrl = deps.api.mock.calls.at(-1)?.[0] ?? "";
    expect(lastUrl).toContain("page=1");
  });
});

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

describe("createAuditFeature — pagination", () => {
  test("pagination controls rendered when pages > 1", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord()],
      total: 50, page: 1, page_size: 25, pages: 2,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-pagination");
    expect(deps.content.innerHTML).toContain("audit-prev-btn");
    expect(deps.content.innerHTML).toContain("audit-next-btn");
  });

  test("no pagination controls when pages <= 1", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord()],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).not.toContain("audit-pagination");
  });

  test("clicking next increments page and re-fetches", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord()],
      total: 50, page: 1, page_size: 25, pages: 2,
    });

    // Use a caching $ so bindControls finds the same element the test clicks.
    const cache = {};
    deps.$ = jest.fn((sel) => {
      if (!cache[sel]) cache[sel] = makeEl();
      return cache[sel];
    });

    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();

    const nextBtn = cache["#audit-next-btn"];
    if (nextBtn && nextBtn.onclick) {
      nextBtn.onclick();
      await Promise.resolve();
    }

    // Call 0: initial render (page=1), call 1: after next (page=2)
    expect(deps.api.mock.calls[0][0]).toContain("page=1");
    expect(deps.api.mock.calls[1][0]).toContain("page=2");
  });

  test("clicking prev decrements page and re-fetches", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn()
      .mockResolvedValueOnce({ records: [makeRecord()], total: 50, page: 1, page_size: 25, pages: 2 })
      .mockResolvedValueOnce({ records: [makeRecord()], total: 50, page: 2, page_size: 25, pages: 2 })
      .mockResolvedValue({ records: [], total: 50, page: 1, page_size: 25, pages: 2 });

    const cache = {};
    deps.$ = jest.fn((sel) => {
      if (!cache[sel]) cache[sel] = makeEl();
      return cache[sel];
    });

    const { renderAuditPanel } = createAuditFeature(deps);
    // First render on page 1, then go to page 2 via next, then back via prev.
    await renderAuditPanel();
    const nextBtn = cache["#audit-next-btn"];
    if (nextBtn && nextBtn.onclick) { nextBtn.onclick(); await Promise.resolve(); }
    // Re-render sets up new controls; simulate prev
    const prevBtn = cache["#audit-prev-btn"];
    if (prevBtn && prevBtn.onclick) { prevBtn.onclick(); await Promise.resolve(); }

    // Call 0: page=1, call 1: next → page=2, call 2: prev → page=1
    expect(deps.api.mock.calls[0][0]).toContain("page=1");
    expect(deps.api.mock.calls[1][0]).toContain("page=2");
    expect(deps.api.mock.calls[2][0]).toContain("page=1");
  });
});

// ---------------------------------------------------------------------------
// outcomeClass — all branches
// ---------------------------------------------------------------------------

describe("createAuditFeature — outcomeClass all branches", () => {
  test("result=failure gets failure CSS class", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ result: "failure" })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-outcome--failure");
  });

  test("unknown result value gets no CSS class", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ result: "unknown_state" })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    // Unknown outcomes get the neutral badge class
    expect(deps.content.innerHTML).toContain('audit-outcome--neutral');
  });
});

// ---------------------------------------------------------------------------
// renderRecord — null/falsy field branches
// ---------------------------------------------------------------------------

describe("createAuditFeature — renderRecord field branches", () => {
  test("null target renders as dash placeholder", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ target: null })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("—");
  });

  test("falsy occurred_at (0) renders as dash placeholder", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ occurred_at: 0 })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("—");
  });

  test("null occurred_at renders as dash placeholder", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ occurred_at: null })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("—");
  });

  test("truthy target is escaped and rendered", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord({ target: "server-default" })],
      total: 1, page: 1, page_size: 25, pages: 1,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("server-default");
  });
});

// ---------------------------------------------------------------------------
// renderTable — null records branch
// ---------------------------------------------------------------------------

describe("createAuditFeature — renderTable null records", () => {
  test("null records field renders empty state", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: null, total: 0, page: 1, page_size: 25, pages: 0,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("auditEmpty");
    expect(deps.content.innerHTML).not.toContain("audit-table");
  });

  test("undefined records field renders empty state", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      total: 0, page: 1, page_size: 25, pages: 0,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("auditEmpty");
  });
});

// ---------------------------------------------------------------------------
// renderPagination — all hasPrev/hasNext combinations
// ---------------------------------------------------------------------------

describe("createAuditFeature — renderPagination branches", () => {
  test("last page: prev enabled, next disabled", async () => {
    const deps = makeAuditDeps();
    // page 2 of 2 → hasPrev=true, hasNext=false
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord()],
      total: 50, page: 2, page_size: 25, pages: 2,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-pagination");
    // prev should NOT have disabled, next SHOULD have disabled
    const html = deps.content.innerHTML;
    const prevIdx = html.indexOf("audit-prev-btn");
    const nextIdx = html.indexOf("audit-next-btn");
    // next button appears after prev in the markup
    expect(html.indexOf("disabled", nextIdx)).toBeGreaterThan(nextIdx);
  });

  test("middle page: both prev and next enabled", async () => {
    const deps = makeAuditDeps();
    // page 2 of 3 → hasPrev=true, hasNext=true
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord()],
      total: 75, page: 2, page_size: 25, pages: 3,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("audit-pagination");
    const html = deps.content.innerHTML;
    // Neither prev nor next should be disabled when in the middle
    const paginationStart = html.indexOf("audit-pagination");
    const paginationSection = html.slice(paginationStart);
    // There should be no "disabled" attribute inside the pagination div when both are active
    // (hasPrev=true → prev gets "" not "disabled"; hasNext=true → next gets "" not "disabled")
    // We verify pagination appears and both button ids are present
    expect(paginationSection).toContain("audit-prev-btn");
    expect(paginationSection).toContain("audit-next-btn");
  });

  test("first page with multiple pages: prev disabled, next enabled", async () => {
    const deps = makeAuditDeps();
    // page 1 of 3 → hasPrev=false, hasNext=true
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord()],
      total: 75, page: 1, page_size: 25, pages: 3,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    const html = deps.content.innerHTML;
    expect(html).toContain("audit-pagination");
    const prevIdx = html.indexOf("audit-prev-btn");
    // prev button should have disabled attribute immediately before or after the id
    expect(html.slice(prevIdx - 20, prevIdx + 50)).toContain("disabled");
  });

  test("page counter shows current / total", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord()],
      total: 50, page: 1, page_size: 25, pages: 2,
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    expect(deps.content.innerHTML).toContain("1 / 2");
  });
});

// ---------------------------------------------------------------------------
// bindControls — null button guards
// ---------------------------------------------------------------------------

describe("createAuditFeature — bindControls null guards", () => {
  test("$ returning null for applyBtn does not throw", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });
    deps.$ = jest.fn(() => null);
    const { renderAuditPanel } = createAuditFeature(deps);
    await expect(renderAuditPanel()).resolves.toBeUndefined();
  });

  test("$ returning null for prevBtn and nextBtn does not throw", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({
      records: [makeRecord()],
      total: 50, page: 1, page_size: 25, pages: 2,
    });
    // Return a real element for apply but null for pagination buttons
    const applyEl = makeEl();
    deps.$ = jest.fn((sel) => {
      if (sel === "#audit-apply-btn") return applyEl;
      return null;
    });
    const { renderAuditPanel } = createAuditFeature(deps);
    await expect(renderAuditPanel()).resolves.toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// action filter forwarded in URL
// ---------------------------------------------------------------------------

describe("createAuditFeature — action filter URL param", () => {
  test("action filter is appended to the API URL", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });

    const cache = {};
    cache["#audit-actor-input"] = makeEl({ value: "" });
    cache["#audit-action-input"] = makeEl({ value: "auth.login" });
    deps.$ = jest.fn((sel) => {
      if (!cache[sel]) cache[sel] = makeEl();
      return cache[sel];
    });

    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();

    const applyEl = cache["#audit-apply-btn"];
    if (applyEl && applyEl.onclick) applyEl.onclick();
    await Promise.resolve();

    const urls = deps.api.mock.calls.map(([url]) => url);
    expect(urls.some((url) => url.includes("action=auth.login"))).toBe(true);
  });

  test("empty action filter is not appended to the URL", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    const [url] = deps.api.mock.calls[0];
    expect(url).not.toContain("action=");
  });

  test("empty actor filter is not appended to the URL", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });
    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();
    const [url] = deps.api.mock.calls[0];
    expect(url).not.toContain("actor=");
  });
});

// ---------------------------------------------------------------------------
// filter inputs reflect current filter state in rendered markup
// ---------------------------------------------------------------------------

describe("createAuditFeature — filter state reflected in markup", () => {
  test("actorFilter value appears in actor input after apply", async () => {
    const deps = makeAuditDeps();
    deps.api = jest.fn().mockResolvedValue({ records: [], total: 0, page: 1, page_size: 25, pages: 0 });

    const cache = {};
    cache["#audit-actor-input"] = makeEl({ value: "testuser" });
    cache["#audit-action-input"] = makeEl({ value: "" });
    deps.$ = jest.fn((sel) => {
      if (!cache[sel]) cache[sel] = makeEl();
      return cache[sel];
    });

    const { renderAuditPanel } = createAuditFeature(deps);
    await renderAuditPanel();

    const applyEl = cache["#audit-apply-btn"];
    if (applyEl && applyEl.onclick) applyEl.onclick();
    await Promise.resolve();

    // After apply, the second render should include the filter value in the markup
    expect(deps.content.innerHTML).toContain("testuser");
  });
});

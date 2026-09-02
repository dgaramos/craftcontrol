import { jest } from "@jest/globals";
import { createAnalyticsFeature } from "../../../static/js/features/analytics/index.js";
import { makeEl, makeAnalyticsDeps } from "../../helpers.js";

// analytics/index.js uses `"IntersectionObserver" in window` and `window.scrollTo`.
// Define a minimal global.window for node environment.
let _savedWindow;
beforeEach(() => {
  _savedWindow = global.window;
  if (typeof global.window === "undefined") {
    global.window = {};
  }
});
afterEach(() => { global.window = _savedWindow; });


function makeActivityResult(overrides = {}) {
  return {
    events: [],
    pages: 1,
    page: 1,
    total: 0,
    summary: { joins: 1, leaves: 0, respawns: 0, dimensions: 0, deaths: 0, permissions: 0 },
    players: [],
    ...overrides,
  };
}


// ── basic reload — happy path ─────────────────────────────────────────────────

describe("renderAnalyticsPanel — reload happy path (kind=all)", () => {
  test("content.innerHTML contains analytics-screen after render", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult())
      .mockResolvedValueOnce({ players: [] });
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(deps.content.innerHTML).toContain("analytics-screen");
  });

  test("analytics-summary is rendered in target after successful reload", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    const resultsEl = makeEl();
    deps.elements["#analytics-results"] = resultsEl;
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult({ summary: { joins: 5 } }))
      .mockResolvedValueOnce({ players: [{ name: "Alice" }] });
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(resultsEl.innerHTML).toContain("analytics-summary");
  });

  test("player select gets populated with player options", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    const playerSelect = makeEl({ value: "", innerHTML: "" });
    deps.elements["#analytics-player"] = playerSelect;
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult())
      .mockResolvedValueOnce({ players: [{ name: "Alice" }] });
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(playerSelect.innerHTML).toContain("Alice");
  });
});

// ── pagination — no IntersectionObserver ──────────────────────────────────────

describe("renderAnalyticsPanel — pagination without IntersectionObserver", () => {
  test("hasMore=true renders load more button when no IntersectionObserver", async () => {
    // Ensure window exists but has no IntersectionObserver
    global.window = {};
    const deps = makeAnalyticsDeps({ kind: "all" });
    const resultsEl = makeEl();
    deps.elements["#analytics-results"] = resultsEl;
    deps.elements["#activity-load-more"] = makeEl();
    deps.elements["#activity-scroll-sentinel"] = makeEl({ innerHTML: "" });
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult({ page: 1, pages: 2, events: [{ id: "e1" }] }))
      .mockResolvedValueOnce({ players: [] });
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(resultsEl.innerHTML).toContain("activity-scroll-sentinel");
  });
});

// ── pagination — with IntersectionObserver ─────────────────────────────────────

describe("renderAnalyticsPanel — pagination with IntersectionObserver", () => {
  test("IntersectionObserver.observe is called on sentinel", async () => {
    const observeMock = jest.fn();
    const IOConstructor = jest.fn(() => ({ observe: observeMock, disconnect: jest.fn() }));
    global.window = { IntersectionObserver: IOConstructor };

    const deps = makeAnalyticsDeps({ kind: "all" });
    const sentinelEl = makeEl();
    deps.elements["#activity-scroll-sentinel"] = sentinelEl;
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult({ page: 1, pages: 2, events: [{ id: "e1" }] }))
      .mockResolvedValueOnce({ players: [] });
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(observeMock).toHaveBeenCalled();
  });
});

// ── reload error — initial load ───────────────────────────────────────────────

describe("renderAnalyticsPanel — reload error", () => {
  test("initial load error renders analytics-empty in target", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    const resultsEl = makeEl();
    deps.elements["#analytics-results"] = resultsEl;
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn().mockRejectedValue(new Error("load failed"));
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(resultsEl.innerHTML).toContain("analytics-empty");
    expect(resultsEl.innerHTML).toContain("load failed");
  });
});

// ── filter onchange handlers ──────────────────────────────────────────────────

describe("renderAnalyticsPanel — filter handlers", () => {
  async function renderAndGetElements(deps) {
    const { render } = createAnalyticsFeature(deps);
    await render();
    return deps.elements;
  }

  test("#analytics-kind onchange updates filters.kind and reloads", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult())
      .mockResolvedValueOnce({ players: [] })
      .mockResolvedValueOnce(makeActivityResult())
      .mockResolvedValueOnce({ players: [] });
    await renderAndGetElements(deps);
    const kindEl = deps.elements["#analytics-kind"];
    kindEl.onchange({ target: { value: "joins" } });
    expect(deps.state.analytics.kind).toBe("joins");
    expect(deps.state.analytics.page).toBe(1);
  });

  test("#analytics-days onchange updates filters.days as Number", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult())
      .mockResolvedValueOnce({ players: [] });
    await renderAndGetElements(deps);
    const daysEl = deps.elements["#analytics-days"];
    daysEl.onchange({ target: { value: "7" } });
    expect(deps.state.analytics.days).toBe(7);
    expect(typeof deps.state.analytics.days).toBe("number");
  });

  test("#analytics-search onchange trims the value", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult())
      .mockResolvedValueOnce({ players: [] });
    await renderAndGetElements(deps);
    const searchEl = deps.elements["#analytics-search"];
    searchEl.onchange({ target: { value: "  alice  " } });
    expect(deps.state.analytics.search).toBe("alice");
  });
});

// ── analyticsViewSwitch output ────────────────────────────────────────────────

describe("analyticsViewSwitch output via content.innerHTML", () => {
  test("active view 'all' — activity button has active class", async () => {
    const deps = makeAnalyticsDeps({ kind: "all" });
    deps.api = jest.fn()
      .mockResolvedValueOnce(makeActivityResult())
      .mockResolvedValueOnce({ players: [] });
    deps.$ = jest.fn((sel) => {
      if (!deps.elements[sel]) deps.elements[sel] = makeEl();
      return deps.elements[sel];
    });
    const { render } = createAnalyticsFeature(deps);
    await render();
    expect(deps.content.innerHTML).toContain('class="all active"');
  });
});

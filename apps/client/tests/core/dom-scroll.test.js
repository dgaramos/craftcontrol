import { jest } from "@jest/globals";
import { resetPanelScroll, scrollRoot } from "../../static/js/core/dom.js";

function fakeDoc(main) {
  return { querySelector: (sel) => (sel === "main" && main ? main : null) };
}

describe("resetPanelScroll", () => {
  test("scrolls <main>, which is what actually scrolls in the shell", () => {
    // The regression: the page never scrolls, so window.scrollTo did nothing
    // and a screen opened after scrolling appeared already scrolled down.
    const main = { scrollTo: jest.fn() };
    const view = { scrollTo: jest.fn() };
    resetPanelScroll("auto", fakeDoc(main), view);
    expect(main.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: "auto" });
  });

  test("resets the window too, for layouts where the document scrolls", () => {
    const view = { scrollTo: jest.fn() };
    resetPanelScroll("smooth", fakeDoc({ scrollTo: jest.fn() }), view);
    expect(view.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: "smooth" });
  });

  test("passes the requested behaviour through", () => {
    const main = { scrollTo: jest.fn() };
    resetPanelScroll("smooth", fakeDoc(main), { scrollTo: jest.fn() });
    expect(main.scrollTo).toHaveBeenCalledWith(expect.objectContaining({ behavior: "smooth" }));
  });

  test("falls back to scrollTop where scrollTo is unavailable", () => {
    const main = { scrollTop: 900 };
    resetPanelScroll("auto", fakeDoc(main), { scrollTo: jest.fn() });
    expect(main.scrollTop).toBe(0);
  });

  test("survives a missing main and a missing window", () => {
    expect(() => resetPanelScroll("auto", fakeDoc(null), null)).not.toThrow();
  });
});

describe("scrollRoot", () => {
  test("returns the panel scroll container", () => {
    const main = {};
    expect(scrollRoot(fakeDoc(main))).toBe(main);
  });

  test("returns null when there is no document to query", () => {
    expect(scrollRoot(fakeDoc(null))).toBeNull();
  });
});

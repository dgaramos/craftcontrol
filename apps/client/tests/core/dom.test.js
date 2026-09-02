import { escapeHtml } from "../../static/js/core/dom.js";

describe("escapeHtml", () => {
  test("escapes ampersand", () => expect(escapeHtml("a&b")).toBe("a&amp;b"));
  test("escapes less-than", () => expect(escapeHtml("<b>")).toBe("&lt;b&gt;"));
  test("escapes greater-than", () => expect(escapeHtml("a>b")).toBe("a&gt;b"));
  test("escapes single quote", () => expect(escapeHtml("it's")).toBe("it&#39;s"));
  test("escapes double quote", () => expect(escapeHtml('"hi"')).toBe("&quot;hi&quot;"));
  test("escapes multiple special chars", () =>
    expect(escapeHtml('<script>alert("xss")</script>')).toBe(
      "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;"
    )
  );
  test("returns empty string for null", () => expect(escapeHtml(null)).toBe(""));
  test("returns empty string for undefined", () => expect(escapeHtml(undefined)).toBe(""));
  test("returns empty string for empty string", () => expect(escapeHtml("")).toBe(""));
  test("does not modify safe strings", () => expect(escapeHtml("hello world")).toBe("hello world"));
  test("coerces numbers to string", () => expect(escapeHtml(42)).toBe("42"));
});

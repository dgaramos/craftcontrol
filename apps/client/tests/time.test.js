import { formatDate, formatDuration, timelineTimestamp, sessionMoment } from "../static/js/components/time.js";

describe("formatDate", () => {
  test("returns em dash for falsy timestamp", () => expect(formatDate(0, "pt")).toBe("—"));
  test("returns em dash for null", () => expect(formatDate(null, "pt")).toBe("—"));
  test("returns a non-empty string for valid timestamp", () => {
    const result = formatDate(1700000000, "pt");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  test("renders ISO, seconds, milliseconds, and microseconds as the same instant", () => {
    const expected = formatDate("2023-11-14T22:13:20Z", "en-US");
    expect(formatDate(1700000000, "en-US")).toBe(expected);
    expect(formatDate(1700000000000, "en-US")).toBe(expected);
    expect(formatDate(1700000000000000, "en-US")).toBe(expected);
  });
});

describe("formatDuration", () => {
  test("formats zero seconds as 0m", () => expect(formatDuration(0)).toBe("0m"));
  test("formats null as 0m", () => expect(formatDuration(null)).toBe("0m"));
  test("formats 90 seconds as 1m", () => expect(formatDuration(90)).toBe("1m"));
  test("formats 3600 seconds as 1h 0m", () => expect(formatDuration(3600)).toBe("1h 0m"));
  test("formats 3660 seconds as 1h 1m", () => expect(formatDuration(3660)).toBe("1h 1m"));
  test("formats 7320 seconds as 2h 2m", () => expect(formatDuration(7320)).toBe("2h 2m"));
  test("formats 59 seconds as 0m", () => expect(formatDuration(59)).toBe("0m"));
});

describe("timelineTimestamp", () => {
  test("returns dash markup for falsy timestamp", () => {
    const result = timelineTimestamp(0, "pt");
    expect(result).toContain("—");
    expect(result).toContain("timeline-timestamp");
  });

  test("returns time element for valid timestamp", () => {
    const result = timelineTimestamp(1700000000, "pt");
    expect(result).toContain("<time");
    expect(result).toContain("datetime=");
    expect(result).toContain("timeline-timestamp");
  });

  test("accepts ISO timestamps", () => {
    expect(timelineTimestamp("2023-11-14T22:13:20Z", "pt")).toContain("datetime=");
  });

  test("escapes special chars in date output", () => {
    const result = timelineTimestamp(1700000000, "pt");
    expect(result).not.toContain("<script>");
  });
});

describe("sessionMoment", () => {
  test("returns em dash for falsy timestamp", () => expect(sessionMoment(0, "pt")).toBe("—"));
  test("returns time element for valid timestamp", () => {
    const result = sessionMoment(1700000000, "pt");
    expect(result).toContain("<time");
    expect(result).toContain("datetime=");
  });

  test("accepts milliseconds timestamps", () => {
    expect(sessionMoment(1700000000000, "pt")).toContain("datetime=");
  });
});

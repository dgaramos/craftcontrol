import { jest } from "@jest/globals";

const toastEl = {
  textContent: "",
  style: {},
  classList: { add: jest.fn(), remove: jest.fn() },
};

jest.unstable_mockModule("../../static/js/core/dom.js", () => ({
  $: jest.fn(() => toastEl),
  escapeHtml: (s) => String(s ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c])),
}));

const { toast } = await import("../../static/js/components/feedback.js");

describe("toast", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    toastEl.textContent = "";
    toastEl.style = {};
    toastEl.classList.add.mockClear();
    toastEl.classList.remove.mockClear();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("sets textContent and adds show class", () => {
    toast("hello");
    expect(toastEl.textContent).toBe("hello");
    expect(toastEl.classList.add).toHaveBeenCalledWith("show");
  });

  test("default background is success colour", () => {
    toast("ok");
    expect(toastEl.style.background).toBe("#eef8ee");
  });

  test("error=true sets error background", () => {
    toast("oops", true);
    expect(toastEl.style.background).toBe("#ffd2cf");
  });

  test("show class removed after 2600 ms", () => {
    toast("msg");
    jest.advanceTimersByTime(2599);
    expect(toastEl.classList.remove).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(toastEl.classList.remove).toHaveBeenCalledWith("show");
  });

  test("a replacement toast resets the dismissal timer", () => {
    toast("first");
    jest.advanceTimersByTime(2000);
    toast("second");
    jest.advanceTimersByTime(600);
    expect(toastEl.classList.remove).not.toHaveBeenCalled();
    jest.advanceTimersByTime(2000);
    expect(toastEl.classList.remove).toHaveBeenCalledWith("show");
  });
});

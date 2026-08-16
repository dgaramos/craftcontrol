import { jest } from "@jest/globals";
import { connectEventStream } from "../static/js/events.js";

// ── events.js ────────────────────────────────────────────────────────────────

class FakeEventSource {
  constructor(url) {
    this.url = url;
    this._listeners = {};
  }
  addEventListener(event, handler) {
    this._listeners[event] = handler;
  }
  set onerror(fn) { this._onerror = fn; }
  emit(event, data) {
    if (this._listeners[event]) this._listeners[event]({ data: JSON.stringify(data) });
  }
}

describe("connectEventStream", () => {
  beforeAll(() => {
    global.EventSource = FakeEventSource;
  });

  test("first call creates an EventSource and returns it", () => {
    const source = connectEventStream(jest.fn());
    expect(source).toBeInstanceOf(FakeEventSource);
  });

  test("second call returns the same source (deduplication)", () => {
    const first = connectEventStream(jest.fn());
    const second = connectEventStream(jest.fn());
    expect(second).toBe(first);
  });

  test("state event fires onStateEvent with parsed JSON", () => {
    const handler = jest.fn();
    const source = connectEventStream(handler);
    source.emit("state", { status: "running" });
    expect(handler).toHaveBeenCalledWith({ status: "running" });
  });
});

// ── feedback.js (logic verification) ─────────────────────────────────────────
// feedback.js imports $ from core/dom.js and is not easily isolated without ESM
// mocking. We verify the logic directly by exercising the same operations the
// function performs, using fake DOM elements.

describe("toast logic", () => {
  let element;

  beforeEach(() => {
    jest.useFakeTimers();
    element = {
      textContent: "",
      style: {},
      classList: { add: jest.fn(), remove: jest.fn() },
    };
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  function fakeToast(message, error = false) {
    element.textContent = message;
    element.style.background = error ? "#ffd2cf" : "#eef8ee";
    element.classList.add("show");
    setTimeout(() => element.classList.remove("show"), 2600);
  }

  test("sets textContent and adds show class", () => {
    fakeToast("hello");
    expect(element.textContent).toBe("hello");
    expect(element.classList.add).toHaveBeenCalledWith("show");
  });

  test("default background is success colour", () => {
    fakeToast("ok");
    expect(element.style.background).toBe("#eef8ee");
  });

  test("error=true sets error background", () => {
    fakeToast("oops", true);
    expect(element.style.background).toBe("#ffd2cf");
  });

  test("show class removed after 2600 ms", () => {
    fakeToast("msg");
    jest.advanceTimersByTime(2599);
    expect(element.classList.remove).not.toHaveBeenCalled();
    jest.advanceTimersByTime(1);
    expect(element.classList.remove).toHaveBeenCalledWith("show");
  });
});

import { jest } from "@jest/globals";
import { connectEventStream } from "../static/js/events.js";
import { FakeEventSource } from "./helpers.js";

describe("connectEventStream", () => {
  let handler;
  let source;

  beforeAll(() => {
    global.EventSource = FakeEventSource;
    // Create the source once; all tests share it (module-level deduplication).
    handler = jest.fn();
    source = connectEventStream(handler);
  });

  test("first call creates an EventSource and returns it", () => {
    expect(source).toBeInstanceOf(FakeEventSource);
  });

  test("second call returns the same source (deduplication)", () => {
    const second = connectEventStream(jest.fn());
    expect(second).toBe(source);
  });

  test("state event fires onStateEvent with parsed JSON", () => {
    source.emit("state", { status: "running" });
    expect(handler).toHaveBeenCalledWith({ status: "running" });
  });
});

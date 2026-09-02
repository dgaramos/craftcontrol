import { jest } from "@jest/globals";

export function suppressConsoleWarn() {
    return jest.spyOn(console, "warn").mockImplementation(() => {});
}

export function suppressConsoleError() {
    return jest.spyOn(console, "error").mockImplementation(() => {});
}

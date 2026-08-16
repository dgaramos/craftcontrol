import { jest } from "@jest/globals";

export function makeEl(extra = {}) {
  return {
    innerHTML: "",
    textContent: "",
    hidden: false,
    value: "",
    checked: false,
    open: false,
    onchange: null,
    onclick: null,
    oninput: null,
    className: "",
    dataset: {},
    close: jest.fn(),
    showModal: jest.fn(),
    addEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
    querySelector: jest.fn(() => null),
    querySelectorAll: jest.fn(() => []),
    closest: jest.fn(() => null),
    classList: { add: jest.fn(), remove: jest.fn(), toggle: jest.fn() },
    ...extra,
  };
}

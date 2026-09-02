import { jest } from "@jest/globals";
import { renderMarkup, renderTemplate } from "../../static/js/core/render.js";

describe("render helpers", () => {
  test("rejects targets without DOM replacement support", () => {
    expect(() => renderMarkup({}, "<p>ignored</p>")).toThrow("Target does not support DOM replacement");
  });

  test("replaces children with a contextual fragment in the browser", () => {
    const fragment = { nodeName: "#document-fragment" };
    const target = { replaceChildren: jest.fn() };
    const createContextualFragment = jest.fn(() => fragment);
    const previousDocument = globalThis.document;
    globalThis.document = { createRange: () => ({ createContextualFragment }) };

    try {
      renderMarkup(target, "<p>safe markup</p>");
      expect(createContextualFragment).toHaveBeenCalledWith("<p>safe markup</p>");
      expect(target.replaceChildren).toHaveBeenCalledWith(fragment);
    } finally {
      globalThis.document = previousDocument;
    }
  });

  test("clones a static template and runs setup", () => {
    const clone = { firstElementChild: { tagName: "ARTICLE" } };
    const template = { content: { cloneNode: jest.fn(() => clone) } };
    const target = { replaceChildren: jest.fn(), firstElementChild: clone.firstElementChild };
    const setup = jest.fn();
    const previousDocument = globalThis.document;
    globalThis.document = { querySelector: jest.fn(() => template) };

    try {
      expect(renderTemplate(target, "#card-template", setup)).toBe(clone.firstElementChild);
      expect(template.content.cloneNode).toHaveBeenCalledWith(true);
      expect(setup).toHaveBeenCalledWith(clone);
      expect(target.replaceChildren).toHaveBeenCalledWith(clone);
    } finally {
      globalThis.document = previousDocument;
    }
  });

  test("reports a missing static template", () => {
    const previousDocument = globalThis.document;
    globalThis.document = { querySelector: () => null };
    try {
      expect(() => renderTemplate({ replaceChildren() {} }, "#missing-template")).toThrow("Missing template");
    } finally {
      globalThis.document = previousDocument;
    }
  });
});

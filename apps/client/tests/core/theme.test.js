import { jest } from "@jest/globals";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createThemePreference } from "../../static/js/core/theme.js";
import { makeEl } from "../helpers.js";

const bootstrap = readFileSync(new URL("../../static/theme-init.js", import.meta.url), "utf8");

test.each([
  [null, "system", "(prefers-color-scheme: light)"],
  ["invalid", "system", "(prefers-color-scheme: light)"],
  ["light", "light", "all"],
  ["dark", "dark", "not all"],
])("first paint restores %s", (saved, preference, media) => {
  const root = makeEl();
  const stylesheet = makeEl();
  runInNewContext(bootstrap, {
    document: { documentElement: root, getElementById: () => stylesheet },
    localStorage: { getItem: () => saved },
  });
  expect(root.dataset.theme).toBe(preference);
  expect(stylesheet.media).toBe(media);
});

test("blocked storage keeps system mode before first paint", () => {
  const root = makeEl();
  const stylesheet = makeEl();
  runInNewContext(bootstrap, {
    document: { documentElement: root, getElementById: () => stylesheet },
    get localStorage() { throw new Error("blocked"); },
  });
  expect(root.dataset.theme).toBe("system");
  expect(stylesheet.media).toBe("(prefers-color-scheme: light)");
});

test("profile choices apply immediately, persist, and expose their pressed state", () => {
  const root = makeEl({ dataset: { theme: "dark" } });
  const stylesheet = makeEl();
  const buttons = ["system", "light", "dark"].map((themeChoice) => makeEl({ dataset: { themeChoice } }));
  const storage = { setItem: jest.fn() };
  createThemePreference({ root, stylesheet, buttons, storage: () => storage });
  expect(buttons[2].setAttribute).toHaveBeenLastCalledWith("aria-pressed", "true");
  for (const [index, media] of [[1, "all"], [2, "not all"], [0, "(prefers-color-scheme: light)"]]) {
    buttons[index].onclick();
    expect(stylesheet.media).toBe(media);
    expect(storage.setItem).toHaveBeenLastCalledWith("craftcontrol-theme", buttons[index].dataset.themeChoice);
    buttons.forEach((button, i) => expect(button.setAttribute).toHaveBeenLastCalledWith("aria-pressed", String(i === index)));
  }
});

test("a blocked storage getter does not prevent choosing a theme", () => {
  const root = makeEl();
  const stylesheet = makeEl();
  const button = makeEl({ dataset: { themeChoice: "light" } });
  createThemePreference({ root, stylesheet, buttons: [button], storage: () => { throw new Error("blocked"); } });
  expect(() => button.onclick()).not.toThrow();
  expect(stylesheet.media).toBe("all");
  expect(root.dataset.theme).toBe("light");
});

import { jest } from "@jest/globals";
import { downloadFile, fileNameFrom } from "../../static/js/core/download.js";

function makeBrowser() {
  const anchor = { click: jest.fn(), remove: jest.fn(), href: "", download: "" };
  return {
    anchor,
    view: { URL: { createObjectURL: jest.fn(() => "blob:x"), revokeObjectURL: jest.fn() } },
    documentRef: { createElement: jest.fn(() => anchor), body: { appendChild: jest.fn() } },
  };
}

function response({ ok = true, status = 200, body = "{}", disposition = null, json } = {}) {
  return {
    ok, status,
    headers: { get: () => disposition },
    blob: async () => ({ body }),
    json: json || (async () => JSON.parse(body)),
  };
}

test("file name comes from the server's disposition", () => {
  expect(fileNameFrom('attachment; filename="craftcontrol-players.profiles.csv"')).toBe(
    "craftcontrol-players.profiles.csv"
  );
  expect(fileNameFrom(null)).toBe("craftcontrol-export");
});

test("a successful export reaches the browser under the server's file name", async () => {
  const browser = makeBrowser();
  const fetchFn = jest.fn().mockResolvedValue(
    response({ disposition: 'attachment; filename="export.csv"' })
  );
  const name = await downloadFile("/api/exports/players/profiles", { fetchFn, ...browser });
  expect(name).toBe("export.csv");
  expect(browser.anchor.download).toBe("export.csv");
  expect(browser.anchor.click).toHaveBeenCalled();
  expect(browser.view.URL.revokeObjectURL).toHaveBeenCalledWith("blob:x");
});

test("a refusal becomes an error carrying the server's explanation", async () => {
  const browser = makeBrowser();
  const fetchFn = jest.fn().mockResolvedValue(response({
    ok: false, status: 422,
    body: JSON.stringify({ error: "export exceeds the record limit", limit: "record", measured: 20000 }),
  }));
  await expect(downloadFile("/api/exports/players/activity", { fetchFn, ...browser }))
    .rejects.toMatchObject({ status: 422, payload: { limit: "record", measured: 20000 } });
  // Nothing must reach the browser as a file.
  expect(browser.anchor.click).not.toHaveBeenCalled();
});

test("a refusal without a JSON body still fails instead of downloading", async () => {
  const browser = makeBrowser();
  const fetchFn = jest.fn().mockResolvedValue(response({
    ok: false, status: 500, json: async () => { throw new Error("not json"); },
  }));
  await expect(downloadFile("/api/exports/players/profiles", { fetchFn, ...browser }))
    .rejects.toMatchObject({ status: 500 });
  expect(browser.anchor.click).not.toHaveBeenCalled();
});

import { readFileSync } from "fs";
import { join, resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const JS = resolve(__dirname, "..", "static", "js");

describe("composition contracts — players feature dep injection (regression #156)", () => {
  function getCreatePlayersCall() {
    const composition = readFileSync(join(JS, "composition.js"), "utf8");
    const start = composition.indexOf("createPlayersFeature({");
    const end = composition.indexOf("});", start);
    return composition.slice(start, end);
  }

  test("composition.js does not pass bindSegmentedControls directly to createPlayersFeature", () => {
    expect(getCreatePlayersCall()).not.toContain("bindSegmentedControls");
  });

  test("composition.js does not pass bindSettingFields directly to createPlayersFeature", () => {
    expect(getCreatePlayersCall()).not.toContain("bindSettingFields");
  });
});

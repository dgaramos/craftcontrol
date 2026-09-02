import { jest } from "@jest/globals";
import { createActivityView } from "../static/js/features/analytics/activity.js";

function makeDeps(locale = "en") {
  const state = { locale };
  const t = (key) => key;
  const optionLabel = (v) => v;
  const uiIcon = (name) => `<svg data-icon="${name}"/>`;
  const gameTermMarkup = (v, kind) => `<span class="${kind}">${String(v)}</span>`;
  const timelineTimestamp = (ts) => ts ? `<time>${ts}</time>` : "<span>—</span>";
  return { state, t, optionLabel, uiIcon, gameTermMarkup, timelineTimestamp };
}

describe("createActivityView — eventsMarkup", () => {
  test("returns empty state for no events", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const html = eventsMarkup([]);
    expect(html).toContain("analytics-empty");
    expect(html).toContain("activityEmpty");
  });

  test("renders list for events", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.connected", timestamp: 1700000000, player: { id: "uuid1", name: "Hero" }, source: "server" }];
    const html = eventsMarkup(events);
    expect(html).toContain("analytics-event-list");
    expect(html).toContain("Hero");
    expect(html).toContain("tone-join");
  });

  test("renders en event label", () => {
    const { eventsMarkup } = createActivityView(makeDeps("en"));
    const events = [{ topic: "player.connected", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server" }];
    const html = eventsMarkup(events);
    expect(html).toContain("Joined the server");
  });

  test("renders pt event label", () => {
    const { eventsMarkup } = createActivityView(makeDeps("pt"));
    const events = [{ topic: "player.connected", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server" }];
    const html = eventsMarkup(events);
    expect(html).toContain("Entrou no servidor");
  });

  test("renders es event label", () => {
    const { eventsMarkup } = createActivityView(makeDeps("es"));
    const events = [{ topic: "player.connected", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server" }];
    const html = eventsMarkup(events);
    expect(html).toContain("Entró al servidor");
  });

  test("behavior-pack source renders sourceStructured", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.death", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "behavior-pack" }];
    const html = eventsMarkup(events);
    expect(html).toContain("sourceStructured");
    expect(html).toContain("structured");
  });

  test("unknown topic falls back to topic string", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "custom.event", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server" }];
    const html = eventsMarkup(events);
    expect(html).toContain("custom.event");
    expect(html).toContain("tone-default");
  });

  test("death event shows view details button", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.death", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server" }];
    const html = eventsMarkup(events);
    expect(html).toContain("viewDetails");
    expect(html).toContain("analytics-detail-button");
  });
});

describe("createActivityView — eventsMarkup event details", () => {
  test("showDeathDetails populates dialog and opens it", () => {
    const heading = { replaceChildren: jest.fn() };
    const details = { replaceChildren: jest.fn() };
    const dialog = { querySelector: jest.fn((selector) => selector === "h2" ? heading : details), showModal: jest.fn() };
    const deps = { ...makeDeps(), $: jest.fn(() => dialog) };
    const { showDeathDetails } = createActivityView(deps);
    const previousDocument = globalThis.document;
    globalThis.document = { querySelector: jest.fn(() => dialog), createRange: () => ({ createContextualFragment: () => ({}) }) };
    try {
      showDeathDetails({ topic: "player.death", timestamp: 1700000000, player: { name: "Hero" }, source: "server", details: { cause: "fall" } });
      expect(heading.replaceChildren).toHaveBeenCalled();
      expect(details.replaceChildren).toHaveBeenCalled();
      expect(dialog.showModal).toHaveBeenCalled();
    } finally {
      globalThis.document = previousDocument;
    }
  });

  test("death cause appears in details", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.death", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server", details: { cause: "fall" } }];
    const html = eventsMarkup(events);
    expect(html).toContain("fall");
    expect(html).toContain("deathCause");
  });

  test("killer appears in details", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.death", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server", details: { killer: "zombie" } }];
    const html = eventsMarkup(events);
    expect(html).toContain("zombie");
    expect(html).toContain("killedBy");
  });

  test("permission change shows permission detail", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.permission.changed", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server", details: { permission: "operator" } }];
    const html = eventsMarkup(events);
    expect(html).toContain("operator");
  });

  test("dimension change shows from/to", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.dimension.changed", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server", details: { from_dimension: "minecraft:overworld", to_dimension: "minecraft:nether" } }];
    const html = eventsMarkup(events);
    expect(html).toContain("overworld");
    expect(html).toContain("nether");
    expect(html).toContain("fromDimension");
    expect(html).toContain("toDimension");
  });

  test("coordinates appear in details", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.connected", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server", details: { coordinates: { x: 10, y: 64, z: -5 } } }];
    const html = eventsMarkup(events);
    expect(html).toContain("10, 64, -5");
  });

  test("inferred detail shows inferredExit", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.disconnected", timestamp: 1700000000, player: { id: "u1", name: "P" }, source: "server", details: { inferred: true } }];
    const html = eventsMarkup(events);
    expect(html).toContain("inferredExit");
  });

  test("null player handled gracefully", () => {
    const { eventsMarkup } = createActivityView(makeDeps());
    const events = [{ topic: "player.connected", timestamp: 1700000000, player: null, source: "server" }];
    expect(() => eventsMarkup(events)).not.toThrow();
  });
});

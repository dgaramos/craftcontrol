import { createI18n, messages } from "../../static/js/i18n/index.js";

describe("messages object", () => {
  test("is frozen", () => expect(Object.isFrozen(messages)).toBe(true));
  test("has pt, en, es locales", () => {
    expect(messages).toHaveProperty("pt");
    expect(messages).toHaveProperty("en");
    expect(messages).toHaveProperty("es");
  });
});

describe("createI18n — translation lookup (t)", () => {
  const i18n = createI18n(() => "en");

  test("returns string value for known key", () =>
    expect(i18n.t("language")).toBe("Language"));

  test("returns key for unknown key", () =>
    expect(i18n.t("__nonexistent_key__")).toBe("__nonexistent_key__"));

  test("calls function values with args", () =>
    expect(i18n.t("saveCount", 3)).toBe("Save (3)"));

  test("confirmAction is callable", () =>
    expect(i18n.t("confirmAction", "Stop")).toBe("Stop the server?"));

  test("fieldUpdated is callable", () =>
    expect(i18n.t("fieldUpdated", "Difficulty")).toBe("Difficulty updated"));

  test("period day labels pluralize in all supported locales", () => {
    expect(i18n.t("periodDaysLabel", 1)).toBe("1 day");
    expect(createI18n(() => "pt").t("periodDaysLabel", 2)).toBe("2 dias");
    expect(createI18n(() => "es").t("periodDaysLabel", 1)).toBe("1 día");
    expect(createI18n(() => "es").t("periodDaysLabel", 2)).toBe("2 días");
    expect(createI18n(() => "es").t("eventCount", 3)).toBe("3 eventos");
  });
});

describe("createI18n — locale fallback", () => {
  const i18n = createI18n(() => "invalid");

  test("unknown locale falls back to en", () =>
    expect(i18n.t("language")).toBe("Language"));
});

describe("createI18n — pt locale", () => {
  const i18n = createI18n(() => "pt");

  test("returns pt string", () => expect(i18n.t("language")).toBe("Idioma"));
  test("saveCount in pt", () => expect(i18n.t("saveCount", 2)).toBe("Salvar (2)"));
});

describe("createI18n — es locale", () => {
  const i18n = createI18n(() => "es");

  test("returns es string", () => expect(i18n.t("language")).toBe("Idioma"));
  test("saveCount in es", () => expect(i18n.t("saveCount", 5)).toBe("Guardar (5)"));
});

describe("createI18n — localeTag", () => {
  test("en → en-US", () => expect(createI18n(() => "en").localeTag()).toBe("en-US"));
  test("pt → pt-BR", () => expect(createI18n(() => "pt").localeTag()).toBe("pt-BR"));
  test("es → es-ES", () => expect(createI18n(() => "es").localeTag()).toBe("es-ES"));
  test("invalid → en-US fallback", () => expect(createI18n(() => "xx").localeTag()).toBe("en-US"));
});

describe("createI18n — localized", () => {
  test("pt returns ptValue", () =>
    expect(createI18n(() => "pt").localized("olá", "hello", "hola")).toBe("olá"));
  test("en returns enValue", () =>
    expect(createI18n(() => "en").localized("olá", "hello", "hola")).toBe("hello"));
  test("es returns esValue", () =>
    expect(createI18n(() => "es").localized("olá", "hello", "hola")).toBe("hola"));
  test("es defaults to enValue when esValue omitted", () =>
    expect(createI18n(() => "es").localized("olá", "hello")).toBe("hello"));
});

describe("createI18n — groupLabel", () => {
  const en = createI18n(() => "en");
  const pt = createI18n(() => "pt");

  test("__time__ maps to timeControls key", () =>
    expect(en.groupLabel("__time__")).toBe("Time & weather"));
  test("__players__ maps to onlinePlayers key", () =>
    expect(en.groupLabel("__players__")).toBe("Online players"));
  test("known group translates in en", () =>
    expect(en.groupLabel("Geral")).toBe("General"));
  test("pt returns the group name as-is", () =>
    expect(pt.groupLabel("Geral")).toBe("Geral"));
  test("unknown group returns group name", () =>
    expect(en.groupLabel("UnknownGroup")).toBe("UnknownGroup"));
});

describe("createI18n — optionLabel", () => {
  const en = createI18n(() => "en");
  const pt = createI18n(() => "pt");
  const es = createI18n(() => "es");

  test("survival in en", () => expect(en.optionLabel("survival")).toBe("Survival"));
  test("survival in pt", () => expect(pt.optionLabel("survival")).toBe("Sobrevivência"));
  test("creative in es", () => expect(es.optionLabel("creative")).toBe("Creativo"));
  test("peaceful in en", () => expect(en.optionLabel("peaceful")).toBe("Peaceful"));
  test("hard in pt", () => expect(pt.optionLabel("hard")).toBe("Difícil"));
  test("unknown option returns option key", () =>
    expect(en.optionLabel("unknown_option")).toBe("unknown_option"));
  test("visitor in en", () => expect(en.optionLabel("visitor")).toBe("Visitor"));
  test("operator in pt", () => expect(pt.optionLabel("operator")).toBe("Operador"));
  test("DEFAULT in en", () => expect(en.optionLabel("DEFAULT")).toBe("Default"));
  test("FLAT in es", () => expect(es.optionLabel("FLAT")).toBe("Plano"));
});

describe("translation completeness", () => {
  const { en, pt, es } = messages;
  const stringKeys = (locale) => Object.keys(locale).filter((k) => typeof locale[k] !== "function");
  const ptKeys = stringKeys(pt);
  const enKeys = stringKeys(en);
  const esKeys = stringKeys(es);

  test("all pt string keys exist in en", () => {
    const missing = ptKeys.filter((k) => !enKeys.includes(k));
    expect(missing).toEqual([]);
  });

  test("all pt string keys exist in es", () => {
    const missing = ptKeys.filter((k) => !esKeys.includes(k));
    expect(missing).toEqual([]);
  });

  test("all en string keys exist in pt", () => {
    const missing = enKeys.filter((k) => !ptKeys.includes(k));
    expect(missing).toEqual([]);
  });

  test("all es string keys exist in pt", () => {
    const missing = esKeys.filter((k) => !ptKeys.includes(k));
    expect(missing).toEqual([]);
  });
});

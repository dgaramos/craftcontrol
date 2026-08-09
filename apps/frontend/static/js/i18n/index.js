import { en } from "./en.js?v=2";
import { es } from "./es.js?v=2";
import { pt } from "./pt.js?v=2";

export const messages = Object.freeze({ pt, en, es });

const groupNames = {
  en: { Geral: "General", Mundo: "World", Jogadores: "Players", Packs: "Packs", Rede: "Network", Avançado: "Advanced", Interface: "Interface", Jogabilidade: "Gameplay", "Tempo e clima": "Time and weather", Criaturas: "Mobs", Drops: "Drops", Comandos: "Commands" },
  es: { Geral: "General", Mundo: "Mundo", Jogadores: "Jugadores", Packs: "Packs", Rede: "Red", Avançado: "Avanzado", Interface: "Interfaz", Jogabilidade: "Jugabilidad", "Tempo e clima": "Hora y clima", Criaturas: "Criaturas", Drops: "Botín", Comandos: "Comandos" },
};
const optionNames = {
  survival: { pt: "Sobrevivência", en: "Survival", es: "Supervivencia" }, creative: { pt: "Criativo", en: "Creative", es: "Creativo" }, adventure: { pt: "Aventura", en: "Adventure", es: "Aventura" },
  peaceful: { pt: "Pacífico", en: "Peaceful", es: "Pacífico" }, easy: { pt: "Fácil", en: "Easy", es: "Fácil" }, normal: { pt: "Normal", en: "Normal", es: "Normal" }, hard: { pt: "Difícil", en: "Hard", es: "Difícil" },
  DEFAULT: { pt: "Normal", en: "Default", es: "Predeterminado" }, FLAT: { pt: "Plano", en: "Flat", es: "Plano" }, LEGACY: { pt: "Legado", en: "Legacy", es: "Heredado" },
  visitor: { pt: "Visitante", en: "Visitor", es: "Visitante" }, member: { pt: "Membro", en: "Member", es: "Miembro" }, operator: { pt: "Operador", en: "Operator", es: "Operador" },
};
const localeTags = { pt: "pt-BR", en: "en-US", es: "es-ES" };

export function createI18n(getLocale) {
  const locale = () => messages[getLocale()] ? getLocale() : "en";
  const t = (key, ...args) => {
    const value = messages[locale()][key] ?? messages.en[key] ?? key;
    return typeof value === "function" ? value(...args) : value;
  };
  return {
    t,
    localeTag: () => localeTags[locale()],
    localized: (ptValue, enValue, esValue = enValue) => locale() === "pt" ? ptValue : locale() === "es" ? esValue : enValue,
    groupLabel: (group) => {
      if (group === "__time__") return t("timeControls");
      if (group === "__players__") return t("onlinePlayers");
      return locale() === "pt" ? group : groupNames[locale()]?.[group] || group;
    },
    optionLabel: (option) => optionNames[option]?.[locale()] || option,
  };
}

import { messages } from "../static/js/i18n/index.js";

const reference = messages.en;
const locales = ["pt", "en", "es"];
const errors = [];

for (const locale of locales) {
  const catalog = messages[locale];
  for (const key of Object.keys(reference)) {
    if (!(key in catalog)) errors.push(`${locale}: missing ${key}`);
    else if (typeof catalog[key] !== typeof reference[key]) errors.push(`${locale}: incompatible ${key}`);
  }
  for (const key of Object.keys(catalog)) {
    if (!(key in reference)) errors.push(`${locale}: unexpected ${key}`);
  }
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`i18n catalogs: ${locales.length} locales, ${Object.keys(reference).length} keys`);

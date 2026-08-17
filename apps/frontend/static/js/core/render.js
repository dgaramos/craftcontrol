export function renderMarkup(target, markup) {
  if (typeof document === "undefined" || typeof target.replaceChildren !== "function") {
    target.innerHTML = markup;
    return;
  }
  const template = document.createElement("template");
  template.innerHTML = markup;
  target.replaceChildren(template.content.cloneNode(true));
}

export function renderTemplate(target, templateId, setup) {
  const template = document.querySelector(templateId);
  if (!template) throw new Error(`Missing template: ${templateId}`);
  const clone = template.content.cloneNode(true);
  setup?.(clone);
  target.replaceChildren(clone);
  return target.firstElementChild;
}

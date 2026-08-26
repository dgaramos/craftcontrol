export function renderMarkup(target, markup) {
  if (typeof target.replaceChildren !== "function") throw new TypeError("Target does not support DOM replacement");
  if (typeof document === "undefined") {
    target.replaceChildren(markup);
    return;
  }
  const fragment = document.createRange().createContextualFragment(markup);
  target.replaceChildren(fragment);
}

export function renderTemplate(target, templateId, setup) {
  const template = document.querySelector(templateId);
  if (!template) throw new Error(`Missing template: ${templateId}`);
  const clone = template.content.cloneNode(true);
  setup?.(clone);
  target.replaceChildren(clone);
  return target.firstElementChild;
}

export const $ = (selector, root = document) => root.querySelector(selector);

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

/**
 * Returns the element that actually scrolls the panel area.
 *
 * The mobile shell makes <main> the scroll container: .shell is a fixed-height
 * flex column and main carries overflow-y. The page itself never scrolls, so
 * window.scrollTo is a no-op — a screen opened after the user had scrolled
 * would appear already scrolled down.
 */
export function scrollRoot(root) {
  const doc = root ?? (typeof document === "undefined" ? null : document);
  return doc ? doc.querySelector("main") : null;
}

/** Returns the panel area to its top, whichever element owns the scroll. */
export function resetPanelScroll(behavior = "auto", root, view) {
  const main = scrollRoot(root);
  const win = view ?? (typeof window === "undefined" ? null : window);
  if (main && typeof main.scrollTo === "function") main.scrollTo({ top: 0, left: 0, behavior });
  else if (main) main.scrollTop = 0;
  // Also reset the page, for any layout where the document is what scrolls.
  if (win && typeof win.scrollTo === "function") win.scrollTo({ top: 0, left: 0, behavior });
}

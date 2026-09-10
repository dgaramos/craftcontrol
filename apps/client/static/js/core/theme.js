/** Theme is a browser preference, independent of the authenticated account. */
export function createThemePreference({ root, stylesheet, buttons, storage }) {
  function apply(preference) {
    if (!["system", "light", "dark"].includes(preference)) preference = "system";
    root.dataset.theme = preference;
    stylesheet.media = preference === "system"
      ? "(prefers-color-scheme: light)" : preference === "light" ? "all" : "not all";
    buttons.forEach((button) => {
      const selected = button.dataset.themeChoice === preference;
      button.classList.toggle("active", selected);
      button.setAttribute("aria-pressed", String(selected));
    });
  }
  apply(root.dataset.theme || "system");
  buttons.forEach((button) => {
    button.onclick = () => {
      apply(button.dataset.themeChoice);
      try { storage().setItem("craftcontrol-theme", root.dataset.theme); } catch { /* Keep the choice for this page. */ }
    };
  });
}

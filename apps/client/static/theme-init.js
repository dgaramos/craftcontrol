/* Run before first paint; the stylesheet's media query owns system changes. */
(() => {
  let preference = "system";
  try { preference = localStorage.getItem("craftcontrol-theme") || "system"; } catch { /* Storage may be blocked. */ }
  if (!["system", "light", "dark"].includes(preference)) preference = "system";
  document.documentElement.dataset.theme = preference;
  document.getElementById("light-theme").media = preference === "system"
    ? "(prefers-color-scheme: light)" : preference === "light" ? "all" : "not all";
})();

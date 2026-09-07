export function createPlayerAccess({ state, t, $, escapeHtml, api, toast, renderPlayersPanel }) {
function panelAccessHeroRow(profile, account) {
  const sessions = account?.active_sessions || 0;
  const sessionsLabel = t("activeSessionsCount", sessions);
  if (state.user?.role !== "owner") {
    const roleText = escapeHtml(account?.status === "active" ? account.role : t("noAccess"));
    return `<span class="admin-scope panel-scope">CRAFTCONTROL</span><span class="read-only-badge">${roleText}</span><small>${sessionsLabel}</small>`;
  }
  return `<span class="admin-scope panel-scope">CRAFTCONTROL</span><select id="detail-access-role"><option value="viewer" ${account?.role === "viewer" ? "selected" : ""}>Viewer · ${t("roleViewerHint")}</option><option value="operator" ${account?.role === "operator" ? "selected" : ""}>Operator · ${t("roleOperatorHint")}</option><option value="owner" ${account?.role === "owner" ? "selected" : ""}>Owner · ${t("roleOwnerHint")}</option></select><small>${sessionsLabel}</small>`;
}

function panelAccessDetailMarkup(profile, account, title) {
  if (state.user?.role !== "owner") return "";
  const roleLabel = t("roleLabel");
  const actionsLabel = t("actionsLabel");
  const action = account?.status === "active"
    ? t("generateRecovery")
    : t("generateAccess");
  const suspendBtn = account?.status === "active"
    ? `<button id="detail-access-suspend" class="danger" type="button">${t("suspendAccess")}</button>`
    : "";
  return [
    `<div class="player-panel-card">`,
    `<div class="player-panel-header">`,
    `<span class="admin-scope panel-scope">CRAFTCONTROL</span>`,
    `<span class="player-panel-title">${t("panelAccess")}</span>`,
    `</div>`,
    `<div class="player-panel-body">`,
    `<div class="hero-attr-control">`,
    `<span class="hero-attr-label">${roleLabel}</span>`,
    `<select id="detail-access-role" class="gamemode-select">`,
    `<option value="viewer" ${account?.role === "viewer" ? "selected" : ""}>Viewer · ${t("roleViewerHint")}</option>`,
    `<option value="operator" ${account?.role === "operator" ? "selected" : ""}>Operator · ${t("roleOperatorHint")}</option>`,
    `<option value="owner" ${account?.role === "owner" ? "selected" : ""}>Owner · ${t("roleOwnerHint")}</option>`,
    `</select>`,
    `</div>`,
    `<div class="hero-attr-control">`,
    `<span class="hero-attr-label">${actionsLabel}</span>`,
    `<div class="panel-access-actions">`,
    `<button id="detail-access-invite" class="primary" type="button">${action}</button>`,
    suspendBtn,
    `</div>`,
    `</div>`,
    `<div id="detail-access-code" class="access-code" hidden>`,
    `<code></code>`,
    `<button type="button">${t("copyCode")}</button>`,
    `<small>${t("accessCodeHint")}</small>`,
    `</div>`,
    `</div>`,
    `</div>`,
  ].join("");
}

function bindPlayerAccess(profile, account) {
  const invite = $("#detail-access-invite");
  if (!invite) return;
  invite.onclick = async () => {
    try {
      const role = $("#detail-access-role").value;
      const result = await api("/api/auth/access/invite", { method: "POST", body: JSON.stringify({ player: profile.name, role }) });
      const output = $("#detail-access-code");
      output.hidden = false;
      output.querySelector("code").textContent = result.token;
      output.querySelector("button").onclick = async () => { try { await navigator.clipboard.writeText(result.token); toast(t("codeCopied")); } catch { toast(t("codeCopyFailed"), true); } };
    } catch (error) { toast(error.message, true); }
  };
  const suspend = $("#detail-access-suspend");
  if (suspend) suspend.onclick = async () => {
    if (!confirm(t("confirmSuspendAccess", profile.name))) return;
    try { await api(`/api/auth/access/${encodeURIComponent(profile.name)}/suspend`, { method: "PUT" }); toast(t("accessSuspended")); renderPlayersPanel(); }
    catch (error) { toast(error.message, true); }
  };
}


  return { panelAccessHeroRow, panelAccessDetailMarkup, bindPlayerAccess };
}

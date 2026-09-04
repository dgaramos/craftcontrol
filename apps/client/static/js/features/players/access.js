export function createPlayerAccess({ state, t, $, escapeHtml, api, toast, renderPlayersPanel }) {
function panelAccessHeroRow(profile, account) {
  const sessions = account?.active_sessions || 0;
  const sessionsLabel = sessions === 1
    ? (state.locale === "pt" ? "1 sessão ativa" : "1 active session")
    : `${sessions} ${state.locale === "pt" ? "sessões ativas" : "active sessions"}`;
  if (state.user?.role !== "owner") {
    const roleText = escapeHtml(account?.status === "active" ? account.role : (state.locale === "pt" ? "Sem acesso" : "No access"));
    return `<span class="admin-scope panel-scope">CRAFTCONTROL</span><span class="read-only-badge">${roleText}</span><small>${sessionsLabel}</small>`;
  }
  return `<span class="admin-scope panel-scope">CRAFTCONTROL</span><select id="detail-access-role"><option value="viewer" ${account?.role === "viewer" ? "selected" : ""}>Viewer · ${state.locale === "pt" ? "somente leitura" : "read only"}</option><option value="operator" ${account?.role === "operator" ? "selected" : ""}>Operator · ${state.locale === "pt" ? "gerencia o servidor" : "manages server"}</option><option value="owner" ${account?.role === "owner" ? "selected" : ""}>Owner · ${state.locale === "pt" ? "controle completo" : "full control"}</option></select><small>${sessionsLabel}</small>`;
}

function panelAccessDetailMarkup(profile, account, title) {
  if (state.user?.role !== "owner") return "";
  const pt = state.locale === "pt";
  const es = state.locale === "es";
  const roleLabel = pt ? "Papel" : es ? "Rol" : "Role";
  const actionsLabel = pt ? "Ações" : es ? "Acciones" : "Actions";
  const action = account?.status === "active"
    ? (pt ? "Gerar recuperação" : es ? "Generar recuperación" : "Generate recovery")
    : (pt ? "Gerar acesso" : es ? "Generar acceso" : "Generate access");
  const suspendBtn = account?.status === "active"
    ? `<button id="detail-access-suspend" class="danger" type="button">${pt ? "Suspender acesso" : es ? "Suspender acceso" : "Suspend access"}</button>`
    : "";
  return [
    `<div class="player-panel-card">`,
    `<div class="player-panel-header">`,
    `<span class="admin-scope panel-scope">CRAFTCONTROL</span>`,
    `<span class="player-panel-title">${pt ? "Acesso ao painel" : es ? "Acceso al panel" : "Panel access"}</span>`,
    `</div>`,
    `<div class="player-panel-body">`,
    `<div class="hero-attr-control">`,
    `<span class="hero-attr-label">${roleLabel}</span>`,
    `<select id="detail-access-role" class="gamemode-select">`,
    `<option value="viewer" ${account?.role === "viewer" ? "selected" : ""}>Viewer · ${pt ? "somente leitura" : es ? "solo lectura" : "read only"}</option>`,
    `<option value="operator" ${account?.role === "operator" ? "selected" : ""}>Operator · ${pt ? "gerencia o servidor" : es ? "gestiona el servidor" : "manages server"}</option>`,
    `<option value="owner" ${account?.role === "owner" ? "selected" : ""}>Owner · ${pt ? "controle completo" : es ? "control total" : "full control"}</option>`,
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
    `<button type="button">${pt ? "Copiar código" : es ? "Copiar código" : "Copy code"}</button>`,
    `<small>${pt ? "Mostrado uma única vez. Expira em 15 minutos." : es ? "Mostrado una vez. Expira en 15 minutos." : "Shown once. Expires in 15 minutes."}</small>`,
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
      output.querySelector("button").onclick = async () => { try { await navigator.clipboard.writeText(result.token); toast(state.locale === "pt" ? "Código copiado" : "Code copied"); } catch { toast(state.locale === "pt" ? "Não foi possível copiar o código" : "Could not copy code", true); } };
    } catch (error) { toast(error.message, true); }
  };
  const suspend = $("#detail-access-suspend");
  if (suspend) suspend.onclick = async () => {
    if (!confirm(state.locale === "pt" ? `Suspender o acesso de ${profile.name}?` : `Suspend ${profile.name}'s access?`)) return;
    try { await api(`/api/auth/access/${encodeURIComponent(profile.name)}/suspend`, { method: "PUT" }); toast(state.locale === "pt" ? "Acesso suspenso" : "Access suspended"); renderPlayersPanel(); }
    catch (error) { toast(error.message, true); }
  };
}


  return { panelAccessHeroRow, panelAccessDetailMarkup, bindPlayerAccess };
}

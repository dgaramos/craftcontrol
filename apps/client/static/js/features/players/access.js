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
  const action = account?.status === "active" ? (state.locale === "pt" ? "Gerar recuperação" : "Generate recovery") : (state.locale === "pt" ? "Gerar acesso" : "Generate access");
  const suspendBtn = account?.status === "active" ? `<button id="detail-access-suspend" class="danger" type="button">${state.locale === "pt" ? "Suspender acesso" : "Suspend access"}</button>` : "";
  return `<section class="player-access-compact block-panel"><span class="admin-scope panel-scope">CRAFTCONTROL</span><div class="panel-access-actions"><button id="detail-access-invite" class="primary" type="button">${action}</button>${suspendBtn}</div><div id="detail-access-code" class="access-code" hidden><code></code><button type="button">${state.locale === "pt" ? "Copiar código" : "Copy code"}</button><small>${state.locale === "pt" ? "Mostrado uma única vez. Expira em 15 minutos." : "Shown once. Expires in 15 minutes."}</small></div></section>`;
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

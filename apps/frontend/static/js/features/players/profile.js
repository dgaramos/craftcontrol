import { persistTab } from "../../core/route.js?v=7";
import { renderMarkup } from "../../core/render.js";

export function createPlayerProfile({ state, content, t, localized, api, $, escapeHtml, formatDate, formatDuration, playerDataMarkup, profileMarkup, getSettingsFeature, panelAccessDetailMarkup, renderPlayersPanel, renderAnalyticsPanel, getNavigation, toast, bindPlayerAccess }) {
return async function renderPlayerDetail(player, account, back = renderPlayersPanel) {
  renderMarkup(content, `<div class="player-detail-loading">${t("checking")}</div>`);  try {
    const result = await api(`/api/players/profile/${encodeURIComponent(player.id)}`);
    const profile = result?.profile || result;
    if (!profile || !Array.isArray(profile.history)) throw new Error(t("historyUnavailable"));
    const gameTitle = localized("Permissão no Minecraft", "Minecraft permission", "Permiso en Minecraft");
    const panelTitle = localized("Acesso ao CraftControl", "CraftControl access", "Acceso a CraftControl");
    renderMarkup(content, `<div class="player-detail-screen"><button id="back-to-players" class="secondary player-back" type="button">← ${localized("Todos os jogadores", "All players", "Todos los jugadores")}</button><header class="player-detail-hero block-panel"><div class="player-avatar large" aria-hidden="true">${escapeHtml(profile.name.slice(0, 1).toUpperCase())}</div><div><span class="eyebrow">${profile.online ? t("online") : t("offline")}</span><h2>${escapeHtml(profile.name)}</h2><p>${profile.online ? `${t("connectedSince")} ${formatDate(profile.connected_at)}` : `${t("lastSeen")} ${formatDate(profile.last_seen_at)}`}</p></div><button id="compare-player-data" class="secondary player-data-link" type="button">${localized("Ver nos Dados gerais", "View in general Data", "Ver en datos generales")} →</button></header><div class="player-detail-stats">${[[t("playTime"), formatDuration(profile.total_play_seconds)], [t("sessions"), profile.sessions_count], [t("deaths"), profile.deaths_count], [t("firstSeen"), formatDate(profile.first_seen_at)]].map(([label, value]) => `<span><small>${label}</small><b>${value}</b></span>`).join("")}</div>${playerDataMarkup(profile)}<div class="player-history-grid">${profileMarkup(profile)}</div><div class="player-admin-grid"><section class="player-admin-card block-panel"><span class="admin-scope game-scope">MINECRAFT</span><h3>${gameTitle}</h3><p>${localized("Controla comandos administrativos dentro do jogo. Não concede acesso ao painel.", "Controls administrative commands in-game. It does not grant panel access.", "Controla comandos administrativos en el juego. No otorga acceso al panel.")}</p><div class="permission-choice"><div><strong>${profile.operator ? localized("Operador", "Operator", "Operador") : localized("Membro", "Member", "Miembro")}</strong><small>${profile.operator ? t("operatorHelp") : localized("Joga normalmente, sem comandos administrativos.", "Regular play without administrative commands.", "Juega normalmente sin comandos administrativos.")}</small></div>${getSettingsFeature().booleanControl("detail-operator", profile.operator)}</div></section>${panelAccessDetailMarkup(profile, account, panelTitle)}</div></div>`);    if (back === renderAnalyticsPanel) $("#back-to-players").textContent = `← ${localized("Voltar aos dados", "Back to data", "Volver a datos")}`;
    $("#back-to-players").onclick = back;
    $("#compare-player-data").onclick = () => {
      state.analytics.kind = "all";
      state.analytics.player = profile.name;
      state.analytics.page = 1;
      state.tab = "analytics";
      persistTab(state.tab);
      getNavigation().renderTabs();
      renderAnalyticsPanel();
    };
    const operator = $("#detail-operator");
    if (operator) operator.onchange = async (event) => {
      getSettingsFeature().updateToggleLabel(event.target);
      try { await api(`/api/players/${encodeURIComponent(profile.name)}/operator`, { method: "PUT", body: JSON.stringify({ enabled: event.target.checked }) }); toast(t("permissionUpdated")); }
      catch (error) { toast(error.message, true); renderPlayerDetail(player, account, back); }
    };
    bindPlayerAccess(profile, account);
  } catch (error) { renderMarkup(content, `<p class="no-player-results">${escapeHtml(error.message)}</p>`); }
}

}

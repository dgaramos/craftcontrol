import { persistTab } from "../../core/route.js?v=7";
import { renderMarkup } from "../../core/render.js";

export function createPlayerProfile({ state, content, t, localized, api, $, formatDate, formatDuration, playerDataMarkup, profileMarkup, getSettingsFeature, panelAccessDetailMarkup, renderPlayersPanel, renderAnalyticsPanel, getNavigation, toast, bindPlayerAccess }) {
return async function renderPlayerDetail(player, account, back = renderPlayersPanel) {
  renderMarkup(content, `<div class="player-detail-loading">${t("checking")}</div>`);
  try {
    const result = await api(`/api/players/profile/${encodeURIComponent(player.id)}`);
    const profile = result?.profile || result;
    if (!profile || !Array.isArray(profile.history)) throw new Error(t("historyUnavailable"));
    const gameTitle = localized("Permissão no Minecraft", "Minecraft permission", "Permiso en Minecraft");
    const panelTitle = localized("Acesso ao CraftControl", "CraftControl access", "Acceso a CraftControl");

    renderMarkup(content, [
      `<div class="player-detail-screen">`,
      `<button id="back-to-players" class="secondary player-back" type="button"></button>`,
      `<header class="player-detail-hero block-panel">`,
      `<div class="player-avatar large" aria-hidden="true" id="detail-avatar"></div>`,
      `<div>`,
      `<span class="eyebrow" id="detail-status"></span>`,
      `<h2 id="detail-name"></h2>`,
      `<p id="detail-seen"></p>`,
      `</div>`,
      `<button id="compare-player-data" class="secondary player-data-link" type="button"></button>`,
      `</header>`,
      `<div class="player-detail-stats" id="detail-stats"></div>`,
      `<div id="detail-player-data"></div>`,
      `<div class="player-history-grid" id="detail-history"></div>`,
      `<div class="player-admin-grid">`,
      `<section class="player-admin-card block-panel">`,
      `<span class="admin-scope game-scope">MINECRAFT</span>`,
      `<h3 id="detail-game-title"></h3>`,
      `<p id="detail-game-desc"></p>`,
      `<div class="permission-choice">`,
      `<div>`,
      `<strong id="detail-role-label"></strong>`,
      `<small id="detail-role-help"></small>`,
      `</div>`,
      `<div id="detail-operator-control"></div>`,
      `</div>`,
      `</section>`,
      `<div id="detail-panel-access"></div>`,
      `</div>`,
      `</div>`,
    ].join(""));

    $("#back-to-players").textContent = `← ${localized("Todos os jogadores", "All players", "Todos los jugadores")}`;
    $("#detail-avatar").textContent = profile.name.slice(0, 1).toUpperCase();
    $("#detail-status").textContent = profile.online ? t("online") : t("offline");
    $("#detail-name").textContent = profile.name;
    $("#detail-seen").textContent = profile.online
      ? `${t("connectedSince")} ${formatDate(profile.connected_at)}`
      : `${t("lastSeen")} ${formatDate(profile.last_seen_at)}`;
    $("#compare-player-data").textContent = `${localized("Ver nos Dados gerais", "View in general Data", "Ver en datos generales")} →`;

    if (typeof document !== "undefined") {
      const statsEl = $("#detail-stats");
      [
        [t("playTime"), formatDuration(profile.total_play_seconds)],
        [t("sessions"), profile.sessions_count],
        [t("deaths"), profile.deaths_count],
        [t("firstSeen"), formatDate(profile.first_seen_at)],
      ].forEach(([label, value]) => {
        const span = document.createElement("span");
        const small = document.createElement("small");
        const b = document.createElement("b");
        small.textContent = label;
        b.textContent = value;
        span.append(small, b);
        statsEl.append(span);
      });
    }

    $("#detail-player-data").innerHTML = playerDataMarkup(profile);
    $("#detail-history").innerHTML = profileMarkup(profile);
    $("#detail-game-title").textContent = gameTitle;
    $("#detail-game-desc").textContent = localized(
      "Controla comandos administrativos dentro do jogo. Não concede acesso ao painel.",
      "Controls administrative commands in-game. It does not grant panel access.",
      "Controla comandos administrativos en el juego. No otorga acceso al panel."
    );
    $("#detail-role-label").textContent = profile.operator
      ? localized("Operador", "Operator", "Operador")
      : localized("Membro", "Member", "Miembro");
    $("#detail-role-help").textContent = profile.operator
      ? t("operatorHelp")
      : localized("Joga normalmente, sem comandos administrativos.", "Regular play without administrative commands.", "Juega normalmente sin comandos administrativos.");
    $("#detail-operator-control").innerHTML = getSettingsFeature().booleanControl("detail-operator", profile.operator);
    $("#detail-panel-access").innerHTML = panelAccessDetailMarkup(profile, account, panelTitle);

    if (back === renderAnalyticsPanel) $("#back-to-players").textContent = `← ${localized("Voltar aos dados", "Back to data", "Volver a datos")}`;
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
  } catch (error) {
    const p = typeof document !== "undefined" ? document.createElement("p") : null;
    if (p) {
      p.className = "no-player-results";
      p.textContent = error.message;
      content.replaceChildren(p);
    } else {
      renderMarkup(content, `<p class="no-player-results">${error.message.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c])}</p>`);
    }
  }
}

}

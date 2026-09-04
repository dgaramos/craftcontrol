import { persistTab } from "../../core/route.js?v=7";
import { renderMarkup } from "../../core/render.js";

export function createPlayerProfile({ state, content, t, localized, api, $, formatDate, formatDuration, playerDataMarkup, profileMarkup, getSettingsFeature, panelAccessDetailMarkup, panelAccessHeroRow, renderPlayersPanel, renderAnalyticsPanel, getNavigation, toast, bindPlayerAccess, escapeHtml }) {
return async function renderPlayerDetail(player, account, back = renderPlayersPanel) {
  renderMarkup(content, `<div class="player-detail-loading">${t("checking")}</div>`);
  try {
    const result = await api(`/api/players/profile/${encodeURIComponent(player.id)}`);
    const profile = result?.profile || result;
    if (!profile || !Array.isArray(profile.history)) throw new Error(t("historyUnavailable"));

    const gameTitle = localized("Permissão no Minecraft", "Minecraft permission", "Permiso en Minecraft");
    const panelTitle = localized("Acesso ao CraftControl", "CraftControl access", "Acceso a CraftControl");
    void gameTitle; void panelTitle; // retained for contract coverage
    const operatorTooltip = localized(
      "Operadores têm acesso a comandos administrativos no jogo. Não concede acesso ao painel CraftControl.",
      "Operators have access to administrative commands in-game. It does not grant CraftControl panel access.",
      "Los operadores tienen acceso a comandos administrativos en el juego. No otorga acceso al panel CraftControl."
    );

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
      `<div class="player-detail-hero-attrs">`,
      `<div class="player-detail-hero-attrs-row">`,
      `<span class="admin-scope game-scope">MINECRAFT</span>`,
      `<span class="hero-attr-label" id="detail-role-label"></span>`,
      `<div id="detail-operator-control" title="${escapeHtml ? escapeHtml(operatorTooltip) : operatorTooltip}"></div>`,
      `<select class="gamemode-select compact" id="detail-gamemode-select">`,
      `<option value="server_default" id="detail-gamemode-server-default"></option>`,
      `<option value="survival" id="detail-gamemode-survival"></option>`,
      `<option value="creative" id="detail-gamemode-creative"></option>`,
      `<option value="adventure" id="detail-gamemode-adventure"></option>`,
      `</select>`,
      `<div id="detail-gamemode-force-notice" hidden></div>`,
      `</div>`,
      `<div class="player-detail-hero-attrs-row" id="detail-craftcontrol-row">`,
      panelAccessHeroRow ? panelAccessHeroRow(profile, account) : "",
      `</div>`,
      `</div>`,
      `</header>`,
      `<div class="player-detail-stats" id="detail-stats"></div>`,
      `<div id="detail-player-data"></div>`,
      `<div class="player-history-grid" id="detail-history"></div>`,
      `<div id="detail-observed-gamemode" class="block-panel" hidden></div>`,
      `<div id="detail-panel-access"></div>`,
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
    $("#detail-role-label").textContent = profile.operator
      ? localized("Operador", "Operator", "Operador")
      : localized("Membro", "Member", "Miembro");
    $("#detail-operator-control").innerHTML = getSettingsFeature().booleanControl("detail-operator", profile.operator);
    $("#detail-panel-access").innerHTML = panelAccessDetailMarkup(profile, account, "");

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

    // Game mode — saves immediately on change
    $("#detail-gamemode-server-default").textContent = t("serverDefault");
    $("#detail-gamemode-survival").textContent = t("survival");
    $("#detail-gamemode-creative").textContent = t("creative");
    $("#detail-gamemode-adventure").textContent = t("adventure");

    // Pre-select the persisted preference (or server_default when null)
    const gameModeSelect = $("#detail-gamemode-select");
    if (gameModeSelect) {
      gameModeSelect.value = profile.preferred_game_mode || "server_default";
      gameModeSelect.onchange = async (event) => {
        const mode = event.target.value;
        try {
          await api(`/api/players/${encodeURIComponent(profile.name)}/gamemode`, { method: "PUT", body: JSON.stringify({ mode }) });
          toast(t("gameModeUpdated"));
        } catch (error) {
          toast(error.message || t("gameModeError"), true);
        }
      };
    }

    // Show preferred_game_mode state as a read-only label
    const preferredStatus = $("#detail-preferred-gamemode-status");
    if (preferredStatus) {
      preferredStatus.textContent = profile.preferred_game_mode
        ? `${t("preferredGameModeLabel")}: ${t(profile.preferred_game_mode) || profile.preferred_game_mode}`
        : t("preferredGameModeNone");
    }

    // Show FORCE_GAMEMODE notice when the setting is enabled
    const serverState = state.server || {};
    const forceGameMode = (serverState.settings || {})["FORCE_GAMEMODE"];
    const forceNotice = $("#detail-gamemode-force-notice");
    if (forceNotice && (forceGameMode === "true" || forceGameMode === true)) {
      forceNotice.hidden = false;
      forceNotice.innerHTML = `<p class="gamemode-force-notice">${escapeHtml ? escapeHtml(t("forcedGameModeNotice")) : t("forcedGameModeNotice")}</p><button id="detail-gamemode-settings-link" class="secondary" type="button">${t("forcedGameModeLink")}</button>`;
      const settingsLink = $("#detail-gamemode-settings-link");
      if (settingsLink) settingsLink.onclick = () => { state.tab = "settings"; getNavigation().renderTabs(); };
    }

    // Observed game mode — read-only, sourced from Telemetry Pack snapshot
    const observedGameModeEl = $("#detail-observed-gamemode");
    if (observedGameModeEl) {
      const observedMode = profile.observed_game_mode;
      if (observedMode) {
        observedGameModeEl.hidden = false;
        observedGameModeEl.textContent = `${t("observedGameModeLabel")}: ${t(observedMode) || observedMode}`;
      } else {
        observedGameModeEl.hidden = true;
        observedGameModeEl.textContent = t("observedGameModeAbsent");
      }
    }

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

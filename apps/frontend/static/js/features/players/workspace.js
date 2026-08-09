export function createPlayersWorkspace({ state, content, t, api, $, escapeHtml, toast, playerSettingsMarkup, bindSegmentedControls, bindSettingFields, formatDuration, formatDate, renderPlayerDetail }) {
return async function renderPlayersPanel() {
  content.innerHTML = `<div class="players-screen block-panel"><div class="section-heading"><div><span class="eyebrow">${state.locale === "pt" ? "JOGADORES" : "PLAYERS"}</span><h3>${t("allPlayers")}</h3><p>${state.locale === "pt" ? "Selecione uma pessoa para abrir sua ficha, histórico e permissões." : "Select a person to open their profile, history, and permissions."}</p></div></div><div id="player-overview" class="player-overview" hidden></div><div class="player-toolbar" hidden><input id="player-search" type="search" placeholder="${t("searchPlayers")}" autocomplete="off"><div class="player-filters"><button class="active" data-player-filter="all">${t("filterAll")}</button><button data-player-filter="online">${t("filterOnline")}</button><button data-player-filter="offline">${t("filterOffline")}</button><button data-player-filter="operator">${t("filterOperators")}</button></div></div><div class="loading-players">${t("checking")}</div></div>${playerSettingsMarkup()}`;
  bindSegmentedControls();
  bindSettingFields(["Jogadores"]);
  try {
    const result = await api("/api/players");
    const list = result.players || [];
    let access = {};
    if (state.user?.role === "owner") {
      const accessResult = await api("/api/auth/access");
      access = Object.fromEntries((accessResult.players || []).map((item) => [item.name.toLocaleLowerCase(), item]));
    }
    const container = content.querySelector(".loading-players");
    if (!list.length) {
      container.textContent = t("noHistory");
      return;
    }
    renderPlayerOverview(list);
    const toolbar = content.querySelector(".player-toolbar");
    toolbar.hidden = false;
    container.className = "player-management-list";
    let activeFilter = "all";
    const updateList = () => {
      const query = $("#player-search").value.trim().toLocaleLowerCase();
      const filtered = list.filter((player) => (!query || player.name.toLocaleLowerCase().includes(query)) && (activeFilter === "all" || (activeFilter === "online" && player.online) || (activeFilter === "offline" && !player.online) || (activeFilter === "operator" && player.operator)));
      renderPlayerCards(container, filtered, access);
    };
    $("#player-search").oninput = updateList;
    content.querySelectorAll("[data-player-filter]").forEach((button) => button.onclick = () => {
      activeFilter = button.dataset.playerFilter;
      content.querySelectorAll("[data-player-filter]").forEach((item) => item.classList.toggle("active", item === button));
      updateList();
    });
    updateList();
  } catch (error) { const loading = content.querySelector(".loading-players"); if (loading) loading.textContent = error.message; else toast(error.message, true); }
}

function renderPlayerOverview(list) {
  const overview = $("#player-overview");
  const online = list.filter((player) => player.online).length;
  const deaths = list.reduce((total, player) => total + Number(player.deaths_count || 0), 0);
  const seconds = list.reduce((total, player) => total + Number(player.total_play_seconds || 0), 0);
  overview.innerHTML = `<span><b>${list.length}</b>${t("totalPlayers")}</span><span><b>${online}</b>${t("online")}</span><span><b>${deaths}</b>${t("totalDeaths")}</span><span><b>${formatDuration(seconds)}</b>${t("totalPlayTime")}</span>`;
  overview.hidden = false;
}

function renderPlayerCards(container, list, access = {}) {
  if (!list.length) { container.innerHTML = `<p class="no-player-results">${t("noPlayersFound")}</p>`; return; }
  container.innerHTML = list.map((player, index) => {
    const account = access[player.name.toLocaleLowerCase()];
    const gameRole = player.operator ? (state.locale === "pt" ? "Operador Minecraft" : "Minecraft operator") : (state.locale === "pt" ? "Membro Minecraft" : "Minecraft member");
    const panelRole = account?.status === "active" ? `CraftControl · ${account.role}` : (state.locale === "pt" ? "Sem acesso ao painel" : "No panel access");
    return `<article class="player-roster-row ${player.online ? "is-online" : "is-offline"}"><button class="player-roster-open" data-player-index="${index}" type="button"><span class="player-avatar" aria-hidden="true">${escapeHtml(player.name.slice(0, 1).toUpperCase())}</span><span class="player-roster-identity"><strong>${escapeHtml(player.name)}</strong><small>${player.online ? "● " + t("online") : "○ " + t("offline")} · ${player.online ? formatDuration(Date.now() / 1000 - player.connected_at) : formatDate(player.last_seen_at)}</small></span><span class="player-roster-badges"><b class="game-role-badge">${escapeHtml(gameRole)}</b><b class="panel-role-badge ${account?.status === "active" ? "has-access" : ""}">${escapeHtml(panelRole)}</b></span><span class="player-roster-summary"><small>${t("playTime")}</small><b>${formatDuration(player.total_play_seconds)}</b></span><span class="player-roster-arrow" aria-hidden="true">›</span></button></article>`;
  }).join("");
  container.querySelectorAll("[data-player-index]").forEach((button) => {
    button.onclick = () => {
      const player = list[Number(button.dataset.playerIndex)];
      renderPlayerDetail(player, access[player.name.toLocaleLowerCase()]);
    };
  });
}

}


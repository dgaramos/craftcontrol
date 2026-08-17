export function createPlayersWorkspace({ state, content, t, api, $, escapeHtml, toast, playerSettingsMarkup, bindSegmentedControls, bindSettingFields, formatDuration, formatDate, renderPlayerDetail }) {
return async function renderPlayersPanel() {
  const tplScreen = $("#tpl-players-screen");
  const clone = tplScreen.content.cloneNode(true);
  clone.querySelector(".eyebrow").textContent = state.locale === "pt" ? "JOGADORES" : "PLAYERS";
  clone.querySelector("h3").textContent = t("allPlayers");
  clone.querySelector("p").textContent = state.locale === "pt" ? "Selecione uma pessoa para abrir sua ficha, histórico e permissões." : "Select a person to open their profile, history, and permissions.";
  clone.querySelector("#player-search").placeholder = t("searchPlayers");
  clone.querySelector("[data-player-filter=all]").textContent = t("filterAll");
  clone.querySelector("[data-player-filter=online]").textContent = t("filterOnline");
  clone.querySelector("[data-player-filter=offline]").textContent = t("filterOffline");
  clone.querySelector("[data-player-filter=operator]").textContent = t("filterOperators");
  clone.querySelector(".loading-players").textContent = t("checking");
  content.replaceChildren(clone);
  content.insertAdjacentHTML("beforeend", playerSettingsMarkup());
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
  const tpl = $("#tpl-player-overview-stat");
  const items = [
    [String(list.length), t("totalPlayers")],
    [String(online), t("online")],
    [String(deaths), t("totalDeaths")],
    [formatDuration(seconds), t("totalPlayTime")],
  ];
  overview.replaceChildren();
  items.forEach(([value, label]) => {
    const clone = tpl.content.cloneNode(true);
    const span = clone.querySelector("span");
    span.querySelector("b").textContent = value;
    span.append(label);
    overview.appendChild(clone);
  });
  overview.hidden = false;
}

function renderPlayerCards(container, list, access = {}) {
  container.replaceChildren();
  if (!list.length) {
    // inline: single element, no user data
    container.innerHTML = '<p class="no-player-results"></p>';
    container.querySelector("p").textContent = t("noPlayersFound");
    return;
  }
  const tpl = $("#tpl-player-roster-row");
  list.forEach((player) => {
    const account = access[player.name.toLocaleLowerCase()];
    const gameRole = player.operator ? (state.locale === "pt" ? "Operador Minecraft" : "Minecraft operator") : (state.locale === "pt" ? "Membro Minecraft" : "Minecraft member");
    const panelRole = account?.status === "active" ? `CraftControl · ${account.role}` : (state.locale === "pt" ? "Sem acesso ao painel" : "No panel access");
    const clone = tpl.content.cloneNode(true);
    const article = clone.querySelector("article");
    article.className = `player-roster-row ${player.online ? "is-online" : "is-offline"}`;
    clone.querySelector(".player-avatar").textContent = player.name.slice(0, 1).toUpperCase();
    clone.querySelector(".player-roster-identity strong").textContent = player.name;
    clone.querySelector(".player-roster-identity small").textContent = player.online
      ? `● ${t("online")} · ${formatDuration(Date.now() / 1000 - player.connected_at)}`
      : `○ ${t("offline")} · ${formatDate(player.last_seen_at)}`;
    clone.querySelector(".game-role-badge").textContent = gameRole;
    const panelBadge = clone.querySelector(".panel-role-badge");
    panelBadge.textContent = panelRole;
    if (account?.status === "active") panelBadge.classList.add("has-access");
    clone.querySelector(".player-roster-summary small").textContent = t("playTime");
    clone.querySelector(".player-roster-summary b").textContent = formatDuration(player.total_play_seconds);
    const button = clone.querySelector(".player-roster-open");
    button.onclick = () => renderPlayerDetail(player, access[player.name.toLocaleLowerCase()]);
    container.appendChild(clone);
  });
}

}


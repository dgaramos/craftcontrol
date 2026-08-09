export function createPlayerHistory({ state, t, escapeHtml, gameLabel, gameIcon, gameTermMarkup, optionLabel, formatDate, formatDuration, timelineTimestamp }) {
function historyMarkup(events) {
  if (!events.length) return `<p>${t("noHistory")}</p>`;
  const labels = {
    "player.connected": { pt: "Entrou no servidor", en: "Joined the server" },
    "player.disconnected": { pt: "Saiu do servidor", en: "Left the server" },
    "player.death": { pt: "Morreu", en: "Died" },
    "player.permission.changed": { pt: "Permissão alterada", en: "Permission changed" },
  };
  return `<ol class="timeline-list">${events.map((event) => {
    const payload = event?.payload || {};
    const action = (labels[event?.topic] || {})[state.locale] || event?.topic || "event";
    const details = [
      payload.cause ? escapeHtml(gameLabel(payload.cause, "cause")) : "",
      payload.inferred ? (state.locale === "pt" ? "Encerramento inferido pelo estado do servidor" : "Inferred from server state") : "",
    ].filter(Boolean);
    return `<li class="timeline-item"><span class="timeline-node" aria-hidden="true"></span><div class="timeline-action"><strong>${escapeHtml(action)}</strong>${details.length ? `<small>${details.join(" · ")}</small>` : ""}</div>${timelineTimestamp(event?.timestamp)}</li>`;
  }).join("")}</ol>`;
}

function sessionMoment(timestamp) {
  return localizedSessionMoment(timestamp, localeTag());
}

function sessionsMarkup(sessions) {
  if (!sessions.length) return `<p>${t("noHistory")}</p>`;
  return `<ol class="session-list">${sessions.map((session) => {
    const active = Boolean(session.active);
    const inferred = Boolean(session.inferred);
    const title = active
      ? (state.locale === "pt" ? "Sessão em andamento" : "Session in progress")
      : (state.locale === "pt" ? "Sessão encerrada" : "Session ended");
    const status = active ? (state.locale === "pt" ? "Jogador conectado agora" : "Player currently connected") : inferred ? t("inferredExit") : t("normalExit");
    const reason = session.close_reason && session.close_reason !== "disconnect" ? ` · ${escapeHtml(session.close_reason)}` : "";
    return `<li class="session-item ${active ? "is-active" : ""} ${inferred ? "is-inferred" : ""}"><div class="session-state"><span class="session-status-dot" aria-hidden="true"></span><div><strong>${title}</strong><small>${status}${reason}</small></div></div><div class="session-duration"><small>${active ? (state.locale === "pt" ? "Tempo atual" : "Elapsed") : (state.locale === "pt" ? "Duração" : "Duration")}</small><b>${formatDuration(session.duration_seconds)}</b></div><div class="session-period"><span><small>${state.locale === "pt" ? "Início" : "Started"}</small>${sessionMoment(session.connected_at)}</span>${session.disconnected_at ? `<span><small>${state.locale === "pt" ? "Fim" : "Ended"}</small>${sessionMoment(session.disconnected_at)}</span>` : ""}</div></li>`;
  }).join("")}</ol>`;
}

function profileMarkup(profile) {
  const aliases = (profile.aliases || []).filter((name) => name !== profile.name);
  const sessions = Array.isArray(profile.sessions) ? profile.sessions : [];
  const deaths = (profile.history || []).filter((event) => event?.topic === "player.death").length;
  return `<section class="player-records block-panel"><div class="player-records-heading"><div><span class="eyebrow">${state.locale === "pt" ? "EVIDÊNCIAS RECENTES" : "RECENT EVIDENCE"}</span><h3>${state.locale === "pt" ? "Histórico do jogador" : "Player history"}</h3><p>${state.locale === "pt" ? "Os totais acima vêm dos agregados permanentes; estes registros explicam apenas os eventos recentes disponíveis." : "The totals above come from permanent aggregates; these records explain only the recent events still available."}</p></div></div><div class="profile-facts"><span><small>${t("permission")}</small><b>${escapeHtml(optionLabel(profile.permission || "member"))}</b></span><span><small>${t("lastDeath")}</small><b>${formatDate(profile.last_death_at)}</b></span><span><small>${t("aliases")}</small><b>${aliases.length ? aliases.map(escapeHtml).join(" · ") : "—"}</b></span></div><details class="player-record-drawer"><summary><span>${t("deathHistory")}</span><b>${deaths}</b></summary>${deathHistoryMarkup(profile.history || [])}</details><details class="player-record-drawer"><summary><span>${t("recentSessions")}</span><b>${sessions.length}</b></summary><section class="session-history">${sessionsMarkup(sessions)}</section></details><details class="player-record-drawer"><summary><span>${state.locale === "pt" ? "Linha do tempo técnica" : "Technical timeline"}</span><b>${(profile.history || []).length}</b></summary><section class="event-history">${historyMarkup(profile.history || [])}</section></details></section>`;
}

function deathHistoryMarkup(events) {
  const deaths = events.filter((event) => event?.topic === "player.death");
  if (!deaths.length) return `<section class="death-history"><h4>${t("deathHistory")}</h4><p>${t("noDeaths")}</p></section>`;
  return `<section class="death-history"><h4>${t("deathHistory")}</h4><ol>${deaths.map((event) => {
    const data = event.payload || {};
    const killer = data.killer || data.killerType || "—";
    const details = [[t("deathCause"), data.cause, "cause"], [t("killedBy"), killer, "entity"], [t("projectile"), data.projectileType, "entity"]].filter(([, value]) => value);
    const source = event.source === "behavior-pack" ? t("telemetrySource") : t("sourceServer");
    return `<li><header class="death-entry-header"><span class="death-entry-icon">${gameIcon(killer, "entity", gameLabel(killer, "entity"))}</span><div><b>${escapeHtml(gameLabel(data.cause, "cause"))}</b><small class="death-source">${escapeHtml(source)}</small></div>${timelineTimestamp(event.timestamp)}</header><dl>${details.map(([label, value, kind]) => `<div><dt>${escapeHtml(label)}</dt><dd>${gameTermMarkup(value, kind)}</dd></div>`).join("")}</dl></li>`;
  }).join("")}</ol></section>`;
}


  return { historyMarkup, sessionsMarkup, profileMarkup, deathHistoryMarkup };
}

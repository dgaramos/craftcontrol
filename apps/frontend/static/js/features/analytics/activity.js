import { $, escapeHtml } from "../../core/dom.js?v=1";

const eventDefinitions = {
  "player.connected": { icon: "players", pt: "Entrou no servidor", en: "Joined the server", es: "Entró al servidor", tone: "join" },
  "player.disconnected": { icon: "players", pt: "Saiu do servidor", en: "Left the server", es: "Salió del servidor", tone: "leave" },
  "player.respawned": { icon: "restart", pt: "Renasceu", en: "Respawned", es: "Reapareció", tone: "respawn" },
  "player.dimension.changed": { icon: "exploration", pt: "Mudou de dimensão", en: "Changed dimension", es: "Cambió de dimensión", tone: "dimension" },
  "player.death": { icon: "deaths", pt: "Morreu", en: "Died", es: "Murió", tone: "death" },
  "player.permission.changed": { icon: "shield", pt: "Permissão alterada", en: "Permission changed", es: "Permiso modificado", tone: "permission" },
};

export function createActivityView({ state, t, optionLabel, uiIcon, gameTermMarkup, timelineTimestamp }) {
  const presentationFor = (event) => eventDefinitions[event.topic]
    || { icon: "activity", pt: event.topic, en: event.topic, es: event.topic, tone: "default" };

  const detailsMarkup = (event) => {
    const details = event.details || {};
    const items = [];
    if (details.cause) items.push([t("deathCause"), details.cause, "cause"]);
    if (details.killer) items.push([t("killedBy"), details.killer, "entity"]);
    if (details.projectile) items.push([t("projectile"), details.projectile, "entity"]);
    if (details.permission) items.push([t("permission"), optionLabel(details.permission)]);
    if (details.dimension) items.push([state.locale === "pt" ? "Dimensão" : state.locale === "es" ? "Dimensión" : "Dimension", String(details.dimension).replace(/^minecraft:/, "")]);
    if (details.from_dimension) items.push([t("fromDimension"), String(details.from_dimension).replace(/^minecraft:/, "")]);
    if (details.to_dimension) items.push([t("toDimension"), String(details.to_dimension).replace(/^minecraft:/, "")]);
    const coordinates = details.coordinates || {};
    if (Object.keys(coordinates).length) items.push([state.locale === "pt" ? "Coordenadas" : state.locale === "es" ? "Coordenadas" : "Coordinates", [coordinates.x, coordinates.y, coordinates.z].filter((value) => value !== undefined).join(", ")]);
    if (details.inferred) items.push([state.locale === "pt" ? "Observação" : state.locale === "es" ? "Nota" : "Note", t("inferredExit")]);
    return items.length ? `<dl class="analytics-event-details">${items.map(([label, value, kind]) => `<div><dt>${escapeHtml(label)}</dt><dd>${kind ? gameTermMarkup(value, kind) : escapeHtml(value)}</dd></div>`).join("")}</dl>` : "";
  };

  const eventsMarkup = (events) => {
    if (!events.length) return `<div class="analytics-empty"><span>${uiIcon("activity")}</span><p>${t("activityEmpty")}</p></div>`;
    return `<ol class="analytics-event-list">${events.map((event, index) => {
      const presentation = presentationFor(event);
      const source = event.source === "behavior-pack" ? t("sourceStructured") : t("sourceServer");
      return `<li class="analytics-event tone-${presentation.tone}"><span class="analytics-event-icon">${uiIcon(presentation.icon)}</span><div class="analytics-event-main"><div class="analytics-event-title"><div><button class="analytics-player-link" data-analytics-player="${escapeHtml(event.player?.id || "")}" type="button">${escapeHtml(event.player?.name || "—")}</button><span>${escapeHtml(presentation[state.locale])}</span></div><b class="analytics-source ${event.source === "behavior-pack" ? "structured" : "server"}">${escapeHtml(source)}</b></div>${detailsMarkup(event)}${event.topic === "player.death" ? `<button class="analytics-detail-button" data-death-detail="${index}" type="button">${t("viewDetails")} ›</button>` : ""}</div>${timelineTimestamp(event.timestamp)}</li>`;
    }).join("")}</ol>`;
  };

  const showDeathDetails = (event) => {
    const dialog = $("#analytics-death-dialog");
    const presentation = presentationFor(event);
    dialog.querySelector("h2").innerHTML = `${uiIcon(presentation.icon)} ${escapeHtml(event.player?.name || "—")}`;
    dialog.querySelector(".analytics-death-content").innerHTML = `<p>${escapeHtml(presentation[state.locale])}</p>${detailsMarkup(event)}<div class="analytics-death-meta"><span>${event.source === "behavior-pack" ? t("sourceStructured") : t("sourceServer")}</span>${timelineTimestamp(event.timestamp)}</div>`;
    dialog.showModal();
  };

  return { eventsMarkup, showDeathDetails };
}

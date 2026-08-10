import { escapeHtml } from "../core/dom.js?v=5";

export function formatDate(timestamp, locale) {
  if (!timestamp) return "—";
  return new Date(timestamp * 1000).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" });
}

export function timelineTimestamp(timestamp, locale) {
  if (!timestamp) return `<time class="timeline-timestamp"><span>—</span></time>`;
  const value = new Date(timestamp * 1000);
  const date = value.toLocaleDateString(locale, { day: "2-digit", month: "short", year: "numeric" });
  const time = value.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  return `<time class="timeline-timestamp" datetime="${value.toISOString()}"><span>${escapeHtml(date)}</span><b>${escapeHtml(time)}</b></time>`;
}

export function formatDuration(seconds) {
  const minutes = Math.floor((seconds || 0) / 60);
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours}h ${minutes % 60}m` : `${minutes}m`;
}

export function sessionMoment(timestamp, locale) {
  if (!timestamp) return "—";
  const value = new Date(timestamp * 1000);
  const date = value.toLocaleDateString(locale, { day: "2-digit", month: "short", year: "numeric" });
  const time = value.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  return `<time datetime="${value.toISOString()}"><span>${escapeHtml(date)}</span><b>${escapeHtml(time)}</b></time>`;
}

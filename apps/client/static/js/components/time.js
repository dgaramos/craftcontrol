import { escapeHtml } from "../core/dom.js?v=7";

function dateFromTimestamp(value) {
  if (!value) return null;

  const numericValue = typeof value === "number" ? value : Number(value);
  const magnitude = Math.abs(numericValue);
  const milliseconds = Number.isFinite(numericValue)
    ? (magnitude < 100_000_000_000 ? numericValue * 1000
      : magnitude >= 100_000_000_000_000 ? numericValue / 1000
        : numericValue)
    : Date.parse(value);
  const date = new Date(milliseconds);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(timestamp, locale) {
  const value = dateFromTimestamp(timestamp);
  if (!value) return "—";
  return value.toLocaleString(locale, { dateStyle: "short", timeStyle: "short" });
}

export function timelineTimestamp(timestamp, locale) {
  const value = dateFromTimestamp(timestamp);
  if (!value) return `<time class="timeline-timestamp"><span>—</span></time>`;
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
  const value = dateFromTimestamp(timestamp);
  if (!value) return "—";
  const date = value.toLocaleDateString(locale, { day: "2-digit", month: "short", year: "numeric" });
  const time = value.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  return `<time datetime="${value.toISOString()}"><span>${escapeHtml(date)}</span><b>${escapeHtml(time)}</b></time>`;
}

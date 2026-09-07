/**
 * Browser download for authenticated file responses (issue #272).
 *
 * The shared `api()` helper parses every response as JSON, which an export is
 * not. This reads the payload as a blob and hands it to the browser under the
 * file name the server chose, and turns a refusal into an error carrying the
 * server's own explanation instead of downloading it.
 */

export function fileNameFrom(disposition, fallback = "craftcontrol-export") {
  const match = /filename="([^"]+)"/.exec(disposition || "");
  return match ? match[1] : fallback;
}

export async function downloadFile(url, {
  fetchFn = typeof fetch === "function" ? fetch : null,
  view = typeof window === "undefined" ? null : window,
  documentRef = typeof document === "undefined" ? null : document,
} = {}) {
  const response = await fetchFn(url, { headers: { Accept: "application/json, text/csv" } });
  if (!response.ok) {
    let payload = {};
    try { payload = await response.json(); } catch { payload = {}; }
    const error = new Error(payload.error || "Export failed");
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  const blob = await response.blob();
  const name = fileNameFrom(response.headers.get("Content-Disposition"));
  const href = view.URL.createObjectURL(blob);
  const anchor = documentRef.createElement("a");
  anchor.href = href;
  anchor.download = name;
  documentRef.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  view.URL.revokeObjectURL(href);
  return name;
}

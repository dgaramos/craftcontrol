let csrfToken = null;

async function safeJson(response) {
  try { return await response.json(); } catch { return {}; }
}

async function refreshCsrfToken() {
  const response = await fetch("/api/auth/me", { headers: { "Accept": "application/json" } });
  const data = await safeJson(response);
  if (!response.ok || typeof data.csrf_token !== "string") {
    const error = new Error(data.error || "Authentication required");
    error.status = response.status;
    throw error;
  }
  csrfToken = data.csrf_token;
}

export async function api(url, options = {}, retry = true) {
  const method = String(options.method || "GET").toUpperCase();
  const mutation = !["GET", "HEAD", "OPTIONS"].includes(method);
  const csrfProtected = mutation && !["/api/auth/login", "/api/auth/claim"].includes(url);
  if (csrfProtected && !csrfToken) await refreshCsrfToken();
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (csrfProtected && csrfToken) headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(url, {
    ...options,
    headers,
  });
  const data = await safeJson(response);
  if (typeof data.csrf_token === "string") csrfToken = data.csrf_token;
  if (!response.ok) {
    if (csrfProtected && retry && response.status === 403 && data.error === "invalid or missing CSRF token") {
      await refreshCsrfToken();
      return api(url, options, false);
    }
    const error = new Error(data.error || "Request failed");
    error.status = response.status;
    error.payload = data;
    throw error;
  }
  return data;
}

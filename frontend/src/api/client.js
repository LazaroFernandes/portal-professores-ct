let csrfToken = "";

export function setCsrfToken(value) {
  csrfToken = value || "";
}

export async function api(path, options = {}) {
  const headers = { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers };
  if (csrfToken && options.method && options.method !== "GET") headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(path, { credentials: "include", ...options, headers });
  if (response.status === 204) return null;
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const error = new Error(payload?.detail || payload || "Não foi possível concluir a solicitação.");
    error.status = response.status;
    throw error;
  }
  return payload;
}

export function query(path, params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  });
  return api(`${path}${search.size ? `?${search}` : ""}`);
}

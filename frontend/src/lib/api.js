import { getStoredLanguage, translate } from "./i18n";
import { getApiBase } from "./apiBase";

const API_BASE = getApiBase();

const getToken = () => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token") || localStorage.getItem("access_token");
};

const getCookie = (name) => {
  if (typeof document === "undefined") return "";
  const prefix = `${name}=`;
  const parts = document.cookie ? document.cookie.split("; ") : [];
  for (const part of parts) {
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.slice(prefix.length));
    }
  }
  return "";
};

/**
 * @param {string} path
 * @param {any} options
 * @returns {Promise<any>}
 */
export async function apiFetch(
  path,
  { method = "GET", body = null, auth = false, credentials = "same-origin", headers: extraHeaders = undefined } = {}
) {
  const normalizedMethod = String(method || "GET").toUpperCase();
  const headers = { ...(extraHeaders || {}) };
  const token = getToken();
  if (auth && token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (body != null) {
    headers["Content-Type"] = "application/json";
  }
  if (
    path.startsWith("/api/admin/") &&
    !path.startsWith("/api/admin/auth/login") &&
    !["GET", "HEAD", "OPTIONS"].includes(normalizedMethod)
  ) {
    const csrfToken = getCookie("admin_csrf_token");
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: normalizedMethod,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
    credentials,
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      (typeof detail === "string" && detail.trim()) ||
      (detail ? JSON.stringify(detail) : "") ||
      data?.message ||
      translate({ ja: "API エラーが発生しました", en: "API error occurred." }, getStoredLanguage());
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const authTokenExists = () => !!getToken();

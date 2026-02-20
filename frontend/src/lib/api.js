import { getStoredLanguage, translate } from "./i18n";
import { getApiBase } from "./apiBase";

const API_BASE = getApiBase();

const getToken = () => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token") || localStorage.getItem("access_token");
};

export async function apiFetch(
  path,
  { method = "GET", body = null, auth = false, credentials = "same-origin" } = {}
) {
  const headers = {};
  const token = getToken();
  if (auth && token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (body != null) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
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

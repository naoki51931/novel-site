const API_BASE = "";

const getToken = () => {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token") || localStorage.getItem("access_token");
};

export async function apiFetch(
  path,
  { method = "GET", body = null, auth = false, admin = false } = {}
) {
  const headers = {};
  const token = getToken();
  if (auth && token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (admin) {
    const adminToken = import.meta.env.VITE_ADMIN_API_KEY;
    if (adminToken) {
      headers["X-Admin-Token"] = adminToken;
    }
  }
  if (body != null) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body != null ? JSON.stringify(body) : undefined,
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message = data?.detail || data?.message || "API エラーが発生しました";
    const err = new Error(message);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const authTokenExists = () => !!getToken();

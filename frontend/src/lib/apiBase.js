export function getApiBase() {
  const envBase = (process.env.NEXT_PUBLIC_BACKEND_ORIGIN || "")
    .toString()
    .trim()
    .replace(/\/+$/, "");

  // Production: always same-origin so subdomains (romance/history) don't call main-domain APIs.
  if (typeof window !== "undefined") {
    const host = (window.location.hostname || "").toLowerCase();
    const isLocal = host === "localhost" || host === "127.0.0.1";
    if (!isLocal) return "";
  }

  // Dev: allow env override; fallback to local backend.
  return envBase || "http://localhost:8000";
}

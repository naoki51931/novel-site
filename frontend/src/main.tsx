import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";
import AiLogsPage from "./legacy-pages/AiLogsPage";
import { initTheme } from "./theme";
import { LanguageProvider } from "./lib/i18n";

const SITE_KEY_ENV = (process.env.NEXT_PUBLIC_SITE_KEY || "").toString().trim().toLowerCase();
type SiteKey = "romance" | "history" | "main";

function detectSiteKeyFromHost(): SiteKey {
  if (typeof window === "undefined") return "main";
  const host = (window.location.hostname || "").toLowerCase();
  if (!host) return "main";
  if (
    host.startsWith("romance.")
    || host.includes("romance")
    || host.startsWith("renai.")
    || host.includes("renai")
  ) {
    return "romance";
  }
  if (
    host.startsWith("history.")
    || host.includes("history")
    || host.startsWith("rekishi.")
    || host.includes("rekishi")
  ) {
    return "history";
  }
  return "main";
}

function normalizeSiteKey(siteKey: string): SiteKey {
  if (siteKey === "romance" || siteKey === "history") return siteKey;
  return "main";
}

const ACTIVE_SITE_KEY = normalizeSiteKey(SITE_KEY_ENV || detectSiteKeyFromHost());

function applySiteBranding() {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.siteKey = ACTIVE_SITE_KEY;
  const titleBySiteKey: Record<SiteKey, string> = {
    romance: "恋愛小説Lexis（レクシー/レクシス）",
    history: "歴史小説Lexis（レクシー/レクシス）",
    main: "小説投稿サイトLexis（レクシー/レクシス）",
  };
  document.title = titleBySiteKey[ACTIVE_SITE_KEY] || titleBySiteKey.main;
}

function installSiteKeyFetchHeader() {
  if (typeof window === "undefined" || typeof window.fetch !== "function") return;
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
    let urlText = "";
    if (typeof input === "string") {
      urlText = input;
    } else if (input instanceof Request) {
      urlText = input.url;
    }

    let isApiRequest = false;
    try {
      const resolved = new URL(urlText, window.location.origin);
      isApiRequest = resolved.pathname.startsWith("/api/");
    } catch {
      isApiRequest = false;
    }

    if (!isApiRequest) return originalFetch(input, init);

    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    if (init && init.headers) {
      const extra = new Headers(init.headers);
      extra.forEach((value, key) => headers.set(key, value));
    }
    if (!headers.has("x-site-key")) {
      headers.set("X-Site-Key", ACTIVE_SITE_KEY);
    }

    return originalFetch(input, { ...(init || {}), headers });
  };
}

installSiteKeyFetchHeader();
applySiteBranding();

// すべての <a> と <button> に自動で btn btn-border を付ける
function applyGlobalButtonClasses() {
  document
    .querySelectorAll("a:not(.btn-border), button:not(.btn-border)")
    .forEach((el) => {
      el.classList.add("btn", "btn-border");
    });
}

// 初回ロード時
window.addEventListener("DOMContentLoaded", applyGlobalButtonClasses);

// React の更新時にも再適用
const observer = new MutationObserver(applyGlobalButtonClasses);
observer.observe(document.body, { childList: true, subtree: true });

initTheme();

if (typeof window !== "undefined" && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((e) => {
      console.error("failed to register service worker", e);
    });
  });
}

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root element #root was not found.");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <LanguageProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </LanguageProvider>
  </React.StrictMode>
);
